"""
Schema API Stack

Routes:
    POST /api/schema/infer    - Infer schema from sample file
    POST /api/schema/register - Register schema in Glue Schema Registry

Requirements: 2.2, 2.3
"""
from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_iam as iam,
)
from constructs import Construct


class SchemaApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.schema_handler = _lambda.Function(
            self,
            "SchemaApiHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas/schema_api/handler.handler",
            code=_lambda.Code.from_asset("lambda_src"),
            environment={
                "REGISTRY_NAME": "pharma-data-exchange",
            },
            timeout=Duration.seconds(30),
            memory_size=256,
        )

        self.schema_handler.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "glue:CreateRegistry",
                "glue:CreateSchema",
                "glue:UpdateSchema",
                "glue:GetSchema",
                "glue:GetSchemaVersion",
                "glue:RegisterSchemaVersion",
                "glue:GetRegistry",
                "glue:ListRegistries",
                "glue:ListSchemas",
                "glue:ListSchemaVersions",
            ],
            resources=["*"],
        ))

        self.api = apigw.RestApi(
            self,
            "SchemaApi",
            rest_api_name="Schema API",
            description="Schema Inference and Registration API",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
            ),
            binary_media_types=["multipart/form-data", "application/octet-stream"],
        )

        integration = apigw.LambdaIntegration(self.schema_handler)

        api_resource = self.api.root.add_resource("api")
        schema_resource = api_resource.add_resource("schema")
        schema_resource.add_resource("infer").add_method("POST", integration)
        schema_resource.add_resource("register").add_method("POST", integration)
