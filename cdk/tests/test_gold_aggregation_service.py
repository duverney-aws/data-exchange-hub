"""
Unit Tests for Gold Aggregation Service – Silver-to-Gold aggregation,
batch record aggregation by time period, quality metrics calculation,
CMO performance summaries, Gold layer writes, and Glue Data Catalog
registration.

Requirements: 9.5
"""
import io
import sys
import os
from datetime import datetime, timezone

import pandas as pd
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.gold_aggregation_service import (
    GoldAggregationError,
    GoldAggregationService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXED_TS = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)


def _silver_df():
    """Sample Silver layer DataFrame with typical columns."""
    return pd.DataFrame({
        'batch_id': ['B001', 'B002', 'B003', 'B004', 'B005'],
        'product_name': ['Aspirin', 'Ibuprofen', 'Paracetamol', 'Aspirin', 'Ibuprofen'],
        'quantity': [100.0, 200.0, 150.0, 300.0, 250.0],
        'quality_status': ['PASS', 'FAIL', 'PASS', 'PASS', 'FAIL'],
        'cmo_id': ['cmo-alpha', 'cmo-alpha', 'cmo-beta', 'cmo-beta', 'cmo-alpha'],
        'data_domain': ['batch-records', 'batch-records', 'batch-records',
                        'quality-data', 'batch-records'],
        '_validation_timestamp': [
            '2024-06-01T10:00:00+00:00',
            '2024-06-01T11:00:00+00:00',
            '2024-06-15T09:00:00+00:00',
            '2024-07-01T08:00:00+00:00',
            '2024-07-01T12:00:00+00:00',
        ],
    })


def _make_parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_s3():
    return MagicMock()


@pytest.fixture
def mock_glue():
    return MagicMock()


@pytest.fixture
def service(mock_s3, mock_glue):
    return GoldAggregationService(s3_client=mock_s3, glue_client=mock_glue)


# ---------------------------------------------------------------------------
# read_silver_data
# ---------------------------------------------------------------------------

class TestReadSilverData:
    def test_reads_parquet_from_s3(self, service, mock_s3):
        df = _silver_df()
        parquet_bytes = _make_parquet_bytes(df)
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=MagicMock(return_value=parquet_bytes)),
        }

        result = service.read_silver_data('data-lake', 'silver/cmo-alpha/batch-records/data.parquet')

        assert len(result) == 5
        mock_s3.get_object.assert_called_once_with(
            Bucket='data-lake', Key='silver/cmo-alpha/batch-records/data.parquet',
        )

    def test_read_failure_raises(self, service, mock_s3):
        mock_s3.get_object.side_effect = Exception("NoSuchKey")

        with pytest.raises(GoldAggregationError, match="Failed to read Silver data"):
            service.read_silver_data('bad-bucket', 'missing.parquet')


# ---------------------------------------------------------------------------
# aggregate_batch_records
# ---------------------------------------------------------------------------

class TestAggregateBatchRecords:
    def test_daily_aggregation(self, service):
        df = _silver_df()
        result = service.aggregate_batch_records(df, period='daily')

        assert 'record_count' in result.columns
        assert 'period_start' in result.columns
        assert 'aggregation_period' in result.columns
        assert (result['aggregation_period'] == 'daily').all()
        assert result['record_count'].sum() == 5

    def test_weekly_aggregation(self, service):
        df = _silver_df()
        result = service.aggregate_batch_records(df, period='weekly')

        assert (result['aggregation_period'] == 'weekly').all()
        assert result['record_count'].sum() == 5

    def test_monthly_aggregation(self, service):
        df = _silver_df()
        result = service.aggregate_batch_records(df, period='monthly')

        assert (result['aggregation_period'] == 'monthly').all()
        assert result['record_count'].sum() == 5

    def test_quantity_aggregation(self, service):
        df = _silver_df()
        result = service.aggregate_batch_records(df, period='monthly')

        assert 'quantity_sum' in result.columns
        assert 'quantity_avg' in result.columns
        assert result['quantity_sum'].sum() == pytest.approx(1000.0)

    def test_groups_by_cmo_and_domain(self, service):
        df = _silver_df()
        result = service.aggregate_batch_records(df, period='monthly')

        assert 'cmo_id' in result.columns
        assert 'data_domain' in result.columns

    def test_invalid_period_raises(self, service):
        df = _silver_df()
        with pytest.raises(GoldAggregationError, match="Period must be one of"):
            service.aggregate_batch_records(df, period='yearly')

    def test_missing_date_column_raises(self, service):
        df = pd.DataFrame({'batch_id': ['B001']})
        with pytest.raises(GoldAggregationError, match="Date column"):
            service.aggregate_batch_records(df, period='daily')

    def test_empty_dataframe(self, service):
        df = pd.DataFrame(columns=['_validation_timestamp', 'cmo_id', 'quantity'])
        result = service.aggregate_batch_records(df, period='daily')

        assert len(result) == 0
        assert 'record_count' in result.columns

    def test_no_quantity_column(self, service):
        df = pd.DataFrame({
            'batch_id': ['B001', 'B002'],
            '_validation_timestamp': ['2024-06-01T10:00:00+00:00', '2024-06-01T11:00:00+00:00'],
            'cmo_id': ['cmo-alpha', 'cmo-alpha'],
        })
        result = service.aggregate_batch_records(df, period='daily')

        assert len(result) > 0
        assert result['record_count'].sum() == 2


# ---------------------------------------------------------------------------
# calculate_quality_metrics
# ---------------------------------------------------------------------------

class TestCalculateQualityMetrics:
    def test_monthly_quality_metrics(self, service):
        df = _silver_df()
        result = service.calculate_quality_metrics(df, period='monthly')

        assert 'total_records' in result.columns
        assert 'pass_count' in result.columns
        assert 'fail_count' in result.columns
        assert 'pass_rate' in result.columns
        assert result['total_records'].sum() == 5

    def test_pass_fail_counts(self, service):
        df = _silver_df()
        result = service.calculate_quality_metrics(df, period='monthly')

        total_pass = result['pass_count'].sum()
        total_fail = result['fail_count'].sum()
        assert total_pass == 3
        assert total_fail == 2

    def test_pass_rate_calculation(self, service):
        df = pd.DataFrame({
            'batch_id': ['B001', 'B002', 'B003', 'B004'],
            'quality_status': ['PASS', 'PASS', 'PASS', 'FAIL'],
            '_validation_timestamp': ['2024-06-01T10:00:00+00:00'] * 4,
            'cmo_id': ['cmo-alpha'] * 4,
        })
        result = service.calculate_quality_metrics(df, period='monthly')

        assert len(result) == 1
        assert result.iloc[0]['pass_rate'] == 75.0

    def test_daily_quality_metrics(self, service):
        df = _silver_df()
        result = service.calculate_quality_metrics(df, period='daily')

        assert (result['aggregation_period'] == 'daily').all()

    def test_invalid_period_raises(self, service):
        df = _silver_df()
        with pytest.raises(GoldAggregationError, match="Period must be one of"):
            service.calculate_quality_metrics(df, period='quarterly')

    def test_empty_dataframe(self, service):
        df = pd.DataFrame(columns=['_validation_timestamp', 'quality_status'])
        result = service.calculate_quality_metrics(df, period='monthly')

        assert len(result) == 0

    def test_missing_quality_column(self, service):
        df = pd.DataFrame({
            'batch_id': ['B001', 'B002'],
            '_validation_timestamp': ['2024-06-01T10:00:00+00:00'] * 2,
        })
        result = service.calculate_quality_metrics(df, period='monthly')

        # Without quality column, all records treated as pass
        assert result['pass_count'].sum() == 2
        assert result['fail_count'].sum() == 0


# ---------------------------------------------------------------------------
# create_cmo_performance_summary
# ---------------------------------------------------------------------------

class TestCreateCmoPerformanceSummary:
    def test_summary_per_cmo(self, service):
        df = _silver_df()
        result = service.create_cmo_performance_summary(df)

        assert 'cmo_id' in result.columns
        assert set(result['cmo_id']) == {'cmo-alpha', 'cmo-beta'}

    def test_record_counts(self, service):
        df = _silver_df()
        result = service.create_cmo_performance_summary(df)

        assert result['total_records'].sum() == 5

    def test_pass_fail_rates(self, service):
        df = _silver_df()
        result = service.create_cmo_performance_summary(df)

        alpha = result[result['cmo_id'] == 'cmo-alpha'].iloc[0]
        # cmo-alpha: B001=PASS, B002=FAIL, B005=FAIL → 1 pass, 2 fail
        assert alpha['pass_count'] == 1
        assert alpha['fail_count'] == 2

    def test_domain_count(self, service):
        df = _silver_df()
        result = service.create_cmo_performance_summary(df)

        beta = result[result['cmo_id'] == 'cmo-beta'].iloc[0]
        # cmo-beta has batch-records and quality-data
        assert beta['domain_count'] == 2

    def test_avg_quantity(self, service):
        df = _silver_df()
        result = service.create_cmo_performance_summary(df)

        assert 'avg_quantity' in result.columns
        alpha = result[result['cmo_id'] == 'cmo-alpha'].iloc[0]
        # cmo-alpha quantities: 100, 200, 250 → avg ~183.33
        assert alpha['avg_quantity'] == pytest.approx(183.33, rel=0.01)

    def test_empty_dataframe(self, service):
        df = pd.DataFrame(columns=['cmo_id', 'quality_status', 'quantity'])
        result = service.create_cmo_performance_summary(df)

        assert len(result) == 0

    def test_no_cmo_id_column(self, service):
        df = pd.DataFrame({
            'batch_id': ['B001', 'B002'],
            'quality_status': ['PASS', 'FAIL'],
            '_validation_timestamp': ['2024-06-01T10:00:00+00:00'] * 2,
        })
        result = service.create_cmo_performance_summary(df)

        assert len(result) == 1
        assert result.iloc[0]['cmo_id'] == 'unknown'


# ---------------------------------------------------------------------------
# write_gold_data
# ---------------------------------------------------------------------------

class TestWriteGoldData:
    def test_writes_parquet_to_s3(self, service, mock_s3):
        df = pd.DataFrame({'record_count': [10], 'cmo_id': ['cmo-alpha']})
        path = service.write_gold_data(
            df, 'data-lake', 'batch-summary-daily', timestamp=FIXED_TS,
        )

        assert path is not None
        assert 'gold' in path
        assert 'batch-summary-daily' in path
        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs['Bucket'] == 'data-lake'
        assert 'gold/' in call_kwargs['Key']
        # Verify written data is valid parquet
        written_df = pd.read_parquet(io.BytesIO(call_kwargs['Body']))
        assert len(written_df) == 1

    def test_empty_df_returns_none(self, service, mock_s3):
        df = pd.DataFrame(columns=['record_count'])
        path = service.write_gold_data(df, 'data-lake', 'batch-summary-daily')

        assert path is None
        mock_s3.put_object.assert_not_called()

    def test_write_failure_raises(self, service, mock_s3):
        mock_s3.put_object.side_effect = Exception("AccessDenied")
        df = pd.DataFrame({'record_count': [10]})

        with pytest.raises(GoldAggregationError, match="Failed to write Gold data"):
            service.write_gold_data(df, 'bad-bucket', 'batch-summary-daily')

    def test_uses_snappy_compression(self, service, mock_s3):
        df = pd.DataFrame({'record_count': [10, 20]})
        service.write_gold_data(df, 'data-lake', 'batch-summary-daily', timestamp=FIXED_TS)

        call_kwargs = mock_s3.put_object.call_args[1]
        written_df = pd.read_parquet(io.BytesIO(call_kwargs['Body']))
        assert len(written_df) == 2


# ---------------------------------------------------------------------------
# register_gold_table
# ---------------------------------------------------------------------------

class TestRegisterGoldTable:
    def test_creates_glue_table(self, service, mock_glue):
        df = pd.DataFrame({'record_count': [10], 'cmo_id': ['cmo-alpha']})
        table_name = service.register_gold_table(
            df, 'data-lake', 'batch-summary-daily',
        )

        assert table_name == 'batch_summary_daily_gold'
        mock_glue.create_table.assert_called_once()
        call_kwargs = mock_glue.create_table.call_args[1]
        assert call_kwargs['DatabaseName'] == 'cmo_data_lake'
        table_input = call_kwargs['TableInput']
        assert table_input['Name'] == 'batch_summary_daily_gold'
        assert table_input['TableType'] == 'EXTERNAL_TABLE'
        assert 'gold/batch-summary-daily/' in table_input['StorageDescriptor']['Location']

    def test_updates_existing_table(self, service, mock_glue):
        mock_glue.create_table.side_effect = Exception("AlreadyExistsException")
        df = pd.DataFrame({'record_count': [10]})

        table_name = service.register_gold_table(
            df, 'data-lake', 'batch-summary-daily',
        )

        assert table_name == 'batch_summary_daily_gold'
        mock_glue.update_table.assert_called_once()

    def test_partition_keys(self, service, mock_glue):
        df = pd.DataFrame({'record_count': [10]})
        service.register_gold_table(df, 'data-lake', 'batch-summary-daily')

        call_kwargs = mock_glue.create_table.call_args[1]
        partition_keys = call_kwargs['TableInput']['PartitionKeys']
        key_names = [k['Name'] for k in partition_keys]
        assert key_names == ['year', 'month', 'day']

    def test_both_create_and_update_fail_raises(self, service, mock_glue):
        mock_glue.create_table.side_effect = Exception("CreateFailed")
        mock_glue.update_table.side_effect = Exception("UpdateFailed")
        df = pd.DataFrame({'record_count': [10]})

        with pytest.raises(GoldAggregationError, match="Failed to register Glue table"):
            service.register_gold_table(df, 'data-lake', 'batch-summary-daily')

    def test_table_name_replaces_hyphens(self, service, mock_glue):
        df = pd.DataFrame({'metric': [1.0]})
        table_name = service.register_gold_table(
            df, 'data-lake', 'quality-metrics-monthly',
        )

        assert table_name == 'quality_metrics_monthly_gold'
        assert '-' not in table_name


# ---------------------------------------------------------------------------
# aggregate_to_gold – full orchestration
# ---------------------------------------------------------------------------

class TestAggregateToGold:
    def test_full_pipeline(self, service, mock_s3, mock_glue):
        df = _silver_df()
        parquet_bytes = _make_parquet_bytes(df)
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=MagicMock(return_value=parquet_bytes)),
        }

        result = service.aggregate_to_gold(
            bucket='data-lake',
            key='silver/cmo-alpha/batch-records/data.parquet',
            timestamp=FIXED_TS,
        )

        assert result['records_read'] == 5
        assert result['batch_summary_path'] is not None
        assert result['quality_metrics_path'] is not None
        assert result['cmo_performance_path'] is not None
        assert len(result['tables_registered']) == 3
        # 3 Gold writes + 1 Silver read
        assert mock_s3.put_object.call_count == 3
        assert mock_glue.create_table.call_count == 3

    def test_empty_silver_data(self, service, mock_s3, mock_glue):
        df = pd.DataFrame(columns=[
            'batch_id', 'quantity', 'quality_status',
            'cmo_id', 'data_domain', '_validation_timestamp',
        ])
        parquet_bytes = _make_parquet_bytes(df)
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=MagicMock(return_value=parquet_bytes)),
        }

        result = service.aggregate_to_gold(
            bucket='data-lake',
            key='silver/empty/data.parquet',
            timestamp=FIXED_TS,
        )

        assert result['records_read'] == 0
        assert result['batch_summary_path'] is None
        assert result['quality_metrics_path'] is None
        assert result['cmo_performance_path'] is None
        assert result['tables_registered'] == []
        mock_s3.put_object.assert_not_called()
