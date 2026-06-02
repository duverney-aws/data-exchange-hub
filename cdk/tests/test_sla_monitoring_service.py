"""
Unit Tests for SLA Monitoring Service – CloudWatch pipeline metric publishing,
SLA compliance checking, and SNS alert sending.

Requirements: 11.1, 11.2
"""
import json
import sys
import os

import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.sla_monitoring_service import (
    SLAMonitoringError,
    SLAMonitoringService,
    CLOUDWATCH_NAMESPACE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeSLA:
    """Minimal stand-in for a DataContract.sla object."""
    def __init__(self, max_delay_hours=4, min_quality_score=95.0, uptime_percentage=99.0):
        self.timeliness = {'maxDelayHours': max_delay_hours, 'measurementWindow': 'daily'}
        self.quality = {'minQualityScore': min_quality_score, 'measurementWindow': 'monthly'}
        self.availability = {'uptimePercentage': uptime_percentage, 'measurementWindow': 'monthly'}


class FakeDataContract:
    """Minimal stand-in for DataContract with SLA."""
    def __init__(self, max_delay_hours=4, min_quality_score=95.0, uptime_percentage=99.0):
        self.sla = FakeSLA(max_delay_hours, min_quality_score, uptime_percentage)


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
def service(mock_cw, mock_sns):
    return SLAMonitoringService(
        cloudwatch_client=mock_cw,
        sns_client=mock_sns,
        region='us-east-1',
        account_id='123456789012',
    )


# ---------------------------------------------------------------------------
# record_pipeline_metrics – CloudWatch publishing
# ---------------------------------------------------------------------------

class TestRecordPipelineMetrics:
    def test_publishes_three_metrics(self, service, mock_cw):
        service.record_pipeline_metrics(
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
            execution_time_seconds=120.5,
            record_count=5000,
            quality_score=98.5,
        )

        mock_cw.put_metric_data.assert_called_once()
        call_kwargs = mock_cw.put_metric_data.call_args[1]
        assert call_kwargs['Namespace'] == CLOUDWATCH_NAMESPACE
        assert len(call_kwargs['MetricData']) == 3

    def test_execution_time_metric(self, service, mock_cw):
        service.record_pipeline_metrics(
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
            execution_time_seconds=120.5,
            record_count=5000,
            quality_score=98.5,
        )

        metrics = mock_cw.put_metric_data.call_args[1]['MetricData']
        et_metric = next(m for m in metrics if m['MetricName'] == 'ExecutionTime')
        assert et_metric['Value'] == 120.5
        assert et_metric['Unit'] == 'Seconds'
        dims = {d['Name']: d['Value'] for d in et_metric['Dimensions']}
        assert dims['ContractId'] == 'CMO-ALPHA-BATCH-001'
        assert dims['CMOId'] == 'cmo-alpha'

    def test_records_processed_metric(self, service, mock_cw):
        service.record_pipeline_metrics(
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
            execution_time_seconds=60.0,
            record_count=1234,
            quality_score=99.0,
        )

        metrics = mock_cw.put_metric_data.call_args[1]['MetricData']
        rp_metric = next(m for m in metrics if m['MetricName'] == 'RecordsProcessed')
        assert rp_metric['Value'] == 1234.0
        assert rp_metric['Unit'] == 'Count'
        dims = {d['Name']: d['Value'] for d in rp_metric['Dimensions']}
        assert dims['ContractId'] == 'CMO-ALPHA-BATCH-001'
        assert dims['CMOId'] == 'cmo-alpha'

    def test_quality_score_metric(self, service, mock_cw):
        service.record_pipeline_metrics(
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
            execution_time_seconds=60.0,
            record_count=100,
            quality_score=87.3,
        )

        metrics = mock_cw.put_metric_data.call_args[1]['MetricData']
        qs_metric = next(m for m in metrics if m['MetricName'] == 'QualityScore')
        assert qs_metric['Value'] == 87.3
        assert qs_metric['Unit'] == 'Percent'
        dims = {d['Name']: d['Value'] for d in qs_metric['Dimensions']}
        assert dims['ContractId'] == 'CMO-ALPHA-BATCH-001'
        assert dims['CMOId'] == 'cmo-alpha'

    def test_cloudwatch_failure_raises(self, service, mock_cw):
        mock_cw.put_metric_data.side_effect = Exception("Throttled")

        with pytest.raises(SLAMonitoringError, match="Failed to publish CloudWatch"):
            service.record_pipeline_metrics(
                contract_id='CMO-ALPHA-BATCH-001',
                cmo_id='cmo-alpha',
                execution_time_seconds=10.0,
                record_count=1,
                quality_score=100.0,
            )

    def test_namespace_is_cmo_datapipeline(self, service, mock_cw):
        service.record_pipeline_metrics(
            contract_id='CMO-BETA-QC-002',
            cmo_id='cmo-beta',
            execution_time_seconds=30.0,
            record_count=500,
            quality_score=95.0,
        )

        assert mock_cw.put_metric_data.call_args[1]['Namespace'] == 'CMO/DataPipeline'


# ---------------------------------------------------------------------------
# check_sla_compliance – timeliness and quality threshold comparison
# ---------------------------------------------------------------------------

class TestCheckSLACompliance:
    def test_compliant_when_within_thresholds(self, service):
        contract = FakeDataContract(max_delay_hours=4, min_quality_score=90.0)

        result = service.check_sla_compliance(
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
            execution_time_seconds=3600.0,  # 1 hour < 4 hours
            quality_score=95.0,             # 95 >= 90
            data_contract=contract,
        )

        assert result['timeliness_ok'] is True
        assert result['quality_ok'] is True
        assert result['overall_compliant'] is True
        assert result['breaches'] == []

    def test_timeliness_breach(self, service):
        contract = FakeDataContract(max_delay_hours=2, min_quality_score=90.0)

        result = service.check_sla_compliance(
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
            execution_time_seconds=3 * 3600,  # 3 hours > 2 hours
            quality_score=95.0,
            data_contract=contract,
        )

        assert result['timeliness_ok'] is False
        assert result['quality_ok'] is True
        assert result['overall_compliant'] is False
        assert len(result['breaches']) == 1
        assert result['breaches'][0]['type'] == 'timeliness'

    def test_quality_breach(self, service):
        contract = FakeDataContract(max_delay_hours=10, min_quality_score=95.0)

        result = service.check_sla_compliance(
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
            execution_time_seconds=60.0,
            quality_score=80.0,  # 80 < 95
            data_contract=contract,
        )

        assert result['timeliness_ok'] is True
        assert result['quality_ok'] is False
        assert result['overall_compliant'] is False
        assert len(result['breaches']) == 1
        assert result['breaches'][0]['type'] == 'quality'

    def test_both_breaches(self, service):
        contract = FakeDataContract(max_delay_hours=1, min_quality_score=99.0)

        result = service.check_sla_compliance(
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
            execution_time_seconds=2 * 3600,  # 2 hours > 1 hour
            quality_score=50.0,               # 50 < 99
            data_contract=contract,
        )

        assert result['timeliness_ok'] is False
        assert result['quality_ok'] is False
        assert result['overall_compliant'] is False
        assert len(result['breaches']) == 2

    def test_no_contract_returns_compliant(self, service):
        result = service.check_sla_compliance(
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
            execution_time_seconds=9999.0,
            quality_score=0.0,
            data_contract=None,
        )

        assert result['overall_compliant'] is True
        assert result['breaches'] == []

    def test_breach_details_include_thresholds(self, service):
        contract = FakeDataContract(max_delay_hours=2, min_quality_score=95.0)

        result = service.check_sla_compliance(
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
            execution_time_seconds=4 * 3600,  # 4 hours
            quality_score=80.0,
            data_contract=contract,
        )

        timeliness_breach = next(b for b in result['breaches'] if b['type'] == 'timeliness')
        assert timeliness_breach['threshold_hours'] == 2
        assert timeliness_breach['actual_hours'] == 4.0

        quality_breach = next(b for b in result['breaches'] if b['type'] == 'quality')
        assert quality_breach['threshold_score'] == 95.0
        assert quality_breach['actual_score'] == 80.0


# ---------------------------------------------------------------------------
# send_alert – SNS notifications
# ---------------------------------------------------------------------------

class TestSendAlert:
    def test_sends_warning_alert(self, service, mock_sns):
        service.send_alert(
            severity='warning',
            message='Timeliness SLA breached',
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
        )

        mock_sns.publish.assert_called_once()
        call_kwargs = mock_sns.publish.call_args[1]
        assert 'cmo-alerts-warning' in call_kwargs['TopicArn']
        assert call_kwargs['Message'] == 'Timeliness SLA breached'
        assert '[WARNING]' in call_kwargs['Subject']

    def test_sends_critical_alert(self, service, mock_sns):
        service.send_alert(
            severity='critical',
            message='Quality SLA breached',
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
        )

        call_kwargs = mock_sns.publish.call_args[1]
        assert 'cmo-alerts-critical' in call_kwargs['TopicArn']
        assert '[CRITICAL]' in call_kwargs['Subject']

    def test_alert_includes_message_attributes(self, service, mock_sns):
        service.send_alert(
            severity='warning',
            message='test',
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
        )

        attrs = mock_sns.publish.call_args[1]['MessageAttributes']
        assert attrs['ContractId']['StringValue'] == 'CMO-ALPHA-BATCH-001'
        assert attrs['CMOId']['StringValue'] == 'cmo-alpha'
        assert attrs['Severity']['StringValue'] == 'warning'

    def test_topic_arn_uses_configured_region_and_account(self, mock_cw, mock_sns):
        svc = SLAMonitoringService(
            cloudwatch_client=mock_cw,
            sns_client=mock_sns,
            region='eu-west-1',
            account_id='999888777666',
        )

        svc.send_alert(
            severity='critical',
            message='test',
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
        )

        topic_arn = mock_sns.publish.call_args[1]['TopicArn']
        assert 'eu-west-1' in topic_arn
        assert '999888777666' in topic_arn

    def test_sns_failure_raises(self, service, mock_sns):
        mock_sns.publish.side_effect = Exception("AccessDenied")

        with pytest.raises(SLAMonitoringError, match="Failed to send"):
            service.send_alert(
                severity='warning',
                message='test',
                contract_id='CMO-ALPHA-BATCH-001',
                cmo_id='cmo-alpha',
            )


# ---------------------------------------------------------------------------
# record_execution_result – availability tracking
# ---------------------------------------------------------------------------

class TestRecordExecutionResult:
    def test_records_success_and_publishes_metrics(self, service, mock_cw):
        service.record_execution_result(
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
            success=True,
        )

        # One call for availability metrics
        mock_cw.put_metric_data.assert_called_once()
        call_kwargs = mock_cw.put_metric_data.call_args[1]
        assert call_kwargs['Namespace'] == CLOUDWATCH_NAMESPACE
        metric_names = [m['MetricName'] for m in call_kwargs['MetricData']]
        assert 'SuccessRate' in metric_names
        assert 'AvailabilityPercent' in metric_names

    def test_records_failure_and_publishes_metrics(self, service, mock_cw):
        service.record_execution_result(
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
            success=False,
        )

        call_kwargs = mock_cw.put_metric_data.call_args[1]
        metrics = {m['MetricName']: m['Value'] for m in call_kwargs['MetricData']}
        assert metrics['SuccessRate'] == 0.0
        assert metrics['AvailabilityPercent'] == 0.0

    def test_success_rate_after_mixed_results(self, service, mock_cw):
        # 3 successes, 1 failure → 75% success rate
        for success in [True, True, True, False]:
            service.record_execution_result(
                contract_id='CMO-ALPHA-BATCH-001',
                cmo_id='cmo-alpha',
                success=success,
            )

        last_call = mock_cw.put_metric_data.call_args[1]
        metrics = {m['MetricName']: m['Value'] for m in last_call['MetricData']}
        assert metrics['SuccessRate'] == 75.0
        assert metrics['AvailabilityPercent'] == 75.0

    def test_dimensions_include_contract_and_cmo(self, service, mock_cw):
        service.record_execution_result(
            contract_id='CMO-BETA-QC-002',
            cmo_id='cmo-beta',
            success=True,
        )

        call_kwargs = mock_cw.put_metric_data.call_args[1]
        sr_metric = next(m for m in call_kwargs['MetricData'] if m['MetricName'] == 'SuccessRate')
        dims = {d['Name']: d['Value'] for d in sr_metric['Dimensions']}
        assert dims['ContractId'] == 'CMO-BETA-QC-002'
        assert dims['CMOId'] == 'cmo-beta'

    def test_cloudwatch_failure_raises(self, service, mock_cw):
        mock_cw.put_metric_data.side_effect = Exception("Throttled")

        with pytest.raises(SLAMonitoringError, match="Failed to publish availability"):
            service.record_execution_result(
                contract_id='CMO-ALPHA-BATCH-001',
                cmo_id='cmo-alpha',
                success=True,
            )

    def test_separate_contracts_tracked_independently(self, service, mock_cw):
        service.record_execution_result('C-001', 'cmo-a', success=True)
        service.record_execution_result('C-001', 'cmo-a', success=False)
        service.record_execution_result('C-002', 'cmo-b', success=True)

        avail_1 = service.calculate_availability('C-001')
        avail_2 = service.calculate_availability('C-002')
        assert avail_1['success_rate'] == 50.0
        assert avail_2['success_rate'] == 100.0


# ---------------------------------------------------------------------------
# calculate_availability – success rate and uptime computation
# ---------------------------------------------------------------------------

class TestCalculateAvailability:
    def test_no_executions_returns_100_percent(self, service):
        result = service.calculate_availability('CMO-ALPHA-BATCH-001')

        assert result['total_executions'] == 0
        assert result['successful_executions'] == 0
        assert result['success_rate'] == 100.0
        assert result['uptime_percentage'] == 100.0

    def test_all_successes(self, service, mock_cw):
        for _ in range(5):
            service.record_execution_result('CMO-ALPHA-BATCH-001', 'cmo-alpha', success=True)

        result = service.calculate_availability('CMO-ALPHA-BATCH-001')
        assert result['total_executions'] == 5
        assert result['successful_executions'] == 5
        assert result['success_rate'] == 100.0
        assert result['uptime_percentage'] == 100.0

    def test_all_failures(self, service, mock_cw):
        for _ in range(3):
            service.record_execution_result('CMO-ALPHA-BATCH-001', 'cmo-alpha', success=False)

        result = service.calculate_availability('CMO-ALPHA-BATCH-001')
        assert result['total_executions'] == 3
        assert result['successful_executions'] == 0
        assert result['success_rate'] == 0.0
        assert result['uptime_percentage'] == 0.0

    def test_mixed_results(self, service, mock_cw):
        for success in [True, True, False, True]:
            service.record_execution_result('CMO-ALPHA-BATCH-001', 'cmo-alpha', success=success)

        result = service.calculate_availability('CMO-ALPHA-BATCH-001')
        assert result['total_executions'] == 4
        assert result['successful_executions'] == 3
        assert result['success_rate'] == 75.0
        assert result['uptime_percentage'] == 75.0


# ---------------------------------------------------------------------------
# check_sla_compliance – availability threshold comparison
# ---------------------------------------------------------------------------

class TestCheckSLAComplianceAvailability:
    def test_availability_ok_when_above_threshold(self, service, mock_cw):
        # Record 10 successes → 100% uptime, threshold 99%
        for _ in range(10):
            service.record_execution_result('CMO-ALPHA-BATCH-001', 'cmo-alpha', success=True)

        contract = FakeDataContract(max_delay_hours=10, min_quality_score=50.0, uptime_percentage=99.0)
        result = service.check_sla_compliance(
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
            execution_time_seconds=60.0,
            quality_score=95.0,
            data_contract=contract,
        )

        assert result['availability_ok'] is True
        assert result['overall_compliant'] is True

    def test_availability_breach_when_below_threshold(self, service, mock_cw):
        # 1 success, 1 failure → 50% uptime, threshold 99%
        service.record_execution_result('CMO-ALPHA-BATCH-001', 'cmo-alpha', success=True)
        service.record_execution_result('CMO-ALPHA-BATCH-001', 'cmo-alpha', success=False)

        contract = FakeDataContract(max_delay_hours=10, min_quality_score=50.0, uptime_percentage=99.0)
        result = service.check_sla_compliance(
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
            execution_time_seconds=60.0,
            quality_score=95.0,
            data_contract=contract,
        )

        assert result['availability_ok'] is False
        assert result['overall_compliant'] is False
        breach = next(b for b in result['breaches'] if b['type'] == 'availability')
        assert breach['threshold_uptime'] == 99.0
        assert breach['actual_uptime'] == 50.0

    def test_availability_ok_field_present_in_result(self, service):
        result = service.check_sla_compliance(
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
            execution_time_seconds=60.0,
            quality_score=95.0,
            data_contract=None,
        )

        assert 'availability_ok' in result
        assert result['availability_ok'] is True

    def test_all_three_breaches(self, service, mock_cw):
        # Force low availability
        service.record_execution_result('CMO-ALPHA-BATCH-001', 'cmo-alpha', success=False)

        contract = FakeDataContract(max_delay_hours=1, min_quality_score=99.0, uptime_percentage=99.0)
        result = service.check_sla_compliance(
            contract_id='CMO-ALPHA-BATCH-001',
            cmo_id='cmo-alpha',
            execution_time_seconds=2 * 3600,  # 2 hours > 1 hour
            quality_score=50.0,               # 50 < 99
            data_contract=contract,
        )

        assert result['timeliness_ok'] is False
        assert result['quality_ok'] is False
        assert result['availability_ok'] is False
        assert result['overall_compliant'] is False
        assert len(result['breaches']) == 3
        breach_types = {b['type'] for b in result['breaches']}
        assert breach_types == {'timeliness', 'quality', 'availability'}
