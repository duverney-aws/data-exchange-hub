#!/usr/bin/env python3
"""
Seed integration test data into deployed AWS resources.

Can be run standalone:
    python -m tests.integration.seed_test_data [--cleanup]

Or used as a pytest fixture via the ``seed_all`` fixture below.
"""
import argparse
import json
import os
import sys

import boto3

# Allow running from the cdk/ directory
sys.path.insert(0, os.path.dirname(__file__))
from test_data import (
    ALL_CMO_PROFILES,
    ALL_CONTRACTS,
    ALL_EXECUTIONS,
    SAMPLE_CSV_CONTENT,
    SAMPLE_JSON_RECORDS,
)

AWS_PROFILE = os.environ.get("AWS_PROFILE", "hub-387776852668")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

TABLE_NAMES = {
    "cmo_profiles": "cmo-profiles",
    "data_contracts": "data-contracts",
    "pipeline_executions": "pipeline-executions",
}

TEST_CMO_IDS = ["cmo-test-alpha", "cmo-test-beta"]
LAYERS = ["bronze", "silver", "gold"]


def _session() -> boto3.Session:
    return boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)


def _find_bucket(session: boto3.Session, prefix: str) -> str | None:
    s3 = session.client("s3")
    for b in s3.list_buckets()["Buckets"]:
        if b["Name"].startswith(prefix):
            return b["Name"]
    return None


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def seed_dynamodb(session: boto3.Session) -> None:
    """Insert test CMO profiles, contracts, and execution records."""
    ddb = session.resource("dynamodb")

    table = ddb.Table(TABLE_NAMES["cmo_profiles"])
    for profile in ALL_CMO_PROFILES:
        table.put_item(Item=profile)
        print(f"  Seeded CMO profile: {profile['cmoId']}")

    table = ddb.Table(TABLE_NAMES["data_contracts"])
    for contract in ALL_CONTRACTS:
        table.put_item(Item=contract)
        print(f"  Seeded contract: {contract['contractId']}")

    table = ddb.Table(TABLE_NAMES["pipeline_executions"])
    for execution in ALL_EXECUTIONS:
        table.put_item(Item=execution)
        print(f"  Seeded execution: {execution['executionId']}")


def seed_s3(session: boto3.Session) -> None:
    """Create test folder structure and upload sample files to the data lake bucket."""
    bucket = _find_bucket(session, "pharmadataexchangedatalake")
    if bucket is None:
        print("  WARNING: Data lake bucket not found, skipping S3 seed.")
        return

    s3 = session.client("s3")

    # Create folder markers for each CMO / layer
    for cmo_id in TEST_CMO_IDS:
        for layer in LAYERS:
            key = f"{layer}/{cmo_id}/.keep"
            s3.put_object(Bucket=bucket, Key=key, Body=b"")
            print(f"  Created folder: {layer}/{cmo_id}/")

    # Upload sample CSV (Pattern 2)
    csv_key = "bronze/cmo-test-alpha/batch-records/year=2024/month=01/day=15/sample.csv"
    s3.put_object(Bucket=bucket, Key=csv_key, Body=SAMPLE_CSV_CONTENT.encode())
    print(f"  Uploaded sample CSV: {csv_key}")

    # Upload sample JSON (Pattern 1)
    json_key = "bronze/cmo-test-beta/quality-data/year=2024/month=02/day=01/sample.json"
    s3.put_object(Bucket=bucket, Key=json_key, Body=json.dumps(SAMPLE_JSON_RECORDS).encode())
    print(f"  Uploaded sample JSON: {json_key}")


def seed_secrets(session: boto3.Session) -> None:
    """Create test secrets in Secrets Manager."""
    sm = session.client("secretsmanager")

    for cmo_id in TEST_CMO_IDS:
        secret_name = f"cmo/{cmo_id}/test-credentials"
        secret_value = json.dumps({
            "username": f"{cmo_id}-user",
            "password": "test-integration-password",
            "connection_string": f"jdbc:postgresql://localhost:5432/{cmo_id}",
        })
        try:
            sm.create_secret(Name=secret_name, SecretString=secret_value)
            print(f"  Created secret: {secret_name}")
        except sm.exceptions.ResourceExistsException:
            sm.put_secret_value(SecretId=secret_name, SecretString=secret_value)
            print(f"  Updated existing secret: {secret_name}")


# ---------------------------------------------------------------------------
# Cleanup functions
# ---------------------------------------------------------------------------

def cleanup_dynamodb(session: boto3.Session) -> None:
    ddb = session.resource("dynamodb")

    table = ddb.Table(TABLE_NAMES["cmo_profiles"])
    for profile in ALL_CMO_PROFILES:
        table.delete_item(Key={"cmoId": profile["cmoId"]})

    table = ddb.Table(TABLE_NAMES["data_contracts"])
    for contract in ALL_CONTRACTS:
        table.delete_item(Key={"contractId": contract["contractId"]})

    table = ddb.Table(TABLE_NAMES["pipeline_executions"])
    for execution in ALL_EXECUTIONS:
        table.delete_item(Key={
            "contractId": execution["contractId"],
            "executionTimestamp": execution["executionTimestamp"],
        })
    print("  Cleaned up DynamoDB test items.")


def cleanup_s3(session: boto3.Session) -> None:
    bucket = _find_bucket(session, "pharmadataexchangedatalake")
    if bucket is None:
        return
    s3 = session.client("s3")
    for cmo_id in TEST_CMO_IDS:
        for layer in LAYERS:
            prefix = f"{layer}/{cmo_id}/"
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                objects = page.get("Contents", [])
                if objects:
                    s3.delete_objects(
                        Bucket=bucket,
                        Delete={"Objects": [{"Key": o["Key"]} for o in objects]},
                    )
    print("  Cleaned up S3 test prefixes.")


def cleanup_secrets(session: boto3.Session) -> None:
    sm = session.client("secretsmanager")
    for cmo_id in TEST_CMO_IDS:
        secret_name = f"cmo/{cmo_id}/test-credentials"
        try:
            sm.delete_secret(SecretId=secret_name, ForceDeleteWithoutRecovery=True)
            print(f"  Deleted secret: {secret_name}")
        except sm.exceptions.ResourceNotFoundException:
            pass


# ---------------------------------------------------------------------------
# Pytest fixture
# ---------------------------------------------------------------------------

def seed_all(session: boto3.Session) -> None:
    """Seed all test data."""
    print("Seeding integration test data...")
    seed_dynamodb(session)
    seed_s3(session)
    seed_secrets(session)
    print("Seeding complete.")


def cleanup_all(session: boto3.Session) -> None:
    """Remove all test data."""
    print("Cleaning up integration test data...")
    cleanup_dynamodb(session)
    cleanup_s3(session)
    cleanup_secrets(session)
    print("Cleanup complete.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed or clean up integration test data")
    parser.add_argument("--cleanup", action="store_true", help="Remove test data instead of seeding")
    args = parser.parse_args()

    session = _session()
    if args.cleanup:
        cleanup_all(session)
    else:
        seed_all(session)
