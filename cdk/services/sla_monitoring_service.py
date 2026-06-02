"""
SLA Monitoring Service

Publishes CloudWatch custom metrics for pipeline execution (execution time,
record counts, quality scores) with CMO and contract dimensions, and checks
SLA compliance against data-contract thresholds.  Tracks pipeline availability
(success rate, uptime percentage) over configurable measurement windows.

Requirements: 11.1, 11.2, 11.5
"""
import json
import logging
from collections import defaultdict
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CLOUDWATCH_NAMESPACE = 'CMO/DataPipeline'


class SLAMonitoringError(Exception):
    """Base exception for SLA monitoring operations."""
    pass


class SLAMonitoringService:
    """
    Service for pipeline execution metrics and SLA compliance checking.

    Publishes ExecutionTime, RecordsProcessed, and QualityScore metrics
    to CloudWatch with ContractId and CMOId dimensions.  Compares metrics
    against SLA thresholds defined in the data contract.
    """

    def __init__(
        self,
        cloudwatch_client=None,
        sns_client=None,
        region: str = 'us-east-1',
        account_id: str = '000000000000',
    ):
        self.cloudwatch_client = cloudwatch_client
        self.sns_client = sns_client
        self.region = region
        self.account_id = account_id
        # In-memory store for execution results keyed by contract_id
        self._execution_results: Dict[str, List[dict]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_pipeline_metrics(
        self,
        contract_id: str,
        cmo_id: str,
        execution_time_seconds: float,
        record_count: int,
        quality_score: float,
    ) -> None:
        """
        Publish pipeline execution metrics to CloudWatch.

        Publishes three metrics under the CMO/DataPipeline namespace:
        - ExecutionTime (Seconds) with ContractId + CMOId dimensions
        - RecordsProcessed (Count) with ContractId + CMOId dimensions
        - QualityScore (Percent) with ContractId + CMOId dimensions

        Args:
            contract_id: Data contract identifier.
            cmo_id: CMO identifier.
            execution_time_seconds: Pipeline execution duration in seconds.
            record_count: Number of records processed.
            quality_score: Overall quality score (0-100).

        Raises:
            SLAMonitoringError: If CloudWatch publish fails.
        """
        metric_data = [
            {
                'MetricName': 'ExecutionTime',
                'Value': float(execution_time_seconds),
                'Unit': 'Seconds',
                'Dimensions': [
                    {'Name': 'ContractId', 'Value': contract_id},
                    {'Name': 'CMOId', 'Value': cmo_id},
                ],
            },
            {
                'MetricName': 'RecordsProcessed',
                'Value': float(record_count),
                'Unit': 'Count',
                'Dimensions': [
                    {'Name': 'ContractId', 'Value': contract_id},
                    {'Name': 'CMOId', 'Value': cmo_id},
                ],
            },
            {
                'MetricName': 'QualityScore',
                'Value': float(quality_score),
                'Unit': 'Percent',
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
                "Published %d pipeline metrics for contract %s",
                len(metric_data), contract_id,
            )
        except Exception as exc:
            raise SLAMonitoringError(
                f"Failed to publish CloudWatch metrics: {exc}"
            ) from exc

    def record_execution_result(
        self,
        contract_id: str,
        cmo_id: str,
        success: bool,
    ) -> None:
        """
        Record whether a pipeline execution succeeded or failed.

        Stores the result in memory and publishes SuccessRate and
        AvailabilityPercent metrics to CloudWatch.

        Args:
            contract_id: Data contract identifier.
            cmo_id: CMO identifier.
            success: True if the execution succeeded, False otherwise.

        Raises:
            SLAMonitoringError: If CloudWatch publish fails.
        """
        self._execution_results[contract_id].append({
            'cmo_id': cmo_id,
            'success': success,
        })

        # Compute current availability and publish metrics
        availability = self.calculate_availability(contract_id)

        metric_data = [
            {
                'MetricName': 'SuccessRate',
                'Value': availability['success_rate'],
                'Unit': 'Percent',
                'Dimensions': [
                    {'Name': 'ContractId', 'Value': contract_id},
                    {'Name': 'CMOId', 'Value': cmo_id},
                ],
            },
            {
                'MetricName': 'AvailabilityPercent',
                'Value': availability['uptime_percentage'],
                'Unit': 'Percent',
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
                "Published availability metrics for contract %s "
                "(success_rate=%.2f%%, uptime=%.2f%%)",
                contract_id,
                availability['success_rate'],
                availability['uptime_percentage'],
            )
        except Exception as exc:
            raise SLAMonitoringError(
                f"Failed to publish availability metrics: {exc}"
            ) from exc

    def calculate_availability(self, contract_id: str) -> dict:
        """
        Compute success rate and uptime percentage for a contract.

        Success rate is the ratio of successful executions to total
        executions.  Uptime percentage mirrors success rate (a pipeline
        is considered "up" when its executions succeed).

        Args:
            contract_id: Data contract identifier.

        Returns:
            dict with total_executions, successful_executions,
            success_rate (0-100), and uptime_percentage (0-100).
        """
        results = self._execution_results.get(contract_id, [])
        total = len(results)
        if total == 0:
            return {
                'total_executions': 0,
                'successful_executions': 0,
                'success_rate': 100.0,
                'uptime_percentage': 100.0,
            }

        successful = sum(1 for r in results if r['success'])
        success_rate = (successful / total) * 100.0
        return {
            'total_executions': total,
            'successful_executions': successful,
            'success_rate': round(success_rate, 2),
            'uptime_percentage': round(success_rate, 2),
        }

    def check_sla_compliance(
        self,
        contract_id: str,
        cmo_id: str,
        execution_time_seconds: float,
        quality_score: float,
        data_contract=None,
    ) -> dict:
        """
        Compare pipeline metrics against SLA thresholds.

        Args:
            contract_id: Data contract identifier.
            cmo_id: CMO identifier.
            execution_time_seconds: Pipeline execution duration in seconds.
            quality_score: Overall quality score (0-100).
            data_contract: DataContract (or duck-typed object with .sla).

        Returns:
            dict with compliance results including timeliness_ok,
            quality_ok, availability_ok, overall_compliant, and any breaches.
        """
        result = {
            'contract_id': contract_id,
            'cmo_id': cmo_id,
            'timeliness_ok': True,
            'quality_ok': True,
            'availability_ok': True,
            'overall_compliant': True,
            'breaches': [],
        }

        if data_contract is None:
            return result

        sla = data_contract.sla

        # Requirement 11.1 – compare execution time against timeliness
        max_delay_hours = sla.timeliness.get('maxDelayHours', None)
        if max_delay_hours is not None:
            execution_hours = execution_time_seconds / 3600.0
            if execution_hours > max_delay_hours:
                result['timeliness_ok'] = False
                result['overall_compliant'] = False
                result['breaches'].append({
                    'type': 'timeliness',
                    'threshold_hours': max_delay_hours,
                    'actual_hours': round(execution_hours, 4),
                })

        # Requirement 11.2 – compare quality score against quality threshold
        min_quality = sla.quality.get('minQualityScore', None)
        if min_quality is not None:
            if quality_score < min_quality:
                result['quality_ok'] = False
                result['overall_compliant'] = False
                result['breaches'].append({
                    'type': 'quality',
                    'threshold_score': min_quality,
                    'actual_score': quality_score,
                })

        # Requirement 11.5 – compare availability against uptime threshold
        availability_sla = getattr(sla, 'availability', None)
        if availability_sla is not None:
            uptime_threshold = availability_sla.get('uptimePercentage', None)
            if uptime_threshold is not None:
                availability = self.calculate_availability(contract_id)
                actual_uptime = availability['uptime_percentage']
                if actual_uptime < uptime_threshold:
                    result['availability_ok'] = False
                    result['overall_compliant'] = False
                    result['breaches'].append({
                        'type': 'availability',
                        'threshold_uptime': uptime_threshold,
                        'actual_uptime': actual_uptime,
                    })

        return result

    def send_alert(
        self,
        severity: str,
        message: str,
        contract_id: str,
        cmo_id: str,
    ) -> None:
        """
        Send SNS notification for SLA alerts.

        Args:
            severity: Alert severity ('warning' or 'critical').
            message: Alert message body (JSON string or plain text).
            contract_id: Data contract identifier.
            cmo_id: CMO identifier.

        Raises:
            SLAMonitoringError: If SNS publish fails.
        """
        topic_arn = (
            f"arn:aws:sns:{self.region}:{self.account_id}:cmo-alerts-{severity}"
        )

        try:
            self.sns_client.publish(
                TopicArn=topic_arn,
                Subject=f'[{severity.upper()}] CMO Pipeline Alert',
                Message=message,
                MessageAttributes={
                    'ContractId': {
                        'DataType': 'String',
                        'StringValue': contract_id,
                    },
                    'CMOId': {
                        'DataType': 'String',
                        'StringValue': cmo_id,
                    },
                    'Severity': {
                        'DataType': 'String',
                        'StringValue': severity,
                    },
                },
            )
            logger.info(
                "Sent %s alert for contract %s", severity, contract_id,
            )
        except Exception as exc:
            raise SLAMonitoringError(
                f"Failed to send {severity} alert: {exc}"
            ) from exc
