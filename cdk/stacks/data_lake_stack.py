"""
S3 Data Lake Stack for Pharma Data Exchange Hub
Implements Medallion Architecture: Bronze/Silver/Gold layers with CMO partitioning
"""
from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    aws_s3 as s3,
    aws_kms as kms,
    aws_iam as iam,
)
from constructs import Construct


class DataLakeStack(Stack):
    """Stack for S3-based data lake with Bronze, Silver, and Gold layers"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # KMS key for S3 encryption (will be used for CMO-specific keys later)
        self.data_lake_kms_key = kms.Key(
            self,
            "DataLakeKMSKey",
            description="KMS key for Pharma Data Exchange Hub data lake encryption",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Main Data Lake Bucket with Medallion Architecture
        self.data_lake_bucket = s3.Bucket(
            self,
            "DataLakeBucket",
            bucket_name=None,  # Auto-generated name
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.data_lake_kms_key,
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.PUT, s3.HttpMethods.GET],
                    allowed_origins=["https://main.d28qy16znlocxk.amplifyapp.com"],
                    allowed_headers=["*"],
                    exposed_headers=["ETag"],
                    max_age=3000,
                )
            ],
            lifecycle_rules=[
                # Bronze layer: Transition to Glacier after 90 days
                s3.LifecycleRule(
                    id="bronze-layer-lifecycle",
                    prefix="bronze/",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90)
                        )
                    ],
                    enabled=True,
                ),
                # Silver layer: Transition to Glacier after 180 days
                s3.LifecycleRule(
                    id="silver-layer-lifecycle",
                    prefix="silver/",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(180)
                        )
                    ],
                    enabled=True,
                ),
                # Quarantine: Delete after 30 days
                s3.LifecycleRule(
                    id="quarantine-cleanup",
                    prefix="bronze/quarantine/",
                    expiration=Duration.days(30),
                    enabled=True,
                ),
            ],
        )

        # Quality Results Bucket for Glue Data Quality outputs
        self.quality_results_bucket = s3.Bucket(
            self,
            "QualityResultsBucket",
            bucket_name=None,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.data_lake_kms_key,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="quality-results-retention",
                    expiration=Duration.days(365),  # Keep for 1 year
                    enabled=True,
                )
            ],
        )

        # Audit Logs Bucket with Object Lock for immutability (21 CFR Part 11)
        self.audit_logs_bucket = s3.Bucket(
            self,
            "AuditLogsBucket",
            bucket_name=None,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.data_lake_kms_key,
            versioned=True,
            object_lock_enabled=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="audit-logs-retention",
                    # Retain for 7 years per GxP requirements
                    expiration=Duration.days(2555),
                    enabled=True,
                )
            ],
        )

        # Athena Query Results Bucket
        self.athena_results_bucket = s3.Bucket(
            self,
            "AthenaResultsBucket",
            bucket_name=None,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.data_lake_kms_key,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="athena-results-cleanup",
                    expiration=Duration.days(30),
                    enabled=True,
                )
            ],
        )

        # Create folder structure in data lake bucket (logical organization)
        # Note: S3 doesn't have actual folders, but we document the structure here
        # Structure:
        # bronze/{cmo-id}/{data-domain}/year=YYYY/month=MM/day=DD/
        # silver/{cmo-id}/{data-domain}/year=YYYY/month=MM/day=DD/
        # gold/{aggregation-type}/year=YYYY/month=MM/day=DD/
        # bronze/quarantine/{contract-id}/{timestamp}/

        # Grant Lake Formation access to data lake bucket
        self.data_lake_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowLakeFormationAccess",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("lakeformation.amazonaws.com")],
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                ],
                resources=[
                    self.data_lake_bucket.bucket_arn,
                    f"{self.data_lake_bucket.bucket_arn}/*",
                ],
            )
        )
