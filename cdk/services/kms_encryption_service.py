"""
KMS Encryption Service for Pharma Data Exchange Hub

Provides CMO-specific customer-managed KMS keys for data encryption.
Each CMO gets a dedicated KMS key with automatic rotation enabled,
ensuring data isolation at the encryption layer.

Requirements: 9.7
"""
import boto3
import json
from typing import Optional


class KMSEncryptionService:
    """Service for managing CMO-specific KMS encryption keys."""

    def __init__(self, kms_client=None, region: str = "us-east-1"):
        self.kms = kms_client or boto3.client("kms", region_name=region)
        self.region = region

    def create_cmo_kms_key(
        self,
        cmo_id: str,
        account_id: str,
        cmo_role_arn: Optional[str] = None,
    ) -> dict:
        """
        Create a CMO-specific KMS key with rotation enabled.

        Args:
            cmo_id: CMO identifier (e.g., 'cmo-alpha')
            account_id: AWS account ID for key policy
            cmo_role_arn: Optional IAM role ARN to grant usage

        Returns:
            dict with key_id, key_arn, and alias
        """
        if not cmo_id or not cmo_id.startswith("cmo-"):
            raise ValueError(f"Invalid CMO ID format: {cmo_id}. Must start with 'cmo-'")

        key_policy = self._build_key_policy(account_id, cmo_id, cmo_role_arn)

        response = self.kms.create_key(
            Description=f"CMO-specific data lake encryption key for {cmo_id}",
            KeyUsage="ENCRYPT_DECRYPT",
            Origin="AWS_KMS",
            Policy=json.dumps(key_policy),
            Tags=[
                {"TagKey": "cmo-id", "TagValue": cmo_id},
                {"TagKey": "purpose", "TagValue": "data-lake-encryption"},
                {"TagKey": "managed-by", "TagValue": "pharma-data-exchange-hub"},
            ],
        )

        key_id = response["KeyMetadata"]["KeyId"]
        key_arn = response["KeyMetadata"]["Arn"]

        # Enable automatic key rotation
        self.kms.enable_key_rotation(KeyId=key_id)

        # Create alias
        alias_name = self._get_alias_name(cmo_id)
        self.kms.create_alias(AliasName=alias_name, TargetKeyId=key_id)

        return {
            "key_id": key_id,
            "key_arn": key_arn,
            "alias": alias_name,
            "cmo_id": cmo_id,
        }

    def get_cmo_key_arn(self, cmo_id: str) -> Optional[str]:
        """
        Get the KMS key ARN for a specific CMO.

        Args:
            cmo_id: CMO identifier

        Returns:
            Key ARN string or None if not found
        """
        alias_name = self._get_alias_name(cmo_id)
        try:
            response = self.kms.describe_key(KeyId=alias_name)
            return response["KeyMetadata"]["Arn"]
        except self.kms.exceptions.NotFoundException:
            return None

    def is_key_rotation_enabled(self, key_id: str) -> bool:
        """Check if automatic key rotation is enabled for a key."""
        response = self.kms.get_key_rotation_status(KeyId=key_id)
        return response["KeyRotationEnabled"]

    def _get_alias_name(self, cmo_id: str) -> str:
        """Get the KMS alias name for a CMO."""
        return f"alias/cmo/{cmo_id}/data-lake"

    def _build_key_policy(
        self,
        account_id: str,
        cmo_id: str,
        cmo_role_arn: Optional[str] = None,
    ) -> dict:
        """Build a KMS key policy restricting usage to the CMO's role."""
        statements = [
            {
                "Sid": "EnableRootAccountAccess",
                "Effect": "Allow",
                "Principal": {"AWS": f"arn:aws:iam::{account_id}:root"},
                "Action": "kms:*",
                "Resource": "*",
            },
            {
                "Sid": "AllowKeyAdministration",
                "Effect": "Allow",
                "Principal": {"AWS": f"arn:aws:iam::{account_id}:root"},
                "Action": [
                    "kms:Create*",
                    "kms:Describe*",
                    "kms:Enable*",
                    "kms:List*",
                    "kms:Put*",
                    "kms:Update*",
                    "kms:Revoke*",
                    "kms:Disable*",
                    "kms:Get*",
                    "kms:Delete*",
                    "kms:TagResource",
                    "kms:UntagResource",
                    "kms:ScheduleKeyDeletion",
                    "kms:CancelKeyDeletion",
                ],
                "Resource": "*",
            },
            {
                "Sid": "AllowS3ServiceUsage",
                "Effect": "Allow",
                "Principal": {"Service": "s3.amazonaws.com"},
                "Action": [
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                    "kms:GenerateDataKeyWithoutPlaintext",
                ],
                "Resource": "*",
                "Condition": {
                    "StringEquals": {
                        "kms:ViaService": f"s3.{self.region}.amazonaws.com",
                    }
                },
            },
        ]

        if cmo_role_arn:
            statements.append(
                {
                    "Sid": f"AllowCMOKeyUsage-{cmo_id}",
                    "Effect": "Allow",
                    "Principal": {"AWS": cmo_role_arn},
                    "Action": [
                        "kms:Decrypt",
                        "kms:DescribeKey",
                        "kms:GenerateDataKey",
                        "kms:GenerateDataKeyWithoutPlaintext",
                    ],
                    "Resource": "*",
                }
            )

        return {"Version": "2012-10-17", "Id": f"cmo-key-policy-{cmo_id}", "Statement": statements}
