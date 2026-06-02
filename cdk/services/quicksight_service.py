"""
QuickSight Business Intelligence Service

Manages Amazon QuickSight data sources (Athena), datasets for batch records /
quality metrics / SLA compliance, dashboard definitions, row-level security,
and data refresh schedules driven by data-contract delivery frequency.

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
"""
import logging
import uuid
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

FREQUENCY_TO_REFRESH_INTERVAL = {
    'real-time': 'HOURLY',
    'hourly': 'HOURLY',
    'daily': 'DAILY',
    'weekly': 'WEEKLY',
    'monthly': 'MONTHLY',
}

DATASET_DEFINITIONS = {
    'batch-records': {
        'name': 'CMO Batch Records',
        'sql': 'SELECT * FROM cmo_data_lake.batch_records_gold',
        'columns': [
            {'Name': 'batch_id', 'Type': 'STRING'},
            {'Name': 'cmo_id', 'Type': 'STRING'},
            {'Name': 'product_name', 'Type': 'STRING'},
            {'Name': 'manufacture_date', 'Type': 'DATETIME'},
            {'Name': 'quantity', 'Type': 'DECIMAL'},
            {'Name': 'quality_status', 'Type': 'STRING'},
            {'Name': 'data_domain', 'Type': 'STRING'},
        ],
    },
    'quality-metrics': {
        'name': 'CMO Quality Metrics',
        'sql': 'SELECT * FROM cmo_data_lake.quality_metrics_monthly_gold',
        'columns': [
            {'Name': 'period_start', 'Type': 'DATETIME'},
            {'Name': 'cmo_id', 'Type': 'STRING'},
            {'Name': 'total_records', 'Type': 'INTEGER'},
            {'Name': 'pass_count', 'Type': 'INTEGER'},
            {'Name': 'fail_count', 'Type': 'INTEGER'},
            {'Name': 'pass_rate', 'Type': 'DECIMAL'},
        ],
    },
    'sla-compliance': {
        'name': 'SLA Compliance',
        'sql': 'SELECT * FROM cmo_data_lake.cmo_performance_dashboard_gold',
        'columns': [
            {'Name': 'cmo_id', 'Type': 'STRING'},
            {'Name': 'total_records', 'Type': 'INTEGER'},
            {'Name': 'pass_rate', 'Type': 'DECIMAL'},
            {'Name': 'fail_count', 'Type': 'INTEGER'},
            {'Name': 'avg_quantity', 'Type': 'DECIMAL'},
            {'Name': 'domain_count', 'Type': 'INTEGER'},
        ],
    },
}

STANDARD_FILTERS = ['cmo_id', 'date_range', 'data_domain']


class QuickSightService:
    """
    Builds QuickSight configuration dicts for data sources, datasets,
    dashboards, row-level security rules, and interactive filters.

    This service does NOT make real AWS API calls.  It produces the
    configuration structures that would be passed to the QuickSight API.
    """

    ATHENA_WORKGROUP = 'cmo-workgroup'
    DATABASE_NAME = 'cmo_data_lake'

    def __init__(self, aws_account_id='123456789012', region='us-east-1'):
        self.aws_account_id = aws_account_id
        self.region = region

    # ------------------------------------------------------------------
    # 20.1  Data sources & datasets (Req 13.2, 13.4)
    # ------------------------------------------------------------------

    def create_athena_data_source(self, data_source_id=None):
        ds_id = data_source_id or f'athena-cmo-{uuid.uuid4().hex[:8]}'
        return {
            'DataSourceId': ds_id,
            'Name': 'CMO Data Lake Athena',
            'Type': 'ATHENA',
            'DataSourceParameters': {
                'AthenaParameters': {
                    'WorkGroup': self.ATHENA_WORKGROUP,
                },
            },
            'SslProperties': {'DisableSsl': False},
            'AwsAccountId': self.aws_account_id,
        }

    def create_dataset(self, dataset_key, data_source_id, dataset_id=None):
        if dataset_key not in DATASET_DEFINITIONS:
            raise ValueError(
                f"Unknown dataset key '{dataset_key}'. "
                f"Valid keys: {list(DATASET_DEFINITIONS)}"
            )
        defn = DATASET_DEFINITIONS[dataset_key]
        ds_id = dataset_id or f'ds-{dataset_key}-{uuid.uuid4().hex[:8]}'
        return {
            'DataSetId': ds_id,
            'Name': defn['name'],
            'PhysicalTableMap': {
                dataset_key: {
                    'CustomSql': {
                        'DataSourceArn': (
                            f'arn:aws:quicksight:{self.region}:'
                            f'{self.aws_account_id}:datasource/{data_source_id}'
                        ),
                        'Name': defn['name'],
                        'SqlQuery': defn['sql'],
                        'Columns': defn['columns'],
                    },
                },
            },
            'ImportMode': 'SPICE',
            'AwsAccountId': self.aws_account_id,
        }

    def create_all_datasets(self, data_source_id):
        return {
            key: self.create_dataset(key, data_source_id)
            for key in DATASET_DEFINITIONS
        }

    def get_refresh_interval(self, frequency):
        interval = FREQUENCY_TO_REFRESH_INTERVAL.get(frequency)
        if interval is None:
            raise ValueError(
                f"Unsupported frequency '{frequency}'. "
                f"Valid: {list(FREQUENCY_TO_REFRESH_INTERVAL)}"
            )
        return interval

    def create_refresh_schedule(self, dataset_id, frequency, schedule_id=None):
        sched_id = schedule_id or f'sched-{uuid.uuid4().hex[:8]}'
        interval = self.get_refresh_interval(frequency)
        return {
            'ScheduleId': sched_id,
            'DataSetId': dataset_id,
            'ScheduleFrequency': {'Interval': interval},
            'RefreshType': 'FULL_REFRESH',
            'AwsAccountId': self.aws_account_id,
        }

    # ------------------------------------------------------------------
    # 20.3  Dashboard definitions (Req 13.1)
    # ------------------------------------------------------------------

    def create_dashboard(self, dashboard_type, dataset_id, dashboard_id=None):
        builders = {
            'batch-records': self._batch_records_sheets,
            'quality-metrics': self._quality_metrics_sheets,
            'sla-compliance': self._sla_compliance_sheets,
        }
        if dashboard_type not in builders:
            raise ValueError(
                f"Unknown dashboard type '{dashboard_type}'. "
                f"Valid: {list(builders)}"
            )
        db_id = dashboard_id or f'dash-{dashboard_type}-{uuid.uuid4().hex[:8]}'
        sheets = builders[dashboard_type](dataset_id)
        return {
            'DashboardId': db_id,
            'Name': DATASET_DEFINITIONS[dashboard_type]['name'] + ' Dashboard',
            'SourceEntity': {
                'SourceTemplate': {
                    'DataSetReferences': [{
                        'DataSetPlaceholder': dashboard_type,
                        'DataSetArn': (
                            f'arn:aws:quicksight:{self.region}:'
                            f'{self.aws_account_id}:dataset/{dataset_id}'
                        ),
                    }],
                },
            },
            'DashboardPublishOptions': {
                'SheetControlsOption': {'VisibilityState': 'EXPANDED'},
            },
            'Sheets': sheets,
            'AwsAccountId': self.aws_account_id,
        }

    def create_all_dashboards(self, dataset_ids):
        results = {}
        for dtype in ('batch-records', 'quality-metrics', 'sla-compliance'):
            ds_id = dataset_ids.get(dtype)
            if ds_id is None:
                raise ValueError(f"Missing dataset id for '{dtype}'")
            results[dtype] = self.create_dashboard(dtype, ds_id)
        return results

    @staticmethod
    def _batch_records_sheets(dataset_id):
        return [
            {'SheetId': 'batch-volume', 'Name': 'Batch Volume', 'Visuals': [
                {'VisualId': 'batch-volume-bar', 'Type': 'BAR_CHART',
                 'Title': 'Batch Volume by CMO', 'DataSetId': dataset_id,
                 'Columns': ['cmo_id', 'batch_id'], 'Aggregation': 'COUNT'}]},
            {'SheetId': 'batch-trends', 'Name': 'Batch Trends', 'Visuals': [
                {'VisualId': 'batch-trend-line', 'Type': 'LINE_CHART',
                 'Title': 'Batch Trends Over Time', 'DataSetId': dataset_id,
                 'Columns': ['manufacture_date', 'quantity'], 'Aggregation': 'SUM'}]},
            {'SheetId': 'batch-status', 'Name': 'Batch Status', 'Visuals': [
                {'VisualId': 'batch-status-pie', 'Type': 'PIE_CHART',
                 'Title': 'Batch Quality Status Distribution', 'DataSetId': dataset_id,
                 'Columns': ['quality_status'], 'Aggregation': 'COUNT'}]},
        ]

    @staticmethod
    def _quality_metrics_sheets(dataset_id):
        return [
            {'SheetId': 'quality-scores', 'Name': 'Quality Scores', 'Visuals': [
                {'VisualId': 'quality-score-gauge', 'Type': 'KPI',
                 'Title': 'Quality Pass Rate', 'DataSetId': dataset_id,
                 'Columns': ['pass_rate'], 'Aggregation': 'AVERAGE'}]},
            {'SheetId': 'quality-failures', 'Name': 'Quality Failures', 'Visuals': [
                {'VisualId': 'quality-fail-bar', 'Type': 'BAR_CHART',
                 'Title': 'Failure Count by CMO', 'DataSetId': dataset_id,
                 'Columns': ['cmo_id', 'fail_count'], 'Aggregation': 'SUM'}]},
            {'SheetId': 'quality-trends', 'Name': 'Quality Trends', 'Visuals': [
                {'VisualId': 'quality-trend-line', 'Type': 'LINE_CHART',
                 'Title': 'Quality Trends Over Time', 'DataSetId': dataset_id,
                 'Columns': ['period_start', 'pass_rate'], 'Aggregation': 'AVERAGE'}]},
        ]

    @staticmethod
    def _sla_compliance_sheets(dataset_id):
        return [
            {'SheetId': 'sla-timeliness', 'Name': 'SLA Timeliness', 'Visuals': [
                {'VisualId': 'sla-timeliness-kpi', 'Type': 'KPI',
                 'Title': 'SLA Timeliness Compliance', 'DataSetId': dataset_id,
                 'Columns': ['pass_rate'], 'Aggregation': 'AVERAGE'}]},
            {'SheetId': 'sla-availability', 'Name': 'SLA Availability', 'Visuals': [
                {'VisualId': 'sla-availability-bar', 'Type': 'BAR_CHART',
                 'Title': 'Availability by CMO', 'DataSetId': dataset_id,
                 'Columns': ['cmo_id', 'total_records'], 'Aggregation': 'SUM'}]},
            {'SheetId': 'sla-quality', 'Name': 'SLA Quality', 'Visuals': [
                {'VisualId': 'sla-quality-line', 'Type': 'LINE_CHART',
                 'Title': 'SLA Quality Trends', 'DataSetId': dataset_id,
                 'Columns': ['cmo_id', 'pass_rate'], 'Aggregation': 'AVERAGE'}]},
        ]

    # ------------------------------------------------------------------
    # 20.4  Row-level security (Req 13.5)
    # ------------------------------------------------------------------

    def create_row_level_security_dataset(self, cmo_user_mappings, rls_dataset_id=None):
        rls_id = rls_dataset_id or f'rls-{uuid.uuid4().hex[:8]}'
        rules = []
        for cmo_id, users in cmo_user_mappings.items():
            for user in users:
                rules.append({'UserName': user, 'cmo_id': cmo_id})
        return {
            'DataSetId': rls_id,
            'Name': 'CMO Row-Level Security Rules',
            'Rules': rules,
            'AwsAccountId': self.aws_account_id,
            'Format': 'JSON',
        }

    def apply_rls_to_dataset(self, target_dataset_id, rls_dataset_id):
        return {
            'DataSetId': target_dataset_id,
            'RowLevelPermissionDataSet': {
                'Arn': (
                    f'arn:aws:quicksight:{self.region}:'
                    f'{self.aws_account_id}:dataset/{rls_dataset_id}'
                ),
                'PermissionPolicy': 'GRANT_ACCESS',
                'FormatVersion': 'VERSION_2',
                'Namespace': 'default',
            },
            'AwsAccountId': self.aws_account_id,
        }

    def validate_rls_rules(self, rls_config, user, expected_cmo_id):
        for rule in rls_config.get('Rules', []):
            if rule['UserName'] == user and rule['cmo_id'] == expected_cmo_id:
                return True
        return False

    # ------------------------------------------------------------------
    # 20.5  Filters & interactivity (Req 13.3)
    # ------------------------------------------------------------------

    def create_filter_controls(self, dataset_id, extra_filters=None):
        filters = list(STANDARD_FILTERS)
        if extra_filters:
            filters.extend(extra_filters)
        controls = []
        for f in filters:
            controls.append(self._build_filter_control(f, dataset_id))
        return {
            'FilterControls': controls,
            'CrossDatasetTypes': 'ALL_DATASETS',
            'DataSetId': dataset_id,
        }

    def create_drill_down_config(self, hierarchy_columns, dataset_id):
        if not hierarchy_columns:
            raise ValueError('hierarchy_columns must not be empty')
        return {
            'DrillDownFilters': [
                {'CategoryFilter': {'Column': col, 'DataSetId': dataset_id}}
                for col in hierarchy_columns
            ],
            'HierarchyId': f'drill-{"-".join(hierarchy_columns)}',
        }

    def create_realtime_update_config(self):
        return {
            'AutoRefresh': True,
            'RefreshInterval': 'HOURLY',
            'OptimisticLocking': True,
        }

    @staticmethod
    def _build_filter_control(filter_name, dataset_id):
        if filter_name == 'date_range':
            return {
                'FilterControlId': f'filter-{filter_name}',
                'Title': 'Date Range',
                'Type': 'DATE_RANGE',
                'DataSetId': dataset_id,
                'Column': 'manufacture_date',
            }
        return {
            'FilterControlId': f'filter-{filter_name}',
            'Title': filter_name.replace('_', ' ').title(),
            'Type': 'DROPDOWN',
            'DataSetId': dataset_id,
            'Column': filter_name,
        }
