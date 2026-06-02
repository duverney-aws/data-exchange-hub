#!/bin/bash
# Integration test deployment script for Pharma Data Exchange Hub
# Uses the hub-387776852668 AWS profile to deploy to account 387776852668

set -e

AWS_PROFILE="hub-387776852668"
AWS_ACCOUNT="387776852668"
AWS_REGION="us-east-1"

export AWS_PROFILE

echo "=========================================="
echo "Pharma Data Exchange Hub - Integration Test Deployment"
echo "=========================================="
echo ""
echo "  Profile:  $AWS_PROFILE"
echo "  Account:  $AWS_ACCOUNT"
echo "  Region:   $AWS_REGION"
echo ""

# Verify prerequisites
for cmd in python3 aws cdk; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "Error: $cmd is not installed"
        exit 1
    fi
done

# Verify AWS profile is configured and resolves to the expected account
CALLER_ACCOUNT=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text 2>/dev/null) || {
    echo "Error: Unable to authenticate with profile $AWS_PROFILE"
    echo "Ensure the profile is configured in ~/.aws/config"
    exit 1
}

if [ "$CALLER_ACCOUNT" != "$AWS_ACCOUNT" ]; then
    echo "Error: Profile $AWS_PROFILE resolved to account $CALLER_ACCOUNT, expected $AWS_ACCOUNT"
    exit 1
fi

echo "Profile verified: account $AWS_ACCOUNT"
echo ""

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt -q

# Bootstrap CDK if needed
if ! aws cloudformation describe-stacks \
    --stack-name CDKToolkit \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" &> /dev/null; then
    echo "Bootstrapping CDK..."
    cdk bootstrap "aws://$AWS_ACCOUNT/$AWS_REGION" --profile "$AWS_PROFILE"
fi

# Synthesize and deploy all stacks
echo ""
echo "Deploying all stacks..."
cdk deploy --all \
    --require-approval never \
    --profile "$AWS_PROFILE" \
    --context account="$AWS_ACCOUNT" \
    --context region="$AWS_REGION" \
    --outputs-file cdk-outputs.json

echo ""
echo "=========================================="
echo "Deployment complete. Stack outputs saved to cdk-outputs.json"
echo "=========================================="

# Print key resource names from CloudFormation outputs
echo ""
echo "Deployed resources:"

STACKS=(
    "PharmaDataExchangeDatabaseStack"
    "PharmaDataExchangeDataLakeStack"
    "PharmaDataExchangeMonitoringStack"
    "PharmaDataExchangeContractApiStack"
    "PharmaDataExchangeSecretsStack"
)

for stack in "${STACKS[@]}"; do
    echo ""
    echo "--- $stack ---"
    aws cloudformation describe-stacks \
        --stack-name "$stack" \
        --region "$AWS_REGION" \
        --profile "$AWS_PROFILE" \
        --query "Stacks[0].Outputs[*].[OutputKey,OutputValue]" \
        --output table 2>/dev/null || echo "  (no outputs)"
done
