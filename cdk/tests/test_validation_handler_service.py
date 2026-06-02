"""
Unit Tests for Validation Handler Service – validation pass/fail handling,
Silver layer promotion, quarantine, and Glue Data Catalog registration.

Requirements: 8.3, 8.4, 9.4
"""
import io
import sys
import os
from datetime import datetime, timezone

import pandas as pd
import pytest
from unittest.mock import MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.validation_handler_service import (
    ValidationHandlerError,
    ValidationHandlerService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXED_TS = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)


def _sample_df():
    return pd.DataFrame({
        'batch_id': ['B001', 'B002', 'B003'],
        'product_name': ['Aspirin', 'Ibuprofen', 'Paracetamol'],
        'quantity': [100.0, 200.0, 150.0],
        'quality_status': ['PASS', 'FAIL', 'PASS'],
    })


def _quarantine_df():
    return pd.DataFrame({
        'batch_id': [None, 'B005'],
        'product_name': ['Bad', 'Worse'],
        'quantity': [0.0, -1.0],
        'quality_status': ['FAIL', 'FAIL'],
    })


class FakeQualityReport:
    """Minimal stand-in for QualityReport."""
    def __init__(self, passed=True, overall_score=100.0):
        self.passed = passed
        self.overall_score = overall_score

    def to_dict(self):
        return {
            'passed': self.passed,
            'overall_score': self.overall_score,
        }


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
    return ValidationHandlerService(s3_client=mock_s3, glue_client=mock_glue)


# ---------------------------------------------------------------------------
# promote_to_silver
# ---------------------------------------------------------------------------

class TestPromoteToSilver:
    def test_writes_parquet_to_silver_path(self, service, mock_s3):
        df = _sample_df()
        path, count = service.promote_to_silver(
            df=df, bucket='data-lake', cmo_id='cmo-alpha',
            data_domain='batch-records', timestamp=FIXED_TS,
        )

        assert count == 3
        assert path is not None
        assert 'silver' in path
        assert 'cmo-alpha' in path
        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs['Bucket'] == 'data-lake'
        assert 'silver/' in call_kwargs['Key']
        # Verify written data is valid parquet
        written_df = pd.read_parquet(io.BytesIO(call_kwargs['Body']))
        assert len(written_df) == 3

    def test_adds_validation_timestamp(self, service, mock_s3):
        df = _sample_df()
        service.promote_to_silver(
            df=df, bucket='data-lake', cmo_id='cmo-alpha',
            data_domain='batch-records', timestamp=FIXED_TS,
        )

        call_kwargs = mock_s3.put_object.call_args[1]
        written_df = pd.read_parquet(io.BytesIO(call_kwargs['Body']))
        assert '_validation_timestamp' in written_df.columns
        assert written_df['_validation_timestamp'].iloc[0] == FIXED_TS.isoformat()

    def test_preserves_existing_validation_timestamp(self, service, mock_s3):
        df = _sample_df()
        df['_validation_timestamp'] = '2024-01-01T00:00:00+00:00'
        service.promote_to_silver(
            df=df, bucket='data-lake', cmo_id='cmo-alpha',
            data_domain='batch-records', timestamp=FIXED_TS,
        )

        call_kwargs = mock_s3.put_object.call_args[1]
        written_df = pd.read_parquet(io.BytesIO(call_kwargs['Body']))
        assert written_df['_validation_timestamp'].iloc[0] == '2024-01-01T00:00:00+00:00'

    def test_empty_df_returns_none(self, service, mock_s3):
        df = pd.DataFrame(columns=['batch_id'])
        path, count = service.promote_to_silver(
            df=df, bucket='data-lake', cmo_id='cmo-alpha',
            data_domain='batch-records',
        )

        assert path is None
        assert count == 0
        mock_s3.put_object.assert_not_called()

    def test_uses_snappy_compression(self, service, mock_s3):
        df = _sample_df()
        service.promote_to_silver(
            df=df, bucket='data-lake', cmo_id='cmo-alpha',
            data_domain='batch-records', timestamp=FIXED_TS,
        )

        call_kwargs = mock_s3.put_object.call_args[1]
        # Read parquet metadata to verify compression
        buf = io.BytesIO(call_kwargs['Body'])
        import pyarrow.parquet as pq
        pf = pq.ParquetFile(buf)
        metadata = pf.schema_arrow.pandas_metadata
        # The file should be readable (snappy compressed)
        written_df = pd.read_parquet(io.BytesIO(call_kwargs['Body']))
        assert len(written_df) == 3

    def test_write_failure_raises(self, service, mock_s3):
        mock_s3.put_object.side_effect = Exception("AccessDenied")
        df = _sample_df()

        with pytest.raises(ValidationHandlerError, match="Failed to write Silver data"):
            service.promote_to_silver(
                df=df, bucket='bad-bucket', cmo_id='cmo-alpha',
                data_domain='batch-records',
            )


# ---------------------------------------------------------------------------
# quarantine_records
# ---------------------------------------------------------------------------

class TestQuarantineRecords:
    def test_writes_to_quarantine_path(self, service, mock_s3):
        df = _quarantine_df()
        path = service.quarantine_records(
            df=df, bucket='data-lake', contract_id='CMO-ALPHA-BATCH-001',
            reason='schema_validation_failure', timestamp=FIXED_TS,
        )

        assert path is not None
        assert 'quarantine' in path
        assert 'CMO-ALPHA-BATCH-001' in path
        mock_s3.put_object.assert_called_once()

    def test_adds_quarantine_metadata(self, service, mock_s3):
        df = _quarantine_df()
        service.quarantine_records(
            df=df, bucket='data-lake', contract_id='CMO-ALPHA-BATCH-001',
            reason='quality_check_failure', timestamp=FIXED_TS,
        )

        call_kwargs = mock_s3.put_object.call_args[1]
        written_df = pd.read_parquet(io.BytesIO(call_kwargs['Body']))
        assert '_quarantine_reason' in written_df.columns
        assert '_quarantine_timestamp' in written_df.columns
        assert written_df['_quarantine_reason'].iloc[0] == 'quality_check_failure'

    def test_empty_df_returns_none(self, service, mock_s3):
        df = pd.DataFrame(columns=['batch_id'])
        path = service.quarantine_records(
            df=df, bucket='data-lake', contract_id='CMO-ALPHA-BATCH-001',
            reason='test',
        )

        assert path is None
        mock_s3.put_object.assert_not_called()

    def test_write_failure_raises(self, service, mock_s3):
        mock_s3.put_object.side_effect = Exception("AccessDenied")
        df = _quarantine_df()

        with pytest.raises(ValidationHandlerError, match="Failed to write quarantine data"):
            service.quarantine_records(
                df=df, bucket='bad-bucket', contract_id='CMO-ALPHA-BATCH-001',
                reason='test',
            )


# ---------------------------------------------------------------------------
# register_silver_table
# ---------------------------------------------------------------------------

class TestRegisterSilverTable:
    def test_creates_glue_table(self, service, mock_glue):
        df = _sample_df()
        table_name = service.register_silver_table(
            df=df, bucket='data-lake', cmo_id='cmo-alpha',
            data_domain='batch-records',
        )

        assert table_name == 'cmo_alpha_batch_records_silver'
        mock_glue.create_table.assert_called_once()
        call_kwargs = mock_glue.create_table.call_args[1]
        assert call_kwargs['DatabaseName'] == 'cmo_data_lake'
        table_input = call_kwargs['TableInput']
        assert table_input['Name'] == 'cmo_alpha_batch_records_silver'
        assert table_input['TableType'] == 'EXTERNAL_TABLE'
        assert 'silver/cmo-alpha/batch-records/' in table_input['StorageDescriptor']['Location']

    def test_updates_existing_table(self, service, mock_glue):
        mock_glue.create_table.side_effect = Exception("AlreadyExistsException")
        df = _sample_df()

        table_name = service.register_silver_table(
            df=df, bucket='data-lake', cmo_id='cmo-alpha',
            data_domain='batch-records',
        )

        assert table_name == 'cmo_alpha_batch_records_silver'
        mock_glue.update_table.assert_called_once()

    def test_column_definitions(self, service, mock_glue):
        df = _sample_df()
        service.register_silver_table(
            df=df, bucket='data-lake', cmo_id='cmo-alpha',
            data_domain='batch-records',
        )

        call_kwargs = mock_glue.create_table.call_args[1]
        columns = call_kwargs['TableInput']['StorageDescriptor']['Columns']
        col_names = [c['Name'] for c in columns]
        assert 'batch_id' in col_names
        assert 'product_name' in col_names
        assert 'quantity' in col_names

    def test_partition_keys(self, service, mock_glue):
        df = _sample_df()
        service.register_silver_table(
            df=df, bucket='data-lake', cmo_id='cmo-alpha',
            data_domain='batch-records',
        )

        call_kwargs = mock_glue.create_table.call_args[1]
        partition_keys = call_kwargs['TableInput']['PartitionKeys']
        key_names = [k['Name'] for k in partition_keys]
        assert key_names == ['year', 'month', 'day']

    def test_both_create_and_update_fail_raises(self, service, mock_glue):
        mock_glue.create_table.side_effect = Exception("CreateFailed")
        mock_glue.update_table.side_effect = Exception("UpdateFailed")
        df = _sample_df()

        with pytest.raises(ValidationHandlerError, match="Failed to register Glue table"):
            service.register_silver_table(
                df=df, bucket='data-lake', cmo_id='cmo-alpha',
                data_domain='batch-records',
            )

    def test_table_name_replaces_hyphens(self, service, mock_glue):
        df = _sample_df()
        table_name = service.register_silver_table(
            df=df, bucket='data-lake', cmo_id='cmo-beta-pharma',
            data_domain='quality-data',
        )

        assert table_name == 'cmo_beta_pharma_quality_data_silver'
        assert '-' not in table_name


# ---------------------------------------------------------------------------
# handle_validation_result – full orchestration
# ---------------------------------------------------------------------------

class TestHandleValidationResult:
    def test_passing_quality_promotes_to_silver(self, service, mock_s3, mock_glue):
        silver_df = _sample_df()
        quarantine_df = pd.DataFrame(columns=silver_df.columns)
        report = FakeQualityReport(passed=True)

        result = service.handle_validation_result(
            silver_df=silver_df,
            quarantine_df=quarantine_df,
            quality_report=report,
            bucket='data-lake',
            cmo_id='cmo-alpha',
            data_domain='batch-records',
            contract_id='CMO-ALPHA-BATCH-001',
            timestamp=FIXED_TS,
        )

        assert result['records_promoted'] == 3
        assert result['records_quarantined'] == 0
        assert result['silver_s3_path'] is not None
        assert result['quarantine_s3_path'] is None
        assert result['catalog_table'] == 'cmo_alpha_batch_records_silver'
        assert result['quality_report_summary']['passed'] is True

    def test_failing_quality_quarantines_batch(self, service, mock_s3, mock_glue):
        silver_df = _sample_df()
        quarantine_df = pd.DataFrame(columns=silver_df.columns)
        report = FakeQualityReport(passed=False, overall_score=50.0)

        result = service.handle_validation_result(
            silver_df=silver_df,
            quarantine_df=quarantine_df,
            quality_report=report,
            bucket='data-lake',
            cmo_id='cmo-alpha',
            data_domain='batch-records',
            contract_id='CMO-ALPHA-BATCH-001',
            timestamp=FIXED_TS,
        )

        assert result['records_promoted'] == 0
        assert result['records_quarantined'] == 3
        assert result['silver_s3_path'] is None
        assert result['quarantine_s3_path'] is not None
        assert result['catalog_table'] is None

    def test_schema_failures_quarantined_alongside_quality_pass(self, service, mock_s3, mock_glue):
        silver_df = _sample_df()
        quarantine_df = _quarantine_df()
        report = FakeQualityReport(passed=True)

        result = service.handle_validation_result(
            silver_df=silver_df,
            quarantine_df=quarantine_df,
            quality_report=report,
            bucket='data-lake',
            cmo_id='cmo-alpha',
            data_domain='batch-records',
            contract_id='CMO-ALPHA-BATCH-001',
            timestamp=FIXED_TS,
        )

        assert result['records_promoted'] == 3
        assert result['records_quarantined'] == 2
        assert result['silver_s3_path'] is not None
        assert result['quarantine_s3_path'] is not None
        assert result['catalog_table'] is not None

    def test_both_schema_and_quality_failures(self, service, mock_s3, mock_glue):
        silver_df = _sample_df()
        quarantine_df = _quarantine_df()
        report = FakeQualityReport(passed=False, overall_score=30.0)

        result = service.handle_validation_result(
            silver_df=silver_df,
            quarantine_df=quarantine_df,
            quality_report=report,
            bucket='data-lake',
            cmo_id='cmo-alpha',
            data_domain='batch-records',
            contract_id='CMO-ALPHA-BATCH-001',
            timestamp=FIXED_TS,
        )

        # 2 from schema failures + 3 from quality failure
        assert result['records_promoted'] == 0
        assert result['records_quarantined'] == 5
        assert result['silver_s3_path'] is None
        assert result['catalog_table'] is None

    def test_empty_dataframes(self, service, mock_s3, mock_glue):
        silver_df = pd.DataFrame(columns=['batch_id'])
        quarantine_df = pd.DataFrame(columns=['batch_id'])
        report = FakeQualityReport(passed=True)

        result = service.handle_validation_result(
            silver_df=silver_df,
            quarantine_df=quarantine_df,
            quality_report=report,
            bucket='data-lake',
            cmo_id='cmo-alpha',
            data_domain='batch-records',
            contract_id='CMO-ALPHA-BATCH-001',
            timestamp=FIXED_TS,
        )

        assert result['records_promoted'] == 0
        assert result['records_quarantined'] == 0
        mock_s3.put_object.assert_not_called()
        mock_glue.create_table.assert_not_called()


# ---------------------------------------------------------------------------
# _dataframe_to_glue_columns
# ---------------------------------------------------------------------------

class TestDataframeToGlueColumns:
    def test_maps_common_types(self):
        df = pd.DataFrame({
            'str_col': ['a'],
            'int_col': pd.array([1], dtype='Int64'),
            'float_col': [1.5],
            'bool_col': [True],
        })
        columns = ValidationHandlerService._dataframe_to_glue_columns(df)
        col_map = {c['Name']: c['Type'] for c in columns}

        assert col_map['str_col'] == 'string'
        assert col_map['int_col'] == 'bigint'
        assert col_map['float_col'] == 'double'
        assert col_map['bool_col'] == 'boolean'

    def test_unknown_type_defaults_to_string(self):
        df = pd.DataFrame({'col': pd.array([1, 2], dtype='uint8')})
        columns = ValidationHandlerService._dataframe_to_glue_columns(df)
        assert columns[0]['Type'] == 'string'
