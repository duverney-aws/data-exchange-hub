# Quick Start Guide

Get the Pharma Data Exchange Hub infrastructure up and running in minutes.

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
3. **Python 3.9+** installed
4. **Node.js 14+** installed (for CDK CLI)
5. **AWS CDK CLI** installed globally

## Installation Steps

### 1. Install AWS CDK CLI

```bash
npm install -g aws-cdk
```

### 2. Configure AWS Credentials

```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and default region
```

### 3. Update Context Configuration

Edit `cdk.context.json` and replace with your AWS account ID:

```json
{
  "account": "123456789012",
  "region": "us-east-1"
}
```

### 4. Install Python Dependencies

```bash
cd cdk
pip install -r requirements.txt
```

### 5. Bootstrap CDK (First Time Only)

```bash
cdk bootstrap aws://550129454303/us-east-1
```

Replace `ACCOUNT-ID` with your AWS account ID and `REGION` with your target region.

### 6. Deploy Infrastructure

#### Option A: Automated Deployment (Recommended)

```bash
chmod +x deploy.sh
./deploy.sh
```

#### Option B: Manual Deployment

```bash
# Synthesize CloudFormation templates
cdk synth

# Deploy all stacks
cdk deploy --all

# Or deploy individual stacks
cdk deploy PharmaDataExchangeSecretsStack
cdk deploy PharmaDataExchangeDatabaseStack
cdk deploy PharmaDataExchangeDataLakeStack
cdk deploy PharmaDataExchangeMonitoringStack
```

## Verify Deployment

### Check DynamoDB Tables

```bash
aws dynamodb list-tables
```

You should see:
- `cmo-profiles`
- `data-contracts`
- `pipeline-executions`

### Check S3 Buckets

```bash
aws s3 ls
```

You should see buckets for:
- Data lake (Bronze/Silver/Gold)
- Quality results
- Audit logs
- Athena results

### Check CloudWatch Log Groups

```bash
aws logs describe-log-groups --log-group-name-prefix /pharma-data-exchange
```

You should see log groups for:
- API
- Pipeline
- ETL
- Schema Registry
- AI Processing

## Test the Infrastructure

### 1. Create a Test CMO Profile

```python
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('cmo-profiles')

table.put_item(Item={
    'cmoId': 'cmo-test',
    'organizationName': 'Test Pharmaceuticals',
    'contactEmail': 'test@example.com',
    'contactPhone': '+1-555-0100',
    'address': '123 Test St, Boston, MA',
    'gxpCertified': True,
    'createdAt': datetime.now().isoformat(),
    'status': 'active'
})

print("CMO profile created successfully!")
```

### 2. Verify S3 Bucket Structure

```bash
# Get data lake bucket name
BUCKET=$(aws s3 ls | grep pharmadat | awk '{print $3}')

# Create test folder structure
aws s3api put-object --bucket $BUCKET --key bronze/cmo-test/batch-records/
aws s3api put-object --bucket $BUCKET --key silver/cmo-test/batch-records/
aws s3api put-object --bucket $BUCKET --key gold/batch-summary-daily/

echo "Folder structure created!"
```

### 3. Test CloudWatch Logging

```python
import boto3

logs = boto3.client('logs')

logs.put_log_events(
    logGroupName='/pharma-data-exchange/api',
    logStreamName='test-stream',
    logEvents=[
        {
            'timestamp': int(time.time() * 1000),
            'message': 'Test log message from Quick Start'
        }
    ]
)

print("Log event created successfully!")
```

## Common Issues

### Issue: CDK Bootstrap Failed

**Solution**: Ensure you have sufficient IAM permissions. You need:
- CloudFormation full access
- S3 full access
- IAM role creation permissions

### Issue: Stack Deployment Timeout

**Solution**: Some resources (like KMS keys) can take time. Wait and retry:

```bash
cdk deploy --all --require-approval never
```

### Issue: Table Already Exists

**Solution**: If tables exist from a previous deployment:

```bash
# Delete existing tables
aws dynamodb delete-table --table-name cmo-profiles
aws dynamodb delete-table --table-name data-contracts
aws dynamodb delete-table --table-name pipeline-executions

# Redeploy
cdk deploy PharmaDataExchangeDatabaseStack
```

## Next Steps

After successful deployment:

1. **Configure Schema Registry**
   - Set up AWS Glue Schema Registry
   - Register initial schemas

2. **Deploy Lambda Functions**
   - API handlers for self-service portal
   - ETL processing functions
   - Schema validation functions

3. **Set Up Step Functions**
   - Pipeline deployment workflow
   - Data processing orchestration

4. **Deploy Frontend**
   - React self-service portal
   - AWS Amplify hosting

5. **Configure Lake Formation**
   - Register S3 locations
   - Set up access policies
   - Configure row/column-level security

## Cleanup

To remove all infrastructure:

```bash
# WARNING: This will delete all data!
cdk destroy --all
```

Note: Some resources with `RemovalPolicy.RETAIN` will not be deleted and must be removed manually:
- DynamoDB tables (cmo-profiles, data-contracts)
- Data lake S3 bucket
- Audit logs S3 bucket
- KMS keys

## Support

For issues or questions:
1. Check the main [README.md](README.md)
2. Review AWS CloudFormation stack events in the console
3. Check CloudWatch logs for error messages
4. Consult the [AWS CDK documentation](https://docs.aws.amazon.com/cdk/)

## Cost Estimation

Estimated monthly costs for development environment:
- DynamoDB (on-demand): ~$5-10
- S3 storage (100 GB): ~$2-3
- CloudWatch logs (10 GB): ~$5
- KMS keys: ~$2
- **Total**: ~$15-20/month

Production costs will vary based on:
- Number of CMOs
- Data volume
- Query frequency
- Retention policies
