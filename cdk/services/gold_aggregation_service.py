"""
Gold Aggregation Service

Reads validated Silver layer data, aggregates batch records by time period
(daily, weekly, monthly), calculates quality metrics and trends, creates
CMO performance summaries, writes to Gold layer, and registers Gold tables
in Glue Data Catalog.

Requirements: 9.5
"""
import io
import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from utils.s3_path_utils import generate_gold_path

logger = logging.getLogger(__name__)


class GoldAggregationError(Exception):
    """Base exception for Gold aggregation operations."""
    pass


class GoldAggregationService:
    """
    Service for Silver-to-Gold aggregation.

    Reads validated Parquet data from Silver layer, produces business-ready
    aggregations (daily/weekly/monthly batch summaries, quality metrics,
    CMO performance dashboards), writes results to Gold layer S3 paths,
    and registers tables in Glue Data Catalog.
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

    def read_silver_data(self, bucket: str, key: str) -> pd.DataFrame:
        """
        Read validated Parquet data from the Silver layer.

        Args:
            bucket: S3 bucket name.
            key: S3 object key.

        Returns:
            pandas DataFrame with Silver layer data.

        Raises:
            GoldAggregationError: If the read fails.
        """
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            body = response['Body'].read()
            df = pd.read_parquet(io.BytesIO(body))
            logger.info("Read %d records from s3://%s/%s", len(df), bucket, key)
            return df
        except Exception as exc:
            raise GoldAggregationError(
                f"Failed to read Silver data from s3://{bucket}/{key}: {exc}"
            ) from exc

    def aggregate_batch_records(
        self,
        df: pd.DataFrame,
        period: str = 'daily',
        date_column: str = '_validation_timestamp',
    ) -> pd.DataFrame:
        """
        Aggregate batch records by time period.

        Groups records by the specified period and computes record counts,
        quantity sums, and quantity averages per CMO and data domain.

        Args:
            df: Silver layer DataFrame (must contain *date_column*, and
                optionally 'cmo_id', 'data_domain', 'quantity').
            period: One of 'daily', 'weekly', 'monthly'.
            date_column: Column containing the timestamp to group by.

        Returns:
            Aggregated DataFrame with columns:
                period_start, cmo_id, data_domain, record_count,
                quantity_sum, quantity_avg.

        Raises:
            GoldAggregationError: On invalid period or missing date column.
        """
        valid_periods = {'daily': 'D', 'weekly': 'W', 'monthly': 'M'}
        if period not in valid_periods:
            raise GoldAggregationError(
                f"Period must be one of {list(valid_periods)}, got: {period}"
            )

        if df.empty:
            return pd.DataFrame(columns=[
                'period_start', 'cmo_id', 'data_domain',
                'record_count', 'quantity_sum', 'quantity_avg',
            ])

        if date_column not in df.columns:
            raise GoldAggregationError(
                f"Date column '{date_column}' not found in DataFrame"
            )

        result = df.copy()
        result[date_column] = pd.to_datetime(result[date_column], utc=True)
        result['period_start'] = result[date_column].dt.to_period(
            valid_periods[period]
        ).dt.start_time

        group_cols = ['period_start']
        if 'cmo_id' in result.columns:
            group_cols.append('cmo_id')
        if 'data_domain' in result.columns:
            group_cols.append('data_domain')

        agg_dict: dict = {'period_start': 'count'}
        rename_map = {'period_start': 'record_count'}

        if 'quantity' in result.columns:
            result['quantity'] = pd.to_numeric(result['quantity'], errors='coerce').fillna(0.0)
            agg_dict['quantity_sum'] = ('quantity', 'sum')
            agg_dict['quantity_avg'] = ('quantity', 'mean')

        grouped = result.groupby(group_cols, as_index=False).agg(
            record_count=(date_column, 'count'),
            **({
                'quantity_sum': ('quantity', 'sum'),
                'quantity_avg': ('quantity', 'mean'),
            } if 'quantity' in result.columns else {}),
        )

        # Ensure all expected columns exist
        for col in ['cmo_id', 'data_domain', 'quantity_sum', 'quantity_avg']:
            if col not in grouped.columns:
                grouped[col] = None if col in ('cmo_id', 'data_domain') else 0.0

        grouped['aggregation_period'] = period
        logger.info(
            "Aggregated %d records into %d %s groups",
            len(df), len(grouped), period,
        )
        return grouped

    def calculate_quality_metrics(
        self,
        df: pd.DataFrame,
        period: str = 'monthly',
        date_column: str = '_validation_timestamp',
        quality_column: str = 'quality_status',
    ) -> pd.DataFrame:
        """
        Calculate quality metrics and trends over time.

        Computes pass/fail counts, pass rate, and total records per period.

        Args:
            df: Silver layer DataFrame.
            period: One of 'daily', 'weekly', 'monthly'.
            date_column: Timestamp column for grouping.
            quality_column: Column with quality status values (e.g. PASS/FAIL).

        Returns:
            DataFrame with columns:
                period_start, cmo_id, total_records, pass_count,
                fail_count, pass_rate.
        """
        valid_periods = {'daily': 'D', 'weekly': 'W', 'monthly': 'M'}
        if period not in valid_periods:
            raise GoldAggregationError(
                f"Period must be one of {list(valid_periods)}, got: {period}"
            )

        if df.empty:
            return pd.DataFrame(columns=[
                'period_start', 'cmo_id', 'total_records',
                'pass_count', 'fail_count', 'pass_rate',
            ])

        if date_column not in df.columns:
            raise GoldAggregationError(
                f"Date column '{date_column}' not found in DataFrame"
            )

        result = df.copy()
        result[date_column] = pd.to_datetime(result[date_column], utc=True)
        result['period_start'] = result[date_column].dt.to_period(
            valid_periods[period]
        ).dt.start_time

        # Normalise quality status
        if quality_column in result.columns:
            result['_is_pass'] = result[quality_column].astype(str).str.upper() == 'PASS'
        else:
            result['_is_pass'] = True

        group_cols = ['period_start']
        if 'cmo_id' in result.columns:
            group_cols.append('cmo_id')

        grouped = result.groupby(group_cols, as_index=False).agg(
            total_records=('_is_pass', 'count'),
            pass_count=('_is_pass', 'sum'),
        )
        grouped['fail_count'] = grouped['total_records'] - grouped['pass_count']
        grouped['pass_rate'] = (
            grouped['pass_count'] / grouped['total_records'] * 100
        ).round(2)

        if 'cmo_id' not in grouped.columns:
            grouped['cmo_id'] = None

        grouped['aggregation_period'] = period
        logger.info(
            "Calculated quality metrics: %d period groups", len(grouped),
        )
        return grouped

    def create_cmo_performance_summary(
        self,
        df: pd.DataFrame,
        date_column: str = '_validation_timestamp',
        quality_column: str = 'quality_status',
    ) -> pd.DataFrame:
        """
        Create cross-domain performance summary per CMO.

        Produces one row per CMO with total records, domain count,
        pass/fail rates, and average quantity.

        Args:
            df: Silver layer DataFrame.
            date_column: Timestamp column.
            quality_column: Column with quality status values.

        Returns:
            DataFrame with columns:
                cmo_id, total_records, domain_count, pass_count,
                fail_count, pass_rate, avg_quantity.
        """
        if df.empty:
            return pd.DataFrame(columns=[
                'cmo_id', 'total_records', 'domain_count',
                'pass_count', 'fail_count', 'pass_rate', 'avg_quantity',
            ])

        result = df.copy()

        if quality_column in result.columns:
            result['_is_pass'] = result[quality_column].astype(str).str.upper() == 'PASS'
        else:
            result['_is_pass'] = True

        if 'cmo_id' not in result.columns:
            result['cmo_id'] = 'unknown'

        agg_spec = {
            'total_records': ('_is_pass', 'count'),
            'pass_count': ('_is_pass', 'sum'),
        }
        if 'data_domain' in result.columns:
            agg_spec['domain_count'] = ('data_domain', 'nunique')
        if 'quantity' in result.columns:
            result['quantity'] = pd.to_numeric(result['quantity'], errors='coerce').fillna(0.0)
            agg_spec['avg_quantity'] = ('quantity', 'mean')

        grouped = result.groupby('cmo_id', as_index=False).agg(**agg_spec)
        grouped['fail_count'] = grouped['total_records'] - grouped['pass_count']
        grouped['pass_rate'] = (
            grouped['pass_count'] / grouped['total_records'] * 100
        ).round(2)

        for col, default in [('domain_count', 0), ('avg_quantity', 0.0)]:
            if col not in grouped.columns:
                grouped[col] = default

        logger.info(
            "Created CMO performance summary for %d CMOs", len(grouped),
        )
        return grouped

    # ------------------------------------------------------------------
    # Write & Catalog
    # ------------------------------------------------------------------

    def write_gold_data(
        self,
        df: pd.DataFrame,
        bucket: str,
        aggregation_type: str,
        timestamp: Optional[datetime] = None,
    ) -> Optional[str]:
        """
        Write aggregated DataFrame to Gold layer as Parquet.

        Args:
            df: Aggregated DataFrame.
            bucket: S3 bucket name.
            aggregation_type: Gold sub-path (e.g. 'batch-summary-daily').
            timestamp: Date for partitioning (defaults to now).

        Returns:
            Full S3 path written to, or None if df is empty.

        Raises:
            GoldAggregationError: If the write fails.
        """
        if df.empty:
            logger.info("No records to write to Gold layer")
            return None

        gold_s3_path = generate_gold_path(bucket, aggregation_type, timestamp)
        key = gold_s3_path.replace(f's3://{bucket}/', '') + 'data.parquet'

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
                "Wrote %d records to Gold: s3://%s/%s",
                len(df), bucket, key,
            )
            return gold_s3_path
        except Exception as exc:
            raise GoldAggregationError(
                f"Failed to write Gold data to s3://{bucket}/{key}: {exc}"
            ) from exc

    def register_gold_table(
        self,
        df: pd.DataFrame,
        bucket: str,
        aggregation_type: str,
        database_name: str = 'cmo_data_lake',
    ) -> Optional[str]:
        """
        Register or update a Gold table in Glue Data Catalog.

        Table name is derived from *aggregation_type* with hyphens replaced
        by underscores and a ``_gold`` suffix.

        Args:
            df: Aggregated DataFrame (used for column inference).
            bucket: S3 bucket name.
            aggregation_type: Gold sub-path (e.g. 'batch-summary-daily').
            database_name: Glue database name.

        Returns:
            Table name, or None on failure.

        Raises:
            GoldAggregationError: If both create and update fail.
        """
        table_name = f"{aggregation_type}_gold".replace('-', '_')
        s3_location = f"s3://{bucket}/gold/{aggregation_type}/"

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
        except Exception:
            try:
                self.glue_client.update_table(
                    DatabaseName=database_name,
                    TableInput=table_input,
                )
                logger.info("Updated Glue table %s.%s", database_name, table_name)
            except Exception as update_exc:
                raise GoldAggregationError(
                    f"Failed to register Glue table: {update_exc}"
                ) from update_exc

        return table_name

    # ------------------------------------------------------------------
    # Full orchestration
    # ------------------------------------------------------------------

    def aggregate_to_gold(
        self,
        bucket: str,
        key: str,
        timestamp: Optional[datetime] = None,
    ) -> dict:
        """
        Full Silver-to-Gold aggregation pipeline.

        Reads Silver data, produces daily batch summary, monthly quality
        metrics, and CMO performance dashboard, writes each to Gold layer,
        and registers tables in Glue Data Catalog.

        Args:
            bucket: S3 bucket containing Silver data.
            key: S3 key for the Silver Parquet file.
            timestamp: Partition date (defaults to now).

        Returns:
            dict summarising paths and table names.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        silver_df = self.read_silver_data(bucket, key)

        results: dict = {
            'batch_summary_path': None,
            'quality_metrics_path': None,
            'cmo_performance_path': None,
            'tables_registered': [],
            'records_read': len(silver_df),
        }

        # 1. Daily batch summary
        batch_agg = self.aggregate_batch_records(silver_df, period='daily')
        if not batch_agg.empty:
            results['batch_summary_path'] = self.write_gold_data(
                batch_agg, bucket, 'batch-summary-daily', timestamp,
            )
            tbl = self.register_gold_table(batch_agg, bucket, 'batch-summary-daily')
            results['tables_registered'].append(tbl)

        # 2. Monthly quality metrics
        quality_agg = self.calculate_quality_metrics(silver_df, period='monthly')
        if not quality_agg.empty:
            results['quality_metrics_path'] = self.write_gold_data(
                quality_agg, bucket, 'quality-metrics-monthly', timestamp,
            )
            tbl = self.register_gold_table(quality_agg, bucket, 'quality-metrics-monthly')
            results['tables_registered'].append(tbl)

        # 3. CMO performance dashboard
        perf_agg = self.create_cmo_performance_summary(silver_df)
        if not perf_agg.empty:
            results['cmo_performance_path'] = self.write_gold_data(
                perf_agg, bucket, 'cmo-performance-dashboard', timestamp,
            )
            tbl = self.register_gold_table(perf_agg, bucket, 'cmo-performance-dashboard')
            results['tables_registered'].append(tbl)

        logger.info("Gold aggregation complete: %s", results)
        return results

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
