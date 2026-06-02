"""
Unit Tests for SecureTransferService.

Validates:
- SFTP endpoint provisioning with unique credentials (8.1)
- File format validation (8.3)
- S3 event-driven file processing (8.3)
- S3 event notification configuration (8.3)

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""
import sys
import os
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.secure_transfer_service import (
    SecureTransferService,
    SecureTransferError,
    SFTPProvisioningError,
    FileValidationError,
    FileProcessingError,
    ALLOWED_EXTENSIONS,
    ALLOWED_FILE_PATTERNS,
    MAX_FILE_SIZE_BYTES,
    SFTP_PASSWORD_LENGTH,
    SFTP_HOSTNAME_TEMPLATE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _contract(**overrides):
    """Return a minimal contract for testing."""
    contract = {
        "contractId": "CMO-ALPHA-BATCH-RECORDS-001",
        "cmoId": "cmo-alpha",
        "dataDomain": "batch-records",
        "integrationPattern": "secure-transfer",
        "status": "active",
    }
    contract.update(overrides)
    return contract


def _s3_event(key="bronze/cmo-alpha/batch-records/incoming/data.csv", size=1024, bucket="cmo-data-lake"):
    """Return a minimal S3 event notification."""
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


@pytest.fixture
def service():
    return SecureTransferService()


# ---------------------------------------------------------------------------
# 8.1 — SFTP endpoint provisioning
# ---------------------------------------------------------------------------

class TestProvisionSftpEndpoint:
    """Requirements 6.1, 6.2: Provision SFTP endpoint with unique credentials."""

    def test_returns_hostname(self, service):
        result = service.provision_sftp_endpoint(_contract())
        assert result["sftpConfig"]["hostname"] == SFTP_HOSTNAME_TEMPLATE

    def test_returns_username_with_cmo_prefix(self, service):
        result = service.provision_sftp_endpoint(_contract())
        username = result["sftpConfig"]["username"]
        assert username.startswith("cmo-alpha-batch-records-")

    def test_returns_password(self, service):
        result = service.provision_sftp_endpoint(_contract())
        password = result["sftpConfig"]["password"]
        assert len(password) == SFTP_PASSWORD_LENGTH

    def test_password_has_mixed_characters(self, service):
        result = service.provision_sftp_endpoint(_contract())
        pwd = result["sftpConfig"]["password"]
        assert any(c.isupper() for c in pwd)
        assert any(c.islower() for c in pwd)
        assert any(c.isdigit() for c in pwd)

    def test_unique_usernames_across_calls(self, service):
        r1 = service.provision_sftp_endpoint(_contract())
        r2 = service.provision_sftp_endpoint(_contract())
        assert r1["sftpConfig"]["username"] != r2["sftpConfig"]["username"]

    def test_unique_passwords_across_calls(self, service):
        r1 = service.provision_sftp_endpoint(_contract())
        r2 = service.provision_sftp_endpoint(_contract())
        assert r1["sftpConfig"]["password"] != r2["sftpConfig"]["password"]

    def test_home_directory_follows_pattern(self, service):
        result = service.provision_sftp_endpoint(_contract())
        assert result["sftpConfig"]["homeDirectory"] == "/bronze/cmo-alpha/batch-records/incoming/"

    def test_secret_config_included(self, service):
        result = service.provision_sftp_endpoint(_contract())
        secret = result["secretConfig"]
        assert secret["secretName"] == "cmo/cmo-alpha/sftp-credentials"
        assert "username" in secret["secretValue"]
        assert "password" in secret["secretValue"]

    def test_allowed_file_patterns_included(self, service):
        result = service.provision_sftp_endpoint(_contract())
        assert result["sftpConfig"]["allowedFilePatterns"] == ALLOWED_FILE_PATTERNS

    def test_max_file_size_included(self, service):
        result = service.provision_sftp_endpoint(_contract())
        assert result["sftpConfig"]["maxFileSizeMb"] == 500

    def test_provisioned_at_timestamp(self, service):
        result = service.provision_sftp_endpoint(_contract())
        assert "provisionedAt" in result

    def test_pattern_step_set(self, service):
        result = service.provision_sftp_endpoint(_contract())
        assert result["patternStep"] == "ProvisionSFTP"

    def test_contract_fields_preserved(self, service):
        result = service.provision_sftp_endpoint(_contract())
        assert result["contractId"] == "CMO-ALPHA-BATCH-RECORDS-001"
        assert result["cmoId"] == "cmo-alpha"

    def test_missing_cmo_id_raises(self, service):
        with pytest.raises(SFTPProvisioningError, match="cmoId and dataDomain"):
            service.provision_sftp_endpoint(_contract(cmoId=""))

    def test_missing_data_domain_raises(self, service):
        with pytest.raises(SFTPProvisioningError, match="cmoId and dataDomain"):
            service.provision_sftp_endpoint(_contract(dataDomain=""))

    def test_cloudwatch_metric_published(self):
        mock_cw = MagicMock()
        svc = SecureTransferService(cloudwatch_client=mock_cw)
        svc.provision_sftp_endpoint(_contract())
        mock_cw.put_metric_data.assert_called_once()
        call_args = mock_cw.put_metric_data.call_args
        assert call_args.kwargs["Namespace"] == "CMO/DataPipeline"

    def test_cloudwatch_failure_does_not_raise(self):
        mock_cw = MagicMock()
        mock_cw.put_metric_data.side_effect = Exception("CW unavailable")
        svc = SecureTransferService(cloudwatch_client=mock_cw)
        result = svc.provision_sftp_endpoint(_contract())
        assert "sftpConfig" in result


# ---------------------------------------------------------------------------
# 8.3 — File format validation
# ---------------------------------------------------------------------------

class TestValidateFileFormat:
    """Requirement 6.4: Validate file format against contract schema."""

    def test_csv_is_valid(self, service):
        result = service.validate_file_format("incoming/data.csv", _contract())
        assert result["valid"] is True
        assert result["extension"] == ".csv"

    def test_parquet_is_valid(self, service):
        result = service.validate_file_format("incoming/data.parquet", _contract())
        assert result["valid"] is True
        assert result["extension"] == ".parquet"

    def test_json_is_valid(self, service):
        result = service.validate_file_format("incoming/data.json", _contract())
        assert result["valid"] is True

    def test_uppercase_extension_is_valid(self, service):
        result = service.validate_file_format("incoming/data.CSV", _contract())
        assert result["valid"] is True

    def test_invalid_extension_raises(self, service):
        with pytest.raises(FileValidationError, match="not allowed"):
            service.validate_file_format("incoming/data.xlsx", _contract())

    def test_no_extension_raises(self, service):
        with pytest.raises(FileValidationError, match="not allowed"):
            service.validate_file_format("incoming/datafile", _contract())

    def test_exe_extension_raises(self, service):
        with pytest.raises(FileValidationError, match="not allowed"):
            service.validate_file_format("incoming/malware.exe", _contract())


# ---------------------------------------------------------------------------
# 8.3 — S3 event-driven file processing
# ---------------------------------------------------------------------------

class TestProcessUploadedFile:
    """Requirements 6.3, 6.5, 6.6: Detect, validate, move to Bronze, archive."""

    def test_successful_processing(self, service):
        result = service.process_uploaded_file(
            _s3_event("bronze/cmo-alpha/batch-records/incoming/data.csv", 1024),
            _contract(),
        )
        assert result["status"] == "processed"
        assert result["contractId"] == "CMO-ALPHA-BATCH-RECORDS-001"

    def test_bronze_path_generated(self, service):
        result = service.process_uploaded_file(
            _s3_event("incoming/data.csv", 512),
            _contract(),
        )
        assert "bronzePath" in result
        assert "bronze/cmo-alpha/batch-records/" in result["bronzePath"]

    def test_bronze_key_has_date_partitioning(self, service):
        result = service.process_uploaded_file(
            _s3_event("incoming/data.csv", 512),
            _contract(),
        )
        key = result["bronzeKey"]
        assert "year=" in key
        assert "month=" in key
        assert "day=" in key

    def test_archive_key_generated(self, service):
        result = service.process_uploaded_file(
            _s3_event("incoming/data.csv", 512),
            _contract(),
        )
        assert "archive" in result["archiveKey"]
        assert "data.csv" in result["archiveKey"]

    def test_file_size_recorded(self, service):
        result = service.process_uploaded_file(
            _s3_event("incoming/data.csv", 2048),
            _contract(),
        )
        assert result["fileSize"] == 2048

    def test_processed_at_timestamp(self, service):
        result = service.process_uploaded_file(
            _s3_event("incoming/data.csv", 512),
            _contract(),
        )
        assert "processedAt" in result

    def test_invalid_extension_raises(self, service):
        with pytest.raises(FileValidationError, match="not allowed"):
            service.process_uploaded_file(
                _s3_event("incoming/data.xlsx", 512),
                _contract(),
            )

    def test_oversized_file_raises(self, service):
        over_limit = MAX_FILE_SIZE_BYTES + 1
        with pytest.raises(FileValidationError, match="exceeds maximum"):
            service.process_uploaded_file(
                _s3_event("incoming/data.csv", over_limit),
                _contract(),
            )

    def test_file_at_max_size_succeeds(self, service):
        result = service.process_uploaded_file(
            _s3_event("incoming/data.csv", MAX_FILE_SIZE_BYTES),
            _contract(),
        )
        assert result["status"] == "processed"

    def test_missing_file_key_raises(self, service):
        event = {"Records": [{"s3": {"bucket": {"name": "b"}, "object": {"key": "", "size": 0}}}]}
        with pytest.raises(FileProcessingError, match="No file key"):
            service.process_uploaded_file(event, _contract())

    def test_missing_cmo_id_raises(self, service):
        with pytest.raises(FileProcessingError, match="cmoId and dataDomain"):
            service.process_uploaded_file(
                _s3_event("incoming/data.csv", 512),
                _contract(cmoId=""),
            )

    def test_source_bucket_from_event(self, service):
        result = service.process_uploaded_file(
            _s3_event("incoming/data.csv", 512, bucket="custom-bucket"),
            _contract(),
        )
        assert result["sourceBucket"] == "custom-bucket"

    def test_cloudwatch_metric_published(self):
        mock_cw = MagicMock()
        svc = SecureTransferService(cloudwatch_client=mock_cw)
        svc.process_uploaded_file(
            _s3_event("incoming/data.csv", 512),
            _contract(),
        )
        mock_cw.put_metric_data.assert_called_once()


# ---------------------------------------------------------------------------
# 8.3 — S3 event notification configuration
# ---------------------------------------------------------------------------

class TestBuildS3EventConfig:
    """Requirement 6.3: Configure S3 event notifications for new uploads."""

    def test_config_has_bucket_name(self, service):
        result = service.build_s3_event_config(_contract(), "my-bucket")
        assert result["bucketName"] == "my-bucket"

    def test_config_has_prefix(self, service):
        result = service.build_s3_event_config(_contract(), "my-bucket")
        assert result["prefix"] == "bronze/cmo-alpha/batch-records/incoming/"

    def test_config_has_lambda_configuration(self, service):
        result = service.build_s3_event_config(_contract(), "my-bucket")
        configs = result["notificationConfig"]["LambdaFunctionConfigurations"]
        assert len(configs) == 1
        assert configs[0]["Events"] == ["s3:ObjectCreated:*"]

    def test_config_has_filter_rules(self, service):
        result = service.build_s3_event_config(_contract(), "my-bucket")
        configs = result["notificationConfig"]["LambdaFunctionConfigurations"]
        filter_rules = configs[0]["Filter"]["Key"]["FilterRules"]
        assert any(r["Name"] == "prefix" for r in filter_rules)

    def test_suffix_rules_for_allowed_extensions(self, service):
        result = service.build_s3_event_config(_contract(), "my-bucket")
        suffixes = {r["Value"] for r in result["suffixRules"]}
        assert suffixes == ALLOWED_EXTENSIONS

    def test_missing_cmo_id_raises(self, service):
        with pytest.raises(SFTPProvisioningError, match="cmoId and dataDomain"):
            service.build_s3_event_config(_contract(cmoId=""), "my-bucket")

    def test_contract_id_included(self, service):
        result = service.build_s3_event_config(_contract(), "my-bucket")
        assert result["contractId"] == "CMO-ALPHA-BATCH-RECORDS-001"


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class TestExceptionHierarchy:
    def test_sftp_provisioning_error_is_secure_transfer_error(self):
        assert issubclass(SFTPProvisioningError, SecureTransferError)

    def test_file_validation_error_is_secure_transfer_error(self):
        assert issubclass(FileValidationError, SecureTransferError)

    def test_file_processing_error_is_secure_transfer_error(self):
        assert issubclass(FileProcessingError, SecureTransferError)

    def test_error_includes_step_and_contract_id(self):
        err = SFTPProvisioningError("bad", step="ProvisionSFTP", contract_id="CMO-001")
        assert err.step == "ProvisionSFTP"
        assert err.contract_id == "CMO-001"
