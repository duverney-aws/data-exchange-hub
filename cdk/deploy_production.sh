#!/bin/bash
# Production deployment script for Pharma Data Exchange Hub
# Requires explicit AWS_PROFILE and AWS_ACCOUNT parameters for safety.
#
# Usage:
#   ./deploy_production.sh --profile <aws-profile> --account <account-id> [--dry-run]
#
# Examples:
#   ./deploy_production.sh --profile prod-pharma --account 123456789012
#   ./deploy_production.sh --profile prod-pharma --account 123456789012 --dry-run

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
AWS_REGION="us-east-1"
DRY_RUN=false
AWS_PROFILE=""
AWS_ACCOUNT=""
OUTPUTS_FILE="production-outputs.json"

# ── All 8 CDK stacks in dependency order ──────────────────────────────────────
STACKS=(
    "PharmaDataExchangeSecretsStack"
    "PharmaDataExchangeDatabaseStack"
    "PharmaDataExchangeDataLakeStack"
    "PharmaDataExchangeMonitoringStack"
    "PharmaDataExchangeContractApiStack"
    "PharmaDataExchangePipelineOrchestrationStack"
    "PharmaDataExchangeSecurityStack"
    "PharmaDataExchangeAuditComplianceStack"
)

# ── Parse arguments ───────────────────────────────────────────────────────────
usage() {
    echo "Usage: $0 --profile <aws-profile> --account <account-id> [--dry-run]"
    echo ""
    echo "Options:"
    echo "  --profile    AWS CLI profile name (required)"
    echo "  --account    Expected AWS account ID (required)"
    echo "  --dry-run    Synthesize only, do not deploy"
    echo "  --help       Show this help message"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)  AWS_PROFILE="$2"; shift 2 ;;
        --account)  AWS_ACCOUNT="$2"; shift 2 ;;
        --dry-run)  DRY_RUN=true; shift ;;
        --help)     usage ;;
        *)          echo "Unknown option: $1"; usage ;;
    esac
done

if [[ -z "$AWS_PROFILE" || -z "$AWS_ACCOUNT" ]]; then
    echo "Error: --profile and --account are required for production deployments."
    usage
fi

export AWS_PROFILE

echo "=========================================="
echo "Pharma Data Exchange Hub - PRODUCTION Deployment"
echo "=========================================="
echo ""
echo "  Profile:  $AWS_PROFILE"
echo "  Account:  $AWS_ACCOUNT"
echo "  Region:   $AWS_REGION"
echo "  Dry Run:  $DRY_RUN"
echo ""

# ── Prerequisite checks ──────────────────────────────────────────────────────
echo "Checking prerequisites..."
for cmd in python3 aws cdk; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "Error: $cmd is not installed."
        exit 1
    fi
done
echo "  All tools present."

# ── Verify AWS profile resolves to the expected account ───────────────────────
echo "Verifying AWS credentials..."
CALLER_ACCOUNT=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Account --output text 2>/dev/null) || {
    echo "Error: Unable to authenticate with profile '$AWS_PROFILE'."
    echo "Ensure the profile is configured in ~/.aws/config or ~/.aws/credentials."
    exit 1
}

if [[ "$CALLER_ACCOUNT" != "$AWS_ACCOUNT" ]]; then
    echo "Error: Profile '$AWS_PROFILE' resolved to account $CALLER_ACCOUNT, expected $AWS_ACCOUNT."
    echo "Aborting to prevent deploying to the wrong account."
    exit 1
fi
echo "  Profile verified: account $AWS_ACCOUNT"

CALLER_ARN=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query Arn --output text)
echo "  Identity: $CALLER_ARN"
echo ""

# ── Install dependencies ─────────────────────────────────────────────────────
echo "Installing Python dependencies..."
pip install -r requirements.txt -q

# ── Bootstrap CDK if needed ──────────────────────────────────────────────────
if ! aws cloudformation describe-stacks \
    --stack-name CDKToolkit \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" &> /dev/null; then
    echo "CDK not bootstrapped. Bootstrapping..."
    cdk bootstrap "aws://$AWS_ACCOUNT/$AWS_REGION" --profile "$AWS_PROFILE"
fi

# ── Synthesize CloudFormation templates ──────────────────────────────────────
echo ""
echo "Synthesizing CloudFormation templates..."
cdk synth \
    --profile "$AWS_PROFILE" \
    --context account="$AWS_ACCOUNT" \
    --context region="$AWS_REGION" \
    --quiet

TEMPLATE_COUNT=$(find cdk.out -name "*.template.json" 2>/dev/null | wc -l)
echo "  Generated $TEMPLATE_COUNT CloudFormation templates."

# Validate templates exist for all expected stacks
echo "Validating templates..."
MISSING=0
for stack in "${STACKS[@]}"; do
    if ! ls cdk.out/${stack}.template.json &> /dev/null; then
        echo "  WARNING: Template missing for $stack"
        MISSING=$((MISSING + 1))
    fi
done

if [[ $MISSING -gt 0 ]]; then
    echo "Error: $MISSING stack template(s) missing. Check cdk synth output."
    exit 1
fi
echo "  All 8 stack templates validated."

# ── Dry-run exit ─────────────────────────────────────────────────────────────
if [[ "$DRY_RUN" == "true" ]]; then
    echo ""
    echo "=========================================="
    echo "DRY RUN complete. Templates synthesized in cdk.out/"
    echo "No resources were deployed."
    echo "=========================================="
    exit 0
fi

# ── Deploy all stacks ────────────────────────────────────────────────────────
echo ""
echo "Deploying all 8 stacks to production..."
echo "  (--require-approval broadening: IAM/security changes need review)"
echo ""

cdk deploy --all \
    --require-approval broadening \
    --profile "$AWS_PROFILE" \
    --context account="$AWS_ACCOUNT" \
    --context region="$AWS_REGION" \
    --outputs-file "$OUTPUTS_FILE"

echo ""
echo "=========================================="
echo "Deployment complete. Outputs saved to $OUTPUTS_FILE"
echo "=========================================="

# ── Print deployed resource summary ──────────────────────────────────────────
echo ""
echo "Deployed Resource Summary"
echo "=========================================="

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

echo ""
echo "Next steps:"
echo "  1. Run smoke tests:       python3 smoke_tests.py --profile $AWS_PROFILE"
echo "  2. Monitor deployment:    ./monitor_deployment.sh --profile $AWS_PROFILE"
echo "  3. Subscribe to SNS alerts (see docs/DEPLOYMENT_GUIDE.md)"
echo ""
