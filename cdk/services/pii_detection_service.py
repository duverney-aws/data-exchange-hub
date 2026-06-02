"""
PII Detection and Masking Service for Pharma Data Exchange Hub

Uses Amazon Macie for classification jobs on Silver layer data and
provides local regex-based PII detection for real-time use. Applies
masking strategies (hash, redact, partial) based on data classification.

Requirements: 10.4
"""
import boto3
import copy
import hashlib
import re
import time
from typing import Optional


class PIIDetectionService:
    """Service for detecting and masking PII in CMO data."""

    # Regex patterns for common PII types
    EMAIL_PATTERN = re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE
    )
    PHONE_PATTERN = re.compile(
        r"(?:\+?1[\s\-]?)?"
        r"(?:\(\d{3}\)|\d{3})[\s\-]?"
        r"\d{3}[\s\-]?\d{4}"
    )
    SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

    # Field-name heuristics for name-like PII
    NAME_FIELD_SUFFIXES = ("_name", "_contact", "_person")

    MASKING_STRATEGIES = ("hash", "redact", "partial")

    CLASSIFICATION_MASKING_MAP = {
        "public": None,
        "internal": "partial",
        "confidential": "hash",
        "restricted": "redact",
    }

    def __init__(self, macie_client=None, region: str = "us-east-1"):
        self.macie = macie_client or boto3.client("macie2", region_name=region)
        self.region = region

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_cmo_id(cmo_id: str) -> None:
        if not cmo_id or not cmo_id.startswith("cmo-"):
            raise ValueError(
                f"Invalid CMO ID format: {cmo_id}. Must start with 'cmo-'"
            )

    # ------------------------------------------------------------------
    # Macie Classification Jobs
    # ------------------------------------------------------------------

    def create_classification_job(
        self,
        cmo_id: str,
        s3_bucket_name: str,
        s3_prefix: str,
    ) -> dict:
        """
        Create a Macie classification job for a CMO's Silver layer data.

        Args:
            cmo_id: CMO identifier (must start with 'cmo-')
            s3_bucket_name: Name of the S3 bucket to scan
            s3_prefix: S3 key prefix to scope the scan

        Returns:
            dict with job_id, job_name, status
        """
        self._validate_cmo_id(cmo_id)

        timestamp = int(time.time())
        job_name = f"pii-scan-{cmo_id}-{timestamp}"

        response = self.macie.create_classification_job(
            jobType="ONE_TIME",
            name=job_name,
            description=f"PII scan for {cmo_id} Silver layer data",
            s3JobDefinition={
                "bucketDefinitions": [
                    {
                        "accountId": self._get_account_id(),
                        "buckets": [s3_bucket_name],
                    }
                ],
                "scoping": {
                    "includes": {
                        "and": [
                            {
                                "simpleScopeTerm": {
                                    "key": "OBJECT_KEY",
                                    "comparator": "STARTS_WITH",
                                    "values": [s3_prefix],
                                }
                            }
                        ]
                    }
                },
            },
            tags={"cmo-id": cmo_id, "managed-by": "pharma-data-exchange-hub"},
        )

        return {
            "job_id": response["jobId"],
            "job_name": job_name,
            "status": "RUNNING",
        }

    def get_classification_results(self, job_id: str) -> list:
        """
        Get findings from a completed Macie classification job.

        Args:
            job_id: Macie classification job ID

        Returns:
            list of dicts with field_name, pii_type, severity
        """
        response = self.macie.list_findings(
            findingCriteria={
                "criterion": {
                    "classificationDetails.jobId": {
                        "eq": [job_id],
                    }
                }
            }
        )

        finding_ids = response.get("findingIds", [])
        if not finding_ids:
            return []

        findings_response = self.macie.get_findings(findingIds=finding_ids)
        results = []

        for finding in findings_response.get("findings", []):
            sensitive_data = (
                finding.get("classificationDetails", {})
                .get("result", {})
                .get("sensitiveData", [])
            )
            for data_group in sensitive_data:
                category = data_group.get("category", "UNKNOWN")
                for detection in data_group.get("detections", []):
                    results.append(
                        {
                            "field_name": detection.get("name", "unknown"),
                            "pii_type": category,
                            "severity": finding.get("severity", {}).get(
                                "description", "Medium"
                            ),
                            "count": detection.get("count", 0),
                        }
                    )

        return results

    # ------------------------------------------------------------------
    # Local PII Detection (regex-based, real-time)
    # ------------------------------------------------------------------

    def detect_pii_fields(self, data_records: list[dict]) -> dict:
        """
        Detect PII fields in data records using regex patterns.

        Scans field values for email addresses, phone numbers, and SSN
        patterns. Also flags fields whose names match name-like heuristics.

        Args:
            data_records: list of dicts representing data rows

        Returns:
            dict mapping field names to set of detected PII types
        """
        if not data_records:
            return {}

        pii_fields: dict[str, set] = {}

        for record in data_records:
            for field_name, value in record.items():
                # Name heuristic based on field name
                lower_name = field_name.lower()
                if any(lower_name.endswith(s) for s in self.NAME_FIELD_SUFFIXES):
                    pii_fields.setdefault(field_name, set()).add("NAME")

                # Value-based detection
                if value is None:
                    continue
                str_value = str(value)

                if self.EMAIL_PATTERN.search(str_value):
                    pii_fields.setdefault(field_name, set()).add("EMAIL")

                if self.PHONE_PATTERN.search(str_value):
                    pii_fields.setdefault(field_name, set()).add("PHONE")

                if self.SSN_PATTERN.search(str_value):
                    pii_fields.setdefault(field_name, set()).add("SSN")

        # Convert sets to sorted lists for deterministic output
        return {k: sorted(v) for k, v in pii_fields.items()}

    # ------------------------------------------------------------------
    # Masking
    # ------------------------------------------------------------------

    def apply_masking(
        self,
        records: list[dict],
        pii_fields: dict,
        masking_strategy: str = "hash",
    ) -> list[dict]:
        """
        Apply masking to PII fields in data records.

        Strategies:
            - "hash": SHA-256 hex digest of the value
            - "redact": Replace with "[REDACTED]"
            - "partial": Show only last 4 characters

        Args:
            records: list of dicts representing data rows
            pii_fields: dict mapping field names to PII types
            masking_strategy: one of "hash", "redact", "partial"

        Returns:
            New list of records with PII fields masked (originals unchanged)
        """
        if masking_strategy not in self.MASKING_STRATEGIES:
            raise ValueError(
                f"Invalid masking strategy: {masking_strategy}. "
                f"Must be one of {self.MASKING_STRATEGIES}"
            )

        masked_records = []
        for record in records:
            new_record = copy.deepcopy(record)
            for field_name in pii_fields:
                if field_name in new_record and new_record[field_name] is not None:
                    new_record[field_name] = self._mask_value(
                        str(new_record[field_name]), masking_strategy
                    )
            masked_records.append(new_record)

        return masked_records

    # ------------------------------------------------------------------
    # Masking Rules by Classification
    # ------------------------------------------------------------------

    def get_masking_rules(self, data_classification: str) -> dict:
        """
        Return masking rules based on data classification level.

        Classification levels:
            - "public"       -> no masking
            - "internal"     -> partial masking
            - "confidential" -> hash masking
            - "restricted"   -> full redaction

        Args:
            data_classification: one of public/internal/confidential/restricted

        Returns:
            dict with classification, strategy (or None), and description
        """
        strategy = self.CLASSIFICATION_MASKING_MAP.get(data_classification)

        if data_classification not in self.CLASSIFICATION_MASKING_MAP:
            raise ValueError(
                f"Unknown data classification: {data_classification}. "
                f"Must be one of {list(self.CLASSIFICATION_MASKING_MAP.keys())}"
            )

        descriptions = {
            None: "No masking required for public data",
            "partial": "Show only last 4 characters of PII fields",
            "hash": "SHA-256 hash of PII field values",
            "redact": "Full redaction — replace PII with [REDACTED]",
        }

        return {
            "classification": data_classification,
            "strategy": strategy,
            "description": descriptions[strategy],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mask_value(value: str, strategy: str) -> str:
        if strategy == "hash":
            return hashlib.sha256(value.encode("utf-8")).hexdigest()
        elif strategy == "redact":
            return "[REDACTED]"
        elif strategy == "partial":
            if len(value) <= 4:
                return "*" * len(value)
            return "*" * (len(value) - 4) + value[-4:]
        return value

    def _get_account_id(self) -> str:
        try:
            sts = boto3.client("sts", region_name=self.region)
            return sts.get_caller_identity()["Account"]
        except Exception:
            return ""
