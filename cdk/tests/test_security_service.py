"""
Unit Tests for KMS Encryption Service and IAM Security Service.

Tests:
- KMS key creation with proper configuration (rotation, alias)
- KMS key policy restricts access to specific CMO
- IAM role creation with correct naming convention
- IAM role policies follow least-privilege (only access own CMO data)
- IAM role trust relationships are correctly configured
- S3 path restrictions are properly scoped to CMO prefix
- DynamoDB access is restricted to CMO's own items
- Secrets Manager access is restricted to CMO's own secrets

Requirements: 9.7, 10.1
"""
import sys
import os
import json
import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.kms_encryption_service import KMSEncryptionService
from services.iam_security_service import IAMSecurityService


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACCOUNT_ID = "123456789012"
REGION = "us-east-1"
DATA_LAKE_BUCKET_ARN = "arn:aws:s3:::pharma-data-lake"
CMO_PROFILES_TABLE_ARN = f"arn:aws:dynamodb:{REGION}:{ACCOUNT_ID}:table/cmo-profiles"
DATA_CONTRACTS_TABLE_ARN = f"arn:aws:dynamodb:{REGION}:{ACCOUNT_ID}:table/data-contracts"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)


@pytest.fixture
def kms_client(aws_env):
    with mock_aws():
        yield boto3.client("kms", region_name=REGION)


@pytest.fixture
def iam_client(aws_env):
    with mock_aws():
        yield boto3.client("iam", region_name=REGION)


@pytest.fixture
def kms_service(kms_client):
    return KMSEncryptionService(kms_client=kms_client, region=REGION)


@pytest.fixture
def iam_service(iam_client):
    return IAMSecurityService(iam_client=iam_client, region=REGION)


# ---------------------------------------------------------------------------
# KMS Encryption Service — Key Creation
# ---------------------------------------------------------------------------

class TestKMSKeyCreation:
    """Requirement 9.7: Encrypt S3 data with CMO-specific customer-managed keys."""

    def test_creates_key_with_correct_alias(self, kms_service, kms_client):
        result = kms_service.create_cmo_kms_key("cmo-alpha", ACCOUNT_ID)
        assert result["alias"] == "alias/cmo/cmo-alpha/data-lake"

    def test_key_has_valid_arn(self, kms_service):
        result = kms_service.create_cmo_kms_key("cmo-alpha", ACCOUNT_ID)
        assert result["key_arn"].startswith("arn:aws:kms:")

    def test_key_has_valid_id(self, kms_service):
        result = kms_service.create_cmo_kms_key("cmo-alpha", ACCOUNT_ID)
        assert len(result["key_id"]) > 0

    def test_key_rotation_enabled(self, kms_service, kms_client):
        result = kms_service.create_cmo_kms_key("cmo-alpha", ACCOUNT_ID)
        assert kms_service.is_key_rotation_enabled(result["key_id"]) is True

    def test_cmo_id_stored_in_result(self, kms_service):
        result = kms_service.create_cmo_kms_key("cmo-alpha", ACCOUNT_ID)
        assert result["cmo_id"] == "cmo-alpha"

    def test_different_cmos_get_different_keys(self, kms_service):
        r1 = kms_service.create_cmo_kms_key("cmo-alpha", ACCOUNT_ID)
        r2 = kms_service.create_cmo_kms_key("cmo-beta", ACCOUNT_ID)
        assert r1["key_id"] != r2["key_id"]
        assert r1["key_arn"] != r2["key_arn"]

    def test_different_cmos_get_different_aliases(self, kms_service):
        r1 = kms_service.create_cmo_kms_key("cmo-alpha", ACCOUNT_ID)
        r2 = kms_service.create_cmo_kms_key("cmo-beta", ACCOUNT_ID)
        assert r1["alias"] == "alias/cmo/cmo-alpha/data-lake"
        assert r2["alias"] == "alias/cmo/cmo-beta/data-lake"

    def test_invalid_cmo_id_raises(self, kms_service):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            kms_service.create_cmo_kms_key("alpha", ACCOUNT_ID)

    def test_empty_cmo_id_raises(self, kms_service):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            kms_service.create_cmo_kms_key("", ACCOUNT_ID)


# ---------------------------------------------------------------------------
# KMS Encryption Service — Key Lookup
# ---------------------------------------------------------------------------

class TestKMSKeyLookup:
    """Requirement 9.7: Retrieve CMO-specific key ARN."""

    def test_get_existing_key_arn(self, kms_service):
        created = kms_service.create_cmo_kms_key("cmo-alpha", ACCOUNT_ID)
        found = kms_service.get_cmo_key_arn("cmo-alpha")
        assert found == created["key_arn"]

    def test_get_nonexistent_key_returns_none(self, kms_service):
        result = kms_service.get_cmo_key_arn("cmo-nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# KMS Encryption Service — Key Policy
# ---------------------------------------------------------------------------

class TestKMSKeyPolicy:
    """Requirement 9.7: Key policy restricts access to specific CMO."""

    def test_policy_includes_root_access(self, kms_service, kms_client):
        result = kms_service.create_cmo_kms_key("cmo-alpha", ACCOUNT_ID)
        policy = json.loads(
            kms_client.get_key_policy(KeyId=result["key_id"], PolicyName="default")["Policy"]
        )
        root_stmts = [s for s in policy["Statement"] if s["Sid"] == "EnableRootAccountAccess"]
        assert len(root_stmts) == 1
        assert f"arn:aws:iam::{ACCOUNT_ID}:root" in root_stmts[0]["Principal"]["AWS"]

    def test_policy_includes_s3_service_access(self, kms_service, kms_client):
        result = kms_service.create_cmo_kms_key("cmo-alpha", ACCOUNT_ID)
        policy = json.loads(
            kms_client.get_key_policy(KeyId=result["key_id"], PolicyName="default")["Policy"]
        )
        s3_stmts = [s for s in policy["Statement"] if s["Sid"] == "AllowS3ServiceUsage"]
        assert len(s3_stmts) == 1
        assert "kms:Decrypt" in s3_stmts[0]["Action"]

    def test_policy_includes_cmo_role_when_provided(self, kms_service, kms_client):
        cmo_role_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/pharma-hub-cmo-cmo-alpha-role"
        result = kms_service.create_cmo_kms_key("cmo-alpha", ACCOUNT_ID, cmo_role_arn=cmo_role_arn)
        policy = json.loads(
            kms_client.get_key_policy(KeyId=result["key_id"], PolicyName="default")["Policy"]
        )
        cmo_stmts = [s for s in policy["Statement"] if "AllowCMOKeyUsage" in s.get("Sid", "")]
        assert len(cmo_stmts) == 1
        assert cmo_stmts[0]["Principal"]["AWS"] == cmo_role_arn

    def test_policy_has_correct_id(self, kms_service, kms_client):
        result = kms_service.create_cmo_kms_key("cmo-alpha", ACCOUNT_ID)
        policy = json.loads(
            kms_client.get_key_policy(KeyId=result["key_id"], PolicyName="default")["Policy"]
        )
        assert policy["Id"] == "cmo-key-policy-cmo-alpha"


# ---------------------------------------------------------------------------
# IAM Security Service — Role Creation
# ---------------------------------------------------------------------------

class TestIAMRoleCreation:
    """Requirement 10.1: Create IAM roles with least-privilege permissions."""

    def test_role_name_follows_convention(self, iam_service):
        result = iam_service.create_cmo_role(
            cmo_id="cmo-alpha",
            account_id=ACCOUNT_ID,
            data_lake_bucket_arn=DATA_LAKE_BUCKET_ARN,
            kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/test-key",
            cmo_profiles_table_arn=CMO_PROFILES_TABLE_ARN,
            data_contracts_table_arn=DATA_CONTRACTS_TABLE_ARN,
        )
        assert result["role_name"] == "pharma-hub-cmo-cmo-alpha-role"

    def test_role_has_valid_arn(self, iam_service):
        result = iam_service.create_cmo_role(
            cmo_id="cmo-alpha",
            account_id=ACCOUNT_ID,
            data_lake_bucket_arn=DATA_LAKE_BUCKET_ARN,
            kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/test-key",
            cmo_profiles_table_arn=CMO_PROFILES_TABLE_ARN,
            data_contracts_table_arn=DATA_CONTRACTS_TABLE_ARN,
        )
        assert "arn:aws:iam::" in result["role_arn"]
        assert "pharma-hub-cmo-cmo-alpha-role" in result["role_arn"]

    def test_cmo_id_stored_in_result(self, iam_service):
        result = iam_service.create_cmo_role(
            cmo_id="cmo-alpha",
            account_id=ACCOUNT_ID,
            data_lake_bucket_arn=DATA_LAKE_BUCKET_ARN,
            kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/test-key",
            cmo_profiles_table_arn=CMO_PROFILES_TABLE_ARN,
            data_contracts_table_arn=DATA_CONTRACTS_TABLE_ARN,
        )
        assert result["cmo_id"] == "cmo-alpha"

    def test_invalid_cmo_id_raises(self, iam_service):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            iam_service.create_cmo_role(
                cmo_id="alpha",
                account_id=ACCOUNT_ID,
                data_lake_bucket_arn=DATA_LAKE_BUCKET_ARN,
                kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/test-key",
                cmo_profiles_table_arn=CMO_PROFILES_TABLE_ARN,
                data_contracts_table_arn=DATA_CONTRACTS_TABLE_ARN,
            )

    def test_empty_cmo_id_raises(self, iam_service):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            iam_service.create_cmo_role(
                cmo_id="",
                account_id=ACCOUNT_ID,
                data_lake_bucket_arn=DATA_LAKE_BUCKET_ARN,
                kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/test-key",
                cmo_profiles_table_arn=CMO_PROFILES_TABLE_ARN,
                data_contracts_table_arn=DATA_CONTRACTS_TABLE_ARN,
            )

    def test_different_cmos_get_different_roles(self, iam_service):
        r1 = iam_service.create_cmo_role(
            cmo_id="cmo-alpha",
            account_id=ACCOUNT_ID,
            data_lake_bucket_arn=DATA_LAKE_BUCKET_ARN,
            kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/key-alpha",
            cmo_profiles_table_arn=CMO_PROFILES_TABLE_ARN,
            data_contracts_table_arn=DATA_CONTRACTS_TABLE_ARN,
        )
        r2 = iam_service.create_cmo_role(
            cmo_id="cmo-beta",
            account_id=ACCOUNT_ID,
            data_lake_bucket_arn=DATA_LAKE_BUCKET_ARN,
            kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/key-beta",
            cmo_profiles_table_arn=CMO_PROFILES_TABLE_ARN,
            data_contracts_table_arn=DATA_CONTRACTS_TABLE_ARN,
        )
        assert r1["role_name"] != r2["role_name"]
        assert r1["role_arn"] != r2["role_arn"]


# ---------------------------------------------------------------------------
# IAM Security Service — Trust Relationships
# ---------------------------------------------------------------------------

class TestIAMTrustRelationships:
    """Requirement 10.1: Trust relationships for Lambda and Glue execution."""

    def test_trust_policy_allows_lambda(self, iam_service, iam_client):
        iam_service.create_cmo_role(
            cmo_id="cmo-alpha",
            account_id=ACCOUNT_ID,
            data_lake_bucket_arn=DATA_LAKE_BUCKET_ARN,
            kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/test-key",
            cmo_profiles_table_arn=CMO_PROFILES_TABLE_ARN,
            data_contracts_table_arn=DATA_CONTRACTS_TABLE_ARN,
        )
        role = iam_client.get_role(RoleName="pharma-hub-cmo-cmo-alpha-role")
        trust = role["Role"]["AssumeRolePolicyDocument"]
        principals = [s["Principal"]["Service"] for s in trust["Statement"]]
        assert "lambda.amazonaws.com" in principals

    def test_trust_policy_allows_glue(self, iam_service, iam_client):
        iam_service.create_cmo_role(
            cmo_id="cmo-alpha",
            account_id=ACCOUNT_ID,
            data_lake_bucket_arn=DATA_LAKE_BUCKET_ARN,
            kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/test-key",
            cmo_profiles_table_arn=CMO_PROFILES_TABLE_ARN,
            data_contracts_table_arn=DATA_CONTRACTS_TABLE_ARN,
        )
        role = iam_client.get_role(RoleName="pharma-hub-cmo-cmo-alpha-role")
        trust = role["Role"]["AssumeRolePolicyDocument"]
        principals = [s["Principal"]["Service"] for s in trust["Statement"]]
        assert "glue.amazonaws.com" in principals


# ---------------------------------------------------------------------------
# IAM Security Service — Least-Privilege Policy
# ---------------------------------------------------------------------------

class TestIAMLeastPrivilegePolicy:
    """Requirement 10.1: IAM policies follow least-privilege."""

    @pytest.fixture
    def policy(self, iam_service):
        iam_service.create_cmo_role(
            cmo_id="cmo-alpha",
            account_id=ACCOUNT_ID,
            data_lake_bucket_arn=DATA_LAKE_BUCKET_ARN,
            kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/test-key",
            cmo_profiles_table_arn=CMO_PROFILES_TABLE_ARN,
            data_contracts_table_arn=DATA_CONTRACTS_TABLE_ARN,
        )
        return iam_service.get_role_policy("cmo-alpha")

    def _find_statement(self, policy, sid):
        return next((s for s in policy["Statement"] if s["Sid"] == sid), None)

    def test_s3_access_scoped_to_cmo_prefix(self, policy):
        stmt = self._find_statement(policy, "AllowS3CMOAccess")
        assert stmt is not None
        for resource in stmt["Resource"]:
            assert "/cmo-alpha/" in resource
        # Verify only bronze and silver
        resources_str = " ".join(stmt["Resource"])
        assert "bronze/cmo-alpha" in resources_str
        assert "silver/cmo-alpha" in resources_str

    def test_s3_list_bucket_has_prefix_condition(self, policy):
        stmt = self._find_statement(policy, "AllowS3ListBucket")
        assert stmt is not None
        prefixes = stmt["Condition"]["StringLike"]["s3:prefix"]
        assert all("cmo-alpha" in p for p in prefixes)

    def test_kms_access_scoped_to_cmo_key(self, policy):
        stmt = self._find_statement(policy, "AllowKMSCMOKeyUsage")
        assert stmt is not None
        assert stmt["Resource"] == "arn:aws:kms:us-east-1:123456789012:key/test-key"

    def test_dynamodb_access_has_leading_keys_condition(self, policy):
        stmt = self._find_statement(policy, "AllowDynamoDBCMOAccess")
        assert stmt is not None
        leading_keys = stmt["Condition"]["ForAllValues:StringEquals"]["dynamodb:LeadingKeys"]
        assert leading_keys == ["cmo-alpha"]

    def test_secrets_manager_scoped_to_cmo(self, policy):
        stmt = self._find_statement(policy, "AllowSecretsManagerCMOAccess")
        assert stmt is not None
        assert "cmo/cmo-alpha/" in stmt["Resource"]

    def test_cloudwatch_logs_scoped_to_pharma_exchange(self, policy):
        stmt = self._find_statement(policy, "AllowCloudWatchLogs")
        assert stmt is not None
        assert "/pharma-data-exchange/" in stmt["Resource"]

    def test_no_wildcard_resource_in_s3_policy(self, policy):
        stmt = self._find_statement(policy, "AllowS3CMOAccess")
        for resource in stmt["Resource"]:
            # Should not be just "*" — must be scoped
            assert resource != "*"

    def test_s3_does_not_allow_delete(self, policy):
        stmt = self._find_statement(policy, "AllowS3CMOAccess")
        actions = stmt["Action"]
        assert "s3:DeleteObject" not in actions
        assert "s3:DeleteBucket" not in actions


# ---------------------------------------------------------------------------
# IAM Security Service — Role Lookup
# ---------------------------------------------------------------------------

class TestIAMRoleLookup:
    """Requirement 10.1: Retrieve CMO role ARN."""

    def test_get_existing_role_arn(self, iam_service):
        created = iam_service.create_cmo_role(
            cmo_id="cmo-alpha",
            account_id=ACCOUNT_ID,
            data_lake_bucket_arn=DATA_LAKE_BUCKET_ARN,
            kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/test-key",
            cmo_profiles_table_arn=CMO_PROFILES_TABLE_ARN,
            data_contracts_table_arn=DATA_CONTRACTS_TABLE_ARN,
        )
        found = iam_service.get_cmo_role_arn("cmo-alpha")
        assert found == created["role_arn"]

    def test_get_nonexistent_role_returns_none(self, iam_service):
        result = iam_service.get_cmo_role_arn("cmo-nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# IAM Security Service — Secrets Manager Custom Prefix
# ---------------------------------------------------------------------------

class TestIAMSecretsManagerCustomPrefix:
    """Requirement 10.1: Custom secrets prefix ARN."""

    def test_custom_secrets_prefix_used(self, iam_service):
        custom_arn = f"arn:aws:secretsmanager:{REGION}:{ACCOUNT_ID}:secret:custom/cmo-alpha/*"
        iam_service.create_cmo_role(
            cmo_id="cmo-alpha",
            account_id=ACCOUNT_ID,
            data_lake_bucket_arn=DATA_LAKE_BUCKET_ARN,
            kms_key_arn="arn:aws:kms:us-east-1:123456789012:key/test-key",
            cmo_profiles_table_arn=CMO_PROFILES_TABLE_ARN,
            data_contracts_table_arn=DATA_CONTRACTS_TABLE_ARN,
            secrets_prefix_arn=custom_arn,
        )
        policy = iam_service.get_role_policy("cmo-alpha")
        stmt = next(s for s in policy["Statement"] if s["Sid"] == "AllowSecretsManagerCMOAccess")
        assert stmt["Resource"] == custom_arn
