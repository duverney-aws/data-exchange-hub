"""
Unit Tests for PipelineOrchestrationService.

Validates:
- Contract validation before deployment
- Pattern determination logic
- Pattern-specific configuration generation (Glue, SFTP, AI)
- ETL job definition generation
- S3 path configuration
- Error handling, retry logic, and SNS notification building

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.8, 15.1, 15.2
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.pipeline_orchestration_service import (
    PipelineOrchestrationService,
    PipelineOrchestrationError,
    ContractValidationError,
    PatternConfigurationError,
    ETLJobCreationError,
    MAX_RETRY_ATTEMPTS,
    INITIAL_BACKOFF_SECONDS,
    VALID_PATTERNS,
    NATIVE_CONNECTOR_TYPES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _active_contract(pattern="native-connector", **overrides):
    """Return a minimal active contract for testing."""
    contract = {
        "contractId": "CMO-ALPHA-BATCH-RECORDS-001",
        "cmoId": "cmo-alpha",
        "dataDomain": "batch-records",
        "integrationPattern": pattern,
        "status": "active",
        "qualityRules": [
            {
                "ruleId": "rule-001",
                "ruleName": "Batch ID completeness",
                "ruleType": "completeness",
                "expression": 'Completeness "batch_id" > 0.99',
                "threshold": 99.0,
                "severity": "error",
            }
        ],
        "deliverySchedule": {"frequency": "daily"},
        "connectionConfig": {
            "connectionType": "snowflake",
            "connectionUrl": "jdbc:snowflake://account.snowflakecomputing.com",
            "database": "production",
            "schema": "manufacturing",
        },
        "aiConfig": {},
    }
    contract.update(overrides)
    return contract


@pytest.fixture
def service():
    return PipelineOrchestrationService()


# ---------------------------------------------------------------------------
# validate_contract
# ---------------------------------------------------------------------------

class TestValidateContract:
    def test_valid_active_contract_passes(self, service):
        result = service.validate_contract(_active_contract())
        assert result["contractId"] == "CMO-ALPHA-BATCH-RECORDS-001"
        assert "validatedAt" in result
        assert "deploymentId" in result

    def test_missing_contract_id_raises(self, service):
        contract = _active_contract()
        del contract["contractId"]
        with pytest.raises(ContractValidationError, match="Missing required field"):
            service.validate_contract(contract)

    def test_missing_cmo_id_raises(self, service):
        contract = _active_contract()
        del contract["cmoId"]
        with pytest.raises(ContractValidationError, match="Missing required field"):
            service.validate_contract(contract)

    def test_missing_integration_pattern_raises(self, service):
        contract = _active_contract()
        del contract["integrationPattern"]
        with pytest.raises(ContractValidationError, match="Missing required field"):
            service.validate_contract(contract)

    def test_draft_status_raises(self, service):
        contract = _active_contract(status="draft")
        with pytest.raises(ContractValidationError, match="must be 'active'"):
            service.validate_contract(contract)

    def test_invalid_pattern_raises(self, service):
        contract = _active_contract(integrationPattern="invalid-pattern")
        with pytest.raises(ContractValidationError, match="Invalid integration pattern"):
            service.validate_contract(contract)

    def test_all_valid_patterns_accepted(self, service):
        for pattern in VALID_PATTERNS:
            result = service.validate_contract(_active_contract(pattern=pattern))
            assert result["integrationPattern"] == pattern

    def test_error_includes_step_and_contract_id(self, service):
        contract = _active_contract(status="draft")
        with pytest.raises(ContractValidationError) as exc_info:
            service.validate_contract(contract)
        assert exc_info.value.step == "ValidateContract"
        assert exc_info.value.contract_id == "CMO-ALPHA-BATCH-RECORDS-001"


# ---------------------------------------------------------------------------
# determine_pattern
# ---------------------------------------------------------------------------

class TestDeterminePattern:
    def test_returns_native_connector(self, service):
        assert service.determine_pattern(_active_contract("native-connector")) == "native-connector"

    def test_returns_secure_transfer(self, service):
        assert service.determine_pattern(_active_contract("secure-transfer")) == "secure-transfer"

    def test_returns_ai_unstructured(self, service):
        assert service.determine_pattern(_active_contract("ai-unstructured")) == "ai-unstructured"


# ---------------------------------------------------------------------------
# configure_glue_connector (Pattern 1)
# ---------------------------------------------------------------------------

class TestConfigureGlueConnector:
    def test_snowflake_connector(self, service):
        contract = _active_contract(connectionConfig={
            "connectionType": "snowflake",
            "database": "prod_db",
            "schema": "mfg",
        })
        result = service.configure_glue_connector(contract)
        assert "connectorConfig" in result
        cfg = result["connectorConfig"]
        assert cfg["connectionName"] == "cmo-alpha-batch-records-snowflake"
        assert cfg["connectionType"] == "SNOWFLAKE"
        assert cfg["database"] == "prod_db"
        assert result["patternStep"] == "ConfigureGlueConnector"

    def test_jdbc_connector_types(self, service):
        for conn_type in ("oracle", "sqlserver", "postgresql", "sap"):
            contract = _active_contract(connectionConfig={
                "connectionType": conn_type,
                "connectionUrl": f"jdbc:{conn_type}://host:1234/db",
                "database": "db",
                "schema": "sch",
            })
            result = service.configure_glue_connector(contract)
            assert result["connectorConfig"]["connectionType"] == "JDBC"

    def test_databricks_connector(self, service):
        contract = _active_contract(connectionConfig={
            "connectionType": "databricks",
            "database": "db",
            "schema": "sch",
        })
        result = service.configure_glue_connector(contract)
        assert result["connectorConfig"]["connectionType"] == "DATABRICKS"

    def test_unsupported_type_raises(self, service):
        contract = _active_contract(connectionConfig={
            "connectionType": "mysql",
            "database": "db",
            "schema": "sch",
        })
        with pytest.raises(PatternConfigurationError, match="Unsupported connection type"):
            service.configure_glue_connector(contract)

    def test_secret_id_follows_convention(self, service):
        result = service.configure_glue_connector(_active_contract())
        assert result["connectorConfig"]["secretId"] == "cmo/cmo-alpha/credentials"

    def test_all_native_connector_types_supported(self, service):
        for conn_type in NATIVE_CONNECTOR_TYPES:
            contract = _active_contract(connectionConfig={
                "connectionType": conn_type,
                "connectionUrl": f"jdbc:{conn_type}://host/db",
                "database": "db",
                "schema": "sch",
            })
            result = service.configure_glue_connector(contract)
            assert "connectorConfig" in result


# ---------------------------------------------------------------------------
# provision_sftp (Pattern 2)
# ---------------------------------------------------------------------------

class TestProvisionSFTP:
    def test_sftp_config_generated(self, service):
        contract = _active_contract("secure-transfer")
        result = service.provision_sftp(contract)
        assert "sftpConfig" in result
        cfg = result["sftpConfig"]
        assert cfg["sftpUsername"] == "cmo-alpha-batch-records-user"
        assert cfg["homeDirectory"] == "/bronze/cmo-alpha/batch-records/incoming/"
        assert cfg["secretId"] == "cmo/cmo-alpha/sftp-credentials"
        assert result["patternStep"] == "ProvisionSFTP"

    def test_sftp_allowed_file_patterns(self, service):
        result = service.provision_sftp(_active_contract("secure-transfer"))
        patterns = result["sftpConfig"]["allowedFilePatterns"]
        assert "*.csv" in patterns
        assert "*.parquet" in patterns
        assert "*.json" in patterns

    def test_sftp_max_file_size(self, service):
        result = service.provision_sftp(_active_contract("secure-transfer"))
        assert result["sftpConfig"]["maxFileSizeMb"] == 500


# ---------------------------------------------------------------------------
# configure_ai_processing (Pattern 3)
# ---------------------------------------------------------------------------

class TestConfigureAIProcessing:
    def test_ai_config_generated(self, service):
        contract = _active_contract("ai-unstructured")
        result = service.configure_ai_processing(contract)
        assert "aiProcessingConfig" in result
        cfg = result["aiProcessingConfig"]
        assert cfg["confidenceThreshold"] == 0.85
        assert cfg["outputFormat"] == "json"
        assert result["patternStep"] == "ConfigureAIProcessing"

    def test_ai_default_document_types(self, service):
        result = service.configure_ai_processing(_active_contract("ai-unstructured"))
        doc_types = result["aiProcessingConfig"]["documentTypes"]
        assert "pdf" in doc_types
        assert "png" in doc_types

    def test_ai_custom_config(self, service):
        contract = _active_contract("ai-unstructured", aiConfig={
            "documentTypes": ["pdf", "tiff"],
            "extractionFeatures": ["TABLES", "FORMS", "QUERIES"],
            "confidenceThreshold": 0.90,
        })
        result = service.configure_ai_processing(contract)
        cfg = result["aiProcessingConfig"]
        assert cfg["documentTypes"] == ["pdf", "tiff"]
        assert cfg["confidenceThreshold"] == 0.90
        assert "QUERIES" in cfg["extractionFeatures"]

    def test_ai_paths_include_cmo_and_domain(self, service):
        result = service.configure_ai_processing(_active_contract("ai-unstructured"))
        cfg = result["aiProcessingConfig"]
        assert "cmo-alpha" in cfg["inputPath"]
        assert "batch-records" in cfg["inputPath"]


# ---------------------------------------------------------------------------
# create_etl_job (Subtask 5.4)
# ---------------------------------------------------------------------------

class TestCreateETLJob:
    def test_etl_job_definition_generated(self, service):
        contract = _active_contract()
        result = service.create_etl_job(contract, bucket_name="my-lake")
        assert "etlJobDefinition" in result
        job = result["etlJobDefinition"]
        assert job["jobName"] == "etl-cmo-alpha-batch-records"
        assert job["contractId"] == "CMO-ALPHA-BATCH-RECORDS-001"

    def test_s3_paths_follow_pattern(self, service):
        result = service.create_etl_job(_active_contract(), bucket_name="my-lake")
        paths = result["etlJobDefinition"]["s3Paths"]
        assert paths["bronze"] == "s3://my-lake/bronze/cmo-alpha/batch-records/"
        assert paths["silver"] == "s3://my-lake/silver/cmo-alpha/batch-records/"
        assert paths["gold"] == "s3://my-lake/gold/cmo-alpha/batch-records/"
        assert "quarantine" in paths["quarantine"]

    def test_s3_paths_contain_bucket_layer_cmo_domain(self, service):
        result = service.create_etl_job(
            _active_contract(cmoId="cmo-beta", dataDomain="quality-data"),
            bucket_name="test-bucket",
        )
        paths = result["etlJobDefinition"]["s3Paths"]
        for layer in ("bronze", "silver", "gold"):
            assert paths[layer].startswith(f"s3://test-bucket/{layer}/cmo-beta/quality-data/")

    def test_quality_rules_extracted(self, service):
        result = service.create_etl_job(_active_contract())
        ruleset = result["etlJobDefinition"]["qualityRuleset"]
        assert len(ruleset) == 1
        assert 'Completeness "batch_id" > 0.99' in ruleset[0]

    def test_glue_job_config_present(self, service):
        result = service.create_etl_job(_active_contract())
        glue_cfg = result["etlJobDefinition"]["glueJobConfig"]
        assert glue_cfg["command"]["name"] == "glueetl"
        assert glue_cfg["maxRetries"] == MAX_RETRY_ATTEMPTS
        assert "--contract-id" in glue_cfg["defaultArguments"]

    def test_missing_cmo_id_raises(self, service):
        contract = _active_contract()
        contract["cmoId"] = ""
        with pytest.raises(ETLJobCreationError, match="missing cmoId"):
            service.create_etl_job(contract)

    def test_missing_data_domain_raises(self, service):
        contract = _active_contract()
        contract["dataDomain"] = ""
        with pytest.raises(ETLJobCreationError, match="missing cmoId or dataDomain"):
            service.create_etl_job(contract)


# ---------------------------------------------------------------------------
# Error handling and notifications (Subtask 5.6)
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_build_error_notification(self, service):
        error = PipelineOrchestrationError(
            "Connection timeout", step="ConfigureGlueConnector", contract_id="CMO-001"
        )
        contract = {"contractId": "CMO-001", "cmoId": "cmo-alpha"}
        notification = service.build_error_notification(error, contract, "ConfigureGlueConnector")

        assert "CRITICAL" in notification["subject"]
        assert "CMO-001" in notification["subject"]
        assert "Connection timeout" in notification["message"]
        assert "Action Required" in notification["message"]
        assert notification["attributes"]["severity"] == "critical"
        assert notification["attributes"]["step"] == "ConfigureGlueConnector"

    def test_build_cloudwatch_log_entry(self, service):
        error = ValueError("bad value")
        contract = {"contractId": "CMO-002", "cmoId": "cmo-beta"}
        log_entry = service.build_cloudwatch_log_entry(error, contract, "CreateETLJob")

        assert log_entry["level"] == "ERROR"
        assert log_entry["contractId"] == "CMO-002"
        assert log_entry["cmoId"] == "cmo-beta"
        assert log_entry["step"] == "CreateETLJob"
        assert log_entry["errorType"] == "ValueError"
        assert "actionRequired" in log_entry

    def test_notification_has_actionable_message(self, service):
        error = Exception("Glue API throttled")
        contract = {"contractId": "CMO-003", "cmoId": "cmo-gamma"}
        notification = service.build_error_notification(error, contract, "CreateETLJob")
        msg = notification["message"]
        assert "Re-activate" in msg or "resolving" in msg
        assert "CloudWatch" in msg

    def test_log_entry_has_actionable_guidance(self, service):
        error = Exception("timeout")
        contract = {"contractId": "CMO-004", "cmoId": "cmo-delta"}
        log_entry = service.build_cloudwatch_log_entry(error, contract, "ProvisionSFTP")
        assert "retry" in log_entry["actionRequired"].lower() or "check" in log_entry["actionRequired"].lower()


# ---------------------------------------------------------------------------
# Retry / backoff logic
# ---------------------------------------------------------------------------

class TestRetryLogic:
    def test_backoff_exponential(self, service):
        assert service.calculate_backoff(0) == INITIAL_BACKOFF_SECONDS * 1  # 1s
        assert service.calculate_backoff(1) == INITIAL_BACKOFF_SECONDS * 2  # 2s
        assert service.calculate_backoff(2) == INITIAL_BACKOFF_SECONDS * 4  # 4s

    def test_backoff_increases_monotonically(self, service):
        delays = [service.calculate_backoff(i) for i in range(MAX_RETRY_ATTEMPTS)]
        assert delays == sorted(delays)
        assert len(set(delays)) == len(delays)  # all distinct

    def test_max_retry_attempts_is_three(self):
        assert MAX_RETRY_ATTEMPTS == 3


# ---------------------------------------------------------------------------
# Full orchestration
# ---------------------------------------------------------------------------

class TestOrchestrateDeployment:
    def test_native_connector_full_flow(self, service):
        result = service.orchestrate_deployment(_active_contract("native-connector"))
        assert "etlJobDefinition" in result
        assert "connectorConfig" in result

    def test_secure_transfer_full_flow(self, service):
        result = service.orchestrate_deployment(_active_contract("secure-transfer"))
        assert "etlJobDefinition" in result
        assert "sftpConfig" in result

    def test_ai_unstructured_full_flow(self, service):
        result = service.orchestrate_deployment(_active_contract("ai-unstructured"))
        assert "etlJobDefinition" in result
        assert "aiProcessingConfig" in result

    def test_invalid_contract_raises(self, service):
        contract = _active_contract(status="draft")
        with pytest.raises(ContractValidationError):
            service.orchestrate_deployment(contract)

    def test_deployment_id_is_unique(self, service):
        r1 = service.orchestrate_deployment(_active_contract())
        r2 = service.orchestrate_deployment(_active_contract())
        assert r1["deploymentId"] != r2["deploymentId"]
