"""
Unit Tests for PII Detection and Masking Service.

Tests:
- Macie classification job creation with proper parameters
- Classification results retrieval
- Local PII field detection (emails, phones, SSNs, names)
- Masking strategies (hash, redact, partial)
- Original records are not modified after masking
- Masking rules per data classification level
- CMO ID validation

Requirements: 10.4

Note: Uses unittest.mock for Macie client (moto doesn't support Macie well).
"""
import sys
import os
import hashlib
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.pii_detection_service import PIIDetectionService


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CMO_ID = "cmo-alpha"
S3_BUCKET = "pharma-data-lake"
S3_PREFIX = "silver/cmo-alpha/batch-records/"
JOB_ID = "job-abc-123"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_macie():
    client = MagicMock()
    client.create_classification_job.return_value = {"jobId": JOB_ID}
    client.list_findings.return_value = {"findingIds": []}
    client.get_findings.return_value = {"findings": []}
    return client


@pytest.fixture
def service(mock_macie):
    return PIIDetectionService(macie_client=mock_macie, region="us-east-1")


@pytest.fixture
def sample_records():
    return [
        {
            "batch_id": "B001",
            "operator_name": "John Doe",
            "operator_email": "john.doe@example.com",
            "phone": "555-123-4567",
            "ssn": "123-45-6789",
            "quantity": 100,
        },
        {
            "batch_id": "B002",
            "operator_name": "Jane Smith",
            "operator_email": "jane@test.org",
            "phone": "(555) 987-6543",
            "ssn": "987-65-4321",
            "quantity": 200,
        },
    ]


@pytest.fixture
def pii_fields():
    return {
        "operator_name": ["NAME"],
        "operator_email": ["EMAIL"],
        "phone": ["PHONE"],
        "ssn": ["SSN"],
    }


# ---------------------------------------------------------------------------
# Classification Job Creation
# ---------------------------------------------------------------------------

class TestCreateClassificationJob:
    """Requirement 10.4: Create Macie classification jobs for Silver layer."""

    def test_returns_job_id(self, service):
        result = service.create_classification_job(CMO_ID, S3_BUCKET, S3_PREFIX)
        assert result["job_id"] == JOB_ID

    def test_job_name_follows_convention(self, service):
        result = service.create_classification_job(CMO_ID, S3_BUCKET, S3_PREFIX)
        assert result["job_name"].startswith(f"pii-scan-{CMO_ID}-")

    def test_status_is_running(self, service):
        result = service.create_classification_job(CMO_ID, S3_BUCKET, S3_PREFIX)
        assert result["status"] == "RUNNING"

    def test_calls_macie_with_one_time_job(self, service, mock_macie):
        service.create_classification_job(CMO_ID, S3_BUCKET, S3_PREFIX)
        call_kwargs = mock_macie.create_classification_job.call_args[1]
        assert call_kwargs["jobType"] == "ONE_TIME"

    def test_calls_macie_with_correct_bucket(self, service, mock_macie):
        service.create_classification_job(CMO_ID, S3_BUCKET, S3_PREFIX)
        call_kwargs = mock_macie.create_classification_job.call_args[1]
        buckets = call_kwargs["s3JobDefinition"]["bucketDefinitions"][0]["buckets"]
        assert S3_BUCKET in buckets

    def test_calls_macie_with_prefix_scoping(self, service, mock_macie):
        service.create_classification_job(CMO_ID, S3_BUCKET, S3_PREFIX)
        call_kwargs = mock_macie.create_classification_job.call_args[1]
        scoping = call_kwargs["s3JobDefinition"]["scoping"]
        scope_term = scoping["includes"]["and"][0]["simpleScopeTerm"]
        assert scope_term["key"] == "OBJECT_KEY"
        assert scope_term["comparator"] == "STARTS_WITH"
        assert S3_PREFIX in scope_term["values"]

    def test_tags_include_cmo_id(self, service, mock_macie):
        service.create_classification_job(CMO_ID, S3_BUCKET, S3_PREFIX)
        call_kwargs = mock_macie.create_classification_job.call_args[1]
        assert call_kwargs["tags"]["cmo-id"] == CMO_ID


# ---------------------------------------------------------------------------
# Classification Results
# ---------------------------------------------------------------------------

class TestGetClassificationResults:
    """Requirement 10.4: Retrieve PII findings from Macie."""

    def test_empty_findings_returns_empty_list(self, service):
        result = service.get_classification_results(JOB_ID)
        assert result == []

    def test_returns_detected_pii_fields(self, service, mock_macie):
        mock_macie.list_findings.return_value = {"findingIds": ["f-1"]}
        mock_macie.get_findings.return_value = {
            "findings": [
                {
                    "severity": {"description": "High"},
                    "classificationDetails": {
                        "result": {
                            "sensitiveData": [
                                {
                                    "category": "PERSONAL_INFORMATION",
                                    "detections": [
                                        {"name": "email", "count": 5},
                                        {"name": "phone", "count": 3},
                                    ],
                                }
                            ]
                        }
                    },
                }
            ]
        }
        results = service.get_classification_results(JOB_ID)
        assert len(results) == 2
        assert results[0]["pii_type"] == "PERSONAL_INFORMATION"
        assert results[0]["field_name"] == "email"
        assert results[0]["severity"] == "High"
        assert results[0]["count"] == 5


# ---------------------------------------------------------------------------
# Local PII Detection
# ---------------------------------------------------------------------------

class TestDetectPIIFields:
    """Requirement 10.4: Detect PII fields using regex patterns."""

    def test_detects_email(self, service):
        records = [{"contact": "user@example.com"}]
        result = service.detect_pii_fields(records)
        assert "EMAIL" in result["contact"]

    def test_detects_phone_dashed(self, service):
        records = [{"phone": "555-123-4567"}]
        result = service.detect_pii_fields(records)
        assert "PHONE" in result["phone"]

    def test_detects_phone_parentheses(self, service):
        records = [{"phone": "(555) 123-4567"}]
        result = service.detect_pii_fields(records)
        assert "PHONE" in result["phone"]

    def test_detects_ssn(self, service):
        records = [{"tax_id": "123-45-6789"}]
        result = service.detect_pii_fields(records)
        assert "SSN" in result["tax_id"]

    def test_detects_name_by_field_suffix(self, service):
        records = [{"operator_name": "John Doe"}]
        result = service.detect_pii_fields(records)
        assert "NAME" in result["operator_name"]

    def test_detects_contact_field(self, service):
        records = [{"primary_contact": "Jane"}]
        result = service.detect_pii_fields(records)
        assert "NAME" in result["primary_contact"]

    def test_detects_person_field(self, service):
        records = [{"responsible_person": "Bob"}]
        result = service.detect_pii_fields(records)
        assert "NAME" in result["responsible_person"]

    def test_no_pii_returns_empty(self, service):
        records = [{"batch_id": "B001", "quantity": 100}]
        result = service.detect_pii_fields(records)
        assert result == {}

    def test_empty_records_returns_empty(self, service):
        assert service.detect_pii_fields([]) == {}

    def test_none_values_skipped(self, service):
        records = [{"email_field": None, "batch_id": "B001"}]
        result = service.detect_pii_fields(records)
        assert "email_field" not in result

    def test_multiple_pii_types_in_one_field(self, service):
        # A field named operator_name with an email value
        records = [{"operator_name": "user@example.com"}]
        result = service.detect_pii_fields(records)
        assert "NAME" in result["operator_name"]
        assert "EMAIL" in result["operator_name"]

    def test_detects_across_multiple_records(self, service, sample_records):
        result = service.detect_pii_fields(sample_records)
        assert "EMAIL" in result["operator_email"]
        assert "PHONE" in result["phone"]
        assert "SSN" in result["ssn"]
        assert "NAME" in result["operator_name"]


# ---------------------------------------------------------------------------
# Masking Strategies
# ---------------------------------------------------------------------------

class TestApplyMasking:
    """Requirement 10.4: Apply masking to PII fields."""

    def test_hash_masking(self, service, sample_records, pii_fields):
        masked = service.apply_masking(sample_records, pii_fields, "hash")
        expected = hashlib.sha256("John Doe".encode()).hexdigest()
        assert masked[0]["operator_name"] == expected

    def test_redact_masking(self, service, sample_records, pii_fields):
        masked = service.apply_masking(sample_records, pii_fields, "redact")
        assert masked[0]["operator_name"] == "[REDACTED]"
        assert masked[0]["operator_email"] == "[REDACTED]"

    def test_partial_masking(self, service, sample_records, pii_fields):
        masked = service.apply_masking(sample_records, pii_fields, "partial")
        # "John Doe" -> "****" + " Doe" (last 4 chars)
        assert masked[0]["operator_name"].endswith(" Doe")
        assert masked[0]["operator_name"].startswith("*")

    def test_partial_masking_short_value(self, service):
        records = [{"name": "Jo"}]
        pii = {"name": ["NAME"]}
        masked = service.apply_masking(records, pii, "partial")
        assert masked[0]["name"] == "**"

    def test_non_pii_fields_unchanged(self, service, sample_records, pii_fields):
        masked = service.apply_masking(sample_records, pii_fields, "redact")
        assert masked[0]["batch_id"] == "B001"
        assert masked[0]["quantity"] == 100

    def test_invalid_strategy_raises(self, service, sample_records, pii_fields):
        with pytest.raises(ValueError, match="Invalid masking strategy"):
            service.apply_masking(sample_records, pii_fields, "invalid")

    def test_default_strategy_is_hash(self, service, sample_records, pii_fields):
        masked = service.apply_masking(sample_records, pii_fields)
        expected = hashlib.sha256("John Doe".encode()).hexdigest()
        assert masked[0]["operator_name"] == expected

    def test_none_values_not_masked(self, service):
        records = [{"name": None, "batch_id": "B001"}]
        pii = {"name": ["NAME"]}
        masked = service.apply_masking(records, pii, "redact")
        assert masked[0]["name"] is None


# ---------------------------------------------------------------------------
# Original Records Not Modified
# ---------------------------------------------------------------------------

class TestOriginalRecordsUnmodified:
    """Requirement 10.4: Masking must not modify original records."""

    def test_original_records_unchanged_after_hash(self, service, sample_records, pii_fields):
        original_name = sample_records[0]["operator_name"]
        service.apply_masking(sample_records, pii_fields, "hash")
        assert sample_records[0]["operator_name"] == original_name

    def test_original_records_unchanged_after_redact(self, service, sample_records, pii_fields):
        original_email = sample_records[0]["operator_email"]
        service.apply_masking(sample_records, pii_fields, "redact")
        assert sample_records[0]["operator_email"] == original_email

    def test_original_records_unchanged_after_partial(self, service, sample_records, pii_fields):
        original_ssn = sample_records[0]["ssn"]
        service.apply_masking(sample_records, pii_fields, "partial")
        assert sample_records[0]["ssn"] == original_ssn


# ---------------------------------------------------------------------------
# Masking Rules by Classification
# ---------------------------------------------------------------------------

class TestGetMaskingRules:
    """Requirement 10.4: Masking rules based on data classification."""

    def test_public_no_masking(self, service):
        rules = service.get_masking_rules("public")
        assert rules["strategy"] is None
        assert rules["classification"] == "public"

    def test_internal_partial(self, service):
        rules = service.get_masking_rules("internal")
        assert rules["strategy"] == "partial"

    def test_confidential_hash(self, service):
        rules = service.get_masking_rules("confidential")
        assert rules["strategy"] == "hash"

    def test_restricted_redact(self, service):
        rules = service.get_masking_rules("restricted")
        assert rules["strategy"] == "redact"

    def test_unknown_classification_raises(self, service):
        with pytest.raises(ValueError, match="Unknown data classification"):
            service.get_masking_rules("top-secret")

    def test_all_classifications_have_description(self, service):
        for level in ("public", "internal", "confidential", "restricted"):
            rules = service.get_masking_rules(level)
            assert "description" in rules
            assert len(rules["description"]) > 0


# ---------------------------------------------------------------------------
# CMO ID Validation
# ---------------------------------------------------------------------------

class TestCMOIDValidation:
    """Requirement 10.4: CMO ID must start with 'cmo-'."""

    @pytest.mark.parametrize("bad_id", ["", "alpha", "CMO-alpha", "cm-alpha"])
    def test_create_job_rejects_bad_cmo_id(self, service, bad_id):
        with pytest.raises(ValueError, match="Invalid CMO ID"):
            service.create_classification_job(bad_id, S3_BUCKET, S3_PREFIX)
