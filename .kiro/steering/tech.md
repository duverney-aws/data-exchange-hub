# Technology Stack

## Platform

AWS Cloud Services (production-ready, GxP-qualified)

## Core AWS Services

### Frontend & API
- **AWS Amplify** - Self-service portal frontend (React)
- **Amazon API Gateway** - REST API management
- **AWS Lambda** - Portal logic and API handlers (Python/Node.js)

### Data Registration & Contracts
- **AWS Glue Schema Registry** - Schema versioning and validation (AVRO/JSON)
- **Amazon DynamoDB** - Data contracts and CMO metadata storage
- **AWS Secrets Manager** - Secure credential management

### Integration Patterns
- **AWS Glue Connectors** - Pattern 1: Native database connectors (JDBC, Snowflake, Oracle, SQL Server, PostgreSQL)
- **AWS Transfer Family** - Pattern 2: Managed SFTP/FTPS/FTP
- **Amazon Textract** - Pattern 3: AI document extraction (PDFs, forms)
- **Amazon Rekognition** - Pattern 3: Image analysis and defect detection

### Data Lake & Processing
- **Amazon S3** - Medallion architecture storage (Bronze/Silver/Gold layers)
- **AWS Glue ETL** - Data transformation, validation, and quality checks (PySpark)
- **AWS Glue Data Catalog** - Metadata management
- **Amazon Athena** - SQL queries on data lake
- **Amazon Bedrock** - Generative AI for natural language queries

### Governance & Security
- **AWS Lake Formation** - Fine-grained access control (row/column level)
- **AWS KMS** - Encryption at rest (customer-managed keys per CMO)
- **AWS CloudTrail** - Audit logging for compliance (21 CFR Part 11)
- **Amazon Macie** - PII detection and sensitive data discovery
- **AWS IAM Identity Center** - SSO and multi-account isolation

### Orchestration & Monitoring
- **AWS Step Functions** - Workflow orchestration for pipeline deployment
- **Amazon EventBridge** - Event routing and scheduling
- **Amazon CloudWatch** - Metrics, logs, alarms, and dashboards
- **Amazon SNS** - Alert notifications

### Data Consumption
- **Amazon QuickSight** - Business intelligence dashboards
- **Amazon Redshift** - Data warehouse integration

## Programming Languages

- **Python** - Primary language for Lambda functions, Glue ETL jobs, and data processing
- **JavaScript/TypeScript** - Frontend (React) and Node.js Lambda functions
- **SQL** - Athena queries and data analysis

## Data Formats

- **Parquet** - Primary storage format (compressed, columnar)
- **JSON** - API responses and unstructured data extraction
- **AVRO** - Schema registry format
- **CSV** - Legacy file ingestion support
- **YAML** - Data contract definitions

## Infrastructure as Code

- **AWS CloudFormation** - Infrastructure provisioning
- **AWS CDK** (optional) - Infrastructure as code in Python/TypeScript

## Compliance & Standards

- **21 CFR Part 11** - FDA electronic records compliance
- **GxP** - Good practice quality guidelines
- **GDPR** - Data privacy (if applicable)

## Common Commands

### Python Environment
```bash
# Install dependencies
pip install boto3 awswrangler pandas pyarrow

# Run Glue job locally (for testing)
python glue_job.py --JOB_NAME test-job
```

### AWS CLI
```bash
# Deploy infrastructure
aws cloudformation deploy --template-file template.yaml --stack-name cmo-hub

# Register schema
aws glue register-schema-version --schema-id SchemaName=batch-records --schema-definition file://schema.avro

# Query data with Athena
aws athena start-query-execution --query-string "SELECT * FROM batch_records LIMIT 10"

# List CMO contracts
aws dynamodb scan --table-name cmo-data-contracts
```

### Diagram Generation
```bash
# Generate architecture diagrams
pip install diagrams
python architecture-diagram-code.py
```

## Development Workflow

1. **Schema Definition** - Define or infer schema from sample data
2. **Contract Creation** - Store in DynamoDB with quality rules and SLAs
3. **Pipeline Deployment** - Step Functions orchestrates Glue job creation
4. **Data Validation** - Glue Data Quality validates against schema and rules
5. **Monitoring** - CloudWatch dashboards track SLA compliance

## Testing

- **Unit Tests** - Lambda functions and data transformations
- **Integration Tests** - End-to-end pipeline validation with sample data
- **Schema Validation** - Compatibility checks before version updates
- **Data Quality Tests** - Automated validation against contract rules
