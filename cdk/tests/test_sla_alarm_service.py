"""
Unit Tests for SLA Alarm Service – CloudWatch alarm configurations
for SLA violations with warning and critical severity levels.

Requirements: 11.3, 11.6
"""
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.sla_alarm_service import (
    CLOUDWATCH_NAMESPACE,
    SLAAlarmService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WARNING_TOPIC = 'arn:aws:sns:us-east-1:123456789012:pharma-data-exchange-warning-alerts'
CRITICAL_TOPIC = 'arn:aws:sns:us-east-1:123456789012:pharma-data-exchange-critical-alerts'
SLA_BREACH_TOPIC = 'arn:aws:sns:us-east-1:123456789012:pharma-data-exchange-sla-breach'


@pytest.fixture
def service():
    return SLAAlarmService(
        warning_topic_arn=WARNING_TOPIC,
        critical_topic_arn=CRITICAL_TOPIC,
        sla_breach_topic_arn=SLA_BREACH_TOPIC,
    )


# ---------------------------------------------------------------------------
# ExecutionTime alarms
# ---------------------------------------------------------------------------

class TestExecutionTimeAlarms:
    def test_returns_two_alarms(self, service):
        alarms = service.create_execution_time_alarms(sla_max_seconds=3600)
        assert len(alarms) == 2

    def test_warning_alarm_name(self, service):
        alarms = service.create_execution_time_alarms(sla_max_seconds=3600)
        assert alarms[0]['AlarmName'] == 'SLA-ExecutionTime-Warning'

    def test_critical_alarm_name(self, service):
        alarms = service.create_execution_time_alarms(sla_max_seconds=3600)
        assert alarms[1]['AlarmName'] == 'SLA-ExecutionTime-Critical'

    def test_warning_threshold_is_80_percent_of_sla(self, service):
        alarms = service.create_execution_time_alarms(sla_max_seconds=3600)
        assert alarms[0]['Threshold'] == pytest.approx(2880.0)

    def test_critical_threshold_is_100_percent_of_sla(self, service):
        alarms = service.create_execution_time_alarms(sla_max_seconds=3600)
        assert alarms[1]['Threshold'] == pytest.approx(3600.0)

    def test_custom_warning_pct(self, service):
        alarms = service.create_execution_time_alarms(
            sla_max_seconds=1000, warning_pct=0.50,
        )
        assert alarms[0]['Threshold'] == pytest.approx(500.0)

    def test_comparison_is_greater_than(self, service):
        alarms = service.create_execution_time_alarms(sla_max_seconds=3600)
        for a in alarms:
            assert a['ComparisonOperator'] == 'GreaterThanThreshold'

    def test_metric_name_is_execution_time(self, service):
        alarms = service.create_execution_time_alarms(sla_max_seconds=3600)
        for a in alarms:
            assert a['MetricName'] == 'ExecutionTime'

    def test_namespace_is_cmo_datapipeline(self, service):
        alarms = service.create_execution_time_alarms(sla_max_seconds=3600)
        for a in alarms:
            assert a['Namespace'] == CLOUDWATCH_NAMESPACE

    def test_warning_routes_to_warning_topic(self, service):
        alarms = service.create_execution_time_alarms(sla_max_seconds=3600)
        assert WARNING_TOPIC in alarms[0]['AlarmActions']

    def test_critical_routes_to_critical_and_breach_topics(self, service):
        alarms = service.create_execution_time_alarms(sla_max_seconds=3600)
        assert CRITICAL_TOPIC in alarms[1]['AlarmActions']
        assert SLA_BREACH_TOPIC in alarms[1]['AlarmActions']


# ---------------------------------------------------------------------------
# QualityScore alarms
# ---------------------------------------------------------------------------

class TestQualityScoreAlarms:
    def test_returns_two_alarms(self, service):
        alarms = service.create_quality_score_alarms()
        assert len(alarms) == 2

    def test_warning_threshold_default_95(self, service):
        alarms = service.create_quality_score_alarms()
        assert alarms[0]['Threshold'] == pytest.approx(95.0)

    def test_critical_threshold_default_90(self, service):
        alarms = service.create_quality_score_alarms()
        assert alarms[1]['Threshold'] == pytest.approx(90.0)

    def test_custom_thresholds(self, service):
        alarms = service.create_quality_score_alarms(
            warning_threshold=98.0, critical_threshold=92.0,
        )
        assert alarms[0]['Threshold'] == pytest.approx(98.0)
        assert alarms[1]['Threshold'] == pytest.approx(92.0)

    def test_comparison_is_less_than(self, service):
        alarms = service.create_quality_score_alarms()
        for a in alarms:
            assert a['ComparisonOperator'] == 'LessThanThreshold'

    def test_metric_name_is_quality_score(self, service):
        alarms = service.create_quality_score_alarms()
        for a in alarms:
            assert a['MetricName'] == 'QualityScore'

    def test_severity_labels(self, service):
        alarms = service.create_quality_score_alarms()
        assert alarms[0]['Severity'] == 'warning'
        assert alarms[1]['Severity'] == 'critical'


# ---------------------------------------------------------------------------
# SuccessRate alarms
# ---------------------------------------------------------------------------

class TestSuccessRateAlarms:
    def test_returns_two_alarms(self, service):
        alarms = service.create_success_rate_alarms()
        assert len(alarms) == 2

    def test_warning_threshold_default_99(self, service):
        alarms = service.create_success_rate_alarms()
        assert alarms[0]['Threshold'] == pytest.approx(99.0)

    def test_critical_threshold_default_95(self, service):
        alarms = service.create_success_rate_alarms()
        assert alarms[1]['Threshold'] == pytest.approx(95.0)

    def test_comparison_is_less_than(self, service):
        alarms = service.create_success_rate_alarms()
        for a in alarms:
            assert a['ComparisonOperator'] == 'LessThanThreshold'

    def test_metric_name_is_success_rate(self, service):
        alarms = service.create_success_rate_alarms()
        for a in alarms:
            assert a['MetricName'] == 'SuccessRate'

    def test_warning_routes_to_warning_topic(self, service):
        alarms = service.create_success_rate_alarms()
        assert WARNING_TOPIC in alarms[0]['AlarmActions']
        assert CRITICAL_TOPIC not in alarms[0]['AlarmActions']

    def test_critical_routes_to_critical_and_breach_topics(self, service):
        alarms = service.create_success_rate_alarms()
        assert CRITICAL_TOPIC in alarms[1]['AlarmActions']
        assert SLA_BREACH_TOPIC in alarms[1]['AlarmActions']


# ---------------------------------------------------------------------------
# create_all_alarms
# ---------------------------------------------------------------------------

class TestCreateAllAlarms:
    def test_returns_six_alarms(self, service):
        alarms = service.create_all_alarms()
        assert len(alarms) == 6

    def test_alarm_names_are_unique(self, service):
        alarms = service.create_all_alarms()
        names = [a['AlarmName'] for a in alarms]
        assert len(names) == len(set(names))

    def test_all_alarms_have_required_keys(self, service):
        required_keys = {
            'AlarmName', 'AlarmDescription', 'Namespace', 'MetricName',
            'Statistic', 'Period', 'EvaluationPeriods', 'Threshold',
            'ComparisonOperator', 'AlarmActions', 'Severity',
            'TreatMissingData',
        }
        alarms = service.create_all_alarms()
        for a in alarms:
            assert required_keys.issubset(a.keys())

    def test_custom_sla_max_seconds_propagated(self, service):
        alarms = service.create_all_alarms(sla_max_seconds=7200)
        exec_alarms = [a for a in alarms if a['MetricName'] == 'ExecutionTime']
        assert exec_alarms[0]['Threshold'] == pytest.approx(5760.0)  # 80%
        assert exec_alarms[1]['Threshold'] == pytest.approx(7200.0)  # 100%

    def test_custom_evaluation_periods(self, service):
        alarms = service.create_all_alarms(evaluation_periods=5)
        for a in alarms:
            assert a['EvaluationPeriods'] == 5

    def test_custom_period_seconds(self, service):
        alarms = service.create_all_alarms(period_seconds=60)
        for a in alarms:
            assert a['Period'] == 60

    def test_treat_missing_data_is_not_breaching(self, service):
        alarms = service.create_all_alarms()
        for a in alarms:
            assert a['TreatMissingData'] == 'notBreaching'

    def test_all_use_cmo_datapipeline_namespace(self, service):
        alarms = service.create_all_alarms()
        for a in alarms:
            assert a['Namespace'] == 'CMO/DataPipeline'

    def test_statistic_is_average(self, service):
        alarms = service.create_all_alarms()
        for a in alarms:
            assert a['Statistic'] == 'Average'
