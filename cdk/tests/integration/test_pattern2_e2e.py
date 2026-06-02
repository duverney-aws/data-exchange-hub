"""
Pattern 2 End-to-End Integration Test

Tests the full Pattern 2 (Secure File Transfer / SFTP) flow:
  CMO registration → Contract creation (secure-transfer) →
  SFTP endpoint provisioning → File upload simulation →
  File detection & processing → Bronze data write →
  ETL Bronze-to-Silver → Data quality validation →
  Silver promotion → File archival verification

Uses moto mocks so the test is self-contained and does not require
deployed AWS infrastructure.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 8.1, 8.2, 8.3
"""
import io
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import boto3
import pandas as pd
import pytest
from moto import mock_aws

# Ensure the cdk root is on sys.path so service imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from models.data_contract import QualityRule
from services.secure_transfer_service import SecureTransferService
from services.pipeline_orchestration_service import PipelineOrchestrationService
from services.etl_processing_service import ETLProcessingService
from services.data_quality_service import DataQualityService
from services.validation_handler_service import ValidationHandlerService
from utils.s3_path_utils import generate_bronze_path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGION = "us-east-1"
BUCKET = "cmo-data-lake-test"
FIXED_TS = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)

CMO_ID = "cmo-test-beta"
DATA_DOMAIN = "quality-data"
CONTRACT_ID = "CMO-TEST-BETA-QUALITY-001"
SCHEMA_ID = "test-beta-quality-data"

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

SAMPLE_QUALITY_RECORDS = pd.DataFrame({
    "sample_id": ["SMP001", "SMP002", "SMP003", "SMP004"],
    "test_name": ["Dissolution", "Assay", "Impurity", "Moisture"],
    "test_date": ["2024-06-01", "2024-06-02", "2024-06-03", "2024-06-04"],
    "result_value": [98.5, 99.2, 0.15, 2.3],
    "unit": ["%", "%", "%", "%"],
    "quality_status": ["PASS", "PASS", "PASS", "PASS"],
})

TEST_SCHEMA_DEFINITION = {
    "type": "object",
    "properties": {
        "sample_id": {"type": "string"},
        "test_name": {"type": "string"},
        "test_date": {"type": "string"},
        "result_value": {"type": "number"},
        "unit": {"type": "string"},
        "quality_status": {"type": "string"},
    },
    "required": ["sample_id", "test_name", "result_value"],
}

QUALITY_RULES = [
    QualityRule(
        rule_id="qr-010",
        rule_name="sample_id_completeness",
        rule_type="completeness",
        expression='Completeness "sample_id" > 0.99',
        threshold=99.0,
        severity="error",
    ),
]

CONTRACT_DICT = {
    "contractId": CONTRACT_ID,
    "cmoId": CMO_ID,
    "dataDomain": DATA_DOMAIN,
    "integrationPattern": "secure-transfer",
    "status": "active",
    "schemaId": SCHEMA_ID,
    "schemaVersion": "1.0",
    "qualityRules": [r.to_dict() for r in QUALITY_RULES],
    "sla": {
        "timeliness": {"maxDelayHours": 48, "measurementWindow": "weekly"},
        "availability": {"uptimePercentage": 99.0, "measurementWindow": "monthly"},
        "quality": {"minQualityScore": 90.0, "measurementWindow": "weekly"},
    },
    "deliverySchedule": {
        "frequency": "weekly",
        "timezone": "UTC",
    },
    "governance": {
        "dataClassification": "restricted",
        "retentionYears": 7,
        "allowedUsers": ["merck-quality-team"],
        "allowedGroups": ["pharma-analysts"],
        "piiFields": ["operator_name"],
        "encryptionRequired": True,
    },
}

CMO_PROFILE = {
    "cmoId": CMO_ID,
    "organizationName": "Test Beta BioManufacturing",
    "contactEmail": "admin@test-beta-bio.example.com",
    "contactPhone": "+1-555-0200",
    "address": "200 Test Beta Blvd, Cambridge, MA 02139",
    "gxpCertified": False,
    "createdAt": FIXED_TS.isoformat(),
    "status": "active",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _floats_to_decimal(obj):
    """Recursively convert float values to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _floats_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_floats_to_decimal(v) for v in obj]
    return obj


def _create_dynamodb_tables(dynamodb_resource):
    """Create DynamoDB tables matching production key schemas."""
    dynamodb_resource.create_table(
        TableName="cmo-profiles",
        KeySchema=[{"AttributeName": "cmoId", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "cmoId", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    dynamodb_resource.create_table(
        TableName="data-contracts",
        KeySchema=[{"AttributeName": "contractId", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "contractId", "AttributeType": "S"},
            {"AttributeName": "cmoId", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "cmo-contracts-index",
                "KeySchema": [
                    {"AttributeName": "cmoId", "KeyType": "HASH"},
                    {"AttributeName": "status", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _create_s3_bucket(s3_client):
    """Create the test data lake bucket."""
    s3_client.create_bucket(Bucket=BUCKET)


def _create_glue_database(glue_client):
    """Create the Glue database used by catalog registration."""
    glue_client.create_database(
        DatabaseInput={"Name": "cmo_data_lake", "Description": "Test database"}
    )


def _create_sns_topics(sns_client):
    """Create SNS topics used by alert services."""
    sns_client.create_topic(Name="cmo-alerts-warning")
    sns_client.create_topic(Name="cmo-alerts-critical")


def _write_bronze_parquet(s3_client, df: pd.DataFrame) -> str:
    """Write sample data as Parquet to the Bronze S3 path and return the key."""
    bronze_path = generate_bronze_path(BUCKET, CMO_ID, DATA_DOMAIN, FIXED_TS)
    key = bronze_path.replace(f"s3://{BUCKET}/", "") + "data.parquet"

    buf = io.BytesIO()
    df.to_parquet(buf, index=False, compression="snappy")
    buf.seek(0)
    s3_client.put_object(Bucket=BUCKET, Key=key, Body=buf.getvalue())
    return key


def _build_mock_schema_registry():
    """Return a mock SchemaRegistryService that returns our test schema."""
    mock_registry = MagicMock()
    mock_registry.get_schema.return_value = {
        "schema_name": SCHEMA_ID,
        "schema_version_id": "v1",
        "schema_definition": TEST_SCHEMA_DEFINITION,
        "data_format": "JSON",
        "version_number": 1,
    }
    return mock_registry


def _build_s3_event(bucket: str, key: str, size: int) -> dict:
    """Build an S3 event notification dict simulating a file upload."""
    return {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": bucket},
                    "object": {"key": key, "size": size},
                }
            }
        ]
    }


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestPattern2EndToEnd:
    """
    End-to-end test for Pattern 2 (Secure File Transfer / SFTP).

    Exercises the full service-layer flow using moto-mocked AWS resources.
    """

    @mock_aws
    def test_full_pattern2_pipeline(self):
        """
        Complete Pattern 2 flow:
        1. Register CMO profile
        2. Create data contract with secure-transfer pattern
        3. Provision SFTP endpoint
        4. Simulate file upload via S3 event
        5. Write sample CSV data to Bronze as Parquet
        6. Run ETL Bronze-to-Silver
        7. Run data quality validation
        8. Handle validation result (promote to Silver)
        9. Verify data across Bronze and Silver, quality passed, archival
        """
        # -- Setup mocked AWS resources --
        os.environ["AWS_DEFAULT_REGION"] = REGION
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SECURITY_TOKEN"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"

        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        s3 = boto3.client("s3", region_name=REGION)
        glue = boto3.client("glue", region_name=REGION)
        sns = boto3.client("sns", region_name=REGION)

        _create_dynamodb_tables(dynamodb)
        _create_s3_bucket(s3)
        _create_glue_database(glue)
        _create_sns_topics(sns)

        # ---------------------------------------------------------------
        # Step 1: Register CMO profile in DynamoDB
        # ---------------------------------------------------------------
        cmo_table = dynamodb.Table("cmo-profiles")
        cmo_table.put_item(Item=CMO_PROFILE)

        cmo_item = cmo_table.get_item(Key={"cmoId": CMO_ID})["Item"]
        assert cmo_item["cmoId"] == CMO_ID
        assert cmo_item["status"] == "active"

        # ---------------------------------------------------------------
        # Step 2: Create data contract with Pattern 2 (secure-transfer)
        # ---------------------------------------------------------------
        contracts_table = dynamodb.Table("data-contracts")
        contracts_table.put_item(
            Item=_floats_to_decimal({
                **CONTRACT_DICT,
                "createdAt": FIXED_TS.isoformat(),
                "updatedAt": FIXED_TS.isoformat(),
            })
        )

        contract_item = contracts_table.get_item(
            Key={"contractId": CONTRACT_ID}
        )["Item"]
        assert contract_item["contractId"] == CONTRACT_ID
        assert contract_item["integrationPattern"] == "secure-transfer"

        # ---------------------------------------------------------------
        # Step 3: Provision SFTP endpoint
        # ---------------------------------------------------------------
        sftp_svc = SecureTransferService()
        sftp_result = sftp_svc.provision_sftp_endpoint(CONTRACT_DICT)

        sftp_config = sftp_result["sftpConfig"]
        assert sftp_config["hostname"] is not None
        assert sftp_config["username"].startswith(f"{CMO_ID}-{DATA_DOMAIN}-")
        assert len(sftp_config["password"]) == 32
        assert sftp_config["homeDirectory"] == f"/bronze/{CMO_ID}/{DATA_DOMAIN}/incoming/"

        # Verify unique credentials across two provisioning calls
        sftp_result_2 = sftp_svc.provision_sftp_endpoint(CONTRACT_DICT)
        assert sftp_result["sftpConfig"]["username"] != sftp_result_2["sftpConfig"]["username"]
        assert sftp_result["sftpConfig"]["password"] != sftp_result_2["sftpConfig"]["password"]

        # Verify secret config
        assert sftp_result["secretConfig"]["secretName"] == f"cmo/{CMO_ID}/sftp-credentials"
        assert "provisionedAt" in sftp_result
        assert sftp_result["patternStep"] == "ProvisionSFTP"

        # ---------------------------------------------------------------
        # Step 4: Simulate file upload via S3 event
        # ---------------------------------------------------------------
        incoming_key = f"bronze/{CMO_ID}/{DATA_DOMAIN}/incoming/quality_data.csv"
        csv_content = SAMPLE_QUALITY_RECORDS.to_csv(index=False).encode("utf-8")
        s3.put_object(Bucket=BUCKET, Key=incoming_key, Body=csv_content)

        s3_event = _build_s3_event(
            bucket=BUCKET, key=incoming_key, size=len(csv_content)
        )
        file_result = sftp_svc.process_uploaded_file(
            s3_event, CONTRACT_DICT, bucket_name=BUCKET
        )

        assert file_result["status"] == "processed"
        assert file_result["contractId"] == CONTRACT_ID
        assert "bronzePath" in file_result
        assert f"bronze/{CMO_ID}/{DATA_DOMAIN}/" in file_result["bronzePath"]
        assert "year=" in file_result["bronzeKey"]
        assert "month=" in file_result["bronzeKey"]
        assert "day=" in file_result["bronzeKey"]

        # Verify archival path generated
        assert "archiveKey" in file_result
        assert "archive" in file_result["archiveKey"]
        assert "quality_data.csv" in file_result["archiveKey"]

        # ---------------------------------------------------------------
        # Step 5: Write sample CSV data to Bronze as Parquet
        # ---------------------------------------------------------------
        bronze_key = _write_bronze_parquet(s3, SAMPLE_QUALITY_RECORDS)

        bronze_obj = s3.get_object(Bucket=BUCKET, Key=bronze_key)
        bronze_df = pd.read_parquet(io.BytesIO(bronze_obj["Body"].read()))
        assert len(bronze_df) == 4
        assert "sample_id" in bronze_df.columns

        # ---------------------------------------------------------------
        # Step 6: Run ETL Bronze-to-Silver transformation
        # ---------------------------------------------------------------
        mock_registry = _build_mock_schema_registry()
        etl_svc = ETLProcessingService(
            s3_client=s3, schema_registry_service=mock_registry
        )
        etl_result = etl_svc.transform_bronze_to_silver(
            bucket=BUCKET,
            key=bronze_key,
            schema_id=SCHEMA_ID,
            schema_version="1.0",
            dedup_key_columns=["sample_id"],
        )

        silver_df = etl_result["silver_df"]
        quarantine_df = etl_result["quarantine_df"]
        metrics = etl_result["metrics"]

        assert metrics["total_records"] == 4
        assert metrics["valid_records"] == 4
        assert metrics["invalid_records"] == 0
        assert metrics["duplicates_removed"] == 0
        assert len(silver_df) == 4
        assert "_validation_timestamp" in silver_df.columns

        # ---------------------------------------------------------------
        # Step 7: Run data quality validation
        # ---------------------------------------------------------------
        dq_svc = DataQualityService()
        quality_report = dq_svc.evaluate_rules(silver_df, QUALITY_RULES)

        assert quality_report.passed is True
        assert quality_report.overall_score == 100.0
        assert quality_report.rules_passed == 1
        assert quality_report.rules_failed == 0
        assert quality_report.errors == 0

        # ---------------------------------------------------------------
        # Step 8: Handle validation result – promote to Silver
        # ---------------------------------------------------------------
        validation_svc = ValidationHandlerService(
            s3_client=s3, glue_client=glue
        )
        validation_result = validation_svc.handle_validation_result(
            silver_df=silver_df,
            quarantine_df=quarantine_df,
            quality_report=quality_report,
            bucket=BUCKET,
            cmo_id=CMO_ID,
            data_domain=DATA_DOMAIN,
            contract_id=CONTRACT_ID,
            timestamp=FIXED_TS,
        )

        assert validation_result["records_promoted"] == 4
        assert validation_result["records_quarantined"] == 0
        assert validation_result["silver_s3_path"] is not None
        assert "silver" in validation_result["silver_s3_path"]
        assert validation_result["catalog_table"] == "cmo_test_beta_quality_data_silver"

        # ---------------------------------------------------------------
        # Step 9: Verify data across Bronze and Silver layers
        # ---------------------------------------------------------------
        # Verify Bronze data in S3
        bronze_check = s3.get_object(Bucket=BUCKET, Key=bronze_key)
        assert bronze_check["ContentLength"] > 0

        # Verify Silver data in S3
        silver_s3_path = validation_result["silver_s3_path"]
        silver_key = silver_s3_path.replace(f"s3://{BUCKET}/", "") + "data.parquet"
        silver_obj = s3.get_object(Bucket=BUCKET, Key=silver_key)
        silver_read_df = pd.read_parquet(io.BytesIO(silver_obj["Body"].read()))
        assert len(silver_read_df) == 4
        assert "_validation_timestamp" in silver_read_df.columns

        # Verify quality report summary
        report_dict = quality_report.to_dict()
        assert report_dict["overall_score"] == 100.0
        assert report_dict["passed"] is True
        assert report_dict["total_rules"] == 1
