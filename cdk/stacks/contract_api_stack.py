"""
Contract API Stack — with Cognito authorizer and approval workflow routes.
"""
from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_events as events,
    aws_events_targets as targets,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subs,
    aws_iam as iam,
    aws_s3_deployment as s3deploy,
)
from aws_cdk import CustomResource, custom_resources as cr
from constructs import Construct


class ContractApiStack(Stack):
    def __init__(self, scope, construct_id, database_stack, cognito_stack, data_lake_stack=None, sftp_ingestion_stack=None, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        self.contract_handler = _lambda.Function(
            self, "ContractApiHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas/contract_api/handler.handler",
            code=_lambda.Code.from_asset("lambda_src"),
            environment={
                "TABLE_NAME": database_stack.data_contracts_table.table_name,
                "CMO_TABLE_NAME": database_stack.cmo_profiles_table.table_name,
                "USER_POOL_ID": cognito_stack.user_pool.user_pool_id,
            },
            timeout=Duration.seconds(30),
            memory_size=256,
        )

        database_stack.data_contracts_table.grant_read_write_data(self.contract_handler)
        database_stack.cmo_profiles_table.grant_read_write_data(self.contract_handler)

        # Allow Lambda to update Cognito user attributes (for CMO org linking)
        from aws_cdk import aws_iam as iam
        self.contract_handler.add_to_role_policy(iam.PolicyStatement(
            actions=["cognito-idp:ListUsers", "cognito-idp:AdminUpdateUserAttributes", "cognito-idp:AdminCreateUser", "cognito-idp:AdminAddUserToGroup"],
            resources=[cognito_stack.user_pool.user_pool_arn],
        ))

        self.api = apigw.RestApi(
            self, "ContractApi",
            rest_api_name="Contract API",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
            binary_media_types=["multipart/form-data", "application/octet-stream"],
        )

        # Cognito authorizer
        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "CognitoAuthorizer",
            cognito_user_pools=[cognito_stack.user_pool],
            authorizer_name="CognitoAuthorizer",
            identity_source="method.request.header.Authorization",
        )
        auth_opts = apigw.MethodOptions(
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )

        integration = apigw.LambdaIntegration(self.contract_handler)
        api = self.api.root.add_resource("api")

        # /api/cmo and /api/cmo/register
        cmo_resource = api.add_resource("cmo")
        cmo_resource.add_method("GET", integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        cmo_resource.add_resource("register").add_method("POST", integration, **auth_opts.__dict__ if False else {
            "authorizer": authorizer,
            "authorization_type": apigw.AuthorizationType.COGNITO,
        })
        cmo_id_resource = cmo_resource.add_resource("{cmoId}")
        cmo_id_resource.add_resource("invite").add_method("POST", integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        cmo_id_resource.add_method("PUT", integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        cmo_id_resource.add_method("DELETE", integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)

        # /api/contract
        contract = api.add_resource("contract")
        contract.add_method("POST", integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        contract.add_method("GET", integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)

        # /api/contract/{contractId}
        cid = contract.add_resource("{contractId}")
        cid.add_method("GET", integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        cid.add_method("PUT", integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)

        # SFTP integration env vars + IAM (Pattern 2)
        if sftp_ingestion_stack and data_lake_stack:
            self.contract_handler.add_environment(
                "SFTP_SERVER_ID", sftp_ingestion_stack.sftp_server.attr_server_id)
            self.contract_handler.add_environment(
                "TRANSFER_ROLE_ARN", sftp_ingestion_stack.transfer_role.role_arn)
            self.contract_handler.add_environment(
                "DATA_LAKE_BUCKET", data_lake_stack.data_lake_bucket.bucket_name)
            self.contract_handler.add_to_role_policy(iam.PolicyStatement(
                actions=["transfer:CreateUser", "transfer:DeleteUser", "transfer:DescribeUser"],
                resources=["*"],
            ))
            self.contract_handler.add_to_role_policy(iam.PolicyStatement(
                actions=["secretsmanager:CreateSecret", "secretsmanager:PutSecretValue",
                         "secretsmanager:GetSecretValue"],
                resources=[f"arn:aws:secretsmanager:*:*:secret:cmo/*"],
            ))
            self.contract_handler.add_to_role_policy(iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[sftp_ingestion_stack.transfer_role.role_arn],
            ))

        # Pipeline status: needs connections table read, S3 list, Glue job runs
        if database_stack:
            database_stack.connections_table.grant_read_data(self.contract_handler)
            self.contract_handler.add_environment(
                "CONNECTION_TABLE_NAME", database_stack.connections_table.table_name)
        if data_lake_stack:
            data_lake_stack.data_lake_bucket.grant_read(self.contract_handler)
        self.contract_handler.add_to_role_policy(iam.PolicyStatement(
            actions=["glue:GetJobRuns", "glue:GetJobRun"],
            resources=["*"],
        ))

        for action in ("submit", "accept", "approve", "reject", "activate", "status"):
            cid.add_resource(action).add_method(
                "GET" if action == "status" else "POST",
                integration,
                authorizer=authorizer,
                authorization_type=apigw.AuthorizationType.COGNITO,
            )

        # --- Batch API ---
        self.batch_handler = _lambda.Function(
            self, "BatchApiHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas/batch_api/handler.handler",
            code=_lambda.Code.from_asset("lambda_src"),
            environment={
                "BATCH_TABLE_NAME": database_stack.batches_table.table_name,
                "CONNECTION_TABLE_NAME": database_stack.connections_table.table_name,
            },
            timeout=Duration.seconds(30),
            memory_size=256,
        )
        database_stack.batches_table.grant_read_write_data(self.batch_handler)
        database_stack.connections_table.grant_read_data(self.batch_handler)
        if data_lake_stack:
            data_lake_stack.data_lake_bucket.grant_read(self.batch_handler)
            self.batch_handler.add_environment(
                "DATA_LAKE_BUCKET", data_lake_stack.data_lake_bucket.bucket_name)

        batch_integration = apigw.LambdaIntegration(self.batch_handler)
        batch = api.add_resource("batch")
        batch.add_method("POST", batch_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        batch.add_method("GET", batch_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        bid = batch.add_resource("{batchId}")
        bid.add_method("GET", batch_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        bid.add_method("PUT", batch_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        bid.add_resource("submit").add_method("POST", batch_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        bid.add_resource("connections").add_method("GET", batch_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        element = bid.add_resource("element").add_resource("{elementType}")
        element.add_resource("view").add_method("GET", batch_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)

        # --- Product API ---
        self.product_handler = _lambda.Function(
            self, "ProductApiHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas/product_api/handler.handler",
            code=_lambda.Code.from_asset("lambda_src"),
            environment={
                "PRODUCT_TABLE_NAME": database_stack.products_table.table_name,
            },
            timeout=Duration.seconds(30),
            memory_size=256,
        )
        database_stack.products_table.grant_read_write_data(self.product_handler)

        product_integration = apigw.LambdaIntegration(self.product_handler)
        product = api.add_resource("product")
        product.add_method("POST", product_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        product.add_method("GET", product_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        pid = product.add_resource("{productId}")
        pid.add_method("GET", product_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        pid.add_method("PUT", product_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)

        # --- Schema Management API ---
        self.schema_mgmt_handler = _lambda.Function(
            self, "SchemaMgmtHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas/schema_mgmt/handler.handler",
            code=_lambda.Code.from_asset("lambda_src"),
            environment={
                "SCHEMA_TABLE_NAME": database_stack.schemas_table.table_name,
                "REGISTRY_NAME": "pharma-data-exchange",
            },
            timeout=Duration.seconds(30),
            memory_size=256,
        )
        database_stack.schemas_table.grant_read_write_data(self.schema_mgmt_handler)
        self.schema_mgmt_handler.add_to_role_policy(iam.PolicyStatement(
            actions=["glue:CreateSchema", "glue:GetSchema", "glue:RegisterSchemaVersion",
                     "glue:GetSchemaVersion", "glue:ListSchemas"],
            resources=["*"],
        ))

        schema_integration = apigw.LambdaIntegration(self.schema_mgmt_handler)
        schema = api.add_resource("schema")
        schema.add_method("POST", schema_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        schema.add_method("GET", schema_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        schema.add_resource("infer").add_method("POST", schema_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        schema_id = schema.add_resource("{schemaId}")
        schema_id.add_method("GET", schema_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        schema_id.add_method("PUT", schema_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        schema_id.add_resource("register").add_method("POST", schema_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)

        # --- Connection API ---
        self.connection_handler = _lambda.Function(
            self, "ConnectionApiHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas/connection_api/handler.handler",
            code=_lambda.Code.from_asset("lambda_src"),
            environment={
                "CONNECTION_TABLE_NAME": database_stack.connections_table.table_name,
            },
            timeout=Duration.seconds(30),
            memory_size=256,
        )
        database_stack.connections_table.grant_read_write_data(self.connection_handler)

        # SFTP env vars for connection activate
        if sftp_ingestion_stack:
            self.connection_handler.add_environment(
                "SFTP_SERVER_ID", sftp_ingestion_stack.sftp_server.attr_server_id)
        if data_lake_stack:
            self.connection_handler.add_environment(
                "DATA_LAKE_BUCKET", data_lake_stack.data_lake_bucket.bucket_name)
        self.connection_handler.add_environment(
            "BATCH_TABLE_NAME", database_stack.batches_table.table_name)
        database_stack.batches_table.grant_read_write_data(self.connection_handler)
        self.connection_handler.add_to_role_policy(iam.PolicyStatement(
            actions=["secretsmanager:CreateSecret", "secretsmanager:PutSecretValue",
                     "secretsmanager:GetSecretValue"],
            resources=[f"arn:aws:secretsmanager:*:*:secret:cmo/*"],
        ))
        # Pattern 1: Glue JDBC connections + ETL job creation
        self.connection_handler.add_to_role_policy(iam.PolicyStatement(
            actions=["glue:CreateConnection", "glue:UpdateConnection",
                     "glue:DeleteConnection", "glue:GetConnection",
                     "glue:CreateJob", "glue:UpdateJob", "glue:GetJob",
                     "glue:CreateTrigger", "glue:UpdateTrigger", "glue:GetTrigger"],
            resources=["*"],
        ))
        # Optional VPC config for Glue connections (set via env vars if needed)
        import os as _os
        _glue_subnet = _os.environ.get("GLUE_SUBNET_ID", "")
        _glue_sg = _os.environ.get("GLUE_SECURITY_GROUP_ID", "")
        if _glue_subnet:
            self.connection_handler.add_environment("GLUE_SUBNET_ID", _glue_subnet)
        if _glue_sg:
            self.connection_handler.add_environment("GLUE_SECURITY_GROUP_ID", _glue_sg)
        if data_lake_stack:
            data_lake_stack.data_lake_bucket.grant_put(self.connection_handler)

        # Glue ETL role (assumed by Glue jobs to read JDBC and write to S3)
        if data_lake_stack:
            glue_etl_role = iam.Role(
                self, "GlueEtlRole",
                assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSGlueServiceRole"),
                ],
            )
            data_lake_stack.data_lake_bucket.grant_read_write(glue_etl_role)
            glue_etl_role.add_to_policy(iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[f"arn:aws:secretsmanager:*:*:secret:cmo/*"],
            ))

            # Upload ETL script to data lake bucket under glue-scripts/
            s3deploy.BucketDeployment(
                self, "GlueScriptDeployment",
                sources=[s3deploy.Source.asset("glue_scripts")],
                destination_bucket=data_lake_stack.data_lake_bucket,
                destination_key_prefix="glue-scripts",
            )
            glue_script_path = (
                f"s3://{data_lake_stack.data_lake_bucket.bucket_name}"
                "/glue-scripts/jdbc_to_bronze.py"
            )
            self.connection_handler.add_environment("GLUE_ETL_ROLE_ARN", glue_etl_role.role_arn)
            self.connection_handler.add_environment("GLUE_SCRIPT_S3_PATH", glue_script_path)

            # Allow connection Lambda to pass the Glue ETL role to Glue
            self.connection_handler.add_to_role_policy(iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[glue_etl_role.role_arn],
            ))

        conn_integration = apigw.LambdaIntegration(self.connection_handler)
        connection = api.add_resource("connection")
        connection.add_method("POST", conn_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        connection.add_method("GET", conn_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        conn_id = connection.add_resource("{connectionId}")
        conn_id.add_method("GET", conn_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        conn_id.add_method("PUT", conn_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        conn_id.add_method("DELETE", conn_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        conn_id.add_resource("activate").add_method("POST", conn_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        conn_id.add_resource("configure").add_method("POST", conn_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)
        conn_id.add_resource("upload").add_method("POST", conn_integration, authorizer=authorizer, authorization_type=apigw.AuthorizationType.COGNITO)

        # --- AI Processor (Pattern 3: Unstructured Data) ---
        if data_lake_stack:
            # SNS topic for Textract async job completion
            textract_topic = sns.Topic(self, "TextractCompletionTopic",
                display_name="Textract Job Completion")

            # IAM role that Textract assumes to publish to SNS and read KMS-encrypted S3 objects
            textract_role = iam.Role(self, "TextractSNSRole",
                assumed_by=iam.ServicePrincipal("textract.amazonaws.com"),
                inline_policies={"TextractSNSPublish": iam.PolicyDocument(statements=[
                    iam.PolicyStatement(actions=["sns:Publish"], resources=[textract_topic.topic_arn]),
                    iam.PolicyStatement(
                        actions=["kms:Decrypt", "kms:GenerateDataKey"],
                        resources=[data_lake_stack.data_lake_kms_key.key_arn],
                    ),
                    iam.PolicyStatement(
                        actions=["s3:GetObject"],
                        resources=[data_lake_stack.data_lake_bucket.bucket_arn + "/*"],
                    ),
                ])},
            )

            self.ai_processor = _lambda.Function(
                self, "AiProcessorHandler",
                runtime=_lambda.Runtime.PYTHON_3_12,
                handler="lambdas/ai_processor/handler.handler",
                code=_lambda.Code.from_asset("lambda_src"),
                environment={
                    "DATA_LAKE_BUCKET": data_lake_stack.data_lake_bucket.bucket_name,
                    "CONFIDENCE_THRESHOLD": "85",
                    "TEXTRACT_SNS_TOPIC_ARN": textract_topic.topic_arn,
                    "TEXTRACT_ROLE_ARN": textract_role.role_arn,
                },
                timeout=Duration.seconds(120),
                memory_size=512,
            )
            data_lake_stack.data_lake_bucket.grant_read_write(self.ai_processor)
            self.ai_processor.add_to_role_policy(iam.PolicyStatement(
                actions=["textract:StartDocumentAnalysis", "textract:GetDocumentAnalysis",
                         "textract:AnalyzeDocument", "textract:DetectDocumentText"],
                resources=["*"],
            ))
            self.ai_processor.add_to_role_policy(iam.PolicyStatement(
                actions=["rekognition:DetectLabels", "rekognition:DetectText"],
                resources=["*"],
            ))
            self.ai_processor.add_to_role_policy(iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[textract_role.role_arn],
            ))

            # Textract result processor — triggered by SNS when job completes
            textract_result_processor = _lambda.Function(
                self, "TextractResultProcessor",
                runtime=_lambda.Runtime.PYTHON_3_12,
                handler="lambdas/textract_result_processor/handler.handler",
                code=_lambda.Code.from_asset("lambda_src"),
                environment={
                    "DATA_LAKE_BUCKET": data_lake_stack.data_lake_bucket.bucket_name,
                    "CONFIDENCE_THRESHOLD": "85",
                    "BATCH_TABLE_NAME": database_stack.batches_table.table_name,
                },
                timeout=Duration.seconds(300),
                memory_size=512,
            )
            data_lake_stack.data_lake_bucket.grant_read_write(textract_result_processor)
            database_stack.batches_table.grant_read_write_data(textract_result_processor)
            textract_result_processor.add_to_role_policy(iam.PolicyStatement(
                actions=["textract:GetDocumentAnalysis"],
                resources=["*"],
            ))
            textract_topic.add_subscription(sns_subs.LambdaSubscription(textract_result_processor))

            # Allow S3 to invoke AI processor
            bucket_arn = data_lake_stack.data_lake_bucket.bucket_arn
            self.ai_processor.add_permission(
                "AllowS3InvokeAI",
                principal=iam.ServicePrincipal("s3.amazonaws.com"),
                source_arn=bucket_arn,
            )

            # S3 event notification for AI file types
            ai_notifier = _lambda.Function(
                self, "AiS3NotifSetup",
                runtime=_lambda.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=_lambda.Code.from_inline(_AI_S3_NOTIFIER_CODE),
                timeout=Duration.seconds(60),
            )
            ai_notifier.add_to_role_policy(iam.PolicyStatement(
                actions=["s3:GetBucketNotification*", "s3:PutBucketNotification*"],
                resources=[bucket_arn],
            ))
            ai_provider = cr.Provider(self, "AiS3NotifProvider", on_event_handler=ai_notifier)
            CustomResource(
                self, "AiS3NotifCR",
                service_token=ai_provider.service_token,
                properties={
                    "BucketName": data_lake_stack.data_lake_bucket.bucket_name,
                    "LambdaArn": self.ai_processor.function_arn,
                    "Prefix": "bronze/",
                    "Suffixes": ".pdf,.png,.jpg,.jpeg,.tiff",
                },
            )

        # --- SLA Checker (EventBridge daily) ---
        self.sla_checker = _lambda.Function(
            self, "SlaCheckerHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas/sla_checker/handler.handler",
            code=_lambda.Code.from_asset("lambda_src"),
            environment={
                "BATCH_TABLE_NAME": database_stack.batches_table.table_name,
                "CONTRACT_TABLE_NAME": database_stack.data_contracts_table.table_name,
            },
            timeout=Duration.seconds(120),
            memory_size=256,
        )
        database_stack.batches_table.grant_read_write_data(self.sla_checker)
        database_stack.data_contracts_table.grant_read_data(self.sla_checker)

        events.Rule(
            self, "SlaCheckerSchedule",
            schedule=events.Schedule.cron(hour="6", minute="0"),
            targets=[targets.LambdaFunction(self.sla_checker)],
        )

        # Manual trigger endpoint: POST /api/sla-check (merck-admins only, handled by same Lambda)
        sla_integration = apigw.LambdaIntegration(self.sla_checker)
        api.add_resource("sla-check").add_method(
            "POST", sla_integration,
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
        )


_AI_S3_NOTIFIER_CODE = '''
import json, boto3
s3 = boto3.client("s3")

def handler(event, context):
    props = event["ResourceProperties"]
    bucket = props["BucketName"]
    lambda_arn = props["LambdaArn"]
    prefix = props["Prefix"]
    suffixes = props["Suffixes"].split(",")

    if event["RequestType"] == "Delete":
        cfg = s3.get_bucket_notification_configuration(Bucket=bucket)
        cfg.pop("ResponseMetadata", None)
        cfg["LambdaFunctionConfigurations"] = [
            c for c in cfg.get("LambdaFunctionConfigurations", [])
            if c.get("LambdaFunctionArn") != lambda_arn
        ]
        s3.put_bucket_notification_configuration(Bucket=bucket, NotificationConfiguration=cfg)
        return {"PhysicalResourceId": f"ai-notif-{bucket}"}

    cfg = s3.get_bucket_notification_configuration(Bucket=bucket)
    cfg.pop("ResponseMetadata", None)
    existing = [c for c in cfg.get("LambdaFunctionConfigurations", [])
                if c.get("LambdaFunctionArn") != lambda_arn]

    for suffix in suffixes:
        existing.append({
            "Id": f"ai-{suffix.replace(\'.\', \'\')}",
            "LambdaFunctionArn": lambda_arn,
            "Events": ["s3:ObjectCreated:*"],
            "Filter": {"Key": {"FilterRules": [
                {"Name": "prefix", "Value": prefix},
                {"Name": "suffix", "Value": suffix},
            ]}},
        })

    cfg["LambdaFunctionConfigurations"] = existing
    s3.put_bucket_notification_configuration(Bucket=bucket, NotificationConfiguration=cfg)
    return {"PhysicalResourceId": f"ai-notif-{bucket}"}
'''
