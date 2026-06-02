"""
Unit Tests for NativeConnectorService.

Validates:
- Glue connector configurations for all supported platforms (7.1)
- Connectivity testing with success/failure handling (7.3)
- Data extraction to Bronze layer with Parquet/Snappy, partitioning, metrics (7.4)

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""
import sys
import os
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.native_connector_service import (
    NativeConnectorService,
    NativeConnectorError,
    ConnectorConfigError,
    ConnectivityTestError,
    DataExtractionError,
    SUPPORTED_CONNECTION_TYPES,
    CONNECTOR_TYPE_MAP,
    BRONZE_OUTPUT_FORMAT,
    BRONZE_COMPRESSION,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _contract(connection_type="snowflake", **overrides):
    """Return a minimal contract for testing."""
    contract = {
        "contractId": "CMO-ALPHA-BATCH-RECORDS-001",
        "cmoId": "cmo-alpha",
        "dataDomain": "batch-records",
        "integrationPattern": "native-connector",
        "status": "active",
        "connectionConfig": {
            "connectionType": connection_type,
            "connectionUrl": f"jdbc:{connection_type}://host:5432/db",
            "database": "production",
            "schema": "manufacturing",
            "tableOrQuery": "batch_records",
            "partitionColumn": "batch_date",
            "numPartitions": 8,
        },
    }
    contract.update(overrides)
    return contract


@pytest.fixture
def service():
    return NativeConnectorService()


# ---------------------------------------------------------------------------
# 7.1 — Glue connector configurations
# ---------------------------------------------------------------------------

class TestBuildConnectorConfig:
    """Requirement 5.1: Support Snowflake, Oracle, SQL Server, PostgreSQL, SAP, Databricks."""

    def test_all_six_connection_types_supported(self, service):
        expected = {"snowflake", "oracle", "sqlserver", "postgresql", "sap", "databricks"}
        assert SUPPORTED_CONNECTION_TYPES == expected

    def test_snowflake_native_connector(self, service):
        result = service.build_connector_config(_contract("snowflake"))
        cfg = result["connectorConfig"]
        assert cfg["glueConnectionType"] == "SNOWFLAKE"
        assert cfg["connectionType"] == "snowflake"
        assert cfg["database"] == "production"
        assert cfg["schema"] == "manufacturing"
        assert "connectionUrl" not in cfg  # native, not JDBC

    def test_databricks_native_connector(self, service):
        result = service.build_connector_config(_contract("databricks"))
        cfg = result["connectorConfig"]
        assert cfg["glueConnectionType"] == "DATABRICKS"
        assert "connectionUrl" not in cfg

    def test_oracle_jdbc_connector(self, service):
        result = service.build_connector_config(_contract("oracle"))
        cfg = result["connectorConfig"]
        assert cfg["glueConnectionType"] == "JDBC"
        assert "connectionUrl" in cfg

    def test_sqlserver_jdbc_connector(self, service):
        result = service.build_connector_config(_contract("sqlserver"))
        cfg = result["connectorConfig"]
        assert cfg["glueConnectionType"] == "JDBC"

    def test_postgresql_jdbc_connector(self, service):
        result = service.build_connector_config(_contract("postgresql"))
        cfg = result["connectorConfig"]
        assert cfg["glueConnectionType"] == "JDBC"

    def test_sap_jdbc_connector(self, service):
        result = service.build_connector_config(_contract("sap"))
        cfg = result["connectorConfig"]
        assert cfg["glueConnectionType"] == "JDBC"

    def test_connection_name_follows_convention(self, service):
        result = service.build_connector_config(_contract("snowflake"))
        cfg = result["connectorConfig"]
        assert cfg["connectionName"] == "cmo-alpha-batch-records-snowflake"

    def test_secret_id_follows_convention(self, service):
        result = service.build_connector_config(_contract("snowflake"))
        cfg = result["connectorConfig"]
        assert cfg["secretId"] == "cmo/cmo-alpha/credentials"

    def test_extraction_settings_included(self, service):
        result = service.build_connector_config(_contract("postgresql"))
        cfg = result["connectorConfig"]
        assert cfg["tableOrQuery"] == "batch_records"
        assert cfg["partitionColumn"] == "batch_date"
        assert cfg["numPartitions"] == 8

    def test_unsupported_type_raises(self, service):
        with pytest.raises(ConnectorConfigError, match="Unsupported connection type"):
            service.build_connector_config(_contract("mysql"))

    def test_missing_cmo_id_raises(self, service):
        contract = _contract("snowflake")
        contract["cmoId"] = ""
        with pytest.raises(ConnectorConfigError, match="cmoId and dataDomain"):
            service.build_connector_config(contract)

    def test_missing_data_domain_raises(self, service):
        contract = _contract("snowflake")
        contract["dataDomain"] = ""
        with pytest.raises(ConnectorConfigError, match="cmoId and dataDomain"):
            service.build_connector_config(contract)

    def test_configured_at_timestamp_present(self, service):
        result = service.build_connector_config(_contract("snowflake"))
        assert "configuredAt" in result

    def test_jdbc_url_built_from_template_when_missing(self, service):
        contract = _contract("oracle")
        contract["connectionConfig"]["connectionUrl"] = ""
        contract["connectionConfig"]["host"] = "db.example.com"
        contract["connectionConfig"]["port"] = 1521
        result = service.build_connector_config(contract)
        cfg = result["connectorConfig"]
        assert "jdbc:oracle:thin:@db.example.com:1521/production" == cfg["connectionUrl"]

    def test_get_supported_connection_types(self, service):
        types = service.get_supported_connection_types()
        assert types == ["databricks", "oracle", "postgresql", "sap", "snowflake", "sqlserver"]

    def test_all_types_produce_valid_config(self, service):
        for conn_type in SUPPORTED_CONNECTION_TYPES:
            result = service.build_connector_config(_contract(conn_type))
            assert "connectorConfig" in result
            assert result["connectorConfig"]["connectionType"] == conn_type


# ---------------------------------------------------------------------------
# 7.3 — Connectivity testing
# ---------------------------------------------------------------------------

class TestConnectivityTesting:
    """Requirement 5.2: Test connectivity before activation, return success/failure."""

    def test_successful_connection(self, service):
        mock_glue = MagicMock()
        mock_glue.test_connection.return_value = {"Status": "SUCCEEDED"}

        connector_cfg = service.build_connector_config(_contract("snowflake"))
        result = service.test_connectivity(connector_cfg, glue_client=mock_glue)

        assert result["success"] is True
        assert "succeeded" in result["message"].lower()
        assert result["errorDetails"] is None
        assert result["connectionName"] == "cmo-alpha-batch-records-snowflake"
        assert "testedAt" in result

    def test_failed_connection_returns_error_details(self, service):
        mock_glue = MagicMock()
        mock_glue.test_connection.return_value = {
            "Status": "FAILED",
            "ErrorMessage": "Connection refused on port 5432",
        }

        connector_cfg = service.build_connector_config(_contract("postgresql"))
        result = service.test_connectivity(connector_cfg, glue_client=mock_glue)

        assert result["success"] is False
        assert "failed" in result["message"].lower()
        assert result["errorDetails"] == "Connection refused on port 5432"

    def test_exception_during_test_returns_error(self, service):
        mock_glue = MagicMock()
        mock_glue.test_connection.side_effect = Exception("Network timeout")

        connector_cfg = service.build_connector_config(_contract("oracle"))
        result = service.test_connectivity(connector_cfg, glue_client=mock_glue)

        assert result["success"] is False
        assert "Network timeout" in result["errorDetails"]

    def test_no_client_returns_descriptive_failure(self, service):
        connector_cfg = service.build_connector_config(_contract("snowflake"))
        result = service.test_connectivity(connector_cfg, glue_client=None)

        assert result["success"] is False
        assert "not available" in result["message"].lower()

    def test_missing_connection_name_raises(self, service):
        with pytest.raises(ConnectivityTestError, match="Missing connectionName"):
            service.test_connectivity({"connectorConfig": {}})

    def test_result_includes_connection_type(self, service):
        mock_glue = MagicMock()
        mock_glue.test_connection.return_value = {"Status": "SUCCEEDED"}

        connector_cfg = service.build_connector_config(_contract("databricks"))
        result = service.test_connectivity(connector_cfg, glue_client=mock_glue)
        assert result["connectionType"] == "databricks"


# ---------------------------------------------------------------------------
# 7.4 — Data extraction to Bronze layer
# ---------------------------------------------------------------------------

class TestExtractToBronze:
    """Requirements 5.3, 5.4, 5.5: Extract via JDBC/native, Parquet+Snappy, partitioning, CloudWatch."""

    def test_extraction_job_generated(self, service):
        result = service.extract_to_bronze(_contract("snowflake"))
        assert "extractionJob" in result
        job = result["extractionJob"]
        assert job["jobName"] == "extract-cmo-alpha-batch-records"
        assert job["contractId"] == "CMO-ALPHA-BATCH-RECORDS-001"

    def test_output_format_is_parquet(self, service):
        result = service.extract_to_bronze(_contract("snowflake"))
        output = result["extractionJob"]["outputConfig"]
        assert output["format"] == "parquet"

    def test_compression_is_snappy(self, service):
        result = service.extract_to_bronze(_contract("snowflake"))
        output = result["extractionJob"]["outputConfig"]
        assert output["compression"] == "snappy"

    def test_date_partitioning_applied(self, service):
        fixed_date = datetime(2024, 3, 15, tzinfo=timezone.utc)
        result = service.extract_to_bronze(
            _contract("snowflake"),
            extraction_date=fixed_date,
        )
        output = result["extractionJob"]["outputConfig"]
        assert output["partitioning"]["year"] == "2024"
        assert output["partitioning"]["month"] == "03"
        assert output["partitioning"]["day"] == "15"

    def test_bronze_path_follows_pattern(self, service):
        fixed_date = datetime(2024, 6, 1, tzinfo=timezone.utc)
        result = service.extract_to_bronze(
            _contract("snowflake"),
            bucket_name="my-lake",
            extraction_date=fixed_date,
        )
        path = result["bronzePath"]
        assert path == "s3://my-lake/bronze/cmo-alpha/batch-records/year=2024/month=06/day=01/"

    def test_source_config_includes_connection_details(self, service):
        result = service.extract_to_bronze(_contract("oracle"))
        src = result["extractionJob"]["sourceConfig"]
        assert src["connectionType"] == "oracle"
        assert src["glueConnectionType"] == "JDBC"
        assert src["database"] == "production"
        assert src["schema"] == "manufacturing"

    def test_metrics_include_execution_time(self, service):
        result = service.extract_to_bronze(_contract("snowflake"))
        metrics = result["metrics"]
        assert "executionTimeSeconds" in metrics
        assert metrics["executionTimeSeconds"] >= 0

    def test_metrics_include_contract_info(self, service):
        result = service.extract_to_bronze(_contract("snowflake"))
        metrics = result["metrics"]
        assert metrics["contractId"] == "CMO-ALPHA-BATCH-RECORDS-001"
        assert metrics["cmoId"] == "cmo-alpha"
        assert metrics["dataDomain"] == "batch-records"

    def test_cloudwatch_metrics_published(self, service):
        mock_cw = MagicMock()
        service.extract_to_bronze(
            _contract("snowflake"),
            cloudwatch_client=mock_cw,
        )
        mock_cw.put_metric_data.assert_called_once()
        call_args = mock_cw.put_metric_data.call_args
        assert call_args.kwargs["Namespace"] == "CMO/DataPipeline"

    def test_cloudwatch_failure_does_not_raise(self, service):
        mock_cw = MagicMock()
        mock_cw.put_metric_data.side_effect = Exception("CloudWatch unavailable")
        # Should not raise — just logs a warning
        result = service.extract_to_bronze(
            _contract("snowflake"),
            cloudwatch_client=mock_cw,
        )
        assert result["status"] == "configured"

    def test_missing_cmo_id_raises(self, service):
        contract = _contract("snowflake")
        contract["cmoId"] = ""
        with pytest.raises(DataExtractionError, match="cmoId and dataDomain"):
            service.extract_to_bronze(contract)

    def test_missing_data_domain_raises(self, service):
        contract = _contract("snowflake")
        contract["dataDomain"] = ""
        with pytest.raises(DataExtractionError, match="cmoId and dataDomain"):
            service.extract_to_bronze(contract)

    def test_glue_job_config_present(self, service):
        result = service.extract_to_bronze(_contract("snowflake"))
        glue_cfg = result["extractionJob"]["glueJobConfig"]
        assert glue_cfg["command"]["name"] == "glueetl"
        assert "--contract-id" in glue_cfg["defaultArguments"]
        assert "--output-format" in glue_cfg["defaultArguments"]
        assert "--output-compression" in glue_cfg["defaultArguments"]

    def test_execution_id_is_unique(self, service):
        r1 = service.extract_to_bronze(_contract("snowflake"))
        r2 = service.extract_to_bronze(_contract("snowflake"))
        assert r1["extractionJob"]["executionId"] != r2["extractionJob"]["executionId"]

    def test_custom_bucket_name(self, service):
        result = service.extract_to_bronze(
            _contract("snowflake"), bucket_name="custom-bucket",
        )
        assert "custom-bucket" in result["bronzePath"]


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class TestExceptionHierarchy:
    def test_connector_config_error_is_native_connector_error(self):
        assert issubclass(ConnectorConfigError, NativeConnectorError)

    def test_connectivity_test_error_is_native_connector_error(self):
        assert issubclass(ConnectivityTestError, NativeConnectorError)

    def test_data_extraction_error_is_native_connector_error(self):
        assert issubclass(DataExtractionError, NativeConnectorError)

    def test_error_includes_step_and_contract_id(self):
        err = ConnectorConfigError("bad", step="BuildConnectorConfig", contract_id="CMO-001")
        assert err.step == "BuildConnectorConfig"
        assert err.contract_id == "CMO-001"
