"""
Natural Language Query Stack

Routes:
    POST /api/query - Submit a natural language query (Bedrock + Athena)

Requirements: 12.1, 12.2, 12.3, 12.4, 12.6
"""
from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_iam as iam,
)
from constructs import Construct


class NLQueryStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        data_lake_stack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.nl_query_handler = _lambda.Function(
            self,
            "NLQueryHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas/nl_query/handler.handler",
            code=_lambda.Code.from_asset("lambda_src"),
            environment={
                "DATABASE_NAME": "cmo_data_lake",
                "ATHENA_WORKGROUP": "cmo-workgroup",
                "RESULTS_LOCATION": f"s3://{data_lake_stack.athena_results_bucket.bucket_name}/",
                "BEDROCK_MODEL_ID": "anthropic.claude-3-sonnet-20240229-v1:0",
            },
            timeout=Duration.seconds(60),
            memory_size=512,
        )

        # Bedrock access
        self.nl_query_handler.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=["*"],
        ))

        # Athena + Glue + S3 access
        self.nl_query_handler.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "athena:StartQueryExecution",
                "athena:GetQueryExecution",
                "athena:GetQueryResults",
                "glue:GetDatabase",
                "glue:GetTable",
                "glue:GetTables",
                "lakeformation:GetDataAccess",
                "lakeformation:ListPermissions",
                "lakeformation:GetEffectivePermissionsForPath",
            ],
            resources=["*"],
        ))

        data_lake_stack.data_lake_bucket.grant_read(self.nl_query_handler)
        data_lake_stack.athena_results_bucket.grant_read_write(self.nl_query_handler)

        self.api = apigw.RestApi(
            self,
            "NLQueryApi",
            rest_api_name="NL Query API",
            description="Natural Language Query API",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
            ),
        )

        integration = apigw.LambdaIntegration(self.nl_query_handler)

        api_resource = self.api.root.add_resource("api")
        api_resource.add_resource("query").add_method("POST", integration)
