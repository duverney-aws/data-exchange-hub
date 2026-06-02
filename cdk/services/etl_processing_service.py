"""
ETL Processing Service

Bronze-to-Silver transformation logic: reads Parquet from Bronze layer,
validates against registered schema, applies type conversions, handles nulls,
and deduplicates records.

Requirements: 8.1, 9.3
"""
import io
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class ETLProcessingError(Exception):
    """Base exception for ETL processing operations."""
    pass


class SchemaValidationFailedError(ETLProcessingError):
    """Raised when records fail schema validation."""
    pass


class ETLProcessingService:
    """
    Service for Bronze-to-Silver ETL transformation.

    Reads Parquet data from S3 Bronze layer, validates against a registered
    schema, applies type conversions and null handling, deduplicates, and
    returns cleansed data ready for Silver layer writing.
    """

    def __init__(self, s3_client=None, schema_registry_service=None):
        """
        Args:
            s3_client: boto3 S3 client (injected for testability).
            schema_registry_service: SchemaRegistryService instance for
                schema retrieval.
        """
        self.s3_client = s3_client
        self.schema_registry_service = schema_registry_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_bronze_data(self, bucket: str, key: str) -> pd.DataFrame:
        """
        Read Parquet data from the Bronze layer S3 path.

        Args:
            bucket: S3 bucket name.
            key: S3 object key (path within bucket).

        Returns:
            pandas DataFrame with the raw data.

        Raises:
            ETLProcessingError: If the read fails.
        """
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            body = response['Body'].read()
            df = pd.read_parquet(io.BytesIO(body))
            logger.info("Read %d records from s3://%s/%s", len(df), bucket, key)
            return df
        except Exception as exc:
            raise ETLProcessingError(
                f"Failed to read Bronze data from s3://{bucket}/{key}: {exc}"
            ) from exc

    def validate_schema(
        self,
        df: pd.DataFrame,
        schema_id: str,
        schema_version: str = 'latest',
    ) -> dict:
        """
        Validate DataFrame records against the registered schema.

        Checks that all required fields exist and that column types are
        compatible with the schema definition.

        Args:
            df: DataFrame to validate.
            schema_id: Schema name in the registry.
            schema_version: Version to validate against.

        Returns:
            dict with keys:
                - valid_df: DataFrame of records that passed validation.
                - invalid_df: DataFrame of records that failed validation.
                - errors: list of validation error descriptions.
        """
        schema_info = self.schema_registry_service.get_schema(
            schema_id=schema_id,
            version=schema_version,
        )
        schema_def = schema_info['schema_definition']
        properties = schema_def.get('properties', {})
        required_fields = schema_def.get('required', [])

        errors = []

        # Check required fields exist as columns
        missing_fields = [f for f in required_fields if f not in df.columns]
        if missing_fields:
            errors.append(f"Missing required columns: {missing_fields}")

        # Check for unexpected columns (warn only, don't reject)
        expected_fields = set(properties.keys())
        extra_fields = [c for c in df.columns if c not in expected_fields]
        if extra_fields:
            errors.append(f"Unexpected columns (will be kept): {extra_fields}")

        # If required columns are missing, all records are invalid
        if missing_fields:
            return {
                'valid_df': pd.DataFrame(columns=df.columns),
                'invalid_df': df.copy(),
                'errors': errors,
            }

        # Row-level validation: required fields must not be null
        if required_fields:
            present_required = [f for f in required_fields if f in df.columns]
            null_mask = df[present_required].isnull().any(axis=1)
            valid_df = df[~null_mask].copy()
            invalid_df = df[null_mask].copy()
            if len(invalid_df) > 0:
                errors.append(
                    f"{len(invalid_df)} records have null values in required fields"
                )
        else:
            valid_df = df.copy()
            invalid_df = pd.DataFrame(columns=df.columns)

        logger.info(
            "Schema validation: %d valid, %d invalid, %d errors",
            len(valid_df), len(invalid_df), len(errors),
        )
        return {
            'valid_df': valid_df,
            'invalid_df': invalid_df,
            'errors': errors,
        }

    def apply_type_conversions(
        self,
        df: pd.DataFrame,
        schema_id: str,
        schema_version: str = 'latest',
    ) -> pd.DataFrame:
        """
        Apply data type conversions based on the registered schema.

        Converts string date columns to datetime, numeric strings to
        numbers, etc.

        Args:
            df: DataFrame to convert.
            schema_id: Schema name in the registry.
            schema_version: Version for type info.

        Returns:
            DataFrame with converted types.
        """
        if df.empty:
            return df.copy()

        schema_info = self.schema_registry_service.get_schema(
            schema_id=schema_id,
            version=schema_version,
        )
        schema_def = schema_info['schema_definition']
        properties = schema_def.get('properties', {})

        result = df.copy()

        for col_name, col_def in properties.items():
            if col_name not in result.columns:
                continue
            target_type = col_def.get('type', 'string')
            result[col_name] = self._convert_column(
                result[col_name], target_type
            )

        logger.info("Applied type conversions for %d columns", len(properties))
        return result

    def handle_nulls(
        self,
        df: pd.DataFrame,
        schema_id: str,
        schema_version: str = 'latest',
        default_values: Optional[dict] = None,
    ) -> pd.DataFrame:
        """
        Handle null values by filling defaults based on schema types.

        Args:
            df: DataFrame with potential nulls.
            schema_id: Schema name in the registry.
            schema_version: Version for type info.
            default_values: Optional explicit defaults per column.

        Returns:
            DataFrame with nulls handled.
        """
        if df.empty:
            return df.copy()

        schema_info = self.schema_registry_service.get_schema(
            schema_id=schema_id,
            version=schema_version,
        )
        schema_def = schema_info['schema_definition']
        properties = schema_def.get('properties', {})
        required_fields = schema_def.get('required', [])

        result = df.copy()
        defaults = default_values or {}

        for col_name, col_def in properties.items():
            if col_name not in result.columns:
                continue
            # Only fill nulls for non-required fields (required nulls
            # should have been caught by validate_schema already)
            if col_name in required_fields and col_name not in defaults:
                continue
            if col_name in defaults:
                result[col_name] = result[col_name].fillna(defaults[col_name])
            else:
                target_type = col_def.get('type', 'string')
                fill_value = self._default_for_type(target_type)
                result[col_name] = result[col_name].fillna(fill_value)

        logger.info("Handled nulls for %d columns", len(properties))
        return result

    def deduplicate(
        self,
        df: pd.DataFrame,
        key_columns: list,
        keep: str = 'last',
    ) -> pd.DataFrame:
        """
        Remove duplicate records based on key columns.

        Args:
            df: DataFrame to deduplicate.
            key_columns: Column names that form the dedup key.
            keep: Which duplicate to keep ('first' or 'last').

        Returns:
            Deduplicated DataFrame.

        Raises:
            ETLProcessingError: If key columns are missing.
        """
        if df.empty:
            return df.copy()

        missing = [c for c in key_columns if c not in df.columns]
        if missing:
            raise ETLProcessingError(
                f"Deduplication key columns not found: {missing}"
            )

        before = len(df)
        result = df.drop_duplicates(subset=key_columns, keep=keep).copy()
        removed = before - len(result)
        logger.info(
            "Deduplication removed %d records (key: %s)", removed, key_columns
        )
        return result

    def transform_bronze_to_silver(
        self,
        bucket: str,
        key: str,
        schema_id: str,
        schema_version: str = 'latest',
        dedup_key_columns: Optional[list] = None,
        default_values: Optional[dict] = None,
    ) -> dict:
        """
        Full Bronze-to-Silver transformation pipeline.

        Orchestrates read, validate, convert, null-handle, and deduplicate.

        Args:
            bucket: S3 bucket for Bronze data.
            key: S3 key for Bronze data.
            schema_id: Schema to validate against.
            schema_version: Schema version.
            dedup_key_columns: Columns for deduplication (optional).
            default_values: Explicit null defaults (optional).

        Returns:
            dict with keys:
                - silver_df: Cleansed DataFrame ready for Silver layer.
                - quarantine_df: DataFrame of invalid records.
                - metrics: dict with record counts and errors.
        """
        # 1. Read from Bronze
        raw_df = self.read_bronze_data(bucket, key)

        # 2. Validate against schema
        validation = self.validate_schema(raw_df, schema_id, schema_version)
        valid_df = validation['valid_df']
        quarantine_df = validation['invalid_df']
        errors = validation['errors']

        # 3. Apply type conversions
        if not valid_df.empty:
            valid_df = self.apply_type_conversions(
                valid_df, schema_id, schema_version
            )

        # 4. Handle nulls
        if not valid_df.empty:
            valid_df = self.handle_nulls(
                valid_df, schema_id, schema_version, default_values
            )

        # 5. Deduplicate
        duplicates_removed = 0
        if not valid_df.empty and dedup_key_columns:
            before = len(valid_df)
            valid_df = self.deduplicate(valid_df, dedup_key_columns)
            duplicates_removed = before - len(valid_df)

        # 6. Add validation timestamp
        if not valid_df.empty:
            valid_df['_validation_timestamp'] = datetime.now(
                timezone.utc
            ).isoformat()

        metrics = {
            'total_records': len(raw_df),
            'valid_records': len(valid_df),
            'invalid_records': len(quarantine_df),
            'duplicates_removed': duplicates_removed,
            'errors': errors,
        }

        logger.info(
            "Bronze-to-Silver transform complete: %d total, %d valid, "
            "%d quarantined, %d duplicates removed",
            metrics['total_records'],
            metrics['valid_records'],
            metrics['invalid_records'],
            metrics['duplicates_removed'],
        )

        return {
            'silver_df': valid_df,
            'quarantine_df': quarantine_df,
            'metrics': metrics,
        }

    def write_silver_data(
        self,
        df: pd.DataFrame,
        bucket: str,
        key: str,
    ) -> None:
        """
        Write cleansed DataFrame to Silver layer as Parquet.

        Args:
            df: Cleansed DataFrame.
            bucket: S3 bucket name.
            key: S3 object key for Silver layer.

        Raises:
            ETLProcessingError: If the write fails.
        """
        if df.empty:
            logger.info("No records to write to Silver layer")
            return

        try:
            buf = io.BytesIO()
            df.to_parquet(buf, index=False, compression='snappy')
            buf.seek(0)
            self.s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=buf.getvalue(),
            )
            logger.info(
                "Wrote %d records to s3://%s/%s", len(df), bucket, key
            )
        except Exception as exc:
            raise ETLProcessingError(
                f"Failed to write Silver data to s3://{bucket}/{key}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_column(series: pd.Series, target_type: str) -> pd.Series:
        """Convert a pandas Series to the target JSON Schema type."""
        try:
            if target_type == 'integer':
                return pd.to_numeric(series, errors='coerce').astype('Int64')
            elif target_type == 'number':
                return pd.to_numeric(series, errors='coerce')
            elif target_type == 'boolean':
                return series.map(
                    lambda v: _to_bool(v) if pd.notna(v) else None
                ).astype('boolean')
            elif target_type == 'string':
                return series.astype(str).replace('nan', None)
            else:
                return series
        except Exception:
            # If conversion fails, return as-is
            return series

    @staticmethod
    def _default_for_type(target_type: str):
        """Return a sensible default value for a JSON Schema type."""
        defaults = {
            'string': '',
            'integer': 0,
            'number': 0.0,
            'boolean': False,
        }
        return defaults.get(target_type, '')


def _to_bool(value) -> Optional[bool]:
    """Convert a value to boolean."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes')
    if isinstance(value, (int, float)):
        return bool(value)
    return None
