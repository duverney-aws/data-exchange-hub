"""
SFTP Ingestion Stack — Pattern 2: Secure File Transfer

Deploys:
- Custom identity provider Lambda (password auth via Secrets Manager)
- AWS Transfer Family SFTP server with AWS_LAMBDA identity provider
- IAM role for Transfer Family → S3 access
- Lambda for processing files uploaded via SFTP
- S3 event notification wired via custom resource
"""
from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    CustomResource,
    custom_resources as cr,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_transfer as transfer,
)
from constructs import Construct


class SFTPIngestionStack(Stack):
    def __init__(self, scope, construct_id, data_lake_stack, database_stack, secrets_stack, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        bucket = data_lake_stack.data_lake_bucket
        bucket_arn = bucket.bucket_arn

        # IAM role for Transfer Family users → S3 access
        self.transfer_role = iam.Role(
            self, "TransferFamilyRole",
            assumed_by=iam.ServicePrincipal("transfer.amazonaws.com"),
        )
        bucket.grant_read_write(self.transfer_role)

        # --- Custom Identity Provider Lambda (password auth) ---
        self.auth_handler = _lambda.Function(
            self, "SFTPAuthHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas/sftp_auth/handler.handler",
            code=_lambda.Code.from_asset("lambda_src"),
            environment={
                "TRANSFER_ROLE_ARN": self.transfer_role.role_arn,
                "DATA_LAKE_BUCKET": bucket.bucket_name,
            },
            timeout=Duration.seconds(10),
            memory_size=128,
        )
        # Auth Lambda needs to read secrets
        self.auth_handler.add_to_role_policy(iam.PolicyStatement(
            actions=["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
            resources=[f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:cmo/*"],
        ))

        # Allow Transfer Family to invoke the auth Lambda
        self.auth_handler.add_permission(
            "AllowTransferInvoke",
            principal=iam.ServicePrincipal("transfer.amazonaws.com"),
        )

        # IAM role for Transfer Family to invoke the auth Lambda
        idp_role = iam.Role(
            self, "TransferIdPRole",
            assumed_by=iam.ServicePrincipal("transfer.amazonaws.com"),
        )
        self.auth_handler.grant_invoke(idp_role)

        # --- Transfer Family SFTP server with custom identity provider ---
        self.sftp_server = transfer.CfnServer(
            self, "SFTPServer",
            protocols=["SFTP"],
            identity_provider_type="AWS_LAMBDA",
            identity_provider_details=transfer.CfnServer.IdentityProviderDetailsProperty(
                function=self.auth_handler.function_arn,
            ),
            endpoint_type="PUBLIC",
            tags=[{"key": "Project", "value": "PharmaDataExchange"}],
        )

        CfnOutput(self, "SFTPServerId", value=self.sftp_server.attr_server_id)
        CfnOutput(self, "SFTPEndpoint",
                  value=f"{self.sftp_server.attr_server_id}.server.transfer.us-east-1.amazonaws.com")

        # --- File processor Lambda ---
        self.sftp_processor = _lambda.Function(
            self, "SFTPFileProcessor",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="lambdas/sftp_processor/handler.handler",
            code=_lambda.Code.from_asset("lambda_src"),
            environment={
                "DATA_LAKE_BUCKET": bucket.bucket_name,
                "CONTRACTS_TABLE": database_stack.data_contracts_table.table_name,
                "BATCHES_TABLE": database_stack.batches_table.table_name,
            },
            timeout=Duration.seconds(60),
            memory_size=256,
        )
        bucket.grant_read_write(self.sftp_processor)
        database_stack.data_contracts_table.grant_read_data(self.sftp_processor)
        database_stack.batches_table.grant_read_write_data(self.sftp_processor)

        # Allow S3 to invoke the processor Lambda
        self.sftp_processor.add_permission(
            "AllowS3Invoke",
            principal=iam.ServicePrincipal("s3.amazonaws.com"),
            source_arn=bucket_arn,
        )

        # --- S3 event notifications via custom resource ---
        notifier = _lambda.Function(
            self, "S3NotificationSetup",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=_lambda.Code.from_inline(_S3_NOTIFIER_CODE),
            timeout=Duration.seconds(60),
        )
        notifier.add_to_role_policy(iam.PolicyStatement(
            actions=["s3:GetBucketNotification*", "s3:PutBucketNotification*"],
            resources=[bucket_arn],
        ))

        provider = cr.Provider(self, "S3NotifProvider", on_event_handler=notifier)
        CustomResource(
            self, "S3NotifCR",
            service_token=provider.service_token,
            properties={
                "BucketName": bucket.bucket_name,
                "LambdaArn": self.sftp_processor.function_arn,
                "Prefix": "bronze/",
                "Suffixes": ".csv,.json,.parquet",
            },
        )


_S3_NOTIFIER_CODE = '''
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
        return {"PhysicalResourceId": f"s3-notif-{bucket}"}

    cfg = s3.get_bucket_notification_configuration(Bucket=bucket)
    cfg.pop("ResponseMetadata", None)
    existing = [c for c in cfg.get("LambdaFunctionConfigurations", [])
                if c.get("LambdaFunctionArn") != lambda_arn]

    for suffix in suffixes:
        existing.append({
            "Id": f"sftp-{suffix.replace('.', '')}",
            "LambdaFunctionArn": lambda_arn,
            "Events": ["s3:ObjectCreated:*"],
            "Filter": {"Key": {"FilterRules": [
                {"Name": "prefix", "Value": prefix},
                {"Name": "suffix", "Value": suffix},
            ]}},
        })

    cfg["LambdaFunctionConfigurations"] = existing
    s3.put_bucket_notification_configuration(Bucket=bucket, NotificationConfiguration=cfg)
    return {"PhysicalResourceId": f"s3-notif-{bucket}"}
'''
