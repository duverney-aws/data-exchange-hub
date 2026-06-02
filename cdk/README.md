# Pharma Data Exchange Hub - Infrastructure as Code

This directory contains AWS CDK infrastructure definitions for the Pharma Data Exchange Hub platform.

## Architecture Overview

The infrastructure is organized into four main stacks:

1. **SecretsStack** - AWS Secrets Manager for secure credential storage
2. **DatabaseStack** - DynamoDB tables for CMO profiles, data contracts, and execution history
3. **DataLakeStack** - S3 buckets implementing Medallion Architecture (Bronze/Silver/Gold)
4. **MonitoringStack** - CloudWatch log groups, metrics, and dashboards

## Prerequisites

- Python 3.9 or later
- AWS CLI configured with appropriate credentials
- AWS CDK CLI installed (`npm install -g aws-cdk`)

## Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Bootstrap CDK (first time only)
cdk bootstrap aws://ACCOUNT-ID/REGION
```

## Deployment

```bash
# Synthesize CloudFormation templates
cdk synth

# Deploy all stacks
cdk deploy --all

# Deploy specific stack
cdk deploy PharmaDataExchangeDatabaseStack
```

## Stack Details

### DatabaseStack

Creates three DynamoDB tables:

- **cmo-profiles**: Stores CMO organization details and credentials
  - Partition Key: `cmoId`
  - GSI: `organization-name-index` on `organizationName`

- **data-contracts**: Stores data contract definitions
  - Partition Key: `contractId`
  - GSI: `cmo-contracts-index` on `cmoId` and `status`

- **pipeline-executions**: Stores pipeline execution history
  - Partition Key: `contractId`
  - Sort Key: `executionTimestamp`
  - TTL: 90 days

### DataLakeStack

Creates S3 buckets with encryption and lifecycle policies:

- **Data Lake Bucket**: Main storage with Bronze/Silver/Gold layers
  - Structure: `{layer}/{cmo-id}/{data-domain}/year=YYYY/month=MM/day=DD/`
  - Encryption: KMS with customer-managed keys
  - Lifecycle: Bronze → Glacier (90 days), Silver → Glacier (180 days)

- **Quality Results Bucket**: Glue Data Quality outputs
  - Retention: 365 days

- **Audit Logs Bucket**: Immutable audit trail (21 CFR Part 11 compliance)
  - Object Lock enabled
  - Retention: 7 years (2555 days)

- **Athena Results Bucket**: Query results storage
  - Retention: 30 days

### SecretsStack

Sets up AWS Secrets Manager infrastructure:

- KMS key for secret encryption with automatic rotation
- Secrets created dynamically during CMO onboarding
- Naming convention: `cmo/{cmo-id}/credentials`

### MonitoringStack

Creates CloudWatch resources:

- **Log Groups**:
  - `/pharma-data-exchange/api`
  - `/pharma-data-exchange/pipeline`
  - `/pharma-data-exchange/etl`
  - `/pharma-data-exchange/schema-registry`
  - `/pharma-data-exchange/ai-processing`

- **SNS Topics**:
  - `pharma-data-exchange-critical-alerts`
  - `pharma-data-exchange-warning-alerts`
  - `pharma-data-exchange-sla-breach`

- **Dashboards**: Main operational dashboard

## Custom Metric Namespaces

Metrics are published at runtime to these namespaces:

### CMO/DataPipeline
- `ExecutionTime` (Seconds) - Dimensions: ContractId, CMOId
- `RecordsProcessed` (Count) - Dimensions: ContractId, CMOId
- `QualityScore` (Percent) - Dimensions: ContractId, CMOId
- `ValidationFailures` (Count) - Dimensions: ContractId, CMOId
- `SLACompliance` (Percent) - Dimensions: ContractId, CMOId

### CMO/SchemaRegistry
- `SchemaRegistrations` (Count) - Dimensions: CMOId
- `SchemaValidationFailures` (Count) - Dimensions: CMOId
- `CompatibilityCheckFailures` (Count) - Dimensions: CMOId

### CMO/AIProcessing
- `DocumentsProcessed` (Count) - Dimensions: CMOId, DocumentType
- `ExtractionConfidence` (Percent) - Dimensions: CMOId, DocumentType
- `ManualReviewRequired` (Count) - Dimensions: CMOId

## Data Lake Structure

```
s3://data-lake-bucket/
├── bronze/                          # Raw ingested data
│   ├── cmo-alpha/
│   │   ├── batch-records/
│   │   │   └── year=2024/month=01/day=15/
│   │   └── quality-data/
│   ├── cmo-beta/
│   └── quarantine/                  # Failed validation records
│       └── {contract-id}/{timestamp}/
├── silver/                          # Validated and cleansed data
│   ├── cmo-alpha/
│   │   └── batch-records/
│   └── cmo-beta/
└── gold/                            # Business-ready aggregated data
    ├── batch-summary-daily/
    ├── quality-metrics-monthly/
    └── cmo-performance-dashboard/
```

## Security

- All S3 buckets enforce SSL/TLS
- All data encrypted at rest with KMS
- Public access blocked on all buckets
- Secrets encrypted with dedicated KMS key
- Audit logs immutable with Object Lock

## Compliance

- **21 CFR Part 11**: Audit logs with 7-year retention and immutability
- **GxP**: Point-in-time recovery enabled on DynamoDB tables
- **Data Retention**: Configurable lifecycle policies per regulatory requirements

## Cleanup

```bash
# Destroy all stacks (WARNING: This will delete data)
cdk destroy --all
```

Note: Stacks with `RemovalPolicy.RETAIN` will preserve data even after stack deletion.

## Troubleshooting

### Bootstrap Issues
If you encounter bootstrap errors, ensure your AWS account is bootstrapped:
```bash
cdk bootstrap aws://ACCOUNT-ID/REGION
```

### Permission Errors
Ensure your AWS credentials have sufficient permissions to create:
- DynamoDB tables
- S3 buckets
- KMS keys
- CloudWatch resources
- Secrets Manager secrets

## Next Steps

After infrastructure deployment:
1. Deploy Lambda functions for API and processing
2. Configure AWS Glue Schema Registry
3. Set up Step Functions workflows
4. Deploy self-service portal frontend
5. Configure Lake Formation permissions
