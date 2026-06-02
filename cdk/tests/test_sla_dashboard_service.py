"""
Unit Tests for SLA Dashboard Service – CloudWatch dashboard widget generation
for SLA compliance monitoring.

Requirements: 11.4
"""
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.sla_dashboard_service import (
    CLOUDWATCH_NAMESPACE,
    SLADashboardService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def service():
    return SLADashboardService(region='us-east-1')


@pytest.fixture
def single_cmo_contracts():
    return {'cmo-alpha': ['CMO-ALPHA-BATCH-001']}


@pytest.fixture
def multi_cmo_contracts():
    return {
        'cmo-alpha': ['CMO-ALPHA-BATCH-001', 'CMO-ALPHA-QC-002'],
        'cmo-beta': ['CMO-BETA-BATCH-001'],
    }


# ---------------------------------------------------------------------------
# generate_dashboard_body
# ---------------------------------------------------------------------------

class TestGenerateDashboardBody:
    def test_returns_dict_with_widgets_key(self, service, single_cmo_contracts):
        body = service.generate_dashboard_body(single_cmo_contracts)
        assert isinstance(body, dict)
        assert 'widgets' in body
        assert isinstance(body['widgets'], list)

    def test_first_widget_is_section_header(self, service, single_cmo_contracts):
        body = service.generate_dashboard_body(single_cmo_contracts)
        header = body['widgets'][0]
        assert header['type'] == 'text'
        assert 'SLA Compliance' in header['properties']['markdown']

    def test_single_cmo_produces_five_widgets(self, service, single_cmo_contracts):
        # 1 header + 4 metric widgets (exec time, quality, availability, success rate)
        body = service.generate_dashboard_body(single_cmo_contracts)
        assert len(body['widgets']) == 5

    def test_multi_cmo_produces_correct_widget_count(self, service, multi_cmo_contracts):
        # 1 header + 4 widgets per CMO × 2 CMOs = 9
        body = service.generate_dashboard_body(multi_cmo_contracts)
        assert len(body['widgets']) == 9

    def test_empty_cmo_contracts_returns_header_only(self, service):
        body = service.generate_dashboard_body({})
        assert len(body['widgets']) == 1
        assert body['widgets'][0]['type'] == 'text'

    def test_custom_period_propagated(self, service, single_cmo_contracts):
        body = service.generate_dashboard_body(single_cmo_contracts, period=60)
        metric_widgets = [w for w in body['widgets'] if w['type'] == 'metric']
        for w in metric_widgets:
            assert w['properties']['period'] == 60


# ---------------------------------------------------------------------------
# build_execution_time_widget
# ---------------------------------------------------------------------------

class TestBuildExecutionTimeWidget:
    def test_widget_type_is_metric(self, service):
        w = service.build_execution_time_widget('cmo-alpha', ['C-001'])
        assert w['type'] == 'metric'

    def test_title_contains_cmo_id(self, service):
        w = service.build_execution_time_widget('cmo-alpha', ['C-001'])
        assert 'cmo-alpha' in w['properties']['title']
        assert 'Execution Time' in w['properties']['title']

    def test_metrics_reference_correct_namespace(self, service):
        w = service.build_execution_time_widget('cmo-alpha', ['C-001'])
        for m in w['properties']['metrics']:
            assert m[0] == CLOUDWATCH_NAMESPACE
            assert m[1] == 'ExecutionTime'

    def test_metrics_include_cmo_and_contract_dimensions(self, service):
        w = service.build_execution_time_widget('cmo-alpha', ['C-001'])
        m = w['properties']['metrics'][0]
        assert 'CMOId' in m
        assert 'cmo-alpha' in m
        assert 'ContractId' in m
        assert 'C-001' in m

    def test_multiple_contracts_produce_multiple_metrics(self, service):
        w = service.build_execution_time_widget('cmo-alpha', ['C-001', 'C-002'])
        assert len(w['properties']['metrics']) == 2

    def test_view_is_time_series(self, service):
        w = service.build_execution_time_widget('cmo-alpha', ['C-001'])
        assert w['properties']['view'] == 'timeSeries'

    def test_y_axis_label_is_seconds(self, service):
        w = service.build_execution_time_widget('cmo-alpha', ['C-001'])
        assert w['properties']['yAxis']['left']['label'] == 'Seconds'


# ---------------------------------------------------------------------------
# build_quality_score_widget
# ---------------------------------------------------------------------------

class TestBuildQualityScoreWidget:
    def test_title_contains_quality_score(self, service):
        w = service.build_quality_score_widget('cmo-beta', ['C-001'])
        assert 'Quality Score' in w['properties']['title']
        assert 'cmo-beta' in w['properties']['title']

    def test_metric_name_is_quality_score(self, service):
        w = service.build_quality_score_widget('cmo-beta', ['C-001'])
        for m in w['properties']['metrics']:
            assert m[1] == 'QualityScore'

    def test_y_axis_label_is_percent(self, service):
        w = service.build_quality_score_widget('cmo-beta', ['C-001'])
        assert w['properties']['yAxis']['left']['label'] == 'Percent'


# ---------------------------------------------------------------------------
# build_availability_widget
# ---------------------------------------------------------------------------

class TestBuildAvailabilityWidget:
    def test_title_contains_availability(self, service):
        w = service.build_availability_widget('cmo-alpha', ['C-001'])
        assert 'Availability' in w['properties']['title']

    def test_metric_name_is_availability_percent(self, service):
        w = service.build_availability_widget('cmo-alpha', ['C-001'])
        for m in w['properties']['metrics']:
            assert m[1] == 'AvailabilityPercent'

    def test_view_is_time_series(self, service):
        w = service.build_availability_widget('cmo-alpha', ['C-001'])
        assert w['properties']['view'] == 'timeSeries'


# ---------------------------------------------------------------------------
# build_success_rate_widget
# ---------------------------------------------------------------------------

class TestBuildSuccessRateWidget:
    def test_title_contains_success_rate(self, service):
        w = service.build_success_rate_widget('cmo-alpha', ['C-001'])
        assert 'Success Rate' in w['properties']['title']

    def test_metric_name_is_success_rate(self, service):
        w = service.build_success_rate_widget('cmo-alpha', ['C-001'])
        for m in w['properties']['metrics']:
            assert m[1] == 'SuccessRate'

    def test_view_is_single_value(self, service):
        w = service.build_success_rate_widget('cmo-alpha', ['C-001'])
        assert w['properties']['view'] == 'singleValue'

    def test_default_width_is_six(self, service):
        w = service.build_success_rate_widget('cmo-alpha', ['C-001'])
        assert w['width'] == 6


# ---------------------------------------------------------------------------
# Widget positioning
# ---------------------------------------------------------------------------

class TestWidgetPositioning:
    def test_header_at_top(self, service, single_cmo_contracts):
        body = service.generate_dashboard_body(single_cmo_contracts)
        header = body['widgets'][0]
        assert header['x'] == 0
        assert header['y'] == 0

    def test_widgets_have_non_negative_positions(self, service, multi_cmo_contracts):
        body = service.generate_dashboard_body(multi_cmo_contracts)
        for w in body['widgets']:
            assert w['x'] >= 0
            assert w['y'] >= 0

    def test_second_cmo_widgets_offset_below_first(self, service, multi_cmo_contracts):
        body = service.generate_dashboard_body(multi_cmo_contracts)
        # Header at y=0, first CMO starts at y=2, second CMO at y=14
        metric_widgets = [w for w in body['widgets'] if w['type'] == 'metric']
        # Get unique y values
        y_values = sorted(set(w['y'] for w in metric_widgets))
        assert len(y_values) >= 2  # at least 2 different y positions


# ---------------------------------------------------------------------------
# Namespace consistency
# ---------------------------------------------------------------------------

class TestNamespaceConsistency:
    def test_all_metric_widgets_use_cmo_datapipeline_namespace(
        self, service, multi_cmo_contracts,
    ):
        body = service.generate_dashboard_body(multi_cmo_contracts)
        for w in body['widgets']:
            if w['type'] == 'metric':
                for m in w['properties']['metrics']:
                    assert m[0] == 'CMO/DataPipeline'
