"""
SLA Alarm Service

Creates CloudWatch alarm configurations for SLA violations with
warning and critical severity levels.  Each alarm targets a metric
in the CMO/DataPipeline namespace and routes notifications to the
appropriate SNS topic.

Requirements: 11.3, 11.6
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CLOUDWATCH_NAMESPACE = 'CMO/DataPipeline'


class SLAAlarmService:
    """
    Generates CloudWatch alarm configuration dicts for SLA violation
    detection.  Supports configurable warning/critical thresholds and
    wires alarm actions to SNS topic ARNs.
    """

    # Default thresholds
    DEFAULT_THRESHOLDS = {
        'ExecutionTime': {'warning': 0.80, 'critical': 1.00},
        'QualityScore': {'warning': 95.0, 'critical': 90.0},
        'SuccessRate': {'warning': 99.0, 'critical': 95.0},
    }

    def __init__(
        self,
        warning_topic_arn: str,
        critical_topic_arn: str,
        sla_breach_topic_arn: str,
        region: str = 'us-east-1',
    ):
        self.warning_topic_arn = warning_topic_arn
        self.critical_topic_arn = critical_topic_arn
        self.sla_breach_topic_arn = sla_breach_topic_arn
        self.region = region

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_execution_time_alarms(
        self,
        sla_max_seconds: float,
        warning_pct: float = 0.80,
        critical_pct: float = 1.00,
        evaluation_periods: int = 3,
        period_seconds: int = 300,
    ) -> List[dict]:
        """
        Create warning and critical alarms for ExecutionTime.

        The warning threshold fires at ``sla_max_seconds * warning_pct``
        and the critical threshold at ``sla_max_seconds * critical_pct``.

        Args:
            sla_max_seconds: SLA maximum execution time in seconds.
            warning_pct: Fraction of SLA for warning (default 80%).
            critical_pct: Fraction of SLA for critical (default 100%).
            evaluation_periods: Consecutive periods before alarm fires.
            period_seconds: CloudWatch metric period in seconds.

        Returns:
            List of two alarm configuration dicts (warning, critical).
        """
        warning_threshold = sla_max_seconds * warning_pct
        critical_threshold = sla_max_seconds * critical_pct

        return [
            self._build_alarm(
                alarm_name='SLA-ExecutionTime-Warning',
                metric_name='ExecutionTime',
                threshold=warning_threshold,
                comparison='GreaterThanThreshold',
                severity='warning',
                evaluation_periods=evaluation_periods,
                period_seconds=period_seconds,
                description=(
                    f'ExecutionTime exceeded {warning_pct*100:.0f}% of SLA '
                    f'({warning_threshold:.1f}s of {sla_max_seconds:.1f}s max)'
                ),
            ),
            self._build_alarm(
                alarm_name='SLA-ExecutionTime-Critical',
                metric_name='ExecutionTime',
                threshold=critical_threshold,
                comparison='GreaterThanThreshold',
                severity='critical',
                evaluation_periods=evaluation_periods,
                period_seconds=period_seconds,
                description=(
                    f'ExecutionTime exceeded {critical_pct*100:.0f}% of SLA '
                    f'({critical_threshold:.1f}s of {sla_max_seconds:.1f}s max)'
                ),
            ),
        ]

    def create_quality_score_alarms(
        self,
        warning_threshold: float = 95.0,
        critical_threshold: float = 90.0,
        evaluation_periods: int = 3,
        period_seconds: int = 300,
    ) -> List[dict]:
        """
        Create warning and critical alarms for QualityScore.

        Fires when QualityScore drops below the given thresholds.

        Args:
            warning_threshold: Quality score warning level (default 95%).
            critical_threshold: Quality score critical level (default 90%).
            evaluation_periods: Consecutive periods before alarm fires.
            period_seconds: CloudWatch metric period in seconds.

        Returns:
            List of two alarm configuration dicts (warning, critical).
        """
        return [
            self._build_alarm(
                alarm_name='SLA-QualityScore-Warning',
                metric_name='QualityScore',
                threshold=warning_threshold,
                comparison='LessThanThreshold',
                severity='warning',
                evaluation_periods=evaluation_periods,
                period_seconds=period_seconds,
                description=(
                    f'QualityScore dropped below warning threshold '
                    f'({warning_threshold:.1f}%)'
                ),
            ),
            self._build_alarm(
                alarm_name='SLA-QualityScore-Critical',
                metric_name='QualityScore',
                threshold=critical_threshold,
                comparison='LessThanThreshold',
                severity='critical',
                evaluation_periods=evaluation_periods,
                period_seconds=period_seconds,
                description=(
                    f'QualityScore dropped below critical threshold '
                    f'({critical_threshold:.1f}%)'
                ),
            ),
        ]

    def create_success_rate_alarms(
        self,
        warning_threshold: float = 99.0,
        critical_threshold: float = 95.0,
        evaluation_periods: int = 3,
        period_seconds: int = 300,
    ) -> List[dict]:
        """
        Create warning and critical alarms for SuccessRate.

        Fires when SuccessRate drops below the given thresholds.

        Args:
            warning_threshold: Success rate warning level (default 99%).
            critical_threshold: Success rate critical level (default 95%).
            evaluation_periods: Consecutive periods before alarm fires.
            period_seconds: CloudWatch metric period in seconds.

        Returns:
            List of two alarm configuration dicts (warning, critical).
        """
        return [
            self._build_alarm(
                alarm_name='SLA-SuccessRate-Warning',
                metric_name='SuccessRate',
                threshold=warning_threshold,
                comparison='LessThanThreshold',
                severity='warning',
                evaluation_periods=evaluation_periods,
                period_seconds=period_seconds,
                description=(
                    f'SuccessRate dropped below warning threshold '
                    f'({warning_threshold:.1f}%)'
                ),
            ),
            self._build_alarm(
                alarm_name='SLA-SuccessRate-Critical',
                metric_name='SuccessRate',
                threshold=critical_threshold,
                comparison='LessThanThreshold',
                severity='critical',
                evaluation_periods=evaluation_periods,
                period_seconds=period_seconds,
                description=(
                    f'SuccessRate dropped below critical threshold '
                    f'({critical_threshold:.1f}%)'
                ),
            ),
        ]

    def create_all_alarms(
        self,
        sla_max_seconds: float = 3600.0,
        execution_time_warning_pct: float = 0.80,
        execution_time_critical_pct: float = 1.00,
        quality_warning: float = 95.0,
        quality_critical: float = 90.0,
        success_rate_warning: float = 99.0,
        success_rate_critical: float = 95.0,
        evaluation_periods: int = 3,
        period_seconds: int = 300,
    ) -> List[dict]:
        """
        Create the full set of SLA violation alarms.

        Returns:
            List of six alarm configuration dicts.
        """
        alarms: List[dict] = []
        alarms.extend(self.create_execution_time_alarms(
            sla_max_seconds=sla_max_seconds,
            warning_pct=execution_time_warning_pct,
            critical_pct=execution_time_critical_pct,
            evaluation_periods=evaluation_periods,
            period_seconds=period_seconds,
        ))
        alarms.extend(self.create_quality_score_alarms(
            warning_threshold=quality_warning,
            critical_threshold=quality_critical,
            evaluation_periods=evaluation_periods,
            period_seconds=period_seconds,
        ))
        alarms.extend(self.create_success_rate_alarms(
            warning_threshold=success_rate_warning,
            critical_threshold=success_rate_critical,
            evaluation_periods=evaluation_periods,
            period_seconds=period_seconds,
        ))
        return alarms

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_alarm(
        self,
        alarm_name: str,
        metric_name: str,
        threshold: float,
        comparison: str,
        severity: str,
        evaluation_periods: int,
        period_seconds: int,
        description: str,
    ) -> dict:
        """
        Build a single alarm configuration dict compatible with the
        CloudWatch ``put_metric_alarm`` API.
        """
        if severity == 'critical':
            alarm_actions = [self.critical_topic_arn, self.sla_breach_topic_arn]
        else:
            alarm_actions = [self.warning_topic_arn]

        return {
            'AlarmName': alarm_name,
            'AlarmDescription': description,
            'Namespace': CLOUDWATCH_NAMESPACE,
            'MetricName': metric_name,
            'Statistic': 'Average',
            'Period': period_seconds,
            'EvaluationPeriods': evaluation_periods,
            'Threshold': threshold,
            'ComparisonOperator': comparison,
            'AlarmActions': alarm_actions,
            'Severity': severity,
            'TreatMissingData': 'notBreaching',
        }
