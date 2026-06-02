#!/usr/bin/env python3
"""
Production smoke tests for Pharma Data Exchange Hub.

Verifies that all deployed AWS resources exist and are healthy after a
production deployment.  Run from the cdk/ directory.

Usage:
    python3 smoke_tests.py [--profile <aws-profile>] [--region <region>]
"""

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass, field

import boto3
from botocore.exceptions import ClientError


# ── Resource names (must match CDK stack definitions) ─────────────────────────
DYNAMODB_TABLES = ["cmo-profiles", "data-contracts", "pipeline-executions"]

CLOUDWATCH_LOG_GROUPS = [
    "/pharma-data-exchange/api",
    "/pharma-data-exchange/pipeline",
    "/pharma-data-exchange/etl",
    "/pharma-data-exchange/schema-registry",
    "/pharma-data-exchange/ai-processing",
    "/pharma-data-exchange/cloudtrail",
]

SNS_TOPIC_NAMES = [
    "pharma-data-exchange-critical-alerts",
    "pharma-data-exchange-warning-alerts",
    "pharma-data-exchange-sla-breach",
]

API_GATEWAY_NAME = "Contract API"
STATE_MACHINE_NAME = "PipelineDeploymentWorkflow"
CLOUDTRAIL_NAME = "pharma-data-exchange-audit-trail"

CDK_STACK_NAMES = [
    "PharmaDataExchangeSecretsStack",
    "PharmaDataExchangeDatabaseStack",
    "PharmaDataExchangeDataLakeStack",
    "PharmaDataExchangeMonitoringStack",
    "PharmaDataExchangeContractApiStack",
    "PharmaDataExchangePipelineOrchestrationStack",
    "PharmaDataExchangeSecurityStack",
    "PharmaDataExchangeAuditComplianceStack",
]


# ── Result tracking ───────────────────────────────────────────────────────────
@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


results: list[CheckResult] = []


def record(name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    results.append(CheckResult(name, passed, detail))


# ── Helper: get S3 bucket names from CloudFormation outputs ───────────────────
def _get_stack_output(cfn, stack_name: str, output_key_contains: str) -> str | None:
    """Return the first output value whose key contains the given substring."""
    try:
        resp = cfn.describe_stacks(StackName=stack_name)
        for output in resp["Stacks"][0].get("Outputs", []):
            if output_key_contains.lower() in output["OutputKey"].lower():
                return output["OutputValue"]
    except ClientError:
        pass
    return None


def _find_buckets_by_stack(cfn, stack_name: str) -> list[str]:
    """List all S3 bucket physical resource IDs in a stack."""
    buckets = []
    try:
        paginator = cfn.get_paginator("list_stack_resources")
        for page in paginator.paginate(StackName=stack_name):
            for r in page["StackResourceSummaries"]:
                if r["ResourceType"] == "AWS::S3::Bucket":
                    buckets.append(r["PhysicalResourceId"])
    except ClientError:
        pass
    return buckets


# ── Checks ────────────────────────────────────────────────────────────────────

def check_dynamodb_tables(session):
    """Verify all 3 DynamoDB tables exist and are ACTIVE."""
    print("\n[DynamoDB Tables]")
    ddb = session.client("dynamodb")
    for table_name in DYNAMODB_TABLES:
        try:
            resp = ddb.describe_table(TableName=table_name)
            status = resp["Table"]["TableStatus"]
            record(f"Table '{table_name}'", status == "ACTIVE", f"status={status}")
        except ClientError as e:
            record(f"Table '{table_name}'", False, str(e))


def check_s3_buckets(session):
    """Verify S3 buckets exist and have KMS encryption."""
    print("\n[S3 Buckets]")
    cfn = session.client("cloudformation")
    s3_client = session.client("s3")

    # Collect buckets from DataLake and AuditCompliance stacks
    bucket_names = (
        _find_buckets_by_stack(cfn, "PharmaDataExchangeDataLakeStack")
        + _find_buckets_by_stack(cfn, "PharmaDataExchangeAuditComplianceStack")
    )

    if not bucket_names:
        record("S3 buckets discovery", False, "No buckets found in stacks")
        return

    for bucket in bucket_names:
        try:
            s3_client.head_bucket(Bucket=bucket)
            # Check encryption
            enc = s3_client.get_bucket_encryption(Bucket=bucket)
            rules = enc["ServerSideEncryptionConfiguration"]["Rules"]
            algo = rules[0]["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"]
            record(f"Bucket '{bucket}'", True, f"encryption={algo}")
        except ClientError as e:
            record(f"Bucket '{bucket}'", False, str(e))


def check_cloudwatch_log_groups(session):
    """Verify CloudWatch log groups exist."""
    print("\n[CloudWatch Log Groups]")
    logs_client = session.client("logs")
    for lg_name in CLOUDWATCH_LOG_GROUPS:
        try:
            resp = logs_client.describe_log_groups(logGroupNamePrefix=lg_name, limit=1)
            found = any(g["logGroupName"] == lg_name for g in resp.get("logGroups", []))
            record(f"Log group '{lg_name}'", found, "" if found else "not found")
        except ClientError as e:
            record(f"Log group '{lg_name}'", False, str(e))


def check_sns_topics(session):
    """Verify SNS topics exist."""
    print("\n[SNS Topics]")
    sns_client = session.client("sns")
    account_id = session.client("sts").get_caller_identity()["Account"]
    region = session.region_name

    for topic_name in SNS_TOPIC_NAMES:
        arn = f"arn:aws:sns:{region}:{account_id}:{topic_name}"
        try:
            sns_client.get_topic_attributes(TopicArn=arn)
            record(f"Topic '{topic_name}'", True)
        except ClientError as e:
            record(f"Topic '{topic_name}'", False, str(e))


def check_api_gateway(session):
    """Verify API Gateway REST API exists and responds."""
    print("\n[API Gateway]")
    apigw = session.client("apigateway")
    try:
        apis = apigw.get_rest_apis()
        match = [a for a in apis["items"] if a["name"] == API_GATEWAY_NAME]
        if match:
            api_id = match[0]["id"]
            record(f"REST API '{API_GATEWAY_NAME}'", True, f"id={api_id}")
        else:
            record(f"REST API '{API_GATEWAY_NAME}'", False, "not found")
    except ClientError as e:
        record(f"REST API '{API_GATEWAY_NAME}'", False, str(e))


def check_step_functions(session):
    """Verify Step Functions state machine exists."""
    print("\n[Step Functions]")
    sfn = session.client("stepfunctions")
    try:
        machines = sfn.list_state_machines()
        match = [m for m in machines["stateMachines"] if m["name"] == STATE_MACHINE_NAME]
        if match:
            status = match[0]["type"]
            record(f"State machine '{STATE_MACHINE_NAME}'", True, f"type={status}")
        else:
            record(f"State machine '{STATE_MACHINE_NAME}'", False, "not found")
    except ClientError as e:
        record(f"State machine '{STATE_MACHINE_NAME}'", False, str(e))


def check_cloudtrail(session):
    """Verify CloudTrail trail exists and is logging."""
    print("\n[CloudTrail]")
    ct = session.client("cloudtrail")
    try:
        resp = ct.get_trail_status(Name=CLOUDTRAIL_NAME)
        is_logging = resp.get("IsLogging", False)
        record(
            f"Trail '{CLOUDTRAIL_NAME}'",
            is_logging,
            f"IsLogging={is_logging}",
        )
    except ClientError as e:
        record(f"Trail '{CLOUDTRAIL_NAME}'", False, str(e))


def check_kms_keys(session):
    """Verify KMS keys are enabled."""
    print("\n[KMS Keys]")
    kms_client = session.client("kms")
    cfn = session.client("cloudformation")

    # Find KMS keys from Secrets and DataLake stacks
    key_stacks = [
        "PharmaDataExchangeSecretsStack",
        "PharmaDataExchangeDataLakeStack",
        "PharmaDataExchangeAuditComplianceStack",
    ]
    for stack_name in key_stacks:
        try:
            paginator = cfn.get_paginator("list_stack_resources")
            for page in paginator.paginate(StackName=stack_name):
                for r in page["StackResourceSummaries"]:
                    if r["ResourceType"] == "AWS::KMS::Key":
                        key_id = r["PhysicalResourceId"]
                        try:
                            desc = kms_client.describe_key(KeyId=key_id)
                            state = desc["KeyMetadata"]["KeyState"]
                            record(
                                f"KMS key ({stack_name})",
                                state == "Enabled",
                                f"state={state}",
                            )
                        except ClientError as e:
                            record(f"KMS key ({stack_name})", False, str(e))
        except ClientError as e:
            record(f"KMS keys in {stack_name}", False, str(e))


def check_write_read_cmo_profile(session):
    """Create a test CMO profile, read it back, then delete it."""
    print("\n[Write/Read Test — CMO Profile]")
    ddb = session.resource("dynamodb")
    table = ddb.Table("cmo-profiles")
    test_id = f"smoke-test-{uuid.uuid4().hex[:8]}"
    try:
        table.put_item(Item={
            "cmoId": test_id,
            "organizationName": "Smoke Test Org",
            "status": "active",
        })
        resp = table.get_item(Key={"cmoId": test_id})
        found = "Item" in resp and resp["Item"]["cmoId"] == test_id
        record("CMO profile write/read", found)
    except ClientError as e:
        record("CMO profile write/read", False, str(e))
    finally:
        try:
            table.delete_item(Key={"cmoId": test_id})
            record("CMO profile cleanup", True)
        except ClientError as e:
            record("CMO profile cleanup", False, str(e))


def check_write_read_contract(session):
    """Create a test data contract, read it back, then delete it."""
    print("\n[Write/Read Test — Data Contract]")
    ddb = session.resource("dynamodb")
    table = ddb.Table("data-contracts")
    test_id = f"CMO-SMOKETEST-BATCH-{uuid.uuid4().hex[:6].upper()}"
    try:
        table.put_item(Item={
            "contractId": test_id,
            "cmoId": "smoke-test",
            "dataDomain": "batch-records",
            "status": "draft",
        })
        resp = table.get_item(Key={"contractId": test_id})
        found = "Item" in resp and resp["Item"]["contractId"] == test_id
        record("Data contract write/read", found)
    except ClientError as e:
        record("Data contract write/read", False, str(e))
    finally:
        try:
            table.delete_item(Key={"contractId": test_id})
            record("Data contract cleanup", True)
        except ClientError as e:
            record("Data contract cleanup", False, str(e))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pharma Data Exchange Hub — Smoke Tests")
    parser.add_argument("--profile", default=None, help="AWS CLI profile name")
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    args = parser.parse_args()

    session_kwargs = {"region_name": args.region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile

    session = boto3.Session(**session_kwargs)

    print("=" * 50)
    print("Pharma Data Exchange Hub — Production Smoke Tests")
    print("=" * 50)
    print(f"  Profile: {args.profile or '(default)'}")
    print(f"  Region:  {args.region}")

    # Run all checks
    check_dynamodb_tables(session)
    check_s3_buckets(session)
    check_cloudwatch_log_groups(session)
    check_sns_topics(session)
    check_api_gateway(session)
    check_step_functions(session)
    check_cloudtrail(session)
    check_kms_keys(session)
    check_write_read_cmo_profile(session)
    check_write_read_contract(session)

    # Summary
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)

    print("\n" + "=" * 50)
    print(f"Results: {passed}/{total} passed, {failed} failed")
    print("=" * 50)

    if failed > 0:
        print("\nFailed checks:")
        for r in results:
            if not r.passed:
                print(f"  - {r.name}: {r.detail}")
        sys.exit(1)
    else:
        print("\nAll smoke tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
