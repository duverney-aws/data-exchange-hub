"""
DynamoDB Tables Stack for Pharma Data Exchange Hub
Defines: cmo-profiles, data-contracts, pipeline-executions tables
"""
from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class DatabaseStack(Stack):
    """Stack for DynamoDB tables storing CMO profiles, contracts, and execution history"""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # CMO Profiles Table
        self.cmo_profiles_table = dynamodb.Table(
            self,
            "CMOProfilesTable",
            table_name="cmo-profiles",
            partition_key=dynamodb.Attribute(
                name="cmoId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Global Secondary Index for organization name lookup
        self.cmo_profiles_table.add_global_secondary_index(
            index_name="organization-name-index",
            partition_key=dynamodb.Attribute(
                name="organizationName",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Data Contracts Table
        self.data_contracts_table = dynamodb.Table(
            self,
            "DataContractsTable",
            table_name="data-contracts",
            partition_key=dynamodb.Attribute(
                name="contractId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Global Secondary Index for querying contracts by CMO and status
        self.data_contracts_table.add_global_secondary_index(
            index_name="cmo-contracts-index",
            partition_key=dynamodb.Attribute(
                name="cmoId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Products (Material Master) Table
        self.products_table = dynamodb.Table(
            self,
            "ProductsTable",
            table_name="products",
            partition_key=dynamodb.Attribute(
                name="productId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # GSI: query products by CMO
        self.products_table.add_global_secondary_index(
            index_name="cmo-products-index",
            partition_key=dynamodb.Attribute(
                name="cmoId",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Batches (Lot Tracking) Table
        self.batches_table = dynamodb.Table(
            self,
            "BatchesTable",
            table_name="batches",
            partition_key=dynamodb.Attribute(
                name="batchId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # GSI: query batches by CMO
        self.batches_table.add_global_secondary_index(
            index_name="cmo-batches-index",
            partition_key=dynamodb.Attribute(
                name="cmoId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # GSI: query batches by product
        self.batches_table.add_global_secondary_index(
            index_name="product-batches-index",
            partition_key=dynamodb.Attribute(
                name="productId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="manufacturingDate",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Schemas Table
        self.schemas_table = dynamodb.Table(
            self,
            "SchemasTable",
            table_name="schemas",
            partition_key=dynamodb.Attribute(
                name="schemaId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        self.schemas_table.add_global_secondary_index(
            index_name="cmo-schemas-index",
            partition_key=dynamodb.Attribute(
                name="cmoId",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Connections Table
        self.connections_table = dynamodb.Table(
            self,
            "ConnectionsTable",
            table_name="connections",
            partition_key=dynamodb.Attribute(
                name="connectionId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

        # GSI: query connections by CMO
        self.connections_table.add_global_secondary_index(
            index_name="cmo-connections-index",
            partition_key=dynamodb.Attribute(
                name="cmoId",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # Pipeline Execution History Table
        self.pipeline_executions_table = dynamodb.Table(
            self,
            "PipelineExecutionsTable",
            table_name="pipeline-executions",
            partition_key=dynamodb.Attribute(
                name="contractId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="executionTimestamp",
                type=dynamodb.AttributeType.NUMBER
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            time_to_live_attribute="ttl",  # Auto-delete after 90 days
            removal_policy=RemovalPolicy.DESTROY,  # Execution history can be recreated
        )
