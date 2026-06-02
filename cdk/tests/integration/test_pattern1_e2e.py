"""
Pattern 1 End-to-End Integration Test

Tests the full Pattern 1 (Native Database Connector / Snowflake) flow:
  CMO registration → Contract creation → Snowflake connector config →
  Pipeline orchestration → Bronze data write → ETL Bronze-to-Silver →
  Data quality validation → Silver promotion → Gold aggregation

Uses moto mocks so the test is self-contained and does not require
deployed AWS infrastructure.

Requirements: 5.1, 5.2, 5.3, 5.4, 8.1, 8.2, 8.3, 9.5
"""
import io
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import boto3
import pandas as pd
import pytest
from moto import mock_aws

# Ensure the cdk root is on sys.path so service imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from models.data_contract import DataContract, QualityRule, SLA, DeliverySchedule, Governance
from services.native_connector_service import NativeConnectorService
from services.pipeline_orchestration_service import PipelineOrchestrationService
from services.etl_processing_service import ETLProcessingService
from services.data_quality_service import DataQualityService
from services.validation_handler_service import ValidationHandlerService
from services.gold_aggregation_service import GoldAggregationService
from services.quality_metrics_service import QualityMetricsService
from services.contract_service import ContractService
from utils.s3_path_utils import generate_bronze_path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGION = "us-east-1"
BUCKET = "cmo-data-lake-test"
FIXED_TS = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)

CMO_ID = "cmo-test-alpha"
DATA_DOMAIN = "batch-records"
CONTRACT_ID = "CMO-TEST-ALPHA-BATCH-001"
SCHEMA_ID = "test-alpha-batch-records"

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

SAMPLE_BATCH_RECORDS = pd.DataFrame({
    "batch_id": ["BATCH001", "BATCH002", "BATCH003", "BATCH004", "BATCH005"],
    "product_name": ["Aspirin 500mg", "Ibuprofen 200mg", "Amoxicillin 250mg",
                     "Metformin 500mg", "Lisinopril 10mg"],
    "manufacture_date": ["2024-06-01", "2024-06-02", "2024-06-03",
                         "2024-06-04", "2024-06-05"],
    "quantity": [10000, 5000, 8000, 20000, 15000],
    "unit": ["tablets", "tablets", "capsules", "tablets", "tablets"],
    "quality_status": ["PASS", "PASS", "PASS", "PASS", "PASS"],
})

TEST_SCHEMA_DEFINITION = {
    "type": "object",
    "properties": {
        "batch_id": {"type": "string"},
        "product_name": {"type": "string"},
        "manufacture_date": {"type": "string"},
        "quantity": {"type": "integer"},
        "unit": {"type": "string"},
        "quality_status": {"type": "string"},
    },
    "required": ["batch_id", "product_name", "quantity"],
}

QUALITY_RULES = [
    QualityRule(
        rule_id="qr-001",
        rule_name="batch_id_completeness",
        rule_type="completeness",
        expression='Completeness "batch_id" > 0.99',
        threshold=99.0,
        severity="error",
    ),
    QualityRule(
        rule_id="qr-002",
        rule_name="batch_id_uniqueness",
        rule_type="uniqueness",
        expression='Uniqueness "batch_id" > 0.99',
        threshold=99.0,
        severity="error",
    ),
]

CONTRACT_DICT = {
    "contractId": CONTRACT_ID,
    "cmoId": CMO_ID,
    "dataDomain": DATA_DOMAIN,
    "integrationPattern": "native-connector",
    "status": "active",
    "connectionConfig": {
        "connectionType": "snowflake",
        "database": "PHARMA_DB",
        "schema": "BATCH_DATA",
        "tableOrQuery": "BATCH_RECORDS",
    },
    "schemaId": SCHEMA_ID,
    "schemaVersion": "1.0",
    "qualityRules": [r.to_dict() for r in QUALITY_RULES],
    "sla": {
        "timeliness": {"maxDelayHours": 24, "measurementWindow": "daily"},
        "availability": {"uptimePercentage": 99.5, "measurementWindow": "monthly"},
        "quality": {"minQualityScore": 95.0, "measurementWindow": "daily"},
    },
    "deliverySchedule": {
        "frequency": "daily",
        "cronExpression": "0 2 * * *",
        "timezone": "UTC",
    },
    "governance": {
        "dataClassification": "confidential",
        "retentionYears": 7,
        "allowedUsers": ["merck-quality-team"],
        "allowedGroups": ["pharma-analysts"],
        "piiFields": [],
        "encryptionRequired": True,
    },
}

CMO_PROFILE = {
    "cmoId": CMO_ID,
    "organizationName": "Test Alpha Pharmaceuticals",
    "contactEmail": "admin@test-alpha-pharma.example.com",
    "contactPhone": "+1-555-0100",
    "address": "100 Test Alpha Way, Boston, MA 02101",
    "gxpCertified": True,
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
    # cmo-profiles table
    dynamodb_resource.create_table(
        TableName="cmo-profiles",
        KeySchema=[{"AttributeName": "cmoId", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "cmoId", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    # data-contracts table with GSI
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


def _create_glue_database(glue_client):
    """Create the Glue database used by catalog registration."""
    glue_client.create_database(
        DatabaseInput={"Name": "cmo_data_lake", "Description": "Test database"}
    )


def _create_sns_topics(sns_client):
    """Create SNS topics used by QualityMetricsService."""
    sns_client.create_topic(Name="cmo-alerts-warning")
    sns_client.create_topic(Name="cmo-alerts-critical")


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestPattern1EndToEnd:
    """
    End-to-end test for Pattern 1 (Snowflake native connector).

    Exercises the full service-layer flow using moto-mocked AWS resources.
    """

    @mock_aws
    def test_full_pattern1_pipeline(self):
        """
        Complete Pattern 1 flow:
        1. Register CMO profile
        2. Create data contract with Snowflake config
        3. Build Snowflake connector config
        4. Orchestrate pipeline deployment
        5. Write sample data to Bronze
        6. Run ETL Bronze-to-Silver
        7. Run data quality validation
        8. Handle validation result (promote to Silver)
        9. Run Gold aggregation
        10. Verify data in Bronze, Silver, and Gold
        """
        # -- Setup mocked AWS resources --
        os.environ["AWS_DEFAULT_REGION"] = REGION
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SECURITY_TOKEN"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"

        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        s3 = boto3.client("s3", region_name=REGION)
        cloudwatch = boto3.client("cloudwatch", region_name=REGION)
        sns = boto3.client("sns", region_name=REGION)
        glue = boto3.client("glue", region_name=REGION)

        _create_dynamodb_tables(dynamodb)
        _create_s3_bucket(s3)
        _create_glue_database(glue)
        _create_sns_topics(sns)

        # ---------------------------------------------------------------
        # Step 1: Register CMO profile in DynamoDB
        # ---------------------------------------------------------------
        cmo_table = dynamodb.Table("cmo-profiles")
        cmo_table.put_item(Item=CMO_PROFILE)

        # Verify CMO was registered
        cmo_item = cmo_table.get_item(Key={"cmoId": CMO_ID})["Item"]
        assert cmo_item["cmoId"] == CMO_ID
        assert cmo_item["status"] == "active"

        # ---------------------------------------------------------------
        # Step 2: Create data contract with Pattern 1 (Snowflake)
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
        assert contract_item["integrationPattern"] == "native-connector"
        assert contract_item["connectionConfig"]["connectionType"] == "snowflake"

        # ---------------------------------------------------------------
        # Step 3: Configure Snowflake connector
        # ---------------------------------------------------------------
        connector_svc = NativeConnectorService(
            glue_client=glue, cloudwatch_client=cloudwatch
        )
        connector_config = connector_svc.build_connector_config(CONTRACT_DICT)

        assert connector_config["contractId"] == CONTRACT_ID
        cfg = connector_config["connectorConfig"]
        assert cfg["glueConnectionType"] == "SNOWFLAKE"
        assert cfg["connectionType"] == "snowflake"
        assert cfg["database"] == "PHARMA_DB"
        assert cfg["schema"] == "BATCH_DATA"
        assert cfg["tableOrQuery"] == "BATCH_RECORDS"
        assert cfg["secretId"] == f"cmo/{CMO_ID}/credentials"

        # ---------------------------------------------------------------
        # Step 4: Activate pipeline (orchestrate deployment)
        # ---------------------------------------------------------------
        orchestration_svc = PipelineOrchestrationService()
        deployment = orchestration_svc.orchestrate_deployment(
            CONTRACT_DICT, bucket_name=BUCKET
        )

        assert "etlJobDefinition" in deployment
        etl_def = deployment["etlJobDefinition"]
        assert etl_def["contractId"] == CONTRACT_ID
        assert etl_def["cmoId"] == CMO_ID
        assert f"bronze/{CMO_ID}/{DATA_DOMAIN}" in etl_def["s3Paths"]["bronze"]
        assert f"silver/{CMO_ID}/{DATA_DOMAIN}" in etl_def["s3Paths"]["silver"]
        assert "connectorConfig" in deployment

        # ---------------------------------------------------------------
        # Step 5: Write sample data to Bronze layer
        # ---------------------------------------------------------------
        bronze_key = _write_bronze_parquet(s3, SAMPLE_BATCH_RECORDS)

        # Verify Bronze data exists
        bronze_obj = s3.get_object(Bucket=BUCKET, Key=bronze_key)
        bronze_df = pd.read_parquet(io.BytesIO(bronze_obj["Body"].read()))
        assert len(bronze_df) == 5
        assert "batch_id" in bronze_df.columns

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
            dedup_key_columns=["batch_id"],
        )

        silver_df = etl_result["silver_df"]
        quarantine_df = etl_result["quarantine_df"]
        metrics = etl_result["metrics"]

        assert metrics["total_records"] == 5
        assert metrics["valid_records"] == 5
        assert metrics["invalid_records"] == 0
        assert metrics["duplicates_removed"] == 0
        assert len(silver_df) == 5
        assert "_validation_timestamp" in silver_df.columns

        # ---------------------------------------------------------------
        # Step 7: Run data quality validation
        # ---------------------------------------------------------------
        dq_svc = DataQualityService()
        quality_report = dq_svc.evaluate_rules(silver_df, QUALITY_RULES)

        assert quality_report.passed is True
        assert quality_report.overall_score == 100.0
        assert quality_report.rules_passed == 2
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

        assert validation_result["records_promoted"] == 5
        assert validation_result["records_quarantined"] == 0
        assert validation_result["silver_s3_path"] is not None
        assert "silver" in validation_result["silver_s3_path"]
        assert validation_result["catalog_table"] == "cmo_test_alpha_batch_records_silver"

        # Verify Silver data in S3
        silver_s3_path = validation_result["silver_s3_path"]
        silver_key = silver_s3_path.replace(f"s3://{BUCKET}/", "") + "data.parquet"
        silver_obj = s3.get_object(Bucket=BUCKET, Key=silver_key)
        silver_read_df = pd.read_parquet(io.BytesIO(silver_obj["Body"].read()))
        assert len(silver_read_df) == 5
        assert "_validation_timestamp" in silver_read_df.columns

        # ---------------------------------------------------------------
        # Step 9: Run Gold aggregation
        # ---------------------------------------------------------------
        gold_svc = GoldAggregationService(s3_client=s3, glue_client=glue)
        gold_result = gold_svc.aggregate_to_gold(
            bucket=BUCKET, key=silver_key, timestamp=FIXED_TS
        )

        assert gold_result["records_read"] == 5
        assert gold_result["batch_summary_path"] is not None
        assert "gold" in gold_result["batch_summary_path"]
        assert gold_result["quality_metrics_path"] is not None
        assert gold_result["cmo_performance_path"] is not None
        assert len(gold_result["tables_registered"]) == 3

        # Verify Gold batch summary data in S3
        batch_summary_path = gold_result["batch_summary_path"]
        batch_key = batch_summary_path.replace(f"s3://{BUCKET}/", "") + "data.parquet"
        batch_obj = s3.get_object(Bucket=BUCKET, Key=batch_key)
        batch_df = pd.read_parquet(io.BytesIO(batch_obj["Body"].read()))
        assert len(batch_df) > 0
        assert "record_count" in batch_df.columns

        # ---------------------------------------------------------------
        # Step 10: Verify quality metrics publishing
        # ---------------------------------------------------------------
        contract_svc = ContractService(
            table_name="data-contracts", dynamodb_resource=dynamodb
        )
        metrics_svc = QualityMetricsService(
            cloudwatch_client=cloudwatch,
            sns_client=sns,
            contract_service=contract_svc,
            region=REGION,
            account_id="000000000000",
        )

        # Build a DataContract for SLA checking
        data_contract = DataContract.from_dynamodb_item({
            **CONTRACT_DICT,
            "createdAt": FIXED_TS.isoformat(),
            "updatedAt": FIXED_TS.isoformat(),
        })

        metrics_result = metrics_svc.process_quality_metrics(
            quality_report=quality_report,
            contract_id=CONTRACT_ID,
            cmo_id=CMO_ID,
            data_contract=data_contract,
        )

        assert metrics_result["metrics_published"] is True
        # Quality passed and score (100) >= SLA min (95), so no breach
        assert "sla_quality_breach" not in metrics_result["notifications_sent"]
        # No error-severity failures
        assert "error_rules_failed" not in metrics_result["notifications_sent"]
        # Contract should be set to active since quality passed
        assert metrics_result["contract_status_updated"] is True
        assert metrics_result["new_status"] == "active"

        # Verify contract status was updated in DynamoDB
        updated_contract = contract_svc.get_contract(CONTRACT_ID)
        assert updated_contract.status == "active"

        # ---------------------------------------------------------------
        # Final assertions: data exists across all three layers
        # ---------------------------------------------------------------
        # Bronze
        bronze_check = s3.get_object(Bucket=BUCKET, Key=bronze_key)
        assert bronze_check["ContentLength"] > 0

        # Silver
        silver_check = s3.get_object(Bucket=BUCKET, Key=silver_key)
        assert silver_check["ContentLength"] > 0

        # Gold (batch summary)
        gold_check = s3.get_object(Bucket=BUCKET, Key=batch_key)
        assert gold_check["ContentLength"] > 0
