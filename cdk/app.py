#!/usr/bin/env python3
"""Pharma Data Exchange Hub - CDK Application Entry Point"""
import aws_cdk as cdk
from stacks.cognito_stack import CognitoStack
from stacks.data_lake_stack import DataLakeStack
from stacks.database_stack import DatabaseStack
from stacks.secrets_stack import SecretsStack
from stacks.monitoring_stack import MonitoringStack
from stacks.contract_api_stack import ContractApiStack
from stacks.schema_api_stack import SchemaApiStack
from stacks.nl_query_stack import NLQueryStack
from stacks.pipeline_orchestration_stack import PipelineOrchestrationStack
from stacks.security_stack import SecurityStack
from stacks.audit_compliance_stack import AuditComplianceStack
from stacks.sftp_ingestion_stack import SFTPIngestionStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1"
)

secrets_stack = SecretsStack(app, "PharmaDataExchangeSecretsStack", env=env)
database_stack = DatabaseStack(app, "PharmaDataExchangeDatabaseStack", env=env)
data_lake_stack = DataLakeStack(app, "PharmaDataExchangeDataLakeStack", env=env)
monitoring_stack = MonitoringStack(app, "PharmaDataExchangeMonitoringStack", env=env)
cognito_stack = CognitoStack(app, "PharmaDataExchangeCognitoStack", env=env)

sftp_ingestion_stack = SFTPIngestionStack(
    app, "PharmaDataExchangeSFTPIngestionStack",
    data_lake_stack=data_lake_stack,
    database_stack=database_stack,
    secrets_stack=secrets_stack,
    env=env,
)

contract_api_stack = ContractApiStack(
    app, "PharmaDataExchangeContractApiStack",
    database_stack=database_stack,
    cognito_stack=cognito_stack,
    data_lake_stack=data_lake_stack,
    sftp_ingestion_stack=sftp_ingestion_stack,
    env=env,
)

schema_api_stack = SchemaApiStack(app, "PharmaDataExchangeSchemaApiStack", env=env)

nl_query_stack = NLQueryStack(
    app, "PharmaDataExchangeNLQueryStack",
    data_lake_stack=data_lake_stack,
    env=env,
)

pipeline_orchestration_stack = PipelineOrchestrationStack(
    app, "PharmaDataExchangePipelineOrchestrationStack",
    database_stack=database_stack,
    data_lake_stack=data_lake_stack,
    monitoring_stack=monitoring_stack,
    secrets_stack=secrets_stack,
    env=env,
)

security_stack = SecurityStack(
    app, "PharmaDataExchangeSecurityStack",
    data_lake_stack=data_lake_stack,
    database_stack=database_stack,
    env=env,
)

audit_compliance_stack = AuditComplianceStack(
    app, "PharmaDataExchangeAuditComplianceStack",
    data_lake_stack=data_lake_stack,
    env=env,
)


database_stack.add_dependency(secrets_stack)
data_lake_stack.add_dependency(database_stack)
monitoring_stack.add_dependency(data_lake_stack)
contract_api_stack.add_dependency(database_stack)
contract_api_stack.add_dependency(cognito_stack)
contract_api_stack.add_dependency(sftp_ingestion_stack)
schema_api_stack.add_dependency(data_lake_stack)
nl_query_stack.add_dependency(data_lake_stack)
pipeline_orchestration_stack.add_dependency(database_stack)
pipeline_orchestration_stack.add_dependency(data_lake_stack)
pipeline_orchestration_stack.add_dependency(monitoring_stack)
pipeline_orchestration_stack.add_dependency(secrets_stack)
security_stack.add_dependency(data_lake_stack)
security_stack.add_dependency(database_stack)
audit_compliance_stack.add_dependency(data_lake_stack)

app.synth()

sftp_ingestion_stack.add_dependency(data_lake_stack)
sftp_ingestion_stack.add_dependency(database_stack)
sftp_ingestion_stack.add_dependency(secrets_stack)
