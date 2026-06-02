"""
Lambda handler for Pipeline Orchestration Step Functions tasks.

Each function corresponds to a state in the Step Functions workflow:
- validate_contract
- determine_pattern
- configure_glue_connector (Pattern 1)
- provision_sftp (Pattern 2)
- configure_ai_processing (Pattern 3)
- create_etl_job
- handle_error (catch state)

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.8, 15.1, 15.2
"""
import json
import logging
import os
import sys

# Ensure project root is on the path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.pipeline_orchestration_service import (
    PipelineOrchestrationService,
    PipelineOrchestrationError,
    ContractValidationError,
    PatternConfigurationError,
    ETLJobCreationError,
)

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

_service = PipelineOrchestrationService()

CRITICAL_TOPIC_ARN = os.environ.get('CRITICAL_ALERTS_TOPIC_ARN', '')
WARNING_TOPIC_ARN = os.environ.get('WARNING_ALERTS_TOPIC_ARN', '')
BUCKET_NAME = os.environ.get('DATA_LAKE_BUCKET_NAME', 'cmo-data-lake')


def validate_contract_handler(event, context):
    """Step Functions task: ValidateContract."""
    try:
        result = _service.validate_contract(event)
        logger.info("Contract validated: %s", result.get('contractId'))
        return result
    except ContractValidationError as exc:
        logger.error("Contract validation failed: %s", exc)
        return _error_response(exc, event, "ValidateContract")


def determine_pattern_handler(event, context):
    """Step Functions task: DeterminePattern."""
    pattern = _service.determine_pattern(event)
    logger.info("Determined pattern: %s for contract %s", pattern, event.get('contractId'))
    return {**event, "integrationPattern": pattern}


def configure_glue_connector_handler(event, context):
    """Step Functions task: ConfigureGlueConnector (Pattern 1)."""
    try:
        result = _service.configure_glue_connector(event)
        logger.info("Glue connector configured for %s", event.get('contractId'))
        return result
    except PatternConfigurationError as exc:
        logger.error("Glue connector configuration failed: %s", exc)
        return _error_response(exc, event, "ConfigureGlueConnector")


def provision_sftp_handler(event, context):
    """Step Functions task: ProvisionSFTP (Pattern 2)."""
    try:
        result = _service.provision_sftp(event)
        logger.info("SFTP provisioned for %s", event.get('contractId'))
        return result
    except PatternConfigurationError as exc:
        logger.error("SFTP provisioning failed: %s", exc)
        return _error_response(exc, event, "ProvisionSFTP")


def configure_ai_processing_handler(event, context):
    """Step Functions task: ConfigureAIProcessing (Pattern 3)."""
    try:
        result = _service.configure_ai_processing(event)
        logger.info("AI processing configured for %s", event.get('contractId'))
        return result
    except PatternConfigurationError as exc:
        logger.error("AI processing configuration failed: %s", exc)
        return _error_response(exc, event, "ConfigureAIProcessing")


def create_etl_job_handler(event, context):
    """Step Functions task: CreateETLJob."""
    try:
        result = _service.create_etl_job(event, bucket_name=BUCKET_NAME)
        logger.info("ETL job created for %s", event.get('contractId'))
        return result
    except ETLJobCreationError as exc:
        logger.error("ETL job creation failed: %s", exc)
        return _error_response(exc, event, "CreateETLJob")


def handle_error_handler(event, context):
    """
    Step Functions catch state: log error and build SNS notification.

    This handler is invoked when any step fails after retries are exhausted.
    It logs the error to CloudWatch and returns an SNS notification payload.
    """
    error_info = event.get("error", {})
    cause = event.get("cause", str(error_info))
    step = event.get("step", "unknown")
    contract = event.get("contract", event)

    error = PipelineOrchestrationError(
        message=cause,
        step=step,
        contract_id=contract.get("contractId", "unknown"),
    )

    # Build structured log entry
    log_entry = _service.build_cloudwatch_log_entry(error, contract, step)
    logger.error(json.dumps(log_entry))

    # Build SNS notification
    notification = _service.build_error_notification(error, contract, step)
    notification["topicArn"] = CRITICAL_TOPIC_ARN

    return {
        "status": "failed",
        "notification": notification,
        "logEntry": log_entry,
    }


def handler(event, context):
    """
    Main dispatcher for Step Functions invocations.

    Routes to the appropriate handler based on the 'task' field in the event.
    """
    task = event.get("task", "")

    handlers = {
        "validate_contract": validate_contract_handler,
        "determine_pattern": determine_pattern_handler,
        "configure_glue_connector": configure_glue_connector_handler,
        "provision_sftp": provision_sftp_handler,
        "configure_ai_processing": configure_ai_processing_handler,
        "create_etl_job": create_etl_job_handler,
        "handle_error": handle_error_handler,
    }

    handler_fn = handlers.get(task)
    if handler_fn is None:
        logger.error("Unknown task: %s", task)
        return {"error": f"Unknown task: {task}"}

    # Extract the payload (everything except 'task')
    payload = {k: v for k, v in event.items() if k != "task"}
    return handler_fn(payload, context)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _error_response(error: Exception, contract: dict, step: str) -> dict:
    """Build a standardised error response for Step Functions."""
    return {
        "status": "error",
        "step": step,
        "error": str(error),
        "contractId": contract.get("contractId", "unknown"),
        "contract": contract,
    }
