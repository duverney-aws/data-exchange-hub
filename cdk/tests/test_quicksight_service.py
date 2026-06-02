"""
Unit Tests for QuickSight Business Intelligence Service.

Covers:
  - Athena data source creation (Req 13.2)
  - Dataset creation for batch records, quality metrics, SLA compliance (Req 13.2)
  - Refresh schedule configuration based on delivery frequency (Req 13.4)
  - Dashboard creation for all three types (Req 13.1)
  - Row-level security configuration and validation (Req 13.5)
  - Filter controls and drill-down interactivity (Req 13.3)
"""
import pytest

from services.quicksight_service import (
    DATASET_DEFINITIONS,
    FREQUENCY_TO_REFRESH_INTERVAL,
    STANDARD_FILTERS,
    QuickSightService,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def service():
    return QuickSightService(aws_account_id='111122223333', region='us-east-1')


@pytest.fixture
def data_source_id():
    return 'athena-test-ds'


@pytest.fixture
def dataset_ids():
    return {
        'batch-records': 'ds-batch-001',
        'quality-metrics': 'ds-quality-001',
        'sla-compliance': 'ds-sla-001',
    }


@pytest.fixture
def cmo_user_mappings():
    return {
        'cmo-alpha': ['user-alice', 'user-bob'],
        'cmo-beta': ['user-carol'],
    }


# ------------------------------------------------------------------
# 20.1 – Athena data source (Req 13.2)
# ------------------------------------------------------------------

class TestCreateAthenaDataSource:
    def test_returns_dict_with_required_keys(self, service):
        ds = service.create_athena_data_source('my-ds')
        assert ds['DataSourceId'] == 'my-ds'
        assert ds['Type'] == 'ATHENA'
        assert 'AthenaParameters' in ds['DataSourceParameters']

    def test_workgroup_is_cmo_workgroup(self, service):
        ds = service.create_athena_data_source()
        params = ds['DataSourceParameters']['AthenaParameters']
        assert params['WorkGroup'] == 'cmo-workgroup'

    def test_auto_generated_id_when_none(self, service):
        ds = service.create_athena_data_source()
        assert ds['DataSourceId'].startswith('athena-cmo-')

    def test_ssl_enabled(self, service):
        ds = service.create_athena_data_source()
        assert ds['SslProperties']['DisableSsl'] is False


# ------------------------------------------------------------------
# 20.1 – Dataset creation (Req 13.2)
# ------------------------------------------------------------------

class TestCreateDataset:
    @pytest.mark.parametrize('key', list(DATASET_DEFINITIONS))
    def test_creates_dataset_for_each_key(self, service, data_source_id, key):
        ds = service.create_dataset(key, data_source_id)
        assert ds['Name'] == DATASET_DEFINITIONS[key]['name']
        assert ds['ImportMode'] == 'SPICE'
        assert key in ds['PhysicalTableMap']

    def test_custom_sql_references_data_source(self, service, data_source_id):
        ds = service.create_dataset('batch-records', data_source_id)
        custom_sql = ds['PhysicalTableMap']['batch-records']['CustomSql']
        assert data_source_id in custom_sql['DataSourceArn']
        assert custom_sql['SqlQuery'] == DATASET_DEFINITIONS['batch-records']['sql']

    def test_columns_match_definition(self, service, data_source_id):
        ds = service.create_dataset('quality-metrics', data_source_id)
        custom_sql = ds['PhysicalTableMap']['quality-metrics']['CustomSql']
        assert custom_sql['Columns'] == DATASET_DEFINITIONS['quality-metrics']['columns']

    def test_invalid_key_raises(self, service, data_source_id):
        with pytest.raises(ValueError, match='Unknown dataset key'):
            service.create_dataset('nonexistent', data_source_id)

    def test_create_all_datasets(self, service, data_source_id):
        all_ds = service.create_all_datasets(data_source_id)
        assert set(all_ds.keys()) == set(DATASET_DEFINITIONS.keys())


# ------------------------------------------------------------------
# 20.1 – Refresh schedules (Req 13.4)
# ------------------------------------------------------------------

class TestRefreshSchedule:
    @pytest.mark.parametrize('freq,expected', list(FREQUENCY_TO_REFRESH_INTERVAL.items()))
    def test_frequency_mapping(self, service, freq, expected):
        assert service.get_refresh_interval(freq) == expected

    def test_unsupported_frequency_raises(self, service):
        with pytest.raises(ValueError, match='Unsupported frequency'):
            service.get_refresh_interval('biweekly')

    def test_create_refresh_schedule_structure(self, service):
        sched = service.create_refresh_schedule('ds-001', 'daily', schedule_id='s-1')
        assert sched['ScheduleId'] == 's-1'
        assert sched['DataSetId'] == 'ds-001'
        assert sched['ScheduleFrequency']['Interval'] == 'DAILY'
        assert sched['RefreshType'] == 'FULL_REFRESH'

    def test_realtime_maps_to_hourly(self, service):
        sched = service.create_refresh_schedule('ds-001', 'real-time')
        assert sched['ScheduleFrequency']['Interval'] == 'HOURLY'


# ------------------------------------------------------------------
# 20.3 – Dashboard creation (Req 13.1)
# ------------------------------------------------------------------

class TestCreateDashboard:
    @pytest.mark.parametrize('dtype', ['batch-records', 'quality-metrics', 'sla-compliance'])
    def test_creates_dashboard_for_each_type(self, service, dtype):
        dash = service.create_dashboard(dtype, 'ds-001')
        assert 'DashboardId' in dash
        assert 'Dashboard' in dash['Name']
        assert len(dash['Sheets']) >= 3

    def test_batch_records_sheets_cover_volume_trends_status(self, service):
        dash = service.create_dashboard('batch-records', 'ds-001')
        sheet_names = {s['Name'] for s in dash['Sheets']}
        assert 'Batch Volume' in sheet_names
        assert 'Batch Trends' in sheet_names
        assert 'Batch Status' in sheet_names

    def test_quality_metrics_sheets_cover_scores_failures_trends(self, service):
        dash = service.create_dashboard('quality-metrics', 'ds-001')
        sheet_names = {s['Name'] for s in dash['Sheets']}
        assert 'Quality Scores' in sheet_names
        assert 'Quality Failures' in sheet_names
        assert 'Quality Trends' in sheet_names

    def test_sla_compliance_sheets_cover_timeliness_availability_quality(self, service):
        dash = service.create_dashboard('sla-compliance', 'ds-001')
        sheet_names = {s['Name'] for s in dash['Sheets']}
        assert 'SLA Timeliness' in sheet_names
        assert 'SLA Availability' in sheet_names
        assert 'SLA Quality' in sheet_names

    def test_invalid_dashboard_type_raises(self, service):
        with pytest.raises(ValueError, match='Unknown dashboard type'):
            service.create_dashboard('unknown', 'ds-001')

    def test_source_entity_references_dataset(self, service):
        dash = service.create_dashboard('batch-records', 'ds-001')
        refs = dash['SourceEntity']['SourceTemplate']['DataSetReferences']
        assert len(refs) == 1
        assert 'ds-001' in refs[0]['DataSetArn']

    def test_sheet_controls_expanded(self, service):
        dash = service.create_dashboard('batch-records', 'ds-001')
        assert dash['DashboardPublishOptions']['SheetControlsOption']['VisibilityState'] == 'EXPANDED'

    def test_create_all_dashboards(self, service, dataset_ids):
        all_dash = service.create_all_dashboards(dataset_ids)
        assert set(all_dash.keys()) == {'batch-records', 'quality-metrics', 'sla-compliance'}

    def test_create_all_dashboards_missing_key_raises(self, service):
        with pytest.raises(ValueError, match='Missing dataset id'):
            service.create_all_dashboards({'batch-records': 'ds-1'})


# ------------------------------------------------------------------
# 20.4 – Row-level security (Req 13.5)
# ------------------------------------------------------------------

class TestRowLevelSecurity:
    def test_rls_dataset_has_rules(self, service, cmo_user_mappings):
        rls = service.create_row_level_security_dataset(cmo_user_mappings)
        assert len(rls['Rules']) == 3  # 2 for alpha + 1 for beta

    def test_rls_rules_contain_user_and_cmo(self, service, cmo_user_mappings):
        rls = service.create_row_level_security_dataset(cmo_user_mappings)
        for rule in rls['Rules']:
            assert 'UserName' in rule
            assert 'cmo_id' in rule

    def test_rls_isolates_cmo_data(self, service, cmo_user_mappings):
        rls = service.create_row_level_security_dataset(cmo_user_mappings)
        # alice should see cmo-alpha, not cmo-beta
        assert service.validate_rls_rules(rls, 'user-alice', 'cmo-alpha') is True
        assert service.validate_rls_rules(rls, 'user-alice', 'cmo-beta') is False

    def test_apply_rls_to_dataset(self, service):
        result = service.apply_rls_to_dataset('ds-target', 'rls-001')
        assert result['DataSetId'] == 'ds-target'
        rls_ref = result['RowLevelPermissionDataSet']
        assert 'rls-001' in rls_ref['Arn']
        assert rls_ref['PermissionPolicy'] == 'GRANT_ACCESS'

    def test_empty_mappings_produce_no_rules(self, service):
        rls = service.create_row_level_security_dataset({})
        assert rls['Rules'] == []


# ------------------------------------------------------------------
# 20.5 – Filters and interactivity (Req 13.3)
# ------------------------------------------------------------------

class TestFiltersAndInteractivity:
    def test_standard_filters_present(self, service):
        fc = service.create_filter_controls('ds-001')
        ids = [c['FilterControlId'] for c in fc['FilterControls']]
        for f in STANDARD_FILTERS:
            assert f'filter-{f}' in ids

    def test_date_range_filter_type(self, service):
        fc = service.create_filter_controls('ds-001')
        date_ctrl = next(
            c for c in fc['FilterControls'] if c['FilterControlId'] == 'filter-date_range'
        )
        assert date_ctrl['Type'] == 'DATE_RANGE'

    def test_dropdown_filter_type(self, service):
        fc = service.create_filter_controls('ds-001')
        cmo_ctrl = next(
            c for c in fc['FilterControls'] if c['FilterControlId'] == 'filter-cmo_id'
        )
        assert cmo_ctrl['Type'] == 'DROPDOWN'

    def test_extra_filters_appended(self, service):
        fc = service.create_filter_controls('ds-001', extra_filters=['product_name'])
        ids = [c['FilterControlId'] for c in fc['FilterControls']]
        assert 'filter-product_name' in ids

    def test_drill_down_config(self, service):
        cfg = service.create_drill_down_config(['cmo_id', 'data_domain', 'batch_id'], 'ds-001')
        assert len(cfg['DrillDownFilters']) == 3
        assert 'HierarchyId' in cfg

    def test_drill_down_empty_raises(self, service):
        with pytest.raises(ValueError, match='must not be empty'):
            service.create_drill_down_config([], 'ds-001')

    def test_realtime_update_config(self, service):
        cfg = service.create_realtime_update_config()
        assert cfg['AutoRefresh'] is True
        assert cfg['RefreshInterval'] == 'HOURLY'
