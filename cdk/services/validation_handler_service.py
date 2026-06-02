"""
Validation Handler Service

Orchestrates validation pass/fail handling: promotes passing data to Silver
layer with validation timestamp, quarantines failed records, and registers
Silver tables in Glue Data Catalog.

Requirements: 8.3, 8.4, 9.4
"""
import io
import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from utils.s3_path_utils import generate_silver_path, generate_quarantine_path

logger = logging.getLogger(__name__)


class ValidationHandlerError(Exception):
    """Base exception for validation handler operations."""
    pass


class ValidationHandlerService:
    """
    Service for handling validation pass/fail outcomes.

    Promotes passing data to Silver layer, quarantines failed records,
    and registers Silver tables in Glue Data Catalog.
    """

    def __init__(self, s3_client=None, glue_client=None):
        """
        Args:
            s3_client: boto3 S3 client (injected for testability).
            glue_client: boto3 Glue client (injected for testability).
        """
        self.s3_client = s3_client
        self.glue_client = glue_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle_validation_result(
        self,
        silver_df: pd.DataFrame,
        quarantine_df: pd.DataFrame,
        quality_report: object,
        bucket: str,
        cmo_id: str,
        data_domain: str,
        contract_id: str,
        timestamp: Optional[datetime] = None,
    ) -> dict:
        """
        Handle the full validation result: promote or quarantine data.

        Args:
            silver_df: DataFrame of records that passed schema validation.
            quarantine_df: DataFrame of records that failed schema validation.
            quality_report: QualityReport from DataQualityService.
            bucket: S3 bucket name.
            cmo_id: CMO identifier (e.g. 'cmo-alpha').
            data_domain: Data domain (e.g. 'batch-records').
            contract_id: Data contract ID.
            timestamp: Optional timestamp (defaults to now).

        Returns:
            dict with result summary.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        silver_path = None
        quarantine_path = None
        records_promoted = 0
        records_quarantined = 0
        catalog_table = None

        # Quarantine schema-validation failures first
        if quarantine_df is not None and not quarantine_df.empty:
            quarantine_path = self.quarantine_records(
                df=quarantine_df,
                bucket=bucket,
                contract_id=contract_id,
                reason='schema_validation_failure',
                timestamp=timestamp,
            )
            records_quarantined += len(quarantine_df)

        # Check quality report
        if quality_report.passed:
            # Promote to Silver
            if silver_df is not None and not silver_df.empty:
                silver_path, records_promoted = self.promote_to_silver(
                    df=silver_df,
                    bucket=bucket,
                    cmo_id=cmo_id,
                    data_domain=data_domain,
                    timestamp=timestamp,
                )
                # Register in Glue Data Catalog
                catalog_table = self.register_silver_table(
                    df=silver_df,
                    bucket=bucket,
                    cmo_id=cmo_id,
                    data_domain=data_domain,
                )
        else:
            # Quality report failed — quarantine the entire batch
            if silver_df is not None and not silver_df.empty:
                qpath = self.quarantine_records(
                    df=silver_df,
                    bucket=bucket,
                    contract_id=contract_id,
                    reason='quality_check_failure',
                    timestamp=timestamp,
                )
                if quarantine_path is None:
                    quarantine_path = qpath
                records_quarantined += len(silver_df)

        return {
            'records_promoted': records_promoted,
            'records_quarantined': records_quarantined,
            'quality_report_summary': quality_report.to_dict(),
            'silver_s3_path': silver_path,
            'quarantine_s3_path': quarantine_path,
            'catalog_table': catalog_table,
        }

    def promote_to_silver(
        self,
        df: pd.DataFrame,
        bucket: str,
        cmo_id: str,
        data_domain: str,
        timestamp: Optional[datetime] = None,
    ) -> tuple:
        """
        Write passing data to Silver layer with validation timestamp.

        Returns:
            Tuple of (silver_s3_path, records_promoted).
        """
        if df.empty:
            return None, 0

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Add validation timestamp if not present
        if '_validation_timestamp' not in df.columns:
            df = df.copy()
            df['_validation_timestamp'] = timestamp.isoformat()

        silver_s3_path = generate_silver_path(bucket, cmo_id, data_domain, timestamp)
        # Extract the key from the full s3:// path
        key = silver_s3_path.replace(f's3://{bucket}/', '') + 'data.parquet'

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
                "Promoted %d records to Silver: s3://%s/%s",
                len(df), bucket, key,
            )
            return silver_s3_path, len(df)
        except Exception as exc:
            raise ValidationHandlerError(
                f"Failed to write Silver data: {exc}"
            ) from exc

    def quarantine_records(
        self,
        df: pd.DataFrame,
        bucket: str,
        contract_id: str,
        reason: str,
        timestamp: Optional[datetime] = None,
    ) -> Optional[str]:
        """
        Write failed records to quarantine S3 prefix.

        Returns:
            Quarantine S3 path, or None if no records.
        """
        if df.empty:
            return None

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        quarantine_s3_path = generate_quarantine_path(bucket, contract_id, timestamp)
        key = quarantine_s3_path.replace(f's3://{bucket}/', '') + 'data.parquet'

        # Add quarantine metadata columns
        df_out = df.copy()
        df_out['_quarantine_reason'] = reason
        df_out['_quarantine_timestamp'] = timestamp.isoformat()

        try:
            buf = io.BytesIO()
            df_out.to_parquet(buf, index=False, compression='snappy')
            buf.seek(0)
            self.s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=buf.getvalue(),
            )
            logger.info(
                "Quarantined %d records (%s): s3://%s/%s",
                len(df), reason, bucket, key,
            )
            return quarantine_s3_path
        except Exception as exc:
            raise ValidationHandlerError(
                f"Failed to write quarantine data: {exc}"
            ) from exc

    def register_silver_table(
        self,
        df: pd.DataFrame,
        bucket: str,
        cmo_id: str,
        data_domain: str,
        database_name: str = 'cmo_data_lake',
    ) -> Optional[str]:
        """
        Register or update a Silver table in Glue Data Catalog.

        Table name format: {cmo_id}_{data_domain}_silver (hyphens replaced
        with underscores).

        Returns:
            Table name, or None if registration failed.
        """
        table_name = f"{cmo_id}_{data_domain}_silver".replace('-', '_')
        s3_location = f"s3://{bucket}/silver/{cmo_id}/{data_domain}/"

        columns = self._dataframe_to_glue_columns(df)

        table_input = {
            'Name': table_name,
            'StorageDescriptor': {
                'Columns': columns,
                'Location': s3_location,
                'InputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat',
                'OutputFormat': 'org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat',
                'SerdeInfo': {
                    'SerializationLibrary': 'org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe',
                },
            },
            'PartitionKeys': [
                {'Name': 'year', 'Type': 'string'},
                {'Name': 'month', 'Type': 'string'},
                {'Name': 'day', 'Type': 'string'},
            ],
            'TableType': 'EXTERNAL_TABLE',
        }

        try:
            self.glue_client.create_table(
                DatabaseName=database_name,
                TableInput=table_input,
            )
            logger.info("Created Glue table %s.%s", database_name, table_name)
        except Exception as create_exc:
            # Table may already exist — try update
            try:
                self.glue_client.update_table(
                    DatabaseName=database_name,
                    TableInput=table_input,
                )
                logger.info("Updated Glue table %s.%s", database_name, table_name)
            except Exception as update_exc:
                logger.error(
                    "Failed to register Glue table %s.%s: create=%s, update=%s",
                    database_name, table_name, create_exc, update_exc,
                )
                raise ValidationHandlerError(
                    f"Failed to register Glue table: {update_exc}"
                ) from update_exc

        return table_name

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dataframe_to_glue_columns(df: pd.DataFrame) -> list:
        """Convert DataFrame dtypes to Glue Data Catalog column definitions."""
        type_map = {
            'object': 'string',
            'int64': 'bigint',
            'int32': 'int',
            'Int64': 'bigint',
            'float64': 'double',
            'float32': 'float',
            'bool': 'boolean',
            'boolean': 'boolean',
            'datetime64[ns]': 'timestamp',
            'datetime64[ns, UTC]': 'timestamp',
        }
        columns = []
        for col_name, dtype in df.dtypes.items():
            glue_type = type_map.get(str(dtype), 'string')
            columns.append({'Name': col_name, 'Type': glue_type})
        return columns
