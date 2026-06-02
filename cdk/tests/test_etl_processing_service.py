"""
Unit Tests for ETL Processing Service – Bronze to Silver transformation.

Tests read from Bronze, schema validation, type conversions, null handling,
deduplication, and the full transform_bronze_to_silver pipeline.

Requirements: 8.1, 9.3
"""
import io
import json
import sys
import os

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.etl_processing_service import (
    ETLProcessingService,
    ETLProcessingError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_SCHEMA_DEF = {
    'type': 'object',
    'properties': {
        'batch_id': {'type': 'string'},
        'product_name': {'type': 'string'},
        'quantity': {'type': 'number'},
        'quality_status': {'type': 'string'},
    },
    'required': ['batch_id', 'product_name'],
}


def _schema_response(schema_def=None):
    """Build a mock get_schema return value."""
    return {
        'schema_name': 'test-schema',
        'schema_version_id': 'ver-1',
        'schema_definition': schema_def or SAMPLE_SCHEMA_DEF,
        'data_format': 'JSON',
        'version_number': 1,
    }


def _make_parquet_bytes(df: pd.DataFrame) -> bytes:
    """Serialize a DataFrame to Parquet bytes."""
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    return buf.getvalue()


def _sample_df():
    """Return a small sample DataFrame matching SAMPLE_SCHEMA_DEF."""
    return pd.DataFrame({
        'batch_id': ['B001', 'B002', 'B003'],
        'product_name': ['Aspirin', 'Ibuprofen', 'Paracetamol'],
        'quantity': [100.0, 200.0, 150.0],
        'quality_status': ['PASS', 'FAIL', 'PASS'],
    })


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_s3():
    return MagicMock()


@pytest.fixture
def mock_schema_registry():
    mock = MagicMock()
    mock.get_schema.return_value = _schema_response()
    return mock


@pytest.fixture
def service(mock_s3, mock_schema_registry):
    return ETLProcessingService(
        s3_client=mock_s3,
        schema_registry_service=mock_schema_registry,
    )


# ---------------------------------------------------------------------------
# read_bronze_data
# ---------------------------------------------------------------------------

class TestReadBronzeData:
    def test_reads_parquet_from_s3(self, service, mock_s3):
        df = _sample_df()
        parquet_bytes = _make_parquet_bytes(df)
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=MagicMock(return_value=parquet_bytes)),
        }

        result = service.read_bronze_data('my-bucket', 'bronze/data.parquet')

        assert len(result) == 3
        assert list(result.columns) == ['batch_id', 'product_name', 'quantity', 'quality_status']
        mock_s3.get_object.assert_called_once_with(
            Bucket='my-bucket', Key='bronze/data.parquet'
        )

    def test_read_failure_raises(self, service, mock_s3):
        mock_s3.get_object.side_effect = Exception("NoSuchKey")

        with pytest.raises(ETLProcessingError, match="Failed to read Bronze data"):
            service.read_bronze_data('bad-bucket', 'missing.parquet')


# ---------------------------------------------------------------------------
# validate_schema
# ---------------------------------------------------------------------------

class TestValidateSchema:
    def test_all_valid_records(self, service):
        df = _sample_df()
        result = service.validate_schema(df, 'test-schema')

        assert len(result['valid_df']) == 3
        assert len(result['invalid_df']) == 0

    def test_missing_required_column(self, service):
        df = pd.DataFrame({
            'batch_id': ['B001'],
            'quantity': [100.0],
        })
        result = service.validate_schema(df, 'test-schema')

        assert len(result['valid_df']) == 0
        assert len(result['invalid_df']) == 1
        assert any('Missing required columns' in e for e in result['errors'])

    def test_null_in_required_field_quarantined(self, service):
        df = pd.DataFrame({
            'batch_id': ['B001', None, 'B003'],
            'product_name': ['Aspirin', 'Ibuprofen', 'Paracetamol'],
            'quantity': [100.0, 200.0, 150.0],
            'quality_status': ['PASS', 'FAIL', 'PASS'],
        })
        result = service.validate_schema(df, 'test-schema')

        assert len(result['valid_df']) == 2
        assert len(result['invalid_df']) == 1

    def test_extra_columns_kept(self, service):
        df = _sample_df()
        df['extra_col'] = 'extra'
        result = service.validate_schema(df, 'test-schema')

        assert 'extra_col' in result['valid_df'].columns
        assert any('Unexpected columns' in e for e in result['errors'])

    def test_empty_dataframe(self, service):
        df = pd.DataFrame(columns=['batch_id', 'product_name', 'quantity', 'quality_status'])
        result = service.validate_schema(df, 'test-schema')

        assert len(result['valid_df']) == 0
        assert len(result['invalid_df']) == 0


# ---------------------------------------------------------------------------
# apply_type_conversions
# ---------------------------------------------------------------------------

class TestApplyTypeConversions:
    def test_converts_numeric_strings(self, service, mock_schema_registry):
        schema_def = {
            'type': 'object',
            'properties': {
                'batch_id': {'type': 'string'},
                'quantity': {'type': 'number'},
                'count': {'type': 'integer'},
            },
            'required': ['batch_id'],
        }
        mock_schema_registry.get_schema.return_value = _schema_response(schema_def)

        df = pd.DataFrame({
            'batch_id': ['B001', 'B002'],
            'quantity': ['100.5', '200.3'],
            'count': ['10', '20'],
        })

        result = service.apply_type_conversions(df, 'test-schema')

        assert result['quantity'].dtype == float
        assert result['count'].dtype == 'Int64'

    def test_empty_df_returns_empty(self, service):
        df = pd.DataFrame(columns=['batch_id'])
        result = service.apply_type_conversions(df, 'test-schema')
        assert len(result) == 0

    def test_missing_column_skipped(self, service, mock_schema_registry):
        schema_def = {
            'type': 'object',
            'properties': {
                'batch_id': {'type': 'string'},
                'missing_col': {'type': 'number'},
            },
            'required': [],
        }
        mock_schema_registry.get_schema.return_value = _schema_response(schema_def)

        df = pd.DataFrame({'batch_id': ['B001']})
        result = service.apply_type_conversions(df, 'test-schema')

        assert 'missing_col' not in result.columns


# ---------------------------------------------------------------------------
# handle_nulls
# ---------------------------------------------------------------------------

class TestHandleNulls:
    def test_fills_defaults_for_optional_fields(self, service, mock_schema_registry):
        schema_def = {
            'type': 'object',
            'properties': {
                'batch_id': {'type': 'string'},
                'quality_status': {'type': 'string'},
                'quantity': {'type': 'number'},
            },
            'required': ['batch_id'],
        }
        mock_schema_registry.get_schema.return_value = _schema_response(schema_def)

        df = pd.DataFrame({
            'batch_id': ['B001', 'B002'],
            'quality_status': [None, 'PASS'],
            'quantity': [None, 200.0],
        })

        result = service.handle_nulls(df, 'test-schema')

        assert result.loc[0, 'quality_status'] == ''
        assert result.loc[0, 'quantity'] == 0.0

    def test_explicit_defaults_override(self, service, mock_schema_registry):
        schema_def = {
            'type': 'object',
            'properties': {
                'batch_id': {'type': 'string'},
                'quality_status': {'type': 'string'},
            },
            'required': ['batch_id'],
        }
        mock_schema_registry.get_schema.return_value = _schema_response(schema_def)

        df = pd.DataFrame({
            'batch_id': ['B001'],
            'quality_status': [None],
        })

        result = service.handle_nulls(
            df, 'test-schema', default_values={'quality_status': 'PENDING'}
        )

        assert result.loc[0, 'quality_status'] == 'PENDING'

    def test_empty_df_returns_empty(self, service):
        df = pd.DataFrame(columns=['batch_id'])
        result = service.handle_nulls(df, 'test-schema')
        assert len(result) == 0


# ---------------------------------------------------------------------------
# deduplicate
# ---------------------------------------------------------------------------

class TestDeduplicate:
    def test_removes_duplicates(self, service):
        df = pd.DataFrame({
            'batch_id': ['B001', 'B001', 'B002'],
            'product_name': ['Aspirin', 'Aspirin', 'Ibuprofen'],
            'quantity': [100.0, 100.0, 200.0],
        })

        result = service.deduplicate(df, key_columns=['batch_id'])

        assert len(result) == 2
        assert set(result['batch_id']) == {'B001', 'B002'}

    def test_keeps_last_by_default(self, service):
        df = pd.DataFrame({
            'batch_id': ['B001', 'B001'],
            'quantity': [100.0, 999.0],
        })

        result = service.deduplicate(df, key_columns=['batch_id'])

        assert result.iloc[0]['quantity'] == 999.0

    def test_keeps_first_when_specified(self, service):
        df = pd.DataFrame({
            'batch_id': ['B001', 'B001'],
            'quantity': [100.0, 999.0],
        })

        result = service.deduplicate(df, key_columns=['batch_id'], keep='first')

        assert result.iloc[0]['quantity'] == 100.0

    def test_missing_key_column_raises(self, service):
        df = pd.DataFrame({'batch_id': ['B001']})

        with pytest.raises(ETLProcessingError, match="key columns not found"):
            service.deduplicate(df, key_columns=['nonexistent'])

    def test_empty_df_returns_empty(self, service):
        df = pd.DataFrame(columns=['batch_id'])
        result = service.deduplicate(df, key_columns=['batch_id'])
        assert len(result) == 0

    def test_composite_key(self, service):
        df = pd.DataFrame({
            'batch_id': ['B001', 'B001', 'B001'],
            'product_name': ['Aspirin', 'Aspirin', 'Ibuprofen'],
            'quantity': [100.0, 100.0, 200.0],
        })

        result = service.deduplicate(
            df, key_columns=['batch_id', 'product_name']
        )

        assert len(result) == 2


# ---------------------------------------------------------------------------
# transform_bronze_to_silver (full pipeline)
# ---------------------------------------------------------------------------

class TestTransformBronzeToSilver:
    def test_full_pipeline_happy_path(self, service, mock_s3, mock_schema_registry):
        df = _sample_df()
        parquet_bytes = _make_parquet_bytes(df)
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=MagicMock(return_value=parquet_bytes)),
        }

        result = service.transform_bronze_to_silver(
            bucket='data-lake',
            key='bronze/cmo-alpha/batch-records/data.parquet',
            schema_id='test-schema',
            dedup_key_columns=['batch_id'],
        )

        assert len(result['silver_df']) == 3
        assert len(result['quarantine_df']) == 0
        assert result['metrics']['total_records'] == 3
        assert result['metrics']['valid_records'] == 3
        assert '_validation_timestamp' in result['silver_df'].columns

    def test_pipeline_with_invalid_records(self, service, mock_s3, mock_schema_registry):
        df = pd.DataFrame({
            'batch_id': ['B001', None, 'B003'],
            'product_name': ['Aspirin', 'Ibuprofen', 'Paracetamol'],
            'quantity': [100.0, 200.0, 150.0],
            'quality_status': ['PASS', 'FAIL', 'PASS'],
        })
        parquet_bytes = _make_parquet_bytes(df)
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=MagicMock(return_value=parquet_bytes)),
        }

        result = service.transform_bronze_to_silver(
            bucket='data-lake',
            key='bronze/data.parquet',
            schema_id='test-schema',
        )

        assert result['metrics']['valid_records'] == 2
        assert result['metrics']['invalid_records'] == 1

    def test_pipeline_with_duplicates(self, service, mock_s3, mock_schema_registry):
        df = pd.DataFrame({
            'batch_id': ['B001', 'B001', 'B002'],
            'product_name': ['Aspirin', 'Aspirin', 'Ibuprofen'],
            'quantity': [100.0, 100.0, 200.0],
            'quality_status': ['PASS', 'PASS', 'FAIL'],
        })
        parquet_bytes = _make_parquet_bytes(df)
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=MagicMock(return_value=parquet_bytes)),
        }

        result = service.transform_bronze_to_silver(
            bucket='data-lake',
            key='bronze/data.parquet',
            schema_id='test-schema',
            dedup_key_columns=['batch_id'],
        )

        assert result['metrics']['valid_records'] == 2
        assert result['metrics']['duplicates_removed'] == 1

    def test_pipeline_no_dedup_key(self, service, mock_s3, mock_schema_registry):
        df = _sample_df()
        parquet_bytes = _make_parquet_bytes(df)
        mock_s3.get_object.return_value = {
            'Body': MagicMock(read=MagicMock(return_value=parquet_bytes)),
        }

        result = service.transform_bronze_to_silver(
            bucket='data-lake',
            key='bronze/data.parquet',
            schema_id='test-schema',
        )

        assert result['metrics']['duplicates_removed'] == 0


# ---------------------------------------------------------------------------
# write_silver_data
# ---------------------------------------------------------------------------

class TestWriteSilverData:
    def test_writes_parquet_to_s3(self, service, mock_s3):
        df = _sample_df()
        service.write_silver_data(df, 'data-lake', 'silver/data.parquet')

        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs['Bucket'] == 'data-lake'
        assert call_kwargs['Key'] == 'silver/data.parquet'
        # Verify the body is valid parquet
        written_df = pd.read_parquet(io.BytesIO(call_kwargs['Body']))
        assert len(written_df) == 3

    def test_empty_df_skips_write(self, service, mock_s3):
        df = pd.DataFrame(columns=['batch_id'])
        service.write_silver_data(df, 'data-lake', 'silver/data.parquet')

        mock_s3.put_object.assert_not_called()

    def test_write_failure_raises(self, service, mock_s3):
        mock_s3.put_object.side_effect = Exception("AccessDenied")
        df = _sample_df()

        with pytest.raises(ETLProcessingError, match="Failed to write Silver data"):
            service.write_silver_data(df, 'bad-bucket', 'silver/data.parquet')
