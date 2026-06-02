"""
Unit Tests for Quality Metrics Service – CloudWatch metric publishing,
DynamoDB contract status updates, and SNS notification sending.

Requirements: 8.5, 8.6
"""
import json
import sys
import os

import pytest
from unittest.mock import MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.data_quality_service import QualityReport, RuleEvaluationResult
from services.quality_metrics_service import (
    QualityMetricsError,
    QualityMetricsService,
    CLOUDWATCH_NAMESPACE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rule_result(
    rule_id='R1',
    passed=True,
    severity='error',
    actual_value=100.0,
    threshold=99.0,
):
    return RuleEvaluationResult(
        rule_id=rule_id,
        rule_name=f'Rule {rule_id}',
        rule_type='completeness',
        severity=severity,
        passed=passed,
        actual_value=actual_value,
        threshold=threshold,
        message='test',
    )


def _passing_report():
    """QualityReport where all rules pass."""
    return QualityReport([
        _make_rule_result('R1', passed=True, severity='error'),
        _make_rule_result('R2', passed=True, severity='warning'),
    ])


def _failing_report_with_errors():
    """QualityReport with error-severity failures."""
    return QualityReport([
        _make_rule_result('R1', passed=False, severity='error', actual_value=60.0),
        _make_rule_result('R2', passed=True, severity='warning'),
    ])


def _failing_report_warnings_only():
    """QualityReport with only warning-severity failures (still passes)."""
    return QualityReport([
        _make_rule_result('R1', passed=True, severity='error'),
        _make_rule_result('R2', passed=False, severity='warning', actual_value=50.0),
    ])


class FakeDataContract:
    """Minimal stand-in for DataContract with SLA."""
    def __init__(self, min_quality_score=95.0):
        self.sla = FakeSLA(min_quality_score)


class FakeSLA:
    def __init__(self, min_quality_score):
        self.quality = {'minQualityScore': min_quality_score, 'measurementWindow': 'monthly'}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_cw():
    return MagicMock()


@pytest.fixture
def mock_sns():
    return MagicMock()


@pytest.fixture
def mock_contract_service():
    return MagicMock()


@pytest.fixture
def service(mock_cw, mock_sns, mock_contract_service):
    return QualityMetricsService(
        cloudwatch_client=mock_cw,
        sns_client=mock_sns,
        contract_service=mock_contract_service,
        region='us-east-1',
        account_id='123456789012',
    )


# ---------------------------------------------------------------------------
# log_quality_metrics – CloudWatch
# ---------------------------------------------------------------------------

class TestLogQualityMetrics:
    def test_publishes_four_metrics(self, service, mock_cw):
        report = _passing_report()
        service.log_quality_metrics(report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha')

        mock_cw.put_metric_data.assert_called_once()
        call_kwargs = mock_cw.put_metric_data.call_args[1]
        assert call_kwargs['Namespace'] == CLOUDWATCH_NAMESPACE
        assert len(call_kwargs['MetricData']) == 4

    def test_quality_score_metric(self, service, mock_cw):
        report = _passing_report()
        service.log_quality_metrics(report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha')

        metrics = mock_cw.put_metric_data.call_args[1]['MetricData']
        score_metric = next(m for m in metrics if m['MetricName'] == 'QualityScore')
        assert score_metric['Value'] == 100.0
        assert score_metric['Unit'] == 'Percent'
        dims = {d['Name']: d['Value'] for d in score_metric['Dimensions']}
        assert dims['ContractId'] == 'CMO-ALPHA-BATCH-001'
        assert dims['CMOId'] == 'cmo-alpha'

    def test_rules_passed_count_metric(self, service, mock_cw):
        report = _passing_report()
        service.log_quality_metrics(report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha')

        metrics = mock_cw.put_metric_data.call_args[1]['MetricData']
        passed_metric = next(m for m in metrics if m['MetricName'] == 'RulesPassedCount')
        assert passed_metric['Value'] == 2.0
        assert passed_metric['Unit'] == 'Count'

    def test_rules_failed_count_metric(self, service, mock_cw):
        report = _failing_report_with_errors()
        service.log_quality_metrics(report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha')

        metrics = mock_cw.put_metric_data.call_args[1]['MetricData']
        failed_metric = next(m for m in metrics if m['MetricName'] == 'RulesFailedCount')
        assert failed_metric['Value'] == 1.0

    def test_validation_result_passed(self, service, mock_cw):
        report = _passing_report()
        service.log_quality_metrics(report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha')

        metrics = mock_cw.put_metric_data.call_args[1]['MetricData']
        result_metric = next(m for m in metrics if m['MetricName'] == 'ValidationResult')
        assert result_metric['Value'] == 1.0

    def test_validation_result_failed(self, service, mock_cw):
        report = _failing_report_with_errors()
        service.log_quality_metrics(report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha')

        metrics = mock_cw.put_metric_data.call_args[1]['MetricData']
        result_metric = next(m for m in metrics if m['MetricName'] == 'ValidationResult')
        assert result_metric['Value'] == 0.0

    def test_cloudwatch_failure_raises(self, service, mock_cw):
        mock_cw.put_metric_data.side_effect = Exception("Throttled")
        report = _passing_report()

        with pytest.raises(QualityMetricsError, match="Failed to publish CloudWatch"):
            service.log_quality_metrics(report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha')


# ---------------------------------------------------------------------------
# Contract status updates
# ---------------------------------------------------------------------------

class TestContractStatusUpdate:
    def test_error_failures_suspend_contract(self, service, mock_contract_service):
        report = _failing_report_with_errors()
        result = service.process_quality_metrics(
            report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha',
        )

        mock_contract_service.update_contract_status.assert_called_once_with(
            'CMO-ALPHA-BATCH-001', 'suspended',
        )
        assert result['new_status'] == 'suspended'
        assert result['contract_status_updated'] is True

    def test_passing_report_sets_active(self, service, mock_contract_service):
        report = _passing_report()
        result = service.process_quality_metrics(
            report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha',
        )

        mock_contract_service.update_contract_status.assert_called_once_with(
            'CMO-ALPHA-BATCH-001', 'active',
        )
        assert result['new_status'] == 'active'

    def test_warnings_only_sets_active(self, service, mock_contract_service):
        report = _failing_report_warnings_only()
        result = service.process_quality_metrics(
            report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha',
        )

        mock_contract_service.update_contract_status.assert_called_once_with(
            'CMO-ALPHA-BATCH-001', 'active',
        )
        assert result['new_status'] == 'active'

    def test_no_contract_service_skips_update(self, mock_cw, mock_sns):
        svc = QualityMetricsService(
            cloudwatch_client=mock_cw,
            sns_client=mock_sns,
            contract_service=None,
        )
        report = _failing_report_with_errors()
        result = svc.process_quality_metrics(
            report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha',
        )

        assert result['contract_status_updated'] is False
        assert result['new_status'] is None


# ---------------------------------------------------------------------------
# SNS notifications
# ---------------------------------------------------------------------------

class TestSNSNotifications:
    def test_sla_breach_sends_warning(self, service, mock_sns):
        report = _failing_report_with_errors()  # score = 50.0
        contract = FakeDataContract(min_quality_score=95.0)

        result = service.process_quality_metrics(
            report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha',
            data_contract=contract,
        )

        assert 'sla_quality_breach' in result['notifications_sent']
        # Find the warning call (SLA breach)
        warning_calls = [
            c for c in mock_sns.publish.call_args_list
            if 'cmo-alerts-warning' in str(c)
        ]
        assert len(warning_calls) == 1
        call_kwargs = warning_calls[0][1]
        msg = json.loads(call_kwargs['Message'])
        assert msg['alert_type'] == 'sla_quality_breach'
        assert msg['contract_id'] == 'CMO-ALPHA-BATCH-001'
        assert msg['cmo_id'] == 'cmo-alpha'
        assert 'guidance' in msg

    def test_error_rules_sends_critical(self, service, mock_sns):
        report = _failing_report_with_errors()

        result = service.process_quality_metrics(
            report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha',
        )

        assert 'error_rules_failed' in result['notifications_sent']
        critical_calls = [
            c for c in mock_sns.publish.call_args_list
            if 'cmo-alerts-critical' in str(c)
        ]
        assert len(critical_calls) == 1
        call_kwargs = critical_calls[0][1]
        msg = json.loads(call_kwargs['Message'])
        assert msg['alert_type'] == 'error_rules_failed'
        assert msg['error_count'] == 1

    def test_passing_report_no_notifications(self, service, mock_sns):
        report = _passing_report()

        result = service.process_quality_metrics(
            report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha',
        )

        assert result['notifications_sent'] == []
        mock_sns.publish.assert_not_called()

    def test_score_above_sla_no_breach_notification(self, service, mock_sns):
        report = _passing_report()  # score = 100.0
        contract = FakeDataContract(min_quality_score=95.0)

        result = service.process_quality_metrics(
            report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha',
            data_contract=contract,
        )

        assert 'sla_quality_breach' not in result['notifications_sent']

    def test_sns_failure_raises(self, service, mock_sns):
        mock_sns.publish.side_effect = Exception("AccessDenied")
        report = _failing_report_with_errors()

        with pytest.raises(QualityMetricsError, match="Failed to send"):
            service.process_quality_metrics(
                report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha',
            )

    def test_notification_includes_message_attributes(self, service, mock_sns):
        report = _failing_report_with_errors()

        service.process_quality_metrics(
            report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha',
        )

        call_kwargs = mock_sns.publish.call_args[1]
        attrs = call_kwargs['MessageAttributes']
        assert attrs['ContractId']['StringValue'] == 'CMO-ALPHA-BATCH-001'
        assert 'Severity' in attrs

    def test_sla_breach_with_no_data_contract_skips(self, service, mock_sns):
        report = _failing_report_with_errors()

        result = service.process_quality_metrics(
            report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha',
            data_contract=None,
        )

        # Only error_rules_failed, no sla_quality_breach
        assert 'sla_quality_breach' not in result['notifications_sent']


# ---------------------------------------------------------------------------
# process_quality_metrics – full orchestration
# ---------------------------------------------------------------------------

class TestProcessQualityMetrics:
    def test_passing_report_full_flow(self, service, mock_cw, mock_sns, mock_contract_service):
        report = _passing_report()

        result = service.process_quality_metrics(
            report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha',
        )

        assert result['metrics_published'] is True
        assert result['contract_status_updated'] is True
        assert result['new_status'] == 'active'
        assert result['notifications_sent'] == []
        mock_cw.put_metric_data.assert_called_once()
        mock_sns.publish.assert_not_called()

    def test_failing_report_full_flow(self, service, mock_cw, mock_sns, mock_contract_service):
        report = _failing_report_with_errors()
        contract = FakeDataContract(min_quality_score=95.0)

        result = service.process_quality_metrics(
            report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha',
            data_contract=contract,
        )

        assert result['metrics_published'] is True
        assert result['contract_status_updated'] is True
        assert result['new_status'] == 'suspended'
        assert 'sla_quality_breach' in result['notifications_sent']
        assert 'error_rules_failed' in result['notifications_sent']
        # 2 SNS calls: one warning, one critical
        assert mock_sns.publish.call_count == 2

    def test_topic_arn_uses_configured_region_and_account(self, mock_cw, mock_sns):
        svc = QualityMetricsService(
            cloudwatch_client=mock_cw,
            sns_client=mock_sns,
            region='eu-west-1',
            account_id='999888777666',
        )
        report = _failing_report_with_errors()

        svc.process_quality_metrics(
            report, 'CMO-ALPHA-BATCH-001', 'cmo-alpha',
        )

        call_kwargs = mock_sns.publish.call_args[1]
        assert 'eu-west-1' in call_kwargs['TopicArn']
        assert '999888777666' in call_kwargs['TopicArn']
