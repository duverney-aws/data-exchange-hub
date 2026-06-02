#!/bin/bash
# Deployment script for Pharma Data Exchange Hub infrastructure

set -e

echo "=========================================="
echo "Pharma Data Exchange Hub - CDK Deployment"
echo "=========================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed"
    exit 1
fi

# Check if CDK is installed
if ! command -v cdk &> /dev/null; then
    echo "Error: AWS CDK is not installed"
    echo "Install with: npm install -g aws-cdk"
    exit 1
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Get AWS account and region
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)
AWS_REGION=${AWS_REGION:-us-east-1}

echo ""
echo "Deployment Configuration:"
echo "  AWS Account: $AWS_ACCOUNT"
echo "  AWS Region: $AWS_REGION"
echo ""

# Check if CDK is bootstrapped
echo "Checking CDK bootstrap status..."
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region $AWS_REGION &> /dev/null; then
    echo "CDK is not bootstrapped in this account/region"
    read -p "Would you like to bootstrap now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Bootstrapping CDK..."
        cdk bootstrap aws://$AWS_ACCOUNT/$AWS_REGION
    else
        echo "Deployment cancelled. Please bootstrap CDK first:"
        echo "  cdk bootstrap aws://$AWS_ACCOUNT/$AWS_REGION"
        exit 1
    fi
fi

# Synthesize CloudFormation templates
echo ""
echo "Synthesizing CloudFormation templates..."
cdk synth

# Deploy stacks
echo ""
echo "Deploying infrastructure stacks..."
echo "This will create:"
echo "  - DynamoDB tables (cmo-profiles, data-contracts, pipeline-executions)"
echo "  - S3 buckets (data lake, quality results, audit logs, athena results)"
echo "  - KMS keys for encryption"
echo "  - CloudWatch log groups and dashboards"
echo "  - SNS topics for alerts"
echo ""

read -p "Proceed with deployment? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 0
fi

# Deploy all stacks
cdk deploy --all --require-approval never

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Configure AWS Glue Schema Registry"
echo "  2. Deploy Lambda functions for API and processing"
echo "  3. Set up Step Functions workflows"
echo "  4. Deploy self-service portal frontend"
echo "  5. Configure Lake Formation permissions"
echo ""
echo "View resources in AWS Console:"
echo "  DynamoDB: https://console.aws.amazon.com/dynamodb"
echo "  S3: https://console.aws.amazon.com/s3"
echo "  CloudWatch: https://console.aws.amazon.com/cloudwatch"
echo ""
