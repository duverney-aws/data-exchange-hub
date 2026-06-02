"""
Pattern 3 End-to-End Integration Test

Tests the full Pattern 3 (AI-Powered Unstructured Data Processing) flow:
  CMO registration → Contract creation → AI processing config →
  Pipeline orchestration → Document type detection → Textract extraction →
  Textract result parsing → Rekognition extraction → Rekognition result
  parsing → Confidence thresholding → Manual review flagging →
  Full document processing

Uses moto mocks so the test is self-contained and does not require
deployed AWS infrastructure.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.2
"""
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

import boto3
import pytest
from moto import mock_aws

# Ensure the cdk root is on sys.path so service imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.ai_processing_service import AIProcessingService
from services.pipeline_orchestration_service import PipelineOrchestrationService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGION = "us-east-1"
BUCKET = "cmo-data-lake-test"
FIXED_TS = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)

CMO_ID = "cmo-test-alpha"
DATA_DOMAIN = "batch-documents"
CONTRACT_ID = "CMO-TEST-ALPHA-DOCS-001"
SCHEMA_ID = "test-alpha-batch-documents"

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

CONTRACT_DICT = {
    "contractId": CONTRACT_ID,
    "cmoId": CMO_ID,
    "dataDomain": DATA_DOMAIN,
    "integrationPattern": "ai-unstructured",
    "status": "active",
    "schemaId": SCHEMA_ID,
    "schemaVersion": "1.0",
    "qualityRules": [],
    "sla": {
        "timeliness": {"maxDelayHours": 48, "measurementWindow": "daily"},
        "availability": {"uptimePercentage": 99.0, "measurementWindow": "monthly"},
        "quality": {"minQualityScore": 90.0, "measurementWindow": "daily"},
    },
    "deliverySchedule": {
        "frequency": "daily",
        "cronExpression": "0 6 * * *",
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
# Synthetic Textract response for parsing tests
# ---------------------------------------------------------------------------


def _build_synthetic_textract_response():
    """
    Build a realistic Textract response with LINE, TABLE, and KEY_VALUE_SET
    blocks including relationships and confidence scores.
    """
    return {
        "Blocks": [
            # PAGE block
            {
                "Id": "page-1",
                "BlockType": "PAGE",
                "Confidence": 99.0,
                "Relationships": [
                    {"Type": "CHILD", "Ids": ["line-1", "line-2", "table-1", "kv-key-1"]}
                ],
            },
            # LINE blocks
            {
                "Id": "line-1",
                "BlockType": "LINE",
                "Text": "Batch Record Summary",
                "Confidence": 97.5,
            },
            {
                "Id": "line-2",
                "BlockType": "LINE",
                "Text": "Product: Aspirin 500mg",
                "Confidence": 95.0,
            },
            # TABLE block with CELL children
            {
                "Id": "table-1",
                "BlockType": "TABLE",
                "Confidence": 93.0,
                "Relationships": [
                    {"Type": "CHILD", "Ids": [
                        "cell-1-1", "cell-1-2",
                        "cell-2-1", "cell-2-2",
                    ]}
                ],
            },
            # Header row cells
            {
                "Id": "cell-1-1",
                "BlockType": "CELL",
                "RowIndex": 1,
                "ColumnIndex": 1,
                "Confidence": 96.0,
                "Relationships": [
                    {"Type": "CHILD", "Ids": ["word-batch"]}
                ],
            },
            {
                "Id": "cell-1-2",
                "BlockType": "CELL",
                "RowIndex": 1,
                "ColumnIndex": 2,
                "Confidence": 96.0,
                "Relationships": [
                    {"Type": "CHILD", "Ids": ["word-quantity"]}
                ],
            },
            # Data row cells
            {
                "Id": "cell-2-1",
                "BlockType": "CELL",
                "RowIndex": 2,
                "ColumnIndex": 1,
                "Confidence": 94.0,
                "Relationships": [
                    {"Type": "CHILD", "Ids": ["word-b001"]}
                ],
            },
            {
                "Id": "cell-2-2",
                "BlockType": "CELL",
                "RowIndex": 2,
                "ColumnIndex": 2,
                "Confidence": 92.0,
                "Relationships": [
                    {"Type": "CHILD", "Ids": ["word-10000"]}
                ],
            },
            # WORD blocks for table cells
            {"Id": "word-batch", "BlockType": "WORD", "Text": "BatchID", "Confidence": 98.0},
            {"Id": "word-quantity", "BlockType": "WORD", "Text": "Quantity", "Confidence": 97.0},
            {"Id": "word-b001", "BlockType": "WORD", "Text": "B001", "Confidence": 95.0},
            {"Id": "word-10000", "BlockType": "WORD", "Text": "10000", "Confidence": 93.0},
            # KEY_VALUE_SET blocks
            {
                "Id": "kv-key-1",
                "BlockType": "KEY_VALUE_SET",
                "EntityTypes": ["KEY"],
                "Confidence": 91.0,
                "Relationships": [
                    {"Type": "CHILD", "Ids": ["word-product-label"]},
                    {"Type": "VALUE", "Ids": ["kv-value-1"]},
                ],
            },
            {
                "Id": "kv-value-1",
                "BlockType": "KEY_VALUE_SET",
                "EntityTypes": ["VALUE"],
                "Confidence": 90.0,
                "Relationships": [
                    {"Type": "CHILD", "Ids": ["word-aspirin-val"]},
                ],
            },
            # WORD blocks for key-value pairs
            {"Id": "word-product-label", "BlockType": "WORD", "Text": "Product", "Confidence": 96.0},
            {"Id": "word-aspirin-val", "BlockType": "WORD", "Text": "Aspirin", "Confidence": 94.0},
        ]
    }


def _build_synthetic_rekognition_response():
    """
    Build a synthetic Rekognition response with labels and text detections.
    Confidence values are 0-100 (Rekognition native scale).
    """
    return {
        "labelsResponse": {
            "Labels": [
                {"Name": "Document", "Confidence": 98.5},
                {"Name": "Text", "Confidence": 95.0},
                {"Name": "Paper", "Confidence": 88.0},
            ],
        },
        "textResponse": {
            "TextDetections": [
                {"DetectedText": "Batch Record", "Type": "LINE", "Confidence": 97.0},
                {"DetectedText": "Lot: 12345", "Type": "LINE", "Confidence": 92.0},
                # WORD-type entries should be filtered out by the parser
                {"DetectedText": "Batch", "Type": "WORD", "Confidence": 97.0},
            ],
        },
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


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestPattern3EndToEnd:
    """
    End-to-end test for Pattern 3 (AI-Powered Unstructured Data Processing).

    Exercises the full service-layer flow using moto-mocked AWS resources.
    """

    @mock_aws
    def test_full_pattern3_pipeline(self):
        """
        Complete Pattern 3 flow:
        1.  Register CMO profile
        2.  Create data contract with ai-unstructured pattern
        3.  Orchestrate pipeline deployment (verify AI config)
        4.  Detect document types (PDF and image)
        5.  Textract extraction (stub — no real client)
        6.  Parse synthetic Textract results
        7.  Rekognition extraction (stub — no real client)
        8.  Parse synthetic Rekognition results
        9.  Confidence thresholding — HIGH confidence
        10. Confidence thresholding — LOW confidence
        11. Full document processing orchestration
        """
        # -- Setup mocked AWS resources --
        os.environ["AWS_DEFAULT_REGION"] = REGION
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SECURITY_TOKEN"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"

        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        s3 = boto3.client("s3", region_name=REGION)

        _create_dynamodb_tables(dynamodb)
        _create_s3_bucket(s3)

        # ---------------------------------------------------------------
        # Step 1: Register CMO profile in DynamoDB
        # ---------------------------------------------------------------
        cmo_table = dynamodb.Table("cmo-profiles")
        cmo_table.put_item(Item=CMO_PROFILE)

        cmo_item = cmo_table.get_item(Key={"cmoId": CMO_ID})["Item"]
        assert cmo_item["cmoId"] == CMO_ID
        assert cmo_item["status"] == "active"

        # ---------------------------------------------------------------
        # Step 2: Create data contract with Pattern 3 (ai-unstructured)
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
        assert contract_item["integrationPattern"] == "ai-unstructured"

        # ---------------------------------------------------------------
        # Step 3: Orchestrate pipeline deployment — verify AI config
        # ---------------------------------------------------------------
        orchestration_svc = PipelineOrchestrationService()
        deployment = orchestration_svc.orchestrate_deployment(
            CONTRACT_DICT, bucket_name=BUCKET
        )

        assert "aiProcessingConfig" in deployment
        ai_cfg = deployment["aiProcessingConfig"]
        assert ai_cfg["confidenceThreshold"] == 0.85
        assert ai_cfg["outputFormat"] == "json"
        assert "pdf" in ai_cfg["documentTypes"]

        assert "etlJobDefinition" in deployment
        etl_def = deployment["etlJobDefinition"]
        assert etl_def["contractId"] == CONTRACT_ID
        assert etl_def["cmoId"] == CMO_ID

        # ---------------------------------------------------------------
        # Step 4: Document type detection (PDF and image)
        # ---------------------------------------------------------------
        ai_svc = AIProcessingService()

        pdf_info = ai_svc.detect_document_type("documents/batch-record.pdf")
        assert pdf_info["documentType"] == "pdf"
        assert pdf_info["extension"] == ".pdf"
        assert pdf_info["supported"] is True

        img_info = ai_svc.detect_document_type("images/label-photo.png")
        assert img_info["documentType"] == "image"
        assert img_info["extension"] == ".png"
        assert img_info["supported"] is True

        jpg_info = ai_svc.detect_document_type("images/defect.jpg")
        assert jpg_info["documentType"] == "image"
        assert jpg_info["extension"] == ".jpg"

        # ---------------------------------------------------------------
        # Step 5: Textract extraction (no real client → stub response)
        # ---------------------------------------------------------------
        textract_result = ai_svc.extract_with_textract(
            file_key="documents/batch-record.pdf",
            bucket_name=BUCKET,
            contract=CONTRACT_DICT,
        )

        assert textract_result["status"] == "no_client"
        assert textract_result["documentType"] == "pdf"
        assert textract_result["contractId"] == CONTRACT_ID
        assert textract_result["textractResponse"]["Blocks"] == []

        # ---------------------------------------------------------------
        # Step 6: Parse synthetic Textract results
        # ---------------------------------------------------------------
        synthetic_textract = _build_synthetic_textract_response()
        parsed = ai_svc.parse_textract_results(synthetic_textract, CONTRACT_DICT)

        # Verify extracted text lines
        assert "Batch Record Summary" in parsed["extractedText"]
        assert "Product: Aspirin 500mg" in parsed["extractedText"]

        # Verify extracted tables
        assert len(parsed["extractedTables"]) >= 1
        table = parsed["extractedTables"][0]
        assert len(table) >= 1  # at least one data row
        assert "BatchID" in table[0]  # header became key
        assert table[0]["BatchID"] == "B001"
        assert table[0]["Quantity"] == "10000"

        # Verify extracted forms (key-value pairs)
        assert "Product" in parsed["extractedForms"]
        assert parsed["extractedForms"]["Product"] == "Aspirin"

        # Verify confidence score is calculated and in range
        assert 0.0 < parsed["confidence"] <= 1.0
        assert parsed["contractId"] == CONTRACT_ID
        assert parsed["outputFormat"] == "json"
        assert parsed["blockCount"] == len(synthetic_textract["Blocks"])

        # ---------------------------------------------------------------
        # Step 7: Rekognition extraction (no real client → stub response)
        # ---------------------------------------------------------------
        rekog_result = ai_svc.extract_with_rekognition(
            file_key="images/label-photo.png",
            bucket_name=BUCKET,
            contract=CONTRACT_DICT,
        )

        assert rekog_result["status"] == "no_client"
        assert rekog_result["documentType"] == "image"
        assert rekog_result["contractId"] == CONTRACT_ID
        assert rekog_result["labelsResponse"]["Labels"] == []
        assert rekog_result["textResponse"]["TextDetections"] == []

        # ---------------------------------------------------------------
        # Step 8: Parse synthetic Rekognition results
        # ---------------------------------------------------------------
        synthetic_rekog = _build_synthetic_rekognition_response()
        rekog_parsed = ai_svc.parse_rekognition_results(
            synthetic_rekog, CONTRACT_DICT
        )

        # Verify detected labels
        assert len(rekog_parsed["detectedLabels"]) == 3
        label_names = [l["name"] for l in rekog_parsed["detectedLabels"]]
        assert "Document" in label_names
        assert "Text" in label_names
        assert "Paper" in label_names
        # Confidence should be normalised to 0-1 range
        for label in rekog_parsed["detectedLabels"]:
            assert 0.0 < label["confidence"] <= 1.0

        # Verify detected text (only LINE type, not WORD)
        assert len(rekog_parsed["detectedText"]) == 2
        text_values = [t["text"] for t in rekog_parsed["detectedText"]]
        assert "Batch Record" in text_values
        assert "Lot: 12345" in text_values
        for t in rekog_parsed["detectedText"]:
            assert 0.0 < t["confidence"] <= 1.0

        # Verify overall confidence
        assert 0.0 < rekog_parsed["confidence"] <= 1.0
        assert rekog_parsed["contractId"] == CONTRACT_ID

        # ---------------------------------------------------------------
        # Step 9: Confidence thresholding — HIGH confidence (>= 0.85)
        # ---------------------------------------------------------------
        high_confidence_result = {"confidence": 0.92, "extractedText": ["OK"]}
        threshold_high = ai_svc.apply_confidence_thresholding(
            parsed_result=high_confidence_result,
            contract=CONTRACT_DICT,
            bucket_name=BUCKET,
        )

        assert threshold_high["destination"] == "bronze"
        assert threshold_high["needsReview"] is False
        assert threshold_high["confidence"] == 0.92
        assert threshold_high["contractId"] == CONTRACT_ID
        assert threshold_high["cmoId"] == CMO_ID
        assert "bronze" in threshold_high["destinationPath"]
        assert "manual-review" not in threshold_high["destinationPath"]

        # ---------------------------------------------------------------
        # Step 10: Confidence thresholding — LOW confidence (< 0.85)
        # ---------------------------------------------------------------
        low_confidence_result = {"confidence": 0.72, "extractedText": ["blurry"]}
        threshold_low = ai_svc.apply_confidence_thresholding(
            parsed_result=low_confidence_result,
            contract=CONTRACT_DICT,
            bucket_name=BUCKET,
        )

        assert threshold_low["destination"] == "manual_review"
        assert threshold_low["needsReview"] is True
        assert threshold_low["confidence"] == 0.72
        assert threshold_low["contractId"] == CONTRACT_ID
        assert "manual-review" in threshold_low["destinationPath"]

        # ---------------------------------------------------------------
        # Step 11: Full document processing orchestration
        # ---------------------------------------------------------------
        process_result = ai_svc.process_document(
            event={"file_key": "documents/batch-record.pdf"},
            contract=CONTRACT_DICT,
            bucket_name=BUCKET,
        )

        assert process_result["contractId"] == CONTRACT_ID
        assert process_result["cmoId"] == CMO_ID
        assert process_result["dataDomain"] == DATA_DOMAIN
        assert process_result["documentType"] == "pdf"
        assert process_result["outputFormat"] == "json"
        assert process_result["status"] == "processed"
        assert "bronzePath" in process_result
        assert "destination" in process_result
        assert "destinationPath" in process_result
        assert isinstance(process_result["needsReview"], bool)
        assert isinstance(process_result["extractedText"], list)
        assert isinstance(process_result["extractedTables"], list)
        assert isinstance(process_result["extractedForms"], dict)
        assert "processedAt" in process_result
