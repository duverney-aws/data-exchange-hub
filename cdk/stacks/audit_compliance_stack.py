"""
Audit Compliance Stack for Pharma Data Exchange Hub

Provisions CloudTrail, S3 audit log bucket with object lock, and CloudWatch
log group for comprehensive audit logging per 21 CFR Part 11 / GxP requirements.

Requirements: 10.5, 14.1, 14.2, 14.3, 14.5
"""
from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    aws_s3 as s3,
    aws_kms as kms,
    aws_iam as iam,
    aws_logs as logs,
    aws_cloudtrail as cloudtrail,
)
from constructs import Construct


class AuditComplianceStack(Stack):
    """Stack for CloudTrail audit logging with immutable S3 storage."""

    # 7 years in days
    RETENTION_DAYS = 2555

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        data_lake_stack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- KMS key for audit log encryption ---
        self.audit_kms_key = kms.Key(
            self,
            "AuditKMSKey",
            description="KMS key for CloudTrail audit log encryption",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Allow CloudTrail to use the KMS key
        self.audit_kms_key.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowCloudTrailEncrypt",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("cloudtrail.amazonaws.com")],
                actions=[
                    "kms:GenerateDataKey*",
                    "kms:DescribeKey",
                ],
                resources=["*"],
            )
        )

        # Allow CloudWatch Logs to use the KMS key
        self.audit_kms_key.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowCloudWatchLogsEncrypt",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal(
                    f"logs.{Stack.of(self).region}.amazonaws.com"
                )],
                actions=[
                    "kms:Encrypt*",
                    "kms:Decrypt*",
                    "kms:ReEncrypt*",
                    "kms:GenerateDataKey*",
                    "kms:DescribeKey",
                ],
                resources=["*"],
            )
        )

        # --- S3 bucket for CloudTrail logs with object lock ---
        self.audit_trail_bucket = s3.Bucket(
            self,
            "AuditTrailBucket",
            bucket_name=None,  # Auto-generated
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.audit_kms_key,
            versioned=True,
            object_lock_enabled=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
            object_lock_default_retention=s3.ObjectLockRetention.governance(
                Duration.days(self.RETENTION_DAYS),
            ),
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="audit-trail-retention",
                    expiration=Duration.days(self.RETENTION_DAYS),
                    enabled=True,
                ),
            ],
        )

        # Grant CloudTrail write access to the bucket
        self.audit_trail_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowCloudTrailGetBucketAcl",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("cloudtrail.amazonaws.com")],
                actions=["s3:GetBucketAcl"],
                resources=[self.audit_trail_bucket.bucket_arn],
            )
        )
        self.audit_trail_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowCloudTrailPutObject",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("cloudtrail.amazonaws.com")],
                actions=["s3:PutObject"],
                resources=[f"{self.audit_trail_bucket.bucket_arn}/*"],
                conditions={
                    "StringEquals": {
                        "s3:x-amz-acl": "bucket-owner-full-control",
                    }
                },
            )
        )

        # --- CloudWatch Log Group for CloudTrail (7-year retention) ---
        self.cloudtrail_log_group = logs.LogGroup(
            self,
            "CloudTrailLogGroup",
            log_group_name="/pharma-data-exchange/cloudtrail",
            retention=logs.RetentionDays.SEVEN_YEARS,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # IAM role for CloudTrail to write to CloudWatch Logs
        self.cloudtrail_logs_role = iam.Role(
            self,
            "CloudTrailLogsRole",
            assumed_by=iam.ServicePrincipal("cloudtrail.amazonaws.com"),
            description="Allows CloudTrail to send logs to CloudWatch Logs",
        )

        self.cloudtrail_log_group.grant_write(self.cloudtrail_logs_role)

        # --- CloudTrail trail ---
        self.trail = cloudtrail.Trail(
            self,
            "AuditTrail",
            trail_name="pharma-data-exchange-audit-trail",
            bucket=self.audit_trail_bucket,
            encryption_key=self.audit_kms_key,
            cloud_watch_log_group=self.cloudtrail_log_group,
            is_multi_region_trail=True,
            include_global_service_events=True,
            enable_file_validation=True,
            send_to_cloud_watch_logs=True,
        )

        # Log all management events (read + write)
        self.trail.add_event_selector(
            cloudtrail.DataResourceType.S3_OBJECT,
            data_resource_values=[
                f"{data_lake_stack.data_lake_bucket.bucket_arn}/",
            ],
            include_management_events=True,
            read_write_type=cloudtrail.ReadWriteType.ALL,
        )
