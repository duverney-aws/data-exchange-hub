"""
Pipeline Orchestration Service

Core business logic for pipeline deployment orchestration via Step Functions.
Validates contracts, determines integration patterns, configures pattern-specific
resources, creates ETL job definitions, and handles errors with retry logic.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.8, 15.1, 15.2
"""
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Supported integration patterns
VALID_PATTERNS = {"native-connector", "secure-transfer", "ai-unstructured"}

# Pattern 1: Supported native connector types
NATIVE_CONNECTOR_TYPES = {
    "snowflake", "oracle", "sqlserver", "postgresql", "sap", "databricks",
}

# Pattern 3: Supported AI document types
AI_DOCUMENT_TYPES = {"pdf", "png", "jpg", "tiff"}

# Retry configuration
MAX_RETRY_ATTEMPTS = 3
INITIAL_BACKOFF_SECONDS = 1


class PipelineOrchestrationError(Exception):
    """Base exception for pipeline orchestration failures."""

    def __init__(self, message: str, step: str = "unknown", contract_id: str = ""):
        self.step = step
        self.contract_id = contract_id
        super().__init__(message)


class ContractValidationError(PipelineOrchestrationError):
    """Raised when contract validation fails before deployment."""
    pass


class PatternConfigurationError(PipelineOrchestrationError):
    """Raised when pattern-specific configuration fails."""
    pass


class ETLJobCreationError(PipelineOrchestrationError):
    """Raised when ETL job creation fails."""
    pass


class PipelineOrchestrationService:
    """
    Orchestrates pipeline deployment from data contracts.

    Each public method corresponds to a Step Functions workflow state.
    """

    def validate_contract(self, contract: dict) -> dict:
        """
        Validate that a contract is ready for pipeline deployment.

        Checks:
        - Contract has 'active' status
        - Required fields are present (contractId, cmoId, dataDomain, integrationPattern)
        - Integration pattern is valid

        Args:
            contract: Data contract dictionary.

        Returns:
            Enriched contract dict with validation metadata.

        Raises:
            ContractValidationError: If the contract is not deployable.
        """
        contract_id = contract.get("contractId", "")
        errors: List[str] = []

        # Required fields
        required = ["contractId", "cmoId", "dataDomain", "integrationPattern"]
        for field in required:
            if not contract.get(field):
                errors.append(f"Missing required field: {field}")

        if errors:
            raise ContractValidationError(
                f"Contract validation failed: {'; '.join(errors)}",
                step="ValidateContract",
                contract_id=contract_id,
            )

        # Status check
        status = contract.get("status", "draft")
        if status != "active":
            raise ContractValidationError(
                f"Contract must be 'active' to deploy, current status: '{status}'",
                step="ValidateContract",
                contract_id=contract_id,
            )

        # Pattern check
        pattern = contract["integrationPattern"]
        if pattern not in VALID_PATTERNS:
            raise ContractValidationError(
                f"Invalid integration pattern '{pattern}'. Must be one of {sorted(VALID_PATTERNS)}",
                step="ValidateContract",
                contract_id=contract_id,
            )

        return {
            **contract,
            "validatedAt": datetime.now(timezone.utc).isoformat(),
            "deploymentId": str(uuid.uuid4()),
        }

    def determine_pattern(self, contract: dict) -> str:
        """
        Determine the integration pattern from the contract.

        Args:
            contract: Validated contract dictionary.

        Returns:
            Integration pattern string.
        """
        return contract["integrationPattern"]

    # ------------------------------------------------------------------
    # Pattern-specific configuration (Subtask 5.3)
    # ------------------------------------------------------------------

    def configure_glue_connector(self, contract: dict) -> dict:
        """
        Configure AWS Glue native/JDBC connector for Pattern 1.

        Generates connector configuration for supported platforms:
        Snowflake, Oracle, SQL Server, PostgreSQL, SAP, Databricks.

        Args:
            contract: Validated contract with connectionConfig.

        Returns:
            Connector configuration dictionary.

        Raises:
            PatternConfigurationError: If connection type is unsupported.
        """
        contract_id = contract.get("contractId", "")
        conn_config = contract.get("connectionConfig", {})
        connection_type = conn_config.get("connectionType", "").lower()

        if connection_type not in NATIVE_CONNECTOR_TYPES:
            raise PatternConfigurationError(
                f"Unsupported connection type '{connection_type}'. "
                f"Supported: {sorted(NATIVE_CONNECTOR_TYPES)}",
                step="ConfigureGlueConnector",
                contract_id=contract_id,
            )

        cmo_id = contract["cmoId"]
        data_domain = contract["dataDomain"]
        connector_name = f"{cmo_id}-{data_domain}-{connection_type}"

        # Build Glue connection properties
        connection_properties = {
            "connectionName": connector_name,
            "connectionType": self._map_connection_type(connection_type),
            "secretId": f"cmo/{cmo_id}/credentials",
            "database": conn_config.get("database", ""),
            "schema": conn_config.get("schema", ""),
        }

        if connection_type in ("snowflake", "databricks"):
            connection_properties["connectionType"] = connection_type.upper()
        else:
            connection_properties["connectionUrl"] = conn_config.get("connectionUrl", "")

        return {
            **contract,
            "connectorConfig": connection_properties,
            "configuredAt": datetime.now(timezone.utc).isoformat(),
            "patternStep": "ConfigureGlueConnector",
        }

    def provision_sftp(self, contract: dict) -> dict:
        """
        Provision AWS Transfer Family SFTP endpoint for Pattern 2.

        Generates SFTP configuration with CMO-specific credentials.

        Args:
            contract: Validated contract dictionary.

        Returns:
            SFTP configuration dictionary.

        Raises:
            PatternConfigurationError: On configuration failure.
        """
        contract_id = contract.get("contractId", "")
        cmo_id = contract["cmoId"]
        data_domain = contract["dataDomain"]

        try:
            sftp_config = {
                "sftpUsername": f"{cmo_id}-{data_domain}-user",
                "homeDirectory": f"/bronze/{cmo_id}/{data_domain}/incoming/",
                "secretId": f"cmo/{cmo_id}/sftp-credentials",
                "allowedFilePatterns": ["*.csv", "*.parquet", "*.json"],
                "maxFileSizeMb": 500,
            }

            return {
                **contract,
                "sftpConfig": sftp_config,
                "configuredAt": datetime.now(timezone.utc).isoformat(),
                "patternStep": "ProvisionSFTP",
            }
        except Exception as exc:
            raise PatternConfigurationError(
                f"Failed to provision SFTP: {exc}",
                step="ProvisionSFTP",
                contract_id=contract_id,
            ) from exc

    def configure_ai_processing(self, contract: dict) -> dict:
        """
        Configure Amazon Textract and Rekognition for Pattern 3.

        Args:
            contract: Validated contract dictionary.

        Returns:
            AI processing configuration dictionary.

        Raises:
            PatternConfigurationError: On configuration failure.
        """
        contract_id = contract.get("contractId", "")
        cmo_id = contract["cmoId"]
        data_domain = contract["dataDomain"]
        ai_config_input = contract.get("aiConfig", {})

        try:
            ai_config = {
                "documentTypes": ai_config_input.get(
                    "documentTypes", ["pdf", "png", "jpg"]
                ),
                "extractionFeatures": ai_config_input.get(
                    "extractionFeatures", ["TABLES", "FORMS"]
                ),
                "confidenceThreshold": ai_config_input.get(
                    "confidenceThreshold", 0.85
                ),
                "manualReviewThreshold": ai_config_input.get(
                    "manualReviewThreshold", 0.70
                ),
                "outputFormat": "json",
                "inputPath": f"s3://incoming/{cmo_id}/{data_domain}/documents/",
                "outputPath": f"s3://incoming/{cmo_id}/{data_domain}/extracted/",
            }

            return {
                **contract,
                "aiProcessingConfig": ai_config,
                "configuredAt": datetime.now(timezone.utc).isoformat(),
                "patternStep": "ConfigureAIProcessing",
            }
        except Exception as exc:
            raise PatternConfigurationError(
                f"Failed to configure AI processing: {exc}",
                step="ConfigureAIProcessing",
                contract_id=contract_id,
            ) from exc

    # ------------------------------------------------------------------
    # ETL job creation (Subtask 5.4)
    # ------------------------------------------------------------------

    def create_etl_job(
        self, contract: dict, bucket_name: str = "cmo-data-lake"
    ) -> dict:
        """
        Generate a Glue ETL job definition from a contract.

        Configures S3 paths following: s3://bucket/{layer}/{cmo-id}/{data-domain}/

        Args:
            contract: Validated and pattern-configured contract.
            bucket_name: Data lake S3 bucket name.

        Returns:
            Contract enriched with ETL job definition.

        Raises:
            ETLJobCreationError: If job definition cannot be generated.
        """
        contract_id = contract.get("contractId", "")
        cmo_id = contract.get("cmoId", "")
        data_domain = contract.get("dataDomain", "")

        if not cmo_id or not data_domain:
            raise ETLJobCreationError(
                "Cannot create ETL job: missing cmoId or dataDomain",
                step="CreateETLJob",
                contract_id=contract_id,
            )

        job_name = f"etl-{cmo_id}-{data_domain}"

        # S3 paths following the required pattern
        s3_paths = {
            "bronze": f"s3://{bucket_name}/bronze/{cmo_id}/{data_domain}/",
            "silver": f"s3://{bucket_name}/silver/{cmo_id}/{data_domain}/",
            "gold": f"s3://{bucket_name}/gold/{cmo_id}/{data_domain}/",
            "quarantine": f"s3://{bucket_name}/bronze/quarantine/{contract_id}/",
        }

        # Build quality ruleset from contract
        quality_rules = contract.get("qualityRules", [])
        dqdl_expressions = [
            rule["expression"]
            for rule in quality_rules
            if isinstance(rule, dict) and "expression" in rule
        ]

        etl_job_definition = {
            "jobName": job_name,
            "contractId": contract_id,
            "cmoId": cmo_id,
            "dataDomain": data_domain,
            "s3Paths": s3_paths,
            "glueJobConfig": {
                "role": f"arn:aws:iam::role/glue-etl-{cmo_id}",
                "command": {
                    "name": "glueetl",
                    "scriptLocation": f"s3://{bucket_name}/scripts/{job_name}.py",
                    "pythonVersion": "3",
                },
                "defaultArguments": {
                    "--job-language": "python",
                    "--enable-metrics": "true",
                    "--enable-continuous-cloudwatch-log": "true",
                    "--contract-id": contract_id,
                    "--source-path": s3_paths["bronze"],
                    "--target-path": s3_paths["silver"],
                    "--quarantine-path": s3_paths["quarantine"],
                },
                "maxRetries": MAX_RETRY_ATTEMPTS,
                "workerType": "G.1X",
                "numberOfWorkers": 2,
            },
            "qualityRuleset": dqdl_expressions,
            "schedule": contract.get("deliverySchedule", {}),
        }

        return {
            **contract,
            "etlJobDefinition": etl_job_definition,
            "etlJobCreatedAt": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Error handling and notifications (Subtask 5.6)
    # ------------------------------------------------------------------

    def build_error_notification(
        self,
        error: Exception,
        contract: dict,
        step: str = "unknown",
    ) -> dict:
        """
        Build an SNS notification payload for a deployment failure.

        Args:
            error: The exception that occurred.
            contract: The contract being deployed.
            step: The workflow step where the error occurred.

        Returns:
            Notification payload dict with actionable error message.
        """
        contract_id = contract.get("contractId", "unknown")
        cmo_id = contract.get("cmoId", "unknown")

        return {
            "subject": f"[CRITICAL] Pipeline Deployment Failed - {contract_id}",
            "message": (
                f"Pipeline deployment failed for contract {contract_id} "
                f"(CMO: {cmo_id}) at step '{step}'.\n\n"
                f"Error: {str(error)}\n\n"
                f"Action Required: Review the error above and check CloudWatch "
                f"log group /pharma-data-exchange/pipeline for details. "
                f"Re-activate the contract after resolving the issue."
            ),
            "attributes": {
                "contractId": contract_id,
                "cmoId": cmo_id,
                "step": step,
                "severity": "critical",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    def build_cloudwatch_log_entry(
        self,
        error: Exception,
        contract: dict,
        step: str = "unknown",
    ) -> dict:
        """
        Build a structured CloudWatch log entry for an error.

        Args:
            error: The exception that occurred.
            contract: The contract being deployed.
            step: The workflow step where the error occurred.

        Returns:
            Structured log entry dictionary.
        """
        contract_id = contract.get("contractId", "unknown")
        cmo_id = contract.get("cmoId", "unknown")

        return {
            "level": "ERROR",
            "message": str(error),
            "contractId": contract_id,
            "cmoId": cmo_id,
            "step": step,
            "errorType": type(error).__name__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actionRequired": (
                f"Check contract {contract_id} configuration and retry deployment. "
                f"Failed at step: {step}."
            ),
        }

    def calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay for retry logic.

        Args:
            attempt: Current attempt number (0-based).

        Returns:
            Delay in seconds.
        """
        return INITIAL_BACKOFF_SECONDS * (2 ** attempt)

    # ------------------------------------------------------------------
    # Full orchestration (convenience method)
    # ------------------------------------------------------------------

    def orchestrate_deployment(
        self, contract: dict, bucket_name: str = "cmo-data-lake"
    ) -> dict:
        """
        Run the full pipeline deployment orchestration.

        Steps:
        1. ValidateContract
        2. DeterminePattern
        3. Configure pattern-specific resources
        4. CreateETLJob

        Args:
            contract: Raw contract dictionary.
            bucket_name: Data lake bucket name.

        Returns:
            Fully configured deployment result.

        Raises:
            PipelineOrchestrationError: On any step failure.
        """
        # Step 1: Validate
        validated = self.validate_contract(contract)

        # Step 2: Determine pattern
        pattern = self.determine_pattern(validated)

        # Step 3: Pattern-specific configuration
        if pattern == "native-connector":
            configured = self.configure_glue_connector(validated)
        elif pattern == "secure-transfer":
            configured = self.provision_sftp(validated)
        elif pattern == "ai-unstructured":
            configured = self.configure_ai_processing(validated)
        else:
            raise PipelineOrchestrationError(
                f"Unknown pattern: {pattern}",
                step="DeterminePattern",
                contract_id=validated.get("contractId", ""),
            )

        # Step 4: Create ETL job
        result = self.create_etl_job(configured, bucket_name)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _map_connection_type(connection_type: str) -> str:
        """Map user-facing connection type to Glue connection type."""
        mapping = {
            "snowflake": "SNOWFLAKE",
            "oracle": "JDBC",
            "sqlserver": "JDBC",
            "postgresql": "JDBC",
            "sap": "JDBC",
            "databricks": "DATABRICKS",
        }
        return mapping.get(connection_type, "JDBC")
