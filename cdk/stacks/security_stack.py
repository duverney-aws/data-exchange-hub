"""
Security Stack for Pharma Data Exchange Hub

Provides CMO-specific KMS keys and IAM roles with least-privilege permissions.
Uses a factory pattern since CMOs are onboarded dynamically.

This stack creates:
- Helper constructs for provisioning CMO-specific KMS keys
- Helper constructs for provisioning CMO-specific IAM roles
- A sample CMO security setup to demonstrate the pattern

Requirements: 9.7, 10.1
"""
from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_kms as kms,
    aws_iam as iam,
)
from constructs import Construct
from typing import Optional


class CMOSecurityConstruct(Construct):
    """
    Construct that provisions a CMO-specific KMS key and IAM role.

    Creates:
    - KMS key with alias: alias/cmo/{cmo-id}/data-lake
    - IAM role: pharma-hub-cmo-{cmo-id}-role
    - Least-privilege policy scoped to CMO resources
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        cmo_id: str,
        data_lake_bucket_arn: str,
        cmo_profiles_table_arn: str,
        data_contracts_table_arn: str,
        secrets_kms_key_arn: Optional[str] = None,
    ) -> None:
        super().__init__(scope, construct_id)

        self.cmo_id = cmo_id
        account_id = Stack.of(self).account
        region = Stack.of(self).region

        # --- CMO-specific KMS Key ---
        self.kms_key = kms.Key(
            self,
            "CMODataLakeKey",
            description=f"CMO-specific data lake encryption key for {cmo_id}",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.kms_key.add_alias(f"alias/cmo/{cmo_id}/data-lake")

        # Allow S3 service to use the key
        self.kms_key.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowS3ServiceUsage",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("s3.amazonaws.com")],
                actions=[
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                    "kms:GenerateDataKeyWithoutPlaintext",
                ],
                resources=["*"],
                conditions={
                    "StringEquals": {
                        "kms:ViaService": f"s3.{region}.amazonaws.com",
                    }
                },
            )
        )

        # --- CMO-specific IAM Role ---
        self.role = iam.Role(
            self,
            "CMORole",
            role_name=f"pharma-hub-cmo-{cmo_id}-role",
            description=f"Least-privilege IAM role for CMO {cmo_id}",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("lambda.amazonaws.com"),
                iam.ServicePrincipal("glue.amazonaws.com"),
            ),
        )

        # S3: Only access own CMO prefix in bronze and silver
        self.role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowS3CMOObjectAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                ],
                resources=[
                    f"{data_lake_bucket_arn}/bronze/{cmo_id}/*",
                    f"{data_lake_bucket_arn}/silver/{cmo_id}/*",
                ],
            )
        )

        self.role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowS3ListBucket",
                effect=iam.Effect.ALLOW,
                actions=["s3:ListBucket"],
                resources=[data_lake_bucket_arn],
                conditions={
                    "StringLike": {
                        "s3:prefix": [
                            f"bronze/{cmo_id}/*",
                            f"silver/{cmo_id}/*",
                        ]
                    }
                },
            )
        )

        # KMS: Only use own CMO key
        self.role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowKMSCMOKeyUsage",
                effect=iam.Effect.ALLOW,
                actions=[
                    "kms:Decrypt",
                    "kms:DescribeKey",
                    "kms:GenerateDataKey",
                    "kms:GenerateDataKeyWithoutPlaintext",
                ],
                resources=[self.kms_key.key_arn],
            )
        )

        # DynamoDB: Only access own CMO items
        self.role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowDynamoDBCMOAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                ],
                resources=[
                    cmo_profiles_table_arn,
                    data_contracts_table_arn,
                    f"{data_contracts_table_arn}/index/*",
                ],
                conditions={
                    "ForAllValues:StringEquals": {
                        "dynamodb:LeadingKeys": [cmo_id]
                    }
                },
            )
        )

        # Secrets Manager: Only access own CMO secrets
        self.role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowSecretsManagerCMOAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=[
                    f"arn:aws:secretsmanager:{region}:{account_id}:secret:cmo/{cmo_id}/*"
                ],
            )
        )

        # CloudWatch Logs
        self.role.add_to_policy(
            iam.PolicyStatement(
                sid="AllowCloudWatchLogs",
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{region}:{account_id}:log-group:/pharma-data-exchange/*"
                ],
            )
        )

        # Grant the CMO role usage of its KMS key
        self.kms_key.grant_encrypt_decrypt(self.role)


class SecurityStack(Stack):
    """
    Stack for CMO-specific security resources.

    Provides a factory method to create CMO security constructs
    and demonstrates the pattern with sample CMOs.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        data_lake_stack,
        database_stack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.data_lake_bucket_arn = data_lake_stack.data_lake_bucket.bucket_arn
        self.cmo_profiles_table_arn = database_stack.cmo_profiles_table.table_arn
        self.data_contracts_table_arn = database_stack.data_contracts_table.table_arn

        # Store created CMO security constructs
        self.cmo_security: dict[str, CMOSecurityConstruct] = {}

    def add_cmo_security(self, cmo_id: str) -> CMOSecurityConstruct:
        """
        Factory method to create security resources for a new CMO.

        Args:
            cmo_id: CMO identifier (e.g., 'cmo-alpha')

        Returns:
            CMOSecurityConstruct with KMS key and IAM role
        """
        construct_id = f"CMOSecurity-{cmo_id}"
        cmo_security = CMOSecurityConstruct(
            self,
            construct_id,
            cmo_id=cmo_id,
            data_lake_bucket_arn=self.data_lake_bucket_arn,
            cmo_profiles_table_arn=self.cmo_profiles_table_arn,
            data_contracts_table_arn=self.data_contracts_table_arn,
        )
        self.cmo_security[cmo_id] = cmo_security
        return cmo_security
