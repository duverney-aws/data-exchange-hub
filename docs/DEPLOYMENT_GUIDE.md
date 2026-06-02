# Pharma Data Exchange Hub — Deployment Guide

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Infrastructure Deployment](#2-infrastructure-deployment)
3. [Configuration Guide](#3-configuration-guide)
4. [Frontend Deployment](#4-frontend-deployment)
5. [Post-Deployment Configuration](#5-post-deployment-configuration)
6. [Verification Steps](#6-verification-steps)
7. [Troubleshooting Guide](#7-troubleshooting-guide)
8. [Rollback Procedures](#8-rollback-procedures)
9. [Production Checklist](#9-production-checklist)

---

## 1. Prerequisites

### Required Tools

| Tool | Minimum Version | Install Command |
|------|----------------|-----------------|
| Python | 3.9+ | [python.org](https://www.python.org/downloads/) |
| Node.js | 14+ | [nodejs.org](https://nodejs.org/) |
| AWS CLI | 2.x | `pip install awscli` |
| AWS CDK CLI | 2.120+ | `npm install -g aws-cdk` |
| pip | 21+ | Bundled with Python |
| npm | 8+ | Bundled with Node.js |

### AWS Account Permissions

The deploying IAM principal needs the following permissions (or `AdministratorAccess` for initial setup):

- **CloudFormation**: Full access (stack create/update/delete)
- **S3**: Create buckets, configure encryption, lifecycle rules, object lock
- **DynamoDB**: Create tables, configure GSIs, TTL
- **KMS**: Create keys, manage aliases, key policies
- **Lambda**: Create functions, manage layers
- **API Gateway**: Create REST APIs, configure CORS
- **Step Functions**: Create state machines
- **IAM**: Create roles, policies (for service roles)
- **CloudWatch**: Create log groups, dashboards, alarms
- **SNS**: Create topics, manage subscriptions
- **CloudTrail**: Create trails, configure logging
- **Secrets Manager**: Create secrets, manage encryption
- **Glue**: Schema Registry, Data Catalog, ETL jobs
- **Lake Formation**: Register resources, manage permissions
- **Athena**: Create workgroups, execute queries
- **Transfer Family**: Create SFTP servers
- **Bedrock**: Model access (Claude 3 Sonnet)
- **QuickSight**: Enterprise edition, create data sources
- **STS**: `GetCallerIdentity` (used by deploy scripts)

### AWS CLI Configuration

```bash
# Configure default profile
aws configure
# AWS Access Key ID: <your-access-key>
# AWS Secret Access Key: <your-secret-key>
# Default region name: us-east-1
# Default output format: json

# Verify credentials
aws sts get-caller-identity
```

### Enable Bedrock Model Access

Before deployment, enable Claude 3 Sonnet in the Bedrock console:

1. Open the [Amazon Bedrock console](https://console.aws.amazon.com/bedrock)
2. Navigate to **Model access** in the left sidebar
3. Click **Manage model access**
4. Enable `anthropic.claude-3-sonnet-20240229-v1:0`
5. Submit and wait for access to be granted

---

## 2. Infrastructure Deployment

### Stack Architecture and Dependency Order

The platform deploys 8 CDK stacks in the following dependency order:

```
PharmaDataExchangeSecretsStack          (1) KMS key for secrets
    └── PharmaDataExchangeDatabaseStack (2) DynamoDB tables
        ├── PharmaDataExchangeDataLakeStack       (3) S3 buckets, data lake KMS key
        │   ├── PharmaDataExchangeMonitoringStack  (4) CloudWatch, SNS, dashboards
        │   ├── PharmaDataExchangeSecurityStack    (5) CMO KMS keys, IAM roles
        │   └── PharmaDataExchangeAuditComplianceStack (6) CloudTrail, audit bucket
        ├── PharmaDataExchangeContractApiStack     (5) API Gateway + Lambda
        └── PharmaDataExchangePipelineOrchestrationStack (5) Step Functions
            (depends on: Database, DataLake, Monitoring, Secrets)
```

### Step-by-Step Deployment

#### 1. Clone and install dependencies

```bash
cd cdk
pip install -r requirements.txt
```

#### 2. Set your target account and region

Edit `cdk/cdk.context.json`:

```json
{
  "account": "YOUR_AWS_ACCOUNT_ID",
  "region": "us-east-1"
}
```

#### 3. Bootstrap CDK (first time only)

```bash
cd cdk
cdk bootstrap aws://YOUR_ACCOUNT_ID/us-east-1
```

#### 4. Synthesize templates (validate before deploying)

```bash
cdk synth
```

This generates CloudFormation templates in `cdk/cdk.out/`. Review them to confirm resource definitions.

#### 5a. Automated deployment (recommended)

```bash
chmod +x deploy.sh
./deploy.sh
```

The script checks prerequisites, bootstraps if needed, synthesizes, and deploys all stacks.

#### 5b. Manual deployment (stack by stack)

Deploy in dependency order:

```bash
# Foundation stacks
cdk deploy PharmaDataExchangeSecretsStack --require-approval never
cdk deploy PharmaDataExchangeDatabaseStack --require-approval never
cdk deploy PharmaDataExchangeDataLakeStack --require-approval never

# Dependent stacks (can be deployed in parallel)
cdk deploy PharmaDataExchangeMonitoringStack --require-approval never
cdk deploy PharmaDataExchangeContractApiStack --require-approval never

# Stacks with multiple dependencies
cdk deploy PharmaDataExchangePipelineOrchestrationStack --require-approval never
cdk deploy PharmaDataExchangeSecurityStack --require-approval never
cdk deploy PharmaDataExchangeAuditComplianceStack --require-approval never
```

#### 5c. Deploy all at once

```bash
cdk deploy --all --require-approval never
```

CDK resolves the dependency graph automatically.

#### 6. Integration test deployment (dedicated account)

Use the integration deployment script for the test account:

```bash
chmod +x deploy_integration.sh
./deploy_integration.sh
```

This uses AWS profile `hub-387776852668` and saves outputs to `cdk-outputs.json`.

### Estimated Deployment Time

| Phase | Duration |
|-------|----------|
| CDK Bootstrap (first time) | 2–3 minutes |
| All stacks deployment | 5–10 minutes |
| Total (first deployment) | ~12 minutes |

---

## 3. Configuration Guide

### CDK Context Variables

Set in `cdk/cdk.context.json`:

```json
{
  "account": "550129454303",
  "region": "us-east-1"
}
```

These are read by `cdk/app.py`:

```python
env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1"
)
```

You can also pass context at deploy time:

```bash
cdk deploy --all --context account=123456789012 --context region=us-west-2
```

### Environment Variables (Lambda Functions)

#### Contract API Lambda (`ContractApiStack`)

| Variable | Source | Description |
|----------|--------|-------------|
| `TABLE_NAME` | `database_stack.data_contracts_table.table_name` | DynamoDB data-contracts table |

#### Pipeline Orchestration Lambda (`PipelineOrchestrationStack`)

| Variable | Source | Description |
|----------|--------|-------------|
| `CONTRACTS_TABLE_NAME` | `database_stack.data_contracts_table.table_name` | Data contracts table |
| `EXECUTIONS_TABLE_NAME` | `database_stack.pipeline_executions_table.table_name` | Pipeline executions table |
| `DATA_LAKE_BUCKET_NAME` | `data_lake_stack.data_lake_bucket.bucket_name` | Main data lake S3 bucket |
| `CRITICAL_ALERTS_TOPIC_ARN` | `monitoring_stack.critical_alerts_topic.topic_arn` | Critical SNS topic ARN |
| `WARNING_ALERTS_TOPIC_ARN` | `monitoring_stack.warning_alerts_topic.topic_arn` | Warning SNS topic ARN |

These are set automatically by CDK during deployment. No manual configuration needed.

### AWS Secrets Manager

Secrets are created dynamically during CMO onboarding. The naming convention is:

| Secret Path | Purpose | Created By |
|-------------|---------|------------|
| `cmo/{cmo-id}/credentials` | CMO database connection credentials | Onboarding workflow |
| `cmo/{cmo-id}/sftp-credentials` | Pattern 2 SFTP credentials | Pipeline orchestration |

All secrets are encrypted with the KMS key from `SecretsStack` (`SecretsKMSKey`), which has automatic key rotation enabled.

To manually create a CMO secret:

```bash
aws secretsmanager create-secret \
  --name "cmo/cmo-alpha/credentials" \
  --description "Credentials for CMO Alpha" \
  --secret-string '{
    "username": "cmo-alpha-user",
    "password": "secure-password",
    "connection_string": "jdbc:snowflake://account.snowflakecomputing.com",
    "database": "production",
    "schema": "manufacturing"
  }'
```

### KMS Key Configuration

The platform creates multiple KMS keys:

| Key | Stack | Purpose | Rotation |
|-----|-------|---------|----------|
| `SecretsKMSKey` | SecretsStack | Encrypt Secrets Manager secrets | Enabled |
| `DataLakeKMSKey` | DataLakeStack | Encrypt all S3 data lake buckets | Enabled |
| `AuditKMSKey` | AuditComplianceStack | Encrypt CloudTrail logs | Enabled |
| `alias/cmo/{cmo-id}/data-lake` | SecurityStack | Per-CMO data encryption | Enabled |

All keys use `RemovalPolicy.RETAIN` — they persist even if the stack is deleted.

### SNS Alert Subscriptions

After deployment, subscribe to alert topics:

```bash
# Critical alerts (pager/on-call)
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:pharma-data-exchange-critical-alerts \
  --protocol email \
  --notification-endpoint ops-team@example.com

# Warning alerts
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:pharma-data-exchange-warning-alerts \
  --protocol email \
  --notification-endpoint dev-team@example.com

# SLA breach notifications
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:pharma-data-exchange-sla-breach \
  --protocol email \
  --notification-endpoint sla-team@example.com
```

---

## 4. Frontend Deployment

### Local Development

```bash
cd frontend
npm install
npm run dev
```

The dev server starts at `http://localhost:5173`.

### Build for Production

```bash
cd frontend
npm run build
```

Output is written to `frontend/dist/`.

### Deploy with AWS Amplify

#### Option A: Amplify Console (Git-based)

1. Open the [AWS Amplify console](https://console.aws.amazon.com/amplify)
2. Click **New app** → **Host web app**
3. Connect your Git repository
4. Configure build settings:

```yaml
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - cd frontend
        - npm ci
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: frontend/dist
    files:
      - '**/*'
  cache:
    paths:
      - frontend/node_modules/**/*
```

5. Set environment variables in Amplify console:
   - `VITE_API_ENDPOINT` → API Gateway URL from `PharmaDataExchangeContractApiStack`
   - `VITE_AWS_REGION` → `us-east-1`

#### Option B: Manual Amplify CLI Deployment

```bash
npm install -g @aws-amplify/cli
cd frontend
amplify init
amplify add hosting
amplify publish
```

### Frontend Tech Stack

- React 18 + TypeScript
- Vite 6 (build tool)
- AWS Cloudscape Design System 3.x
- React Router 6
- AWS Amplify 6

---

## 5. Post-Deployment Configuration

### 5.1 Lake Formation Setup

```bash
# Register the data lake S3 bucket with Lake Formation
DATA_LAKE_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name PharmaDataExchangeDataLakeStack \
  --query "Stacks[0].Outputs[?contains(OutputKey,'DataLake')].OutputValue" \
  --output text)

aws lakeformation register-resource \
  --resource-arn "arn:aws:s3:::${DATA_LAKE_BUCKET}" \
  --use-service-linked-role

# Create the Glue database
aws glue create-database \
  --database-input '{"Name": "cmo_data_lake", "Description": "CMO Data Lake - Pharma Data Exchange Hub"}'

# Grant Lake Formation admin permissions
aws lakeformation put-data-lake-settings \
  --data-lake-settings '{
    "DataLakeAdmins": [
      {"DataLakePrincipalIdentifier": "arn:aws:iam::ACCOUNT_ID:role/Admin"}
    ]
  }'
```

### 5.2 Glue Schema Registry

```bash
# Create the schema registry
aws glue create-registry \
  --registry-name "pharma-data-exchange" \
  --description "Schema registry for CMO data contracts"

# Register an example schema
aws glue create-schema \
  --registry-id '{"RegistryName": "pharma-data-exchange"}' \
  --schema-name "cmo-alpha-batch-records" \
  --data-format "AVRO" \
  --compatibility "BACKWARD" \
  --schema-definition '{
    "type": "record",
    "name": "BatchRecord",
    "namespace": "com.merck.cmo.alpha",
    "fields": [
      {"name": "batch_id", "type": "string"},
      {"name": "product_name", "type": "string"},
      {"name": "manufacture_date", "type": {"type": "long", "logicalType": "timestamp-millis"}},
      {"name": "quantity", "type": "double"},
      {"name": "unit", "type": "string"},
      {"name": "quality_status", "type": {"type": "enum", "symbols": ["PASS", "FAIL", "PENDING"]}}
    ]
  }'
```

### 5.3 QuickSight Configuration

1. Open [Amazon QuickSight console](https://quicksight.aws.amazon.com)
2. Ensure QuickSight Enterprise edition is enabled
3. Grant QuickSight access to:
   - The Athena workgroup
   - The data lake S3 bucket
   - The Glue Data Catalog database `cmo_data_lake`
4. Create Athena data sources pointing to Gold layer tables
5. Configure SPICE refresh schedules matching contract delivery frequencies

### 5.4 Step Functions Verification

The state machine `PipelineDeploymentWorkflow` is created automatically. Verify it:

```bash
aws stepfunctions describe-state-machine \
  --state-machine-arn arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:PipelineDeploymentWorkflow
```

### 5.5 Athena Workgroup

```bash
aws athena create-work-group \
  --name "cmo-workgroup" \
  --configuration '{
    "ResultConfiguration": {
      "OutputLocation": "s3://ATHENA_RESULTS_BUCKET/"
    },
    "EnforceWorkGroupConfiguration": true,
    "PublishCloudWatchMetricsEnabled": true
  }'
```

---

## 6. Verification Steps

### 6.1 DynamoDB Tables

```bash
aws dynamodb list-tables --query "TableNames[?contains(@, 'cmo') || contains(@, 'data-contracts') || contains(@, 'pipeline')]"
```

Expected tables:
- `cmo-profiles`
- `data-contracts`
- `pipeline-executions`

Test write/read:

```bash
aws dynamodb put-item --table-name cmo-profiles --item '{
  "cmoId": {"S": "cmo-test"},
  "organizationName": {"S": "Test Pharma"},
  "status": {"S": "active"}
}'

aws dynamodb get-item --table-name cmo-profiles --key '{"cmoId": {"S": "cmo-test"}}'
```

### 6.2 S3 Buckets

```bash
aws s3 ls | grep -i pharma
```

Verify bucket structure:

```bash
DATA_LAKE_BUCKET=$(aws s3 ls | grep -i pharmadataexchange | grep -i datalake | awk '{print $3}')
aws s3api put-object --bucket $DATA_LAKE_BUCKET --key bronze/cmo-test/batch-records/
aws s3api put-object --bucket $DATA_LAKE_BUCKET --key silver/cmo-test/batch-records/
aws s3api put-object --bucket $DATA_LAKE_BUCKET --key gold/batch-summary-daily/
```

### 6.3 CloudWatch Log Groups

```bash
aws logs describe-log-groups --log-group-name-prefix /pharma-data-exchange
```

Expected log groups:
- `/pharma-data-exchange/api`
- `/pharma-data-exchange/pipeline`
- `/pharma-data-exchange/etl`
- `/pharma-data-exchange/schema-registry`
- `/pharma-data-exchange/ai-processing`
- `/pharma-data-exchange/cloudtrail`

### 6.4 CloudWatch Dashboard

Open the [CloudWatch console](https://console.aws.amazon.com/cloudwatch) and verify the `PharmaDataExchangeHub` dashboard exists with SLA compliance widgets.

### 6.5 SNS Topics

```bash
aws sns list-topics | grep pharma-data-exchange
```

Expected topics:
- `pharma-data-exchange-critical-alerts`
- `pharma-data-exchange-warning-alerts`
- `pharma-data-exchange-sla-breach`

### 6.6 API Gateway

```bash
aws apigateway get-rest-apis --query "items[?name=='Contract API']"
```

Test the API endpoint:

```bash
API_ID=$(aws apigateway get-rest-apis --query "items[?name=='Contract API'].id" --output text)
ENDPOINT="https://${API_ID}.execute-api.us-east-1.amazonaws.com/prod"

curl -X POST "${ENDPOINT}/api/contract" \
  -H "Content-Type: application/json" \
  -d '{"cmoId": "cmo-test", "dataDomain": "batch-records"}'
```

### 6.7 Step Functions

```bash
aws stepfunctions list-state-machines --query "stateMachines[?name=='PipelineDeploymentWorkflow']"
```

### 6.8 CloudTrail

```bash
aws cloudtrail describe-trails --query "trailList[?Name=='pharma-data-exchange-audit-trail']"
aws cloudtrail get-trail-status --name pharma-data-exchange-audit-trail
```

Verify `IsLogging` is `true`.

### 6.9 KMS Keys

```bash
aws kms list-aliases --query "Aliases[?contains(AliasName, 'cmo')]"
```

---

## 7. Troubleshooting Guide

### 7.1 CDK Bootstrap Failures

**Symptom**: `CDKToolkit stack not found` or bootstrap errors.

**Fix**:
```bash
# Ensure you have CloudFormation + S3 + IAM permissions
cdk bootstrap aws://ACCOUNT_ID/REGION --force
```

### 7.2 Stack Deployment Failures

**Symptom**: `CREATE_FAILED` or `UPDATE_ROLLBACK_COMPLETE` in CloudFormation.

**Diagnosis**:
```bash
aws cloudformation describe-stack-events \
  --stack-name PharmaDataExchangeDatabaseStack \
  --query "StackEvents[?ResourceStatus=='CREATE_FAILED'].[LogicalResourceId,ResourceStatusReason]" \
  --output table
```

**Common causes**:
- **Resource already exists**: DynamoDB table or S3 bucket name collision. Delete the existing resource or import it.
- **IAM permission denied**: Ensure the deploying role has required permissions.
- **Service limit reached**: Request a limit increase via AWS Support.

### 7.3 DynamoDB Table Already Exists

**Symptom**: `Table already exists: cmo-profiles`

**Fix**: Delete existing tables before redeploying, or import them into the stack:

```bash
aws dynamodb delete-table --table-name cmo-profiles
aws dynamodb delete-table --table-name data-contracts
aws dynamodb delete-table --table-name pipeline-executions
cdk deploy PharmaDataExchangeDatabaseStack
```

### 7.4 S3 Bucket Deletion Blocked

**Symptom**: Stack deletion fails because S3 buckets are not empty.

**Fix**: Empty the bucket first:

```bash
aws s3 rm s3://BUCKET_NAME --recursive
cdk destroy PharmaDataExchangeDataLakeStack
```

Note: Buckets with `RemovalPolicy.RETAIN` are intentionally preserved on stack deletion.

### 7.5 KMS Key Issues

**Symptom**: `AccessDeniedException` when writing to S3 or Secrets Manager.

**Fix**: Verify the Lambda execution role has `kms:Decrypt` and `kms:GenerateDataKey` permissions on the relevant KMS key:

```bash
aws kms describe-key --key-id alias/cmo/cmo-alpha/data-lake
aws kms list-grants --key-id KEY_ID
```

### 7.6 Lambda Function Errors

**Symptom**: API returns 500 errors or Step Functions tasks fail.

**Diagnosis**:
```bash
# Check Lambda logs
aws logs tail /aws/lambda/FUNCTION_NAME --since 1h

# Check specific invocation
aws logs filter-log-events \
  --log-group-name /aws/lambda/FUNCTION_NAME \
  --filter-pattern "ERROR"
```

**Common causes**:
- Missing environment variables → Check stack outputs
- DynamoDB permission denied → Verify IAM grants in stack
- Timeout → Increase Lambda timeout (currently 30s for API, 60s for orchestration)

### 7.7 Step Functions Execution Failures

**Symptom**: Pipeline deployment workflow fails.

**Diagnosis**:
```bash
# List recent executions
aws stepfunctions list-executions \
  --state-machine-arn arn:aws:states:us-east-1:ACCOUNT_ID:stateMachine:PipelineDeploymentWorkflow \
  --status-filter FAILED

# Get execution details
aws stepfunctions describe-execution --execution-arn EXECUTION_ARN
aws stepfunctions get-execution-history --execution-arn EXECUTION_ARN
```

The workflow retries each task 3 times with exponential backoff (1s, 2s, 4s). If all retries fail, check the `HandleError` state output.

### 7.8 CloudTrail Not Logging

**Symptom**: No audit events appearing.

**Fix**:
```bash
aws cloudtrail get-trail-status --name pharma-data-exchange-audit-trail
# Check IsLogging, LatestDeliveryError, LatestNotificationError

# Restart logging if stopped
aws cloudtrail start-logging --name pharma-data-exchange-audit-trail
```

### 7.9 CloudWatch Alarms in INSUFFICIENT_DATA

**Symptom**: SLA alarms show `INSUFFICIENT_DATA` state.

**Cause**: No metrics have been published yet. This is normal before any pipeline executions. Alarms are configured with `TreatMissingData: NOT_BREACHING`, so they won't fire false alerts.

### 7.10 Frontend Build Failures

**Symptom**: `npm run build` fails with TypeScript errors.

**Fix**:
```bash
cd frontend
rm -rf node_modules
npm install
npm run build
```

If TypeScript errors persist, check `tsconfig.json` and ensure all dependencies are at compatible versions.

### 7.11 API Gateway CORS Errors

**Symptom**: Browser console shows CORS errors when calling the API.

**Cause**: The API is configured with `allow_origins=ALL_ORIGINS`. If you've restricted origins, ensure the frontend domain is included. Check that preflight OPTIONS requests return proper headers.

---

## 8. Rollback Procedures

### 8.1 Rolling Back a Single Stack

```bash
# CDK automatically rolls back on deployment failure
# To manually roll back to previous version:
cdk deploy PharmaDataExchangeContractApiStack --previous
```

### 8.2 Rolling Back All Stacks

```bash
# Destroy in reverse dependency order
cdk destroy PharmaDataExchangeAuditComplianceStack
cdk destroy PharmaDataExchangeSecurityStack
cdk destroy PharmaDataExchangePipelineOrchestrationStack
cdk destroy PharmaDataExchangeContractApiStack
cdk destroy PharmaDataExchangeMonitoringStack
cdk destroy PharmaDataExchangeDataLakeStack
cdk destroy PharmaDataExchangeDatabaseStack
cdk destroy PharmaDataExchangeSecretsStack
```

### 8.3 Resources That Survive Deletion

These resources use `RemovalPolicy.RETAIN` and must be deleted manually:

| Resource | Stack | Reason |
|----------|-------|--------|
| `cmo-profiles` DynamoDB table | DatabaseStack | Prevent data loss |
| `data-contracts` DynamoDB table | DatabaseStack | Prevent data loss |
| Data lake S3 bucket | DataLakeStack | Prevent data loss |
| Quality results S3 bucket | DataLakeStack | Audit compliance |
| Audit logs S3 bucket | DataLakeStack | 21 CFR Part 11 |
| Audit trail S3 bucket | AuditComplianceStack | 21 CFR Part 11 |
| All KMS keys | Multiple stacks | Prevent data inaccessibility |
| CloudWatch log groups | MonitoringStack | Audit compliance |
| CloudTrail log group | AuditComplianceStack | 7-year retention |

### 8.4 Safe Rollback Checklist

1. **Stop all running pipelines** — Cancel active Step Functions executions
2. **Disable CloudTrail** — Prevent log gaps during rollback
3. **Export critical data** — Back up DynamoDB tables if needed
4. **Destroy stacks** — In reverse dependency order
5. **Verify cleanup** — Check for orphaned resources
6. **Redeploy** — From a known-good commit

---

## 9. Production Checklist

### Security

- [ ] All S3 buckets have `BlockPublicAccess.BLOCK_ALL` enabled
- [ ] All S3 buckets enforce SSL (`enforce_ssl=True`)
- [ ] KMS key rotation is enabled on all keys
- [ ] Lambda functions use least-privilege IAM roles
- [ ] API Gateway has authentication configured (Cognito/IAM)
- [ ] Secrets Manager secrets are encrypted with dedicated KMS key
- [ ] CMO IAM roles are scoped to their own S3 prefixes and DynamoDB items
- [ ] No hardcoded credentials in Lambda code or environment variables
- [ ] VPC endpoints configured for S3, DynamoDB, Secrets Manager (if using VPC)

### Compliance (21 CFR Part 11 / GxP)

- [ ] CloudTrail is enabled and logging all management + data events
- [ ] Audit trail S3 bucket has Object Lock enabled (GOVERNANCE mode, 7-year retention)
- [ ] CloudTrail log file validation is enabled
- [ ] Audit log CloudWatch group has 7-year retention
- [ ] Electronic signature capture is implemented for critical actions
- [ ] DynamoDB tables have point-in-time recovery enabled
- [ ] Data lake bucket has versioning enabled

### Monitoring

- [ ] SNS topics have subscribers configured (email, PagerDuty, Slack)
- [ ] CloudWatch dashboard `PharmaDataExchangeHub` is accessible
- [ ] SLA alarms are configured:
  - `SLA-ExecutionTime-Warning` (80% of threshold)
  - `SLA-ExecutionTime-Critical` (100% of threshold)
  - `SLA-QualityScore-Warning` (< 95%)
  - `SLA-QualityScore-Critical` (< 90%)
  - `SLA-SuccessRate-Warning` (< 99%)
  - `SLA-SuccessRate-Critical` (< 95%)
- [ ] Lambda function error metrics are monitored
- [ ] API Gateway 4xx/5xx error rates are tracked

### Data Lake

- [ ] Bronze layer lifecycle: Glacier after 90 days
- [ ] Silver layer lifecycle: Glacier after 180 days
- [ ] Quarantine cleanup: Delete after 30 days
- [ ] Quality results retention: 365 days
- [ ] Athena results cleanup: 30 days
- [ ] Lake Formation permissions configured for all CMO users
- [ ] Glue Data Catalog database `cmo_data_lake` created
- [ ] Glue Schema Registry `pharma-data-exchange` created

### Frontend

- [ ] Amplify hosting configured with custom domain
- [ ] HTTPS enforced
- [ ] Environment variables set (`VITE_API_ENDPOINT`, `VITE_AWS_REGION`)
- [ ] Build succeeds with `npm run build`
- [ ] CORS configured correctly on API Gateway

### Operational Readiness

- [ ] Runbook documented for common failure scenarios
- [ ] On-call rotation established for critical alerts
- [ ] Backup and restore procedures tested
- [ ] Load testing completed for expected CMO count
- [ ] Disaster recovery plan documented
- [ ] Cost alerts configured in AWS Budgets

### Cost Estimation

| Environment | Monthly Estimate |
|-------------|-----------------|
| Development | $15–25 |
| Staging | $50–100 |
| Production (5 CMOs) | $200–500 |
| Production (20+ CMOs) | $500–2,000+ |

Key cost drivers: DynamoDB throughput, S3 storage volume, Glue ETL job DPUs, Athena query volume, Bedrock API calls, QuickSight user licenses.
