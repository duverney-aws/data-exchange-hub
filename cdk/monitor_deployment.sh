#!/bin/bash
# Post-deployment monitoring script for Pharma Data Exchange Hub
#
# Watches CloudWatch metrics, alarms, Lambda errors, and CloudTrail events
# for the first 30 minutes after a production deployment.
#
# Usage:
#   ./monitor_deployment.sh --profile <aws-profile> [--duration <minutes>]

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
AWS_REGION="us-east-1"
AWS_PROFILE=""
DURATION_MINUTES=30
CHECK_INTERVAL=60  # seconds between checks

# ── Parse arguments ───────────────────────────────────────────────────────────
usage() {
    echo "Usage: $0 --profile <aws-profile> [--duration <minutes>]"
    echo ""
    echo "Options:"
    echo "  --profile    AWS CLI profile name (required)"
    echo "  --duration   Monitoring duration in minutes (default: 30)"
    echo "  --help       Show this help message"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)   AWS_PROFILE="$2"; shift 2 ;;
        --duration)  DURATION_MINUTES="$2"; shift 2 ;;
        --help)      usage ;;
        *)           echo "Unknown option: $1"; usage ;;
    esac
done

if [[ -z "$AWS_PROFILE" ]]; then
    echo "Error: --profile is required."
    usage
fi

export AWS_PROFILE

ISSUES_FOUND=0
START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "=========================================="
echo "Pharma Data Exchange Hub - Post-Deployment Monitor"
echo "=========================================="
echo ""
echo "  Profile:   $AWS_PROFILE"
echo "  Region:    $AWS_REGION"
echo "  Duration:  ${DURATION_MINUTES}m"
echo "  Started:   $START_TIME"
echo ""

# ── Helper functions ──────────────────────────────────────────────────────────

check_alarms() {
    echo "--- CloudWatch Alarms ---"
    ALARM_JSON=$(aws cloudwatch describe-alarms \
        --state-value ALARM \
        --region "$AWS_REGION" \
        --profile "$AWS_PROFILE" \
        --query "MetricAlarms[*].[AlarmName,StateReason]" \
        --output json 2>/dev/null)

    ALARM_COUNT=$(echo "$ALARM_JSON" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)

    if [[ "$ALARM_COUNT" -gt 0 ]]; then
        echo "  WARNING: $ALARM_COUNT alarm(s) in ALARM state:"
        echo "$ALARM_JSON" | python3 -c "
import sys, json
for a in json.load(sys.stdin):
    print(f'    - {a[0]}: {a[1][:120]}')
"
        ISSUES_FOUND=$((ISSUES_FOUND + ALARM_COUNT))
    else
        echo "  OK: No alarms in ALARM state."
    fi
    echo ""
}

check_lambda_errors() {
    echo "--- Lambda Function Errors (last ${DURATION_MINUTES}m) ---"

    # List Lambda functions related to the platform
    FUNCTIONS=$(aws lambda list-functions \
        --region "$AWS_REGION" \
        --profile "$AWS_PROFILE" \
        --query "Functions[?contains(FunctionName, 'PharmaDataExchange')].FunctionName" \
        --output json 2>/dev/null)

    FUNC_COUNT=$(echo "$FUNCTIONS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)

    if [[ "$FUNC_COUNT" -eq 0 ]]; then
        echo "  No PharmaDataExchange Lambda functions found."
        echo ""
        return
    fi

    ERROR_FOUND=false
    END_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    echo "$FUNCTIONS" | python3 -c "import sys,json; [print(f) for f in json.load(sys.stdin)]" 2>/dev/null | while read -r fn; do
        ERRORS=$(aws cloudwatch get-metric-statistics \
            --namespace "AWS/Lambda" \
            --metric-name "Errors" \
            --dimensions "Name=FunctionName,Value=$fn" \
            --start-time "$START_TIME" \
            --end-time "$END_TIME" \
            --period 300 \
            --statistics Sum \
            --region "$AWS_REGION" \
            --profile "$AWS_PROFILE" \
            --query "Datapoints[].Sum" \
            --output json 2>/dev/null)

        TOTAL=$(echo "$ERRORS" | python3 -c "import sys,json; print(int(sum(json.load(sys.stdin))))" 2>/dev/null || echo 0)

        if [[ "$TOTAL" -gt 0 ]]; then
            echo "  WARNING: $fn — $TOTAL error(s)"
            ERROR_FOUND=true
        fi
    done

    if [[ "$ERROR_FOUND" == "false" ]]; then
        echo "  OK: No Lambda errors detected."
    fi
    echo ""
}

check_cloudtrail_errors() {
    echo "--- CloudTrail Error Events (last ${DURATION_MINUTES}m) ---"

    ERROR_EVENTS=$(aws cloudtrail lookup-events \
        --start-time "$START_TIME" \
        --lookup-attributes "AttributeKey=ReadOnly,AttributeValue=false" \
        --max-results 20 \
        --region "$AWS_REGION" \
        --profile "$AWS_PROFILE" \
        --query "Events[?contains(CloudTrailEvent, '\"errorCode\"')].{Time:EventTime,Name:EventName,Source:EventSource}" \
        --output json 2>/dev/null || echo "[]")

    EVENT_COUNT=$(echo "$ERROR_EVENTS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)

    if [[ "$EVENT_COUNT" -gt 0 ]]; then
        echo "  WARNING: $EVENT_COUNT error event(s) in CloudTrail:"
        echo "$ERROR_EVENTS" | python3 -c "
import sys, json
for e in json.load(sys.stdin)[:10]:
    print(f'    - {e.get(\"Name\",\"?\")} from {e.get(\"Source\",\"?\")} at {e.get(\"Time\",\"?\")}')
"
        ISSUES_FOUND=$((ISSUES_FOUND + EVENT_COUNT))
    else
        echo "  OK: No error events in CloudTrail."
    fi
    echo ""
}

check_stack_health() {
    echo "--- CloudFormation Stack Status ---"
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

    for stack in "${STACKS[@]}"; do
        STATUS=$(aws cloudformation describe-stacks \
            --stack-name "$stack" \
            --region "$AWS_REGION" \
            --profile "$AWS_PROFILE" \
            --query "Stacks[0].StackStatus" \
            --output text 2>/dev/null || echo "NOT_FOUND")

        if [[ "$STATUS" == *"COMPLETE"* && "$STATUS" != *"ROLLBACK"* ]]; then
            echo "  OK: $stack — $STATUS"
        else
            echo "  WARNING: $stack — $STATUS"
            ISSUES_FOUND=$((ISSUES_FOUND + 1))
        fi
    done
    echo ""
}

# ── Run monitoring loop ───────────────────────────────────────────────────────
END_EPOCH=$(( $(date +%s) + DURATION_MINUTES * 60 ))
ITERATION=1

echo "Starting monitoring (Ctrl+C to stop early)..."
echo ""

while [[ $(date +%s) -lt $END_EPOCH ]]; do
    REMAINING=$(( (END_EPOCH - $(date +%s)) / 60 ))
    echo "=========================================="
    echo "Check #${ITERATION} — $(date -u +"%H:%M:%S UTC") — ${REMAINING}m remaining"
    echo "=========================================="
    echo ""

    check_stack_health
    check_alarms
    check_lambda_errors
    check_cloudtrail_errors

    ITERATION=$((ITERATION + 1))

    # Sleep unless we've exceeded the duration
    if [[ $(date +%s) -lt $END_EPOCH ]]; then
        echo "Next check in ${CHECK_INTERVAL}s..."
        echo ""
        sleep "$CHECK_INTERVAL"
    fi
done

# ── Final summary ─────────────────────────────────────────────────────────────
echo ""
echo "=========================================="
echo "Monitoring Complete"
echo "=========================================="
echo "  Duration:  ${DURATION_MINUTES} minutes"
echo "  Checks:    $((ITERATION - 1))"

if [[ $ISSUES_FOUND -gt 0 ]]; then
    echo "  Status:    WARNING — $ISSUES_FOUND issue(s) detected"
    echo ""
    echo "Review the warnings above and check CloudWatch dashboards for details."
    exit 1
else
    echo "  Status:    HEALTHY — No issues detected"
    echo ""
    echo "Production deployment looks good."
    exit 0
fi
