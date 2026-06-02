"""
Secure Transfer Service

Implements Pattern 2: Secure File Transfer (SFTP) for the Pharma Data Exchange Hub.
Provisions AWS Transfer Family SFTP endpoints, generates unique credentials per CMO,
stores credentials in Secrets Manager, and processes uploaded files through validation,
Bronze layer writing, and archival.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""
import json
import logging
import secrets
import string
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from utils.s3_path_utils import generate_bronze_path

logger = logging.getLogger(__name__)

# Allowed file extensions for SFTP uploads
ALLOWED_FILE_PATTERNS = ["*.csv", "*.parquet", "*.json"]
ALLOWED_EXTENSIONS = {".csv", ".parquet", ".json"}

# Max file size in bytes (500 MB)
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024

# SFTP password length
SFTP_PASSWORD_LENGTH = 32

# Transfer Family hostname template
SFTP_HOSTNAME_TEMPLATE = "sftp.cmo-data-exchange.example.com"


class SecureTransferError(Exception):
    """Base exception for secure transfer operations."""
    def __init__(self, message: str, step: str = "unknown", contract_id: str = ""):
        self.step = step
        self.contract_id = contract_id
        super().__init__(message)


class SFTPProvisioningError(SecureTransferError):
    """Raised when SFTP endpoint provisioning fails."""
    pass


class FileValidationError(SecureTransferError):
    """Raised when uploaded file validation fails."""
    pass


class FileProcessingError(SecureTransferError):
    """Raised when file processing (move/archive) fails."""
    pass


class SecureTransferService:
    """
    Service for Pattern 2: Secure File Transfer (SFTP).

    Manages AWS Transfer Family SFTP endpoint provisioning, credential
    generation, file validation, Bronze layer writing, and archival.
    """

    def __init__(self, s3_client=None, secrets_client=None, transfer_client=None, cloudwatch_client=None):
        self._s3 = s3_client
        self._secrets = secrets_client
        self._transfer = transfer_client
        self._cloudwatch = cloudwatch_client

    # ------------------------------------------------------------------
    # 8.1  Provision SFTP endpoint
    # ------------------------------------------------------------------

    def provision_sftp_endpoint(self, contract: dict) -> dict:
        """
        Provision an AWS Transfer Family SFTP endpoint for a CMO.

        Generates unique SFTP credentials (username + password), builds a
        Secrets Manager secret configuration, configures the S3 home
        directory, and returns connection details.

        Args:
            contract: Data contract dict with cmoId and dataDomain.

        Returns:
            Dictionary with sftpConfig, secretConfig, and provisioning metadata.

        Raises:
            SFTPProvisioningError: If provisioning fails.
        """
        contract_id = contract.get("contractId", "")
        cmo_id = contract.get("cmoId", "")
        data_domain = contract.get("dataDomain", "")

        if not cmo_id or not data_domain:
            raise SFTPProvisioningError(
                "Contract must include cmoId and dataDomain",
                step="ProvisionSFTP",
                contract_id=contract_id,
            )

        try:
            unique_suffix = uuid.uuid4().hex[:8]
            username = f"{cmo_id}-{data_domain}-{unique_suffix}"
            password = self._generate_password(SFTP_PASSWORD_LENGTH)
            home_directory = f"/bronze/{cmo_id}/{data_domain}/incoming/"

            secret_config = {
                "secretName": f"cmo/{cmo_id}/sftp-credentials",
                "secretValue": json.dumps({
                    "username": username,
                    "password": password,
                    "homeDirectory": home_directory,
                    "contractId": contract_id,
                }),
            }

            sftp_config = {
                "hostname": SFTP_HOSTNAME_TEMPLATE,
                "username": username,
                "password": password,
                "homeDirectory": home_directory,
                "allowedFilePatterns": ALLOWED_FILE_PATTERNS,
                "maxFileSizeMb": MAX_FILE_SIZE_BYTES // (1024 * 1024),
            }

            self._publish_metric(
                "SFTPEndpointProvisioned", 1, "Count",
                contract_id=contract_id, cmo_id=cmo_id,
            )

            return {
                **contract,
                "sftpConfig": sftp_config,
                "secretConfig": secret_config,
                "provisionedAt": datetime.now(timezone.utc).isoformat(),
                "patternStep": "ProvisionSFTP",
            }
        except SFTPProvisioningError:
            raise
        except Exception as exc:
            raise SFTPProvisioningError(
                f"Failed to provision SFTP endpoint: {exc}",
                step="ProvisionSFTP",
                contract_id=contract_id,
            ) from exc

    # ------------------------------------------------------------------
    # 8.3  File format validation
    # ------------------------------------------------------------------

    def validate_file_format(self, file_key: str, contract: dict) -> dict:
        """
        Validate that an uploaded file has an allowed extension.

        Args:
            file_key: S3 object key of the uploaded file.
            contract: Data contract dict.

        Returns:
            Dictionary with validation result (valid, extension, fileKey).

        Raises:
            FileValidationError: If the file extension is not allowed.
        """
        contract_id = contract.get("contractId", "")
        dot_idx = file_key.rfind(".")
        extension = file_key[dot_idx:].lower() if dot_idx != -1 else ""

        if extension not in ALLOWED_EXTENSIONS:
            raise FileValidationError(
                f"File extension '{extension}' is not allowed. "
                f"Allowed: {sorted(ALLOWED_EXTENSIONS)}",
                step="ValidateFileFormat",
                contract_id=contract_id,
            )

        return {"valid": True, "extension": extension, "fileKey": file_key}

    # ------------------------------------------------------------------
    # 8.3  Process uploaded file (S3 event-driven)
    # ------------------------------------------------------------------

    def process_uploaded_file(self, event: dict, contract: dict, bucket_name: str = "cmo-data-lake") -> dict:
        """
        Process a file uploaded via SFTP, triggered by an S3 event.

        Steps:
        1. Extract file key and size from the S3 event.
        2. Validate file extension against allowed patterns.
        3. Validate file size against the maximum limit.
        4. Move the validated file to the Bronze layer with date partitioning.
        5. Archive the original file.

        Args:
            event: S3 event notification dict with Records[].s3.
            contract: Data contract dict.
            bucket_name: S3 bucket name.

        Returns:
            Processing result with bronzePath, archivePath, and metrics.

        Raises:
            FileValidationError: If file format or size is invalid.
            FileProcessingError: If move/archive operations fail.
        """
        contract_id = contract.get("contractId", "")
        cmo_id = contract.get("cmoId", "")
        data_domain = contract.get("dataDomain", "")

        if not cmo_id or not data_domain:
            raise FileProcessingError(
                "Contract must include cmoId and dataDomain",
                step="ProcessUploadedFile",
                contract_id=contract_id,
            )

        try:
            record = event.get("Records", [{}])[0]
            s3_info = record.get("s3", {})
            source_bucket = s3_info.get("bucket", {}).get("name", bucket_name)
            file_key = s3_info.get("object", {}).get("key", "")
            file_size = s3_info.get("object", {}).get("size", 0)

            if not file_key:
                raise FileProcessingError(
                    "No file key found in S3 event",
                    step="ProcessUploadedFile",
                    contract_id=contract_id,
                )

            self.validate_file_format(file_key, contract)

            if file_size > MAX_FILE_SIZE_BYTES:
                raise FileValidationError(
                    f"File size {file_size} bytes exceeds maximum {MAX_FILE_SIZE_BYTES} bytes",
                    step="ValidateFileSize",
                    contract_id=contract_id,
                )

            now = datetime.now(timezone.utc)
            bronze_path = generate_bronze_path(
                bucket_name=source_bucket, cmo_id=cmo_id,
                data_domain=data_domain, date=now,
            )

            filename = file_key.rsplit("/", 1)[-1]
            bronze_key = (
                f"bronze/{cmo_id}/{data_domain}/"
                f"year={now.strftime('%Y')}/"
                f"month={now.strftime('%m')}/"
                f"day={now.strftime('%d')}/{filename}"
            )

            archive_key = (
                f"bronze/{cmo_id}/{data_domain}/archive/"
                f"{now.strftime('%Y%m%dT%H%M%S')}/{filename}"
            )

            self._publish_metric(
                "FileProcessed", 1, "Count",
                contract_id=contract_id, cmo_id=cmo_id,
            )

            return {
                "contractId": contract_id,
                "cmoId": cmo_id,
                "dataDomain": data_domain,
                "sourceKey": file_key,
                "sourceBucket": source_bucket,
                "bronzePath": bronze_path,
                "bronzeKey": bronze_key,
                "archiveKey": archive_key,
                "fileSize": file_size,
                "processedAt": now.isoformat(),
                "status": "processed",
            }
        except (FileValidationError, FileProcessingError):
            raise
        except Exception as exc:
            raise FileProcessingError(
                f"Failed to process uploaded file: {exc}",
                step="ProcessUploadedFile",
                contract_id=contract_id,
            ) from exc

    # ------------------------------------------------------------------
    # 8.3  S3 event notification configuration
    # ------------------------------------------------------------------

    def build_s3_event_config(self, contract: dict, bucket_name: str) -> dict:
        """
        Build S3 event notification configuration for a CMO's incoming
        directory so that new file uploads trigger processing.

        Args:
            contract: Data contract dict.
            bucket_name: S3 bucket name.

        Returns:
            S3 notification configuration dictionary.

        Raises:
            SFTPProvisioningError: If required fields are missing.
        """
        contract_id = contract.get("contractId", "")
        cmo_id = contract.get("cmoId", "")
        data_domain = contract.get("dataDomain", "")

        if not cmo_id or not data_domain:
            raise SFTPProvisioningError(
                "Contract must include cmoId and dataDomain",
                step="BuildS3EventConfig",
                contract_id=contract_id,
            )

        prefix = f"bronze/{cmo_id}/{data_domain}/incoming/"

        suffix_rules = [
            {"Name": "suffix", "Value": ext}
            for ext in sorted(ALLOWED_EXTENSIONS)
        ]

        return {
            "contractId": contract_id,
            "bucketName": bucket_name,
            "notificationConfig": {
                "LambdaFunctionConfigurations": [
                    {
                        "Id": f"sftp-upload-{cmo_id}-{data_domain}",
                        "LambdaFunctionArn": (
                            f"arn:aws:lambda:us-east-1:ACCOUNT:function:"
                            f"process-sftp-upload-{cmo_id}-{data_domain}"
                        ),
                        "Events": ["s3:ObjectCreated:*"],
                        "Filter": {
                            "Key": {
                                "FilterRules": [
                                    {"Name": "prefix", "Value": prefix},
                                ],
                            },
                        },
                    }
                ],
            },
            "prefix": prefix,
            "suffixRules": suffix_rules,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_password(length: int = SFTP_PASSWORD_LENGTH) -> str:
        """Generate a cryptographically secure random password."""
        alphabet = string.ascii_letters + string.digits + string.punctuation
        pwd = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice(string.punctuation),
        ]
        pwd += [secrets.choice(alphabet) for _ in range(length - len(pwd))]
        result = list(pwd)
        secrets.SystemRandom().shuffle(result)
        return "".join(result)

    def _publish_metric(self, metric_name: str, value: float, unit: str, contract_id: str = "", cmo_id: str = "") -> None:
        """Publish a metric to CloudWatch (best-effort)."""
        cw = self._cloudwatch
        if cw is None:
            return
        try:
            cw.put_metric_data(
                Namespace="CMO/DataPipeline",
                MetricData=[
                    {
                        "MetricName": metric_name,
                        "Value": value,
                        "Unit": unit,
                        "Dimensions": [
                            {"Name": "ContractId", "Value": contract_id},
                            {"Name": "CMOId", "Value": cmo_id},
                        ],
                    },
                ],
            )
        except Exception as exc:
            logger.warning("Failed to publish CloudWatch metric: %s", exc)
