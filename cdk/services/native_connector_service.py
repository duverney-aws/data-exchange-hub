"""
Native Connector Service

Implements Pattern 1: Native Database Connectors for the Pharma Data Exchange Hub.
Provides Glue connector configurations for supported platforms, connectivity testing,
and data extraction to the Bronze layer.

Supported platforms: Snowflake, Oracle, SQL Server, PostgreSQL, SAP, Databricks.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from utils.s3_path_utils import generate_bronze_path

logger = logging.getLogger(__name__)

# Supported connection types and their Glue mapping
CONNECTOR_TYPE_MAP = {
    "snowflake": "SNOWFLAKE",
    "oracle": "JDBC",
    "sqlserver": "JDBC",
    "postgresql": "JDBC",
    "sap": "JDBC",
    "databricks": "DATABRICKS",
}

SUPPORTED_CONNECTION_TYPES = set(CONNECTOR_TYPE_MAP.keys())

# Default JDBC URL templates per platform
JDBC_URL_TEMPLATES = {
    "oracle": "jdbc:oracle:thin:@{host}:{port}/{database}",
    "sqlserver": "jdbc:sqlserver://{host}:{port};databaseName={database}",
    "postgresql": "jdbc:postgresql://{host}:{port}/{database}",
    "sap": "jdbc:sap://{host}:{port}/?databaseName={database}",
}

# Default ports per platform
DEFAULT_PORTS = {
    "oracle": 1521,
    "sqlserver": 1433,
    "postgresql": 5432,
    "sap": 30015,
}

# Bronze layer output settings
BRONZE_OUTPUT_FORMAT = "parquet"
BRONZE_COMPRESSION = "snappy"


class NativeConnectorError(Exception):
    """Base exception for native connector operations."""

    def __init__(self, message: str, step: str = "unknown", contract_id: str = ""):
        self.step = step
        self.contract_id = contract_id
        super().__init__(message)


class ConnectorConfigError(NativeConnectorError):
    """Raised when connector configuration is invalid."""
    pass


class ConnectivityTestError(NativeConnectorError):
    """Raised when connectivity testing fails."""
    pass


class DataExtractionError(NativeConnectorError):
    """Raised when data extraction fails."""
    pass


class NativeConnectorService:
    """
    Service for Pattern 1: Native Database Connectors.

    Manages Glue connector configurations, connectivity testing,
    and data extraction to the Bronze layer for supported database platforms.
    """

    def __init__(self, glue_client=None, cloudwatch_client=None, secrets_client=None):
        """
        Args:
            glue_client: boto3 Glue client (injected for testing).
            cloudwatch_client: boto3 CloudWatch client (injected for testing).
            secrets_client: boto3 Secrets Manager client (injected for testing).
        """
        self._glue = glue_client
        self._cloudwatch = cloudwatch_client
        self._secrets = secrets_client

    # ------------------------------------------------------------------
    # 7.1  Glue connector configurations
    # ------------------------------------------------------------------

    def build_connector_config(self, contract: dict) -> dict:
        """
        Build an AWS Glue connector configuration for the given contract.

        Supports:
        - Snowflake native connector
        - JDBC connectors for Oracle, SQL Server, PostgreSQL, SAP
        - Databricks native connector

        Args:
            contract: Data contract dict with ``connectionConfig`` section.

        Returns:
            Dictionary with full connector configuration including:
            - connectionName, glueConnectionType, connectionProperties,
              secretId, database, schema.

        Raises:
            ConnectorConfigError: If connection type is unsupported or
                required fields are missing.
        """
        contract_id = contract.get("contractId", "")
        conn = contract.get("connectionConfig", {})
        connection_type = conn.get("connectionType", "").lower()

        if connection_type not in SUPPORTED_CONNECTION_TYPES:
            raise ConnectorConfigError(
                f"Unsupported connection type '{connection_type}'. "
                f"Supported: {sorted(SUPPORTED_CONNECTION_TYPES)}",
                step="BuildConnectorConfig",
                contract_id=contract_id,
            )

        cmo_id = contract.get("cmoId", "")
        data_domain = contract.get("dataDomain", "")

        if not cmo_id or not data_domain:
            raise ConnectorConfigError(
                "Contract must include cmoId and dataDomain",
                step="BuildConnectorConfig",
                contract_id=contract_id,
            )

        glue_type = CONNECTOR_TYPE_MAP[connection_type]
        connection_name = f"{cmo_id}-{data_domain}-{connection_type}"
        secret_id = f"cmo/{cmo_id}/credentials"

        # Base properties shared by all connector types
        connection_properties: Dict[str, Any] = {
            "connectionName": connection_name,
            "glueConnectionType": glue_type,
            "connectionType": connection_type,
            "secretId": secret_id,
            "database": conn.get("database", ""),
            "schema": conn.get("schema", ""),
        }

        # Add JDBC-specific properties
        if glue_type == "JDBC":
            connection_url = conn.get("connectionUrl", "")
            if not connection_url:
                # Build from template if host is provided
                host = conn.get("host", "localhost")
                port = conn.get("port", DEFAULT_PORTS.get(connection_type, 0))
                database = conn.get("database", "")
                template = JDBC_URL_TEMPLATES.get(connection_type, "")
                if template:
                    connection_url = template.format(
                        host=host, port=port, database=database,
                    )
            connection_properties["connectionUrl"] = connection_url

        # Add optional extraction settings
        connection_properties["tableOrQuery"] = conn.get("tableOrQuery", "")
        connection_properties["partitionColumn"] = conn.get("partitionColumn", "")
        connection_properties["numPartitions"] = conn.get("numPartitions", 4)

        return {
            "contractId": contract_id,
            "cmoId": cmo_id,
            "dataDomain": data_domain,
            "connectorConfig": connection_properties,
            "configuredAt": datetime.now(timezone.utc).isoformat(),
        }

    def get_supported_connection_types(self) -> List[str]:
        """Return sorted list of supported connection types."""
        return sorted(SUPPORTED_CONNECTION_TYPES)

    # ------------------------------------------------------------------
    # 7.3  Connectivity testing
    # ------------------------------------------------------------------

    def test_connectivity(
        self, connector_config: dict, glue_client=None,
    ) -> dict:
        """
        Test database connectivity before pipeline activation.

        Uses the AWS Glue ``TestConnection`` API (or injected client) to
        verify that the configured connector can reach the target database.

        Args:
            connector_config: Output of ``build_connector_config()``.
            glue_client: Optional override for the Glue client.

        Returns:
            Dictionary with keys:
            - ``success`` (bool): Whether the connection test passed.
            - ``connectionName`` (str): Name of the tested connection.
            - ``message`` (str): Human-readable result description.
            - ``testedAt`` (str): ISO-8601 timestamp.
            - ``errorDetails`` (str | None): Error info on failure.

        Raises:
            ConnectivityTestError: If the test cannot be initiated
                (e.g. missing config).
        """
        client = glue_client or self._glue
        cfg = connector_config.get("connectorConfig", {})
        connection_name = cfg.get("connectionName", "")

        if not connection_name:
            raise ConnectivityTestError(
                "Missing connectionName in connector config",
                step="TestConnectivity",
                contract_id=connector_config.get("contractId", ""),
            )

        result = {
            "connectionName": connection_name,
            "connectionType": cfg.get("connectionType", ""),
            "testedAt": datetime.now(timezone.utc).isoformat(),
            "success": False,
            "message": "",
            "errorDetails": None,
        }

        if client is None:
            # No client available — return a descriptive failure
            result["message"] = (
                "Glue client not available. Provide a glue_client to test connectivity."
            )
            result["errorDetails"] = "No Glue client configured"
            return result

        try:
            response = client.test_connection(ConnectionName=connection_name)
            # Glue TestConnection is async; we check the returned status
            status = response.get("Status", "FAILED")
            if status == "SUCCEEDED":
                result["success"] = True
                result["message"] = (
                    f"Connection '{connection_name}' test succeeded."
                )
            else:
                error_msg = response.get("ErrorMessage", "Unknown error")
                result["message"] = (
                    f"Connection '{connection_name}' test failed: {error_msg}"
                )
                result["errorDetails"] = error_msg
        except Exception as exc:
            result["message"] = (
                f"Connection '{connection_name}' test failed: {exc}"
            )
            result["errorDetails"] = str(exc)

        return result

    # ------------------------------------------------------------------
    # 7.4  Data extraction to Bronze layer
    # ------------------------------------------------------------------

    def extract_to_bronze(
        self,
        contract: dict,
        bucket_name: str = "cmo-data-lake",
        extraction_date: Optional[datetime] = None,
        glue_client=None,
        cloudwatch_client=None,
    ) -> dict:
        """
        Extract data from the source database and write to the Bronze layer.

        Generates a Glue job configuration that:
        - Extracts data using JDBC or native APIs
        - Writes to Bronze in Parquet format with Snappy compression
        - Applies date partitioning (year/month/day)
        - Logs row counts and execution time to CloudWatch

        Args:
            contract: Data contract dict with connectionConfig.
            bucket_name: S3 bucket for the data lake.
            extraction_date: Date for partitioning (defaults to now).
            glue_client: Optional Glue client override.
            cloudwatch_client: Optional CloudWatch client override.

        Returns:
            Extraction result dictionary with job config, output path,
            metrics, and status.

        Raises:
            DataExtractionError: If extraction configuration fails.
        """
        contract_id = contract.get("contractId", "")
        cmo_id = contract.get("cmoId", "")
        data_domain = contract.get("dataDomain", "")

        if not cmo_id or not data_domain:
            raise DataExtractionError(
                "Contract must include cmoId and dataDomain",
                step="ExtractToBronze",
                contract_id=contract_id,
            )

        if extraction_date is None:
            extraction_date = datetime.now(timezone.utc)

        # Build Bronze output path with date partitioning
        bronze_path = generate_bronze_path(
            bucket_name=bucket_name,
            cmo_id=cmo_id,
            data_domain=data_domain,
            date=extraction_date,
        )

        # Build connector config if not already present
        conn_cfg = contract.get("connectionConfig", {})
        connection_type = conn_cfg.get("connectionType", "").lower()
        glue_type = CONNECTOR_TYPE_MAP.get(connection_type, "JDBC")

        start_time = time.monotonic()
        execution_id = str(uuid.uuid4())

        # Build the Glue extraction job definition
        extraction_job = {
            "executionId": execution_id,
            "jobName": f"extract-{cmo_id}-{data_domain}",
            "contractId": contract_id,
            "sourceConfig": {
                "connectionType": connection_type,
                "glueConnectionType": glue_type,
                "database": conn_cfg.get("database", ""),
                "schema": conn_cfg.get("schema", ""),
                "tableOrQuery": conn_cfg.get("tableOrQuery", ""),
                "partitionColumn": conn_cfg.get("partitionColumn", ""),
                "numPartitions": conn_cfg.get("numPartitions", 4),
            },
            "outputConfig": {
                "outputPath": bronze_path,
                "format": BRONZE_OUTPUT_FORMAT,
                "compression": BRONZE_COMPRESSION,
                "partitioning": {
                    "year": extraction_date.strftime("%Y"),
                    "month": extraction_date.strftime("%m"),
                    "day": extraction_date.strftime("%d"),
                },
            },
            "glueJobConfig": {
                "command": {
                    "name": "glueetl",
                    "scriptLocation": (
                        f"s3://{bucket_name}/scripts/extract-{cmo_id}-{data_domain}.py"
                    ),
                    "pythonVersion": "3",
                },
                "defaultArguments": {
                    "--job-language": "python",
                    "--enable-metrics": "true",
                    "--enable-continuous-cloudwatch-log": "true",
                    "--contract-id": contract_id,
                    "--output-path": bronze_path,
                    "--output-format": BRONZE_OUTPUT_FORMAT,
                    "--output-compression": BRONZE_COMPRESSION,
                },
                "workerType": "G.1X",
                "numberOfWorkers": 2,
            },
        }

        elapsed = time.monotonic() - start_time

        # Build metrics (row count would come from actual Glue run;
        # here we record the config-generation metrics)
        metrics = {
            "executionId": execution_id,
            "contractId": contract_id,
            "cmoId": cmo_id,
            "dataDomain": data_domain,
            "executionTimeSeconds": round(elapsed, 3),
            "outputPath": bronze_path,
            "outputFormat": BRONZE_OUTPUT_FORMAT,
            "compression": BRONZE_COMPRESSION,
            "extractionDate": extraction_date.isoformat(),
            "status": "configured",
        }

        # Publish metrics to CloudWatch if client is available
        cw = cloudwatch_client or self._cloudwatch
        if cw is not None:
            self._publish_extraction_metrics(cw, metrics)

        return {
            "extractionJob": extraction_job,
            "metrics": metrics,
            "bronzePath": bronze_path,
            "status": "configured",
        }

    # ------------------------------------------------------------------
    # CloudWatch metric publishing
    # ------------------------------------------------------------------

    def _publish_extraction_metrics(
        self, cloudwatch_client, metrics: dict,
    ) -> None:
        """
        Publish extraction metrics to CloudWatch.

        Logs row counts and execution time per Requirement 5.5.
        """
        try:
            metric_data = [
                {
                    "MetricName": "ExtractionExecutionTime",
                    "Value": metrics.get("executionTimeSeconds", 0),
                    "Unit": "Seconds",
                    "Dimensions": [
                        {"Name": "ContractId", "Value": metrics.get("contractId", "")},
                        {"Name": "CMOId", "Value": metrics.get("cmoId", "")},
                    ],
                },
            ]

            # Include row count if available
            row_count = metrics.get("rowCount")
            if row_count is not None:
                metric_data.append({
                    "MetricName": "ExtractionRowCount",
                    "Value": row_count,
                    "Unit": "Count",
                    "Dimensions": [
                        {"Name": "ContractId", "Value": metrics.get("contractId", "")},
                        {"Name": "CMOId", "Value": metrics.get("cmoId", "")},
                    ],
                })

            cloudwatch_client.put_metric_data(
                Namespace="CMO/DataPipeline",
                MetricData=metric_data,
            )
            logger.info(
                "Published extraction metrics for %s", metrics.get("contractId"),
            )
        except Exception as exc:
            logger.warning("Failed to publish CloudWatch metrics: %s", exc)
