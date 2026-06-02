"""
Glue ETL Job: JDBC → Bronze S3 (Pattern 1 — Native Connectors)

Job parameters (passed via --job-bookmark-option and custom args):
  --cmo_id          CMO identifier (e.g. cmo-9e779df7)
  --data_domain     Data domain slug (e.g. batch-records)
  --glue_conn_name  Glue Connection name to use for JDBC source
  --target_bucket   S3 bucket name (data lake)
  --db_table        Source table name (schema.table or just table)

S3 output path:
  bronze/{cmo_id}/{data_domain}/year=YYYY/month=MM/day=DD/
"""
import sys
from datetime import datetime, timezone

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext

args = getResolvedOptions(sys.argv, [
    'JOB_NAME', 'cmo_id', 'data_domain', 'glue_conn_name', 'target_bucket', 'db_table',
])

sc = SparkContext()
glue_ctx = GlueContext(sc)
spark = glue_ctx.spark_session
job = Job(glue_ctx)
job.init(args['JOB_NAME'], args)

cmo_id = args['cmo_id']
data_domain = args['data_domain']
glue_conn_name = args['glue_conn_name']
target_bucket = args['target_bucket']
db_table = args['db_table']

now = datetime.now(timezone.utc)
dest = (
    f"s3://{target_bucket}/bronze/{cmo_id}/{data_domain}"
    f"/year={now.year}/month={now.month:02d}/day={now.day:02d}/"
)

# Read from JDBC source via Glue Connection
dyf = glue_ctx.create_dynamic_frame.from_options(
    connection_type="jdbc",
    connection_options={
        "useConnectionProperties": "true",
        "connectionName": glue_conn_name,
        "dbtable": db_table,
    },
    transformation_ctx="jdbc_source",
)

# Write to Bronze as Parquet (append — each run adds a new day partition)
glue_ctx.write_dynamic_frame.from_options(
    frame=dyf,
    connection_type="s3",
    connection_options={"path": dest, "partitionKeys": []},
    format="parquet",
    transformation_ctx="bronze_sink",
)

job.commit()
