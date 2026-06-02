"""
Unit Tests for Lake Formation Service.

Tests:
- S3 location registration (bronze, silver, gold)
- Glue Data Catalog database creation and lookup
- Database and table permission grants
- CMO-specific table permission grants
- Permission revocation (table and database)
- Row-level data cell filters (WHERE cmo_id = '{cmo_id}')
- Column-level data cell filters (allowed columns only)
- Combined row+column filters
- Data cell filter deletion
- Permission listing
- CMO ID validation

Requirements: 10.2

Note: moto has limited Lake Formation support, so we use
unittest.mock for Lake Formation APIs and moto for Glue.
"""
import sys
import os
import boto3
import pytest
from unittest.mock import MagicMock, patch, call
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.lake_formation_service import LakeFormationService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACCOUNT_ID = "123456789012"
REGION = "us-east-1"
BUCKET_ARN = "arn:aws:s3:::pharma-data-lake"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT_ID}:role/LakeFormationServiceRole"
CMO_ROLE_ARN = f"arn:aws:iam::{ACCOUNT_ID}:role/pharma-hub-cmo-cmo-alpha-role"


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
def mock_lf_client():
    """Mock Lake Formation client (moto has limited LF support)."""
    client = MagicMock()
    client.list_permissions.return_value = {
        "PrincipalResourcePermissions": []
    }
    return client


@pytest.fixture
def glue_client(aws_env):
    with mock_aws():
        yield boto3.client("glue", region_name=REGION)


@pytest.fixture
def service(mock_lf_client, glue_client):
    return LakeFormationService(
        lakeformation_client=mock_lf_client,
        glue_client=glue_client,
        region=REGION,
    )


# ---------------------------------------------------------------------------
# S3 Location Registration
# ---------------------------------------------------------------------------

class TestS3LocationRegistration:
    """Requirement 10.2: Register S3 locations with Lake Formation."""

    def test_register_single_location(self, service, mock_lf_client):
        result = service.register_s3_location(
            f"{BUCKET_ARN}/bronze/", ROLE_ARN
        )
        assert result["s3_arn"] == f"{BUCKET_ARN}/bronze/"
        assert result["role_arn"] == ROLE_ARN
        assert result["status"] == "registered"
        mock_lf_client.register_resource.assert_called_once_with(
            ResourceArn=f"{BUCKET_ARN}/bronze/",
            UseServiceLinkedRole=False,
            RoleArn=ROLE_ARN,
        )

    def test_register_data_lake_locations_registers_three_layers(
        self, service, mock_lf_client
    ):
        result = service.register_data_lake_locations(BUCKET_ARN, ROLE_ARN)
        assert len(result["locations"]) == 3
        assert result["bucket_arn"] == BUCKET_ARN

        registered_arns = [loc["s3_arn"] for loc in result["locations"]]
        assert f"{BUCKET_ARN}/bronze/" in registered_arns
        assert f"{BUCKET_ARN}/silver/" in registered_arns
        assert f"{BUCKET_ARN}/gold/" in registered_arns

    def test_register_data_lake_locations_calls_register_per_layer(
        self, service, mock_lf_client
    ):
        service.register_data_lake_locations(BUCKET_ARN, ROLE_ARN)
        assert mock_lf_client.register_resource.call_count == 3

    def test_each_registered_location_has_correct_role(self, service):
        result = service.register_data_lake_locations(BUCKET_ARN, ROLE_ARN)
        for loc in result["locations"]:
            assert loc["role_arn"] == ROLE_ARN
            assert loc["status"] == "registered"


# ---------------------------------------------------------------------------
# Glue Data Catalog Database
# ---------------------------------------------------------------------------

class TestGlueDatabaseManagement:
    """Requirement 10.2: Create and manage Glue Data Catalog database."""

    def test_create_database(self, service):
        result = service.create_database()
        assert result["database_name"] == "cmo_data_lake"
        assert result["status"] == "created"

    def test_get_database_after_creation(self, service):
        service.create_database("Test CMO Lake")
        result = service.get_database()
        assert result is not None
        assert result["database_name"] == "cmo_data_lake"
        assert result["description"] == "Test CMO Lake"

    def test_get_database_not_found(self, service):
        result = service.get_database()
        assert result is None


# ---------------------------------------------------------------------------
# Database Permissions
# ---------------------------------------------------------------------------

class TestDatabasePermissions:
    """Requirement 10.2: Grant/revoke database permissions."""

    def test_grant_database_permissions_default(self, service, mock_lf_client):
        result = service.grant_database_permissions(CMO_ROLE_ARN)
        assert result["principal_arn"] == CMO_ROLE_ARN
        assert result["database_name"] == "cmo_data_lake"
        assert result["permissions"] == ["DESCRIBE", "CREATE_TABLE"]
        assert result["status"] == "granted"
        mock_lf_client.grant_permissions.assert_called_once()

    def test_grant_database_permissions_custom(self, service, mock_lf_client):
        result = service.grant_database_permissions(
            CMO_ROLE_ARN, permissions=["DESCRIBE"]
        )
        assert result["permissions"] == ["DESCRIBE"]

    def test_revoke_database_permissions(self, service, mock_lf_client):
        result = service.revoke_database_permissions(CMO_ROLE_ARN)
        assert result["status"] == "revoked"
        assert result["permissions"] == ["DESCRIBE", "CREATE_TABLE"]
        mock_lf_client.revoke_permissions.assert_called_once()


# ---------------------------------------------------------------------------
# Table Permissions
# ---------------------------------------------------------------------------

class TestTablePermissions:
    """Requirement 10.2: Grant/revoke table permissions."""

    def test_grant_table_permissions_default(self, service, mock_lf_client):
        result = service.grant_table_permissions(
            CMO_ROLE_ARN, "cmo_alpha_batch_records_silver"
        )
        assert result["principal_arn"] == CMO_ROLE_ARN
        assert result["table_name"] == "cmo_alpha_batch_records_silver"
        assert result["permissions"] == ["SELECT", "DESCRIBE"]
        assert result["status"] == "granted"

    def test_grant_table_permissions_custom(self, service, mock_lf_client):
        result = service.grant_table_permissions(
            CMO_ROLE_ARN,
            "cmo_alpha_batch_records_silver",
            permissions=["SELECT"],
        )
        assert result["permissions"] == ["SELECT"]

    def test_revoke_table_permissions(self, service, mock_lf_client):
        result = service.revoke_table_permissions(
            CMO_ROLE_ARN, "cmo_alpha_batch_records_silver"
        )
        assert result["status"] == "revoked"
        assert result["table_name"] == "cmo_alpha_batch_records_silver"
        mock_lf_client.revoke_permissions.assert_called_once()

    def test_grant_cmo_table_permissions(self, service, mock_lf_client):
        result = service.grant_cmo_table_permissions(
            cmo_id="cmo-alpha",
            cmo_role_arn=CMO_ROLE_ARN,
            data_domain="batch_records",
        )
        assert result["table_name"] == "cmo_alpha_batch_records_silver"
        assert result["status"] == "granted"

    def test_grant_cmo_table_permissions_with_hyphens(
        self, service, mock_lf_client
    ):
        result = service.grant_cmo_table_permissions(
            cmo_id="cmo-beta",
            cmo_role_arn=CMO_ROLE_ARN,
            data_domain="quality-data",
        )
        assert result["table_name"] == "cmo_beta_quality_data_silver"

    def test_grant_cmo_table_permissions_invalid_cmo_raises(self, service):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            service.grant_cmo_table_permissions(
                cmo_id="alpha",
                cmo_role_arn=CMO_ROLE_ARN,
                data_domain="batch_records",
            )


# ---------------------------------------------------------------------------
# Data Cell Filters — Row-Level Security
# ---------------------------------------------------------------------------

class TestRowLevelFilters:
    """Requirement 10.2: Row-level security via data cell filters."""

    def test_create_row_filter(self, service, mock_lf_client):
        columns = ["batch_id", "cmo_id", "product_name", "quantity"]
        result = service.create_row_filter(
            cmo_id="cmo-alpha",
            table_name="cmo_alpha_batch_records_silver",
            all_columns=columns,
        )
        assert result["filter_type"] == "row"
        assert result["row_filter"] == "cmo_id = 'cmo-alpha'"
        assert result["cmo_id"] == "cmo-alpha"
        assert result["status"] == "created"
        mock_lf_client.create_data_cells_filter.assert_called_once()

    def test_row_filter_name_convention(self, service, mock_lf_client):
        result = service.create_row_filter(
            cmo_id="cmo-alpha",
            table_name="cmo_alpha_batch_records_silver",
            all_columns=["batch_id", "cmo_id"],
        )
        assert result["filter_name"] == (
            "cmo-alpha-row-filter-cmo_alpha_batch_records_silver"
        )

    def test_row_filter_invalid_cmo_raises(self, service):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            service.create_row_filter(
                cmo_id="bad",
                table_name="t",
                all_columns=["c"],
            )

    def test_row_filter_empty_cmo_raises(self, service):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            service.create_row_filter(
                cmo_id="",
                table_name="t",
                all_columns=["c"],
            )


# ---------------------------------------------------------------------------
# Data Cell Filters — Column-Level Security
# ---------------------------------------------------------------------------

class TestColumnLevelFilters:
    """Requirement 10.2: Column-level security via data cell filters."""

    def test_create_column_filter(self, service, mock_lf_client):
        allowed = ["batch_id", "product_name", "quantity"]
        result = service.create_column_filter(
            cmo_id="cmo-alpha",
            table_name="cmo_alpha_batch_records_silver",
            allowed_columns=allowed,
        )
        assert result["filter_type"] == "column"
        assert result["allowed_columns"] == allowed
        assert result["status"] == "created"
        mock_lf_client.create_data_cells_filter.assert_called_once()

    def test_column_filter_excludes_pii(self, service, mock_lf_client):
        """PII columns should not appear in allowed_columns."""
        all_cols = ["batch_id", "operator_name", "operator_email", "quantity"]
        pii_cols = {"operator_name", "operator_email"}
        allowed = [c for c in all_cols if c not in pii_cols]

        result = service.create_column_filter(
            cmo_id="cmo-alpha",
            table_name="cmo_alpha_batch_records_silver",
            allowed_columns=allowed,
        )
        assert "operator_name" not in result["allowed_columns"]
        assert "operator_email" not in result["allowed_columns"]
        assert "batch_id" in result["allowed_columns"]

    def test_column_filter_invalid_cmo_raises(self, service):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            service.create_column_filter(
                cmo_id="nope",
                table_name="t",
                allowed_columns=["c"],
            )


# ---------------------------------------------------------------------------
# Data Cell Filters — Combined Row + Column
# ---------------------------------------------------------------------------

class TestCombinedFilters:
    """Requirement 10.2: Combined row-level and column-level filters."""

    def test_create_combined_filter(self, service, mock_lf_client):
        allowed = ["batch_id", "quantity"]
        result = service.create_combined_filter(
            cmo_id="cmo-alpha",
            table_name="cmo_alpha_batch_records_silver",
            allowed_columns=allowed,
        )
        assert result["filter_type"] == "combined"
        assert result["row_filter"] == "cmo_id = 'cmo-alpha'"
        assert result["allowed_columns"] == allowed
        assert result["status"] == "created"

    def test_combined_filter_name(self, service, mock_lf_client):
        result = service.create_combined_filter(
            cmo_id="cmo-beta",
            table_name="cmo_beta_quality_data_silver",
            allowed_columns=["col1"],
        )
        assert result["filter_name"] == (
            "cmo-beta-combined-filter-cmo_beta_quality_data_silver"
        )

    def test_combined_filter_invalid_cmo_raises(self, service):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            service.create_combined_filter(
                cmo_id="x",
                table_name="t",
                allowed_columns=["c"],
            )


# ---------------------------------------------------------------------------
# Data Cell Filter Deletion
# ---------------------------------------------------------------------------

class TestFilterDeletion:
    """Requirement 10.2: Delete data cell filters."""

    def test_delete_filter(self, service, mock_lf_client):
        result = service.delete_data_cells_filter(
            table_name="cmo_alpha_batch_records_silver",
            filter_name="cmo-alpha-row-filter-cmo_alpha_batch_records_silver",
        )
        assert result["status"] == "deleted"
        assert result["filter_name"] == (
            "cmo-alpha-row-filter-cmo_alpha_batch_records_silver"
        )
        mock_lf_client.delete_data_cells_filter.assert_called_once()


# ---------------------------------------------------------------------------
# List Permissions
# ---------------------------------------------------------------------------

class TestListPermissions:
    """Requirement 10.2: List Lake Formation permissions."""

    def test_list_permissions_empty(self, service, mock_lf_client):
        result = service.list_permissions()
        assert result == []

    def test_list_permissions_with_entries(self, service, mock_lf_client):
        mock_lf_client.list_permissions.return_value = {
            "PrincipalResourcePermissions": [
                {
                    "Principal": {
                        "DataLakePrincipalIdentifier": CMO_ROLE_ARN
                    },
                    "Resource": {
                        "Table": {
                            "DatabaseName": "cmo_data_lake",
                            "Name": "cmo_alpha_batch_records_silver",
                        }
                    },
                    "Permissions": ["SELECT", "DESCRIBE"],
                }
            ]
        }
        result = service.list_permissions()
        assert len(result) == 1
        assert result[0]["principal"] == CMO_ROLE_ARN
        assert result[0]["permissions"] == ["SELECT", "DESCRIBE"]

    def test_list_permissions_filtered_by_principal(
        self, service, mock_lf_client
    ):
        service.list_permissions(principal_arn=CMO_ROLE_ARN)
        mock_lf_client.list_permissions.assert_called_with(
            Principal={"DataLakePrincipalIdentifier": CMO_ROLE_ARN}
        )

    def test_list_permissions_no_filter(self, service, mock_lf_client):
        service.list_permissions()
        mock_lf_client.list_permissions.assert_called_with()


# ---------------------------------------------------------------------------
# CMO ID Validation
# ---------------------------------------------------------------------------

class TestCMOIDValidation:
    """Requirement 10.2: CMO ID must start with 'cmo-'."""

    @pytest.mark.parametrize("bad_id", ["", "alpha", "CMO-alpha", "cm-alpha", "c"])
    def test_row_filter_rejects_bad_cmo_id(self, service, bad_id):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            service.create_row_filter(bad_id, "t", ["c"])

    @pytest.mark.parametrize("bad_id", ["", "alpha", "CMO-alpha"])
    def test_column_filter_rejects_bad_cmo_id(self, service, bad_id):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            service.create_column_filter(bad_id, "t", ["c"])

    @pytest.mark.parametrize("bad_id", ["", "alpha"])
    def test_combined_filter_rejects_bad_cmo_id(self, service, bad_id):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            service.create_combined_filter(bad_id, "t", ["c"])

    @pytest.mark.parametrize("bad_id", ["", "alpha"])
    def test_grant_cmo_table_rejects_bad_cmo_id(self, service, bad_id):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            service.grant_cmo_table_permissions(bad_id, CMO_ROLE_ARN, "d")


# ---------------------------------------------------------------------------
# Table Name Building
# ---------------------------------------------------------------------------

class TestTableNameBuilding:
    """Convention: {cmo_id}_{data_domain}_silver with hyphens as underscores."""

    def test_simple_names(self):
        assert (
            LakeFormationService._build_table_name("cmo-alpha", "batch_records")
            == "cmo_alpha_batch_records_silver"
        )

    def test_hyphenated_domain(self):
        assert (
            LakeFormationService._build_table_name("cmo-beta", "quality-data")
            == "cmo_beta_quality_data_silver"
        )

    def test_multiple_hyphens(self):
        assert (
            LakeFormationService._build_table_name("cmo-gamma-x", "a-b-c")
            == "cmo_gamma_x_a_b_c_silver"
        )
