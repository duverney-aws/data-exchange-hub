"""
IAM Security Service for Pharma Data Exchange Hub

Creates CMO-specific IAM roles with least-privilege permissions.
Each CMO gets a dedicated role scoped to their own S3 prefix,
KMS key, DynamoDB items, and Secrets Manager secrets.

Requirements: 10.1
"""
import boto3
import json
from typing import Optional


class IAMSecurityService:
    """Service for managing CMO-specific IAM roles with least-privilege access."""

    ROLE_NAME_PREFIX = "pharma-hub-cmo"

    def __init__(self, iam_client=None, region: str = "us-east-1"):
        self.iam = iam_client or boto3.client("iam", region_name=region)
        self.region = region

    def create_cmo_role(
        self,
        cmo_id: str,
        account_id: str,
        data_lake_bucket_arn: str,
        kms_key_arn: str,
        cmo_profiles_table_arn: str,
        data_contracts_table_arn: str,
        secrets_prefix_arn: Optional[str] = None,
    ) -> dict:
        """
        Create a CMO-specific IAM role with least-privilege permissions.

        Args:
            cmo_id: CMO identifier (e.g., 'cmo-alpha')
            account_id: AWS account ID
            data_lake_bucket_arn: ARN of the data lake S3 bucket
            kms_key_arn: ARN of the CMO-specific KMS key
            cmo_profiles_table_arn: ARN of the cmo-profiles DynamoDB table
            data_contracts_table_arn: ARN of the data-contracts DynamoDB table
            secrets_prefix_arn: Optional ARN prefix for Secrets Manager

        Returns:
            dict with role_name, role_arn, and attached policies
        """
        if not cmo_id or not cmo_id.startswith("cmo-"):
            raise ValueError(f"Invalid CMO ID format: {cmo_id}. Must start with 'cmo-'")

        role_name = self._get_role_name(cmo_id)

        # Create the IAM role with Lambda trust relationship
        trust_policy = self._build_trust_policy(account_id)
        self.iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description=f"Least-privilege IAM role for CMO {cmo_id}",
            Tags=[
                {"Key": "cmo-id", "Value": cmo_id},
                {"Key": "managed-by", "Value": "pharma-data-exchange-hub"},
            ],
        )

        # Build and attach the inline policy
        policy_document = self._build_cmo_policy(
            cmo_id=cmo_id,
            account_id=account_id,
            data_lake_bucket_arn=data_lake_bucket_arn,
            kms_key_arn=kms_key_arn,
            cmo_profiles_table_arn=cmo_profiles_table_arn,
            data_contracts_table_arn=data_contracts_table_arn,
            secrets_prefix_arn=secrets_prefix_arn,
        )

        policy_name = f"{role_name}-policy"
        self.iam.put_role_policy(
            RoleName=role_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document),
        )

        # Get the role ARN
        role_response = self.iam.get_role(RoleName=role_name)
        role_arn = role_response["Role"]["Arn"]

        return {
            "role_name": role_name,
            "role_arn": role_arn,
            "policy_name": policy_name,
            "cmo_id": cmo_id,
        }

    def get_cmo_role_arn(self, cmo_id: str) -> Optional[str]:
        """Get the IAM role ARN for a specific CMO."""
        role_name = self._get_role_name(cmo_id)
        try:
            response = self.iam.get_role(RoleName=role_name)
            return response["Role"]["Arn"]
        except self.iam.exceptions.NoSuchEntityException:
            return None

    def get_role_policy(self, cmo_id: str) -> Optional[dict]:
        """Get the inline policy document for a CMO role."""
        role_name = self._get_role_name(cmo_id)
        policy_name = f"{role_name}-policy"
        try:
            response = self.iam.get_role_policy(
                RoleName=role_name, PolicyName=policy_name
            )
            return response["PolicyDocument"]
        except self.iam.exceptions.NoSuchEntityException:
            return None

    def _get_role_name(self, cmo_id: str) -> str:
        """Get the IAM role name for a CMO."""
        return f"{self.ROLE_NAME_PREFIX}-{cmo_id}-role"

    def _build_trust_policy(self, account_id: str) -> dict:
        """Build trust policy allowing Lambda service to assume the role."""
        return {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowLambdaAssume",
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                },
                {
                    "Sid": "AllowGlueAssume",
                    "Effect": "Allow",
                    "Principal": {"Service": "glue.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                },
            ],
        }

    def _build_cmo_policy(
        self,
        cmo_id: str,
        account_id: str,
        data_lake_bucket_arn: str,
        kms_key_arn: str,
        cmo_profiles_table_arn: str,
        data_contracts_table_arn: str,
        secrets_prefix_arn: Optional[str] = None,
    ) -> dict:
        """Build least-privilege policy scoped to the CMO's resources."""
        statements = [
            # S3: Only access own CMO prefix in bronze and silver layers
            {
                "Sid": "AllowS3CMOAccess",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                ],
                "Resource": [
                    f"{data_lake_bucket_arn}/bronze/{cmo_id}/*",
                    f"{data_lake_bucket_arn}/silver/{cmo_id}/*",
                ],
            },
            {
                "Sid": "AllowS3ListBucket",
                "Effect": "Allow",
                "Action": "s3:ListBucket",
                "Resource": data_lake_bucket_arn,
                "Condition": {
                    "StringLike": {
                        "s3:prefix": [
                            f"bronze/{cmo_id}/*",
                            f"silver/{cmo_id}/*",
                        ]
                    }
                },
            },
            # KMS: Only use own CMO key
            {
                "Sid": "AllowKMSCMOKeyUsage",
                "Effect": "Allow",
                "Action": [
                    "kms:Decrypt",
                    "kms:DescribeKey",
                    "kms:GenerateDataKey",
                    "kms:GenerateDataKeyWithoutPlaintext",
                ],
                "Resource": kms_key_arn,
            },
            # DynamoDB: Only access own CMO items
            {
                "Sid": "AllowDynamoDBCMOAccess",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                ],
                "Resource": [
                    cmo_profiles_table_arn,
                    data_contracts_table_arn,
                    f"{data_contracts_table_arn}/index/*",
                ],
                "Condition": {
                    "ForAllValues:StringEquals": {
                        "dynamodb:LeadingKeys": [cmo_id]
                    }
                },
            },
            # CloudWatch Logs: Allow writing logs
            {
                "Sid": "AllowCloudWatchLogs",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                "Resource": f"arn:aws:logs:{self.region}:{account_id}:log-group:/pharma-data-exchange/*",
            },
        ]

        # Secrets Manager: Only access own CMO secrets
        if secrets_prefix_arn:
            statements.append(
                {
                    "Sid": "AllowSecretsManagerCMOAccess",
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:GetSecretValue",
                        "secretsmanager:DescribeSecret",
                    ],
                    "Resource": secrets_prefix_arn,
                }
            )
        else:
            statements.append(
                {
                    "Sid": "AllowSecretsManagerCMOAccess",
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:GetSecretValue",
                        "secretsmanager:DescribeSecret",
                    ],
                    "Resource": f"arn:aws:secretsmanager:{self.region}:{account_id}:secret:cmo/{cmo_id}/*",
                }
            )

        return {"Version": "2012-10-17", "Statement": statements}
