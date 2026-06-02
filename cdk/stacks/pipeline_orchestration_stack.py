"""
Pipeline Orchestration Stack

Defines the AWS Step Functions state machine and Lambda functions for
automated pipeline deployment from data contracts.

Workflow states:
  ValidateContract -> DeterminePattern -> (Pattern branch) -> CreateETLJob -> Done
  Any failure -> HandleError (log + SNS notification)

Retry: 3 attempts with exponential backoff on each Task state.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.8, 15.1, 15.2
"""
from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_iam as iam,
    aws_logs as logs,
)
from constructs import Construct


class PipelineOrchestrationStack(Stack):
    """Stack for Step Functions pipeline deployment workflow."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        database_stack,
        data_lake_stack,
        monitoring_stack,
        secrets_stack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ----------------------------------------------------------
        # Lambda function for all orchestration tasks
        # ----------------------------------------------------------
        self.orchestration_handler = _lambda.Function(
            self,
            "PipelineOrchestrationHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas/pipeline_orchestration/handler.handler",
            code=_lambda.Code.from_asset("lambda_src"),
            environment={
                "CONTRACTS_TABLE_NAME": database_stack.data_contracts_table.table_name,
                "EXECUTIONS_TABLE_NAME": database_stack.pipeline_executions_table.table_name,
                "DATA_LAKE_BUCKET_NAME": data_lake_stack.data_lake_bucket.bucket_name,
                "CRITICAL_ALERTS_TOPIC_ARN": monitoring_stack.critical_alerts_topic.topic_arn,
                "WARNING_ALERTS_TOPIC_ARN": monitoring_stack.warning_alerts_topic.topic_arn,
            },
            timeout=Duration.seconds(60),
            memory_size=256,
        )

        # Grant permissions
        database_stack.data_contracts_table.grant_read_data(self.orchestration_handler)
        database_stack.pipeline_executions_table.grant_read_write_data(self.orchestration_handler)
        data_lake_stack.data_lake_bucket.grant_read_write(self.orchestration_handler)
        monitoring_stack.critical_alerts_topic.grant_publish(self.orchestration_handler)
        monitoring_stack.warning_alerts_topic.grant_publish(self.orchestration_handler)

        # ----------------------------------------------------------
        # Retry configuration: 3 attempts, exponential backoff
        # ----------------------------------------------------------
        retry_config = sfn.RetryProps(
            errors=["States.ALL"],
            max_attempts=3,
            interval=Duration.seconds(1),
            backoff_rate=2.0,
        )

        # ----------------------------------------------------------
        # Step Functions task definitions
        # ----------------------------------------------------------

        validate_contract = tasks.LambdaInvoke(
            self,
            "ValidateContract",
            lambda_function=self.orchestration_handler,
            payload=sfn.TaskInput.from_object({
                "task": "validate_contract",
                "contractId": sfn.JsonPath.string_at("$.contractId"),
                "cmoId": sfn.JsonPath.string_at("$.cmoId"),
                "dataDomain": sfn.JsonPath.string_at("$.dataDomain"),
                "integrationPattern": sfn.JsonPath.string_at("$.integrationPattern"),
                "status": sfn.JsonPath.string_at("$.status"),
                "qualityRules": sfn.JsonPath.string_at("$.qualityRules"),
                "connectionConfig": sfn.JsonPath.string_at("$.connectionConfig"),
                "aiConfig": sfn.JsonPath.string_at("$.aiConfig"),
                "deliverySchedule": sfn.JsonPath.string_at("$.deliverySchedule"),
            }),
            result_path="$.taskResult",
            retry_on_service_exceptions=True,
        )
        validate_contract.add_retry(**_retry_kwargs())

        configure_glue_connector = tasks.LambdaInvoke(
            self,
            "ConfigureGlueConnector",
            lambda_function=self.orchestration_handler,
            payload=sfn.TaskInput.from_object({
                "task": "configure_glue_connector",
                "contractId": sfn.JsonPath.string_at("$.taskResult.Payload.contractId"),
                "cmoId": sfn.JsonPath.string_at("$.taskResult.Payload.cmoId"),
                "dataDomain": sfn.JsonPath.string_at("$.taskResult.Payload.dataDomain"),
                "integrationPattern": sfn.JsonPath.string_at("$.taskResult.Payload.integrationPattern"),
                "connectionConfig": sfn.JsonPath.string_at("$.taskResult.Payload.connectionConfig"),
                "qualityRules": sfn.JsonPath.string_at("$.taskResult.Payload.qualityRules"),
                "deliverySchedule": sfn.JsonPath.string_at("$.taskResult.Payload.deliverySchedule"),
                "status": sfn.JsonPath.string_at("$.taskResult.Payload.status"),
            }),
            result_path="$.patternResult",
            retry_on_service_exceptions=True,
        )
        configure_glue_connector.add_retry(**_retry_kwargs())

        provision_sftp = tasks.LambdaInvoke(
            self,
            "ProvisionSFTP",
            lambda_function=self.orchestration_handler,
            payload=sfn.TaskInput.from_object({
                "task": "provision_sftp",
                "contractId": sfn.JsonPath.string_at("$.taskResult.Payload.contractId"),
                "cmoId": sfn.JsonPath.string_at("$.taskResult.Payload.cmoId"),
                "dataDomain": sfn.JsonPath.string_at("$.taskResult.Payload.dataDomain"),
                "integrationPattern": sfn.JsonPath.string_at("$.taskResult.Payload.integrationPattern"),
                "qualityRules": sfn.JsonPath.string_at("$.taskResult.Payload.qualityRules"),
                "deliverySchedule": sfn.JsonPath.string_at("$.taskResult.Payload.deliverySchedule"),
                "status": sfn.JsonPath.string_at("$.taskResult.Payload.status"),
            }),
            result_path="$.patternResult",
            retry_on_service_exceptions=True,
        )
        provision_sftp.add_retry(**_retry_kwargs())

        configure_ai = tasks.LambdaInvoke(
            self,
            "ConfigureAIProcessing",
            lambda_function=self.orchestration_handler,
            payload=sfn.TaskInput.from_object({
                "task": "configure_ai_processing",
                "contractId": sfn.JsonPath.string_at("$.taskResult.Payload.contractId"),
                "cmoId": sfn.JsonPath.string_at("$.taskResult.Payload.cmoId"),
                "dataDomain": sfn.JsonPath.string_at("$.taskResult.Payload.dataDomain"),
                "integrationPattern": sfn.JsonPath.string_at("$.taskResult.Payload.integrationPattern"),
                "qualityRules": sfn.JsonPath.string_at("$.taskResult.Payload.qualityRules"),
                "deliverySchedule": sfn.JsonPath.string_at("$.taskResult.Payload.deliverySchedule"),
                "status": sfn.JsonPath.string_at("$.taskResult.Payload.status"),
            }),
            result_path="$.patternResult",
            retry_on_service_exceptions=True,
        )
        configure_ai.add_retry(**_retry_kwargs())

        create_etl_job = tasks.LambdaInvoke(
            self,
            "CreateETLJob",
            lambda_function=self.orchestration_handler,
            payload=sfn.TaskInput.from_object({
                "task": "create_etl_job",
                "contractId": sfn.JsonPath.string_at("$.taskResult.Payload.contractId"),
                "cmoId": sfn.JsonPath.string_at("$.taskResult.Payload.cmoId"),
                "dataDomain": sfn.JsonPath.string_at("$.taskResult.Payload.dataDomain"),
                "integrationPattern": sfn.JsonPath.string_at("$.taskResult.Payload.integrationPattern"),
                "qualityRules": sfn.JsonPath.string_at("$.taskResult.Payload.qualityRules"),
                "deliverySchedule": sfn.JsonPath.string_at("$.taskResult.Payload.deliverySchedule"),
                "status": sfn.JsonPath.string_at("$.taskResult.Payload.status"),
            }),
            result_path="$.etlResult",
            retry_on_service_exceptions=True,
        )
        create_etl_job.add_retry(**_retry_kwargs())

        # Error handler
        handle_error = tasks.LambdaInvoke(
            self,
            "HandleError",
            lambda_function=self.orchestration_handler,
            payload=sfn.TaskInput.from_object({
                "task": "handle_error",
                "error": sfn.JsonPath.string_at("$.error"),
                "cause": sfn.JsonPath.string_at("$.cause"),
            }),
            result_path="$.errorResult",
        )

        deployment_failed = sfn.Fail(
            self,
            "DeploymentFailed",
            cause="Pipeline deployment failed after retries",
            error="PipelineDeploymentError",
        )

        deployment_succeeded = sfn.Succeed(
            self,
            "DeploymentSucceeded",
        )

        # ----------------------------------------------------------
        # Pattern choice
        # ----------------------------------------------------------
        # Chain shared states: CreateETLJob -> DeploymentSucceeded
        etl_then_success = create_etl_job.next(deployment_succeeded)

        determine_pattern = sfn.Choice(self, "DeterminePattern")

        determine_pattern.when(
            sfn.Condition.string_equals(
                "$.taskResult.Payload.integrationPattern", "native-connector"
            ),
            configure_glue_connector.next(etl_then_success),
        )
        determine_pattern.when(
            sfn.Condition.string_equals(
                "$.taskResult.Payload.integrationPattern", "secure-transfer"
            ),
            provision_sftp.next(etl_then_success),
        )
        determine_pattern.when(
            sfn.Condition.string_equals(
                "$.taskResult.Payload.integrationPattern", "ai-unstructured"
            ),
            configure_ai.next(etl_then_success),
        )
        determine_pattern.otherwise(deployment_failed)

        # ----------------------------------------------------------
        # Chain: Validate -> DeterminePattern -> ...
        # ----------------------------------------------------------
        definition = validate_contract.next(determine_pattern)

        # ----------------------------------------------------------
        # State machine
        # ----------------------------------------------------------
        self.state_machine = sfn.StateMachine(
            self,
            "PipelineDeploymentStateMachine",
            state_machine_name="PipelineDeploymentWorkflow",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.minutes(30),
            tracing_enabled=True,
            logs=sfn.LogOptions(
                destination=monitoring_stack.pipeline_log_group,
                level=sfn.LogLevel.ALL,
            ),
        )


def _retry_kwargs() -> dict:
    """Return retry configuration kwargs for add_retry()."""
    return {
        "errors": ["States.ALL"],
        "max_attempts": 3,
        "interval": Duration.seconds(1),
        "backoff_rate": 2.0,
    }
