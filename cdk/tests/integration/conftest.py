"""
Integration test fixtures for Pharma Data Exchange Hub.

Provides pytest fixtures that connect to real AWS resources deployed via CDK
in account 387776852668 using the hub-387776852668 profile.
"""
import json
import os
import time
from pathlib import Path

import boto3
import pytest

AWS_PROFILE = os.environ.get("AWS_PROFILE", "hub-387776852668")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# CDK stack names
STACKS = {
    "database": "PharmaDataExchangeDatabaseStack",
    "data_lake": "PharmaDataExchangeDataLakeStack",
    "secrets": "PharmaDataExchangeSecretsStack",
    "monitoring": "PharmaDataExchangeMonitoringStack",
    "contract_api": "PharmaDataExchangeContractApiStack",
    "pipeline": "PharmaDataExchangePipelineOrchestrationStack",
    "security": "PharmaDataExchangeSecurityStack",
    "audit": "PharmaDataExchangeAuditComplianceStack",
}

# Well-known resource names from CDK stacks
TABLE_NAMES = {
    "cmo_profiles": "cmo-profiles",
    "data_contracts": "data-contracts",
    "pipeline_executions": "pipeline-executions",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session() -> boto3.Session:
    return boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)


def get_stack_outputs(session: boto3.Session, stack_name: str) -> dict:
    """Return CloudFormation outputs for *stack_name* as {key: value}."""
    cfn = session.client("cloudformation")
    resp = cfn.describe_stacks(StackName=stack_name)
    outputs = resp["Stacks"][0].get("Outputs", [])
    return {o["OutputKey"]: o["OutputValue"] for o in outputs}


def get_physical_resource(session: boto3.Session, stack_name: str, logical_id: str) -> str:
    """Resolve a logical resource ID to its physical name/ARN."""
    cfn = session.client("cloudformation")
    resp = cfn.describe_stack_resource(StackName=stack_name, LogicalResourceId=logical_id)
    return resp["StackResourceDetail"]["PhysicalResourceId"]


def discover_bucket_name(session: boto3.Session, prefix: str) -> str | None:
    """Find the first S3 bucket whose name starts with *prefix*."""
    s3 = session.client("s3")
    for bucket in s3.list_buckets()["Buckets"]:
        if bucket["Name"].startswith(prefix):
            return bucket["Name"]
    return None


# ---------------------------------------------------------------------------
# Session-scoped fixtures (created once per test run)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def aws_session():
    """Boto3 session configured with the integration test profile."""
    return _session()


@pytest.fixture(scope="session")
def dynamodb_resource(aws_session):
    return aws_session.resource("dynamodb")


@pytest.fixture(scope="session")
def s3_client(aws_session):
    return aws_session.client("s3")


@pytest.fixture(scope="session")
def secretsmanager_client(aws_session):
    return aws_session.client("secretsmanager")


@pytest.fixture(scope="session")
def cloudformation_client(aws_session):
    return aws_session.client("cloudformation")


@pytest.fixture(scope="session")
def cmo_profiles_table(dynamodb_resource):
    return dynamodb_resource.Table(TABLE_NAMES["cmo_profiles"])


@pytest.fixture(scope="session")
def data_contracts_table(dynamodb_resource):
    return dynamodb_resource.Table(TABLE_NAMES["data_contracts"])


@pytest.fixture(scope="session")
def pipeline_executions_table(dynamodb_resource):
    return dynamodb_resource.Table(TABLE_NAMES["pipeline_executions"])


@pytest.fixture(scope="session")
def data_lake_bucket_name(aws_session) -> str:
    """Discover the auto-generated data lake bucket name."""
    name = discover_bucket_name(aws_session, "pharmadataexchangedatalake")
    if name is None:
        pytest.skip("Data lake bucket not found – is the stack deployed?")
    return name


@pytest.fixture(scope="session")
def quality_results_bucket_name(aws_session) -> str:
    name = discover_bucket_name(aws_session, "pharmadataexchangedatalake")
    # Quality results bucket has a different prefix
    name = discover_bucket_name(aws_session, "pharmadataexchangedatalakestack-qualityresults")
    if name is None:
        pytest.skip("Quality results bucket not found – is the stack deployed?")
    return name


# ---------------------------------------------------------------------------
# Cleanup fixtures (function-scoped)
# ---------------------------------------------------------------------------

@pytest.fixture()
def cleanup_dynamodb_items(dynamodb_resource):
    """
    Collects (table_name, key_dict) tuples and deletes them after the test.

    Usage:
        def test_something(cleanup_dynamodb_items, cmo_profiles_table):
            cleanup_dynamodb_items.append(("cmo-profiles", {"cmoId": "cmo-test-alpha"}))
            cmo_profiles_table.put_item(Item={...})
    """
    items: list[tuple[str, dict]] = []
    yield items
    for table_name, key in items:
        try:
            dynamodb_resource.Table(table_name).delete_item(Key=key)
        except Exception:
            pass  # best-effort cleanup


@pytest.fixture()
def cleanup_s3_prefixes(s3_client):
    """
    Collects (bucket, prefix) tuples and deletes all objects under them after the test.

    Usage:
        cleanup_s3_prefixes.append((bucket, "bronze/cmo-test-alpha/"))
    """
    prefixes: list[tuple[str, str]] = []
    yield prefixes
    for bucket, prefix in prefixes:
        try:
            paginator = s3_client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                objects = page.get("Contents", [])
                if objects:
                    s3_client.delete_objects(
                        Bucket=bucket,
                        Delete={"Objects": [{"Key": o["Key"]} for o in objects]},
                    )
        except Exception:
            pass


@pytest.fixture()
def cleanup_secrets(secretsmanager_client):
    """
    Collects secret names and deletes them (force, no recovery) after the test.
    """
    names: list[str] = []
    yield names
    for name in names:
        try:
            secretsmanager_client.delete_secret(
                SecretId=name, ForceDeleteWithoutRecovery=True
            )
        except Exception:
            pass
