"""
Quality Metrics Service

Logs quality scores to CloudWatch, updates contract status in DynamoDB,
and sends SNS notifications when thresholds are breached.

Requirements: 8.5, 8.6
"""
import json
import logging
from typing import Optional

from services.data_quality_service import QualityReport

logger = logging.getLogger(__name__)

CLOUDWATCH_NAMESPACE = 'CMO/DataPipeline'


class QualityMetricsError(Exception):
    """Base exception for quality metrics operations."""
    pass


class QualityMetricsService:
    """
    Service for quality metrics logging and notifications.

    Publishes quality metrics to CloudWatch, updates contract status
    in DynamoDB via ContractService, and sends SNS notifications
    when SLA thresholds are breached.
    """

    def __init__(
        self,
        cloudwatch_client=None,
        sns_client=None,
        contract_service=None,
        region: str = 'us-east-1',
        account_id: str = '000000000000',
    ):
        """
        Args:
            cloudwatch_client: boto3 CloudWatch client (injected for testability).
            sns_client: boto3 SNS client (injected for testability).
            contract_service: ContractService instance for status updates.
            region: AWS region for SNS topic ARN construction.
            account_id: AWS account ID for SNS topic ARN construction.
        """
        self.cloudwatch_client = cloudwatch_client
        self.sns_client = sns_client
        self.contract_service = contract_service
        self.region = region
        self.account_id = account_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_quality_metrics(
        self,
        quality_report: QualityReport,
        contract_id: str,
        cmo_id: str,
        data_contract=None,
    ) -> dict:
        """
        Orchestrate quality metrics processing.

        Logs metrics to CloudWatch, checks SLA thresholds and sends
        notifications if breached, and updates contract status if needed.

        Args:
            quality_report: QualityReport from DataQualityService.
            contract_id: Data contract ID.
            cmo_id: CMO identifier.
            data_contract: Optional DataContract for SLA threshold checks.

        Returns:
            dict summarising actions taken.
        """
        actions = {
            'metrics_published': False,
            'contract_status_updated': False,
            'new_status': None,
            'notifications_sent': [],
        }

        # 1. Log metrics to CloudWatch
        self.log_quality_metrics(quality_report, contract_id, cmo_id)
        actions['metrics_published'] = True

        # 2. Check SLA thresholds and send notifications
        if data_contract is not None:
            sla_quality = data_contract.sla.quality
            min_score = sla_quality.get('minQualityScore', 0)

            if quality_report.overall_score < min_score:
                self._send_sla_breach_notification(
                    contract_id, cmo_id, quality_report, min_score,
                )
                actions['notifications_sent'].append('sla_quality_breach')

        # Send notification for error-severity rule failures
        if quality_report.errors > 0:
            self._send_error_rules_notification(
                contract_id, cmo_id, quality_report,
            )
            actions['notifications_sent'].append('error_rules_failed')

        # 3. Update contract status
        if self.contract_service is not None:
            if quality_report.errors > 0:
                self.contract_service.update_contract_status(
                    contract_id, 'suspended',
                )
                actions['contract_status_updated'] = True
                actions['new_status'] = 'suspended'
            elif quality_report.passed:
                self.contract_service.update_contract_status(
                    contract_id, 'active',
                )
                actions['contract_status_updated'] = True
                actions['new_status'] = 'active'

        return actions

    def log_quality_metrics(
        self,
        quality_report: QualityReport,
        contract_id: str,
        cmo_id: str,
    ) -> None:
        """
        Publish quality metrics to CloudWatch.

        Publishes QualityScore, RulesPassedCount, RulesFailedCount,
        and ValidationResult metrics.

        Args:
            quality_report: QualityReport from DataQualityService.
            contract_id: Data contract ID.
            cmo_id: CMO identifier.
        """
        metric_data = [
            {
                'MetricName': 'QualityScore',
                'Value': quality_report.overall_score,
                'Unit': 'Percent',
                'Dimensions': [
                    {'Name': 'ContractId', 'Value': contract_id},
                    {'Name': 'CMOId', 'Value': cmo_id},
                ],
            },
            {
                'MetricName': 'RulesPassedCount',
                'Value': float(quality_report.rules_passed),
                'Unit': 'Count',
                'Dimensions': [
                    {'Name': 'ContractId', 'Value': contract_id},
                ],
            },
            {
                'MetricName': 'RulesFailedCount',
                'Value': float(quality_report.rules_failed),
                'Unit': 'Count',
                'Dimensions': [
                    {'Name': 'ContractId', 'Value': contract_id},
                ],
            },
            {
                'MetricName': 'ValidationResult',
                'Value': 1.0 if quality_report.passed else 0.0,
                'Unit': 'Count',
                'Dimensions': [
                    {'Name': 'ContractId', 'Value': contract_id},
                    {'Name': 'CMOId', 'Value': cmo_id},
                ],
            },
        ]

        try:
            self.cloudwatch_client.put_metric_data(
                Namespace=CLOUDWATCH_NAMESPACE,
                MetricData=metric_data,
            )
            logger.info(
                "Published %d quality metrics for contract %s",
                len(metric_data), contract_id,
            )
        except Exception as exc:
            raise QualityMetricsError(
                f"Failed to publish CloudWatch metrics: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Notification helpers
    # ------------------------------------------------------------------

    def _send_sla_breach_notification(
        self,
        contract_id: str,
        cmo_id: str,
        quality_report: QualityReport,
        min_score: float,
    ) -> None:
        """Send SNS notification for SLA quality threshold breach."""
        failed_rules = [
            r.to_dict() for r in quality_report.rule_results if not r.passed
        ]

        message = {
            'alert_type': 'sla_quality_breach',
            'contract_id': contract_id,
            'cmo_id': cmo_id,
            'quality_score': quality_report.overall_score,
            'min_quality_score': min_score,
            'failed_rules': failed_rules,
            'guidance': (
                f"Quality score {quality_report.overall_score}% is below "
                f"the SLA threshold of {min_score}%. Review failed rules "
                f"and resubmit data after corrections."
            ),
        }

        topic_arn = (
            f"arn:aws:sns:{self.region}:{self.account_id}:cmo-alerts-warning"
        )

        try:
            self.sns_client.publish(
                TopicArn=topic_arn,
                Subject='[WARNING] CMO Pipeline Alert - SLA Quality Breach',
                Message=json.dumps(message),
                MessageAttributes={
                    'ContractId': {
                        'DataType': 'String',
                        'StringValue': contract_id,
                    },
                    'Severity': {
                        'DataType': 'String',
                        'StringValue': 'warning',
                    },
                },
            )
            logger.info(
                "Sent SLA breach notification for contract %s", contract_id,
            )
        except Exception as exc:
            raise QualityMetricsError(
                f"Failed to send SLA breach notification: {exc}"
            ) from exc

    def _send_error_rules_notification(
        self,
        contract_id: str,
        cmo_id: str,
        quality_report: QualityReport,
    ) -> None:
        """Send SNS notification for error-severity rule failures."""
        error_rules = [
            r.to_dict()
            for r in quality_report.rule_results
            if not r.passed and r.severity == 'error'
        ]

        message = {
            'alert_type': 'error_rules_failed',
            'contract_id': contract_id,
            'cmo_id': cmo_id,
            'quality_score': quality_report.overall_score,
            'error_count': quality_report.errors,
            'failed_error_rules': error_rules,
            'guidance': (
                f"{quality_report.errors} error-severity rule(s) failed. "
                f"Contract will be suspended. Review the failed rules "
                f"and resubmit corrected data to reactivate."
            ),
        }

        topic_arn = (
            f"arn:aws:sns:{self.region}:{self.account_id}:cmo-alerts-critical"
        )

        try:
            self.sns_client.publish(
                TopicArn=topic_arn,
                Subject='[CRITICAL] CMO Pipeline Alert - Error Rules Failed',
                Message=json.dumps(message),
                MessageAttributes={
                    'ContractId': {
                        'DataType': 'String',
                        'StringValue': contract_id,
                    },
                    'Severity': {
                        'DataType': 'String',
                        'StringValue': 'critical',
                    },
                },
            )
            logger.info(
                "Sent error rules notification for contract %s", contract_id,
            )
        except Exception as exc:
            raise QualityMetricsError(
                f"Failed to send error rules notification: {exc}"
            ) from exc
