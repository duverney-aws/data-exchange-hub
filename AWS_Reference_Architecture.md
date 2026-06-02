# Pharma Data Exchange Hub - AWS Reference Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                                                             │
│                                          EXTERNAL CMO PARTNERS                                                              │
│                                                                                                                             │
│         ┌──────────────┐         ┌──────────────┐         ┌──────────────┐         ┌──────────────┐                       │
│         │   CMO A      │         │   CMO B      │         │   CMO C      │         │   CMO D      │                       │
│         │  (Cloud DB)  │         │  (On-Prem)   │         │ (Documents)  │         │  (Images)    │                       │
│         └──────┬───────┘         └──────┬───────┘         └──────┬───────┘         └──────┬───────┘                       │
│                │                        │                        │                        │                               │
└────────────────┼────────────────────────┼────────────────────────┼────────────────────────┼───────────────────────────────┘
                 │                        │                        │                        │
                 │                        │                        │                        │
┌────────────────┼────────────────────────┼────────────────────────┼────────────────────────┼───────────────────────────────┐
│                │                        │                        │                        │                               │
│                │                        │                        │                        │                               │
│                │                   SELF-SERVICE PORTAL (CMO ONBOARDING)                   │                               │
│                │                                                                          │                               │
│                │         ┌────────────────────────────────────────────────────────────┐   │                               │
│                │         │                                                            │   │                               │
│                │         │              AWS AMPLIFY (Frontend)                        │   │                               │
│                │         │                                                            │   │                               │
│                │         │  • CMO Registration                                        │   │                               │
│                │         │  • Schema Registration                                     │   │                               │
│                │         │  • Data Contract Setup                                     │   │                               │
│                │         │  • Pattern Selection                                       │   │                               │
│                │         │                                                            │   │                               │
│                │         └────────────────────┬───────────────────────────────────────┘   │                               │
│                │                              │                                           │                               │
│                │                              ▼                                           │                               │
│                │         ┌────────────────────────────────────────────────────────────┐   │                               │
│                │         │                                                            │   │                               │
│                │         │           AMAZON API GATEWAY                               │   │                               │
│                │         │           (REST API + Authentication)                      │   │                               │
│                │         │                                                            │   │                               │
│                │         └────────────────────┬───────────────────────────────────────┘   │                               │
│                │                              │                                           │                               │
│                │                              ▼                                           │                               │
│                │         ┌────────────────────────────────────────────────────────────┐   │                               │
│                │         │                                                            │   │                               │
│                │         │           AWS LAMBDA (Portal Logic)                        │   │                               │
│                │         │                                                            │   │                               │
│                │         │  • Validate CMO registration                               │   │                               │
│                │         │  • Store schema in Glue Schema Registry                    │   │                               │
│                │         │  • Create data contract in DynamoDB                        │   │                               │
│                │         │  • Trigger pipeline deployment                             │   │                               │
│                │         │                                                            │   │                               │
│                │         └──────┬──────────────────────┬──────────────────────────────┘   │                               │
│                │                │                      │                                  │                               │
│                │                ▼                      ▼                                  │                               │
│                │    ┌──────────────────────┐  ┌──────────────────────┐                   │                               │
│                │    │  AWS GLUE SCHEMA     │  │     DYNAMODB         │                   │                               │
│                │    │  REGISTRY            │  │  (Data Contracts)    │                   │                               │
│                │    │                      │  │                      │                   │                               │
│                │    │  • CMO schemas       │  │  • CMO metadata      │                   │                               │
│                │    │  • Data models       │  │  • SLAs              │                   │                               │
│                │    │  • Version control   │  │  • Access policies   │                   │                               │
│                │    └──────────────────────┘  └──────────────────────┘                   │                               │
│                │                                                                          │                               │
│                │                              ▼                                           │                               │
│                │         ┌────────────────────────────────────────────────────────────┐   │                               │
│                │         │                                                            │   │                               │
│                │         │           AWS STEP FUNCTIONS                               │   │                               │
│                │         │           (Orchestration)                                  │   │                               │
│                │         │                                                            │   │                               │
│                │         │  • Deploy ingestion pipeline                               │   │                               │
│                │         │  • Configure validation rules                              │   │                               │
│                │         │  • Setup monitoring                                        │   │                               │
│                │         │                                                            │   │                               │
│                │         └────────────────────────────────────────────────────────────┘   │                               │
│                │                                                                          │                               │
└────────────────┼──────────────────────────────────────────────────────────────────────────┼───────────────────────────────┘
                 │                                                                          │
                 │                                                                          │
┌────────────────┼──────────────────────────────────────────────────────────────────────────┼───────────────────────────────┐
│                │                                                                          │                               │
│                │                        DATA INGESTION PATTERNS                           │                               │
│                │                                                                          │                               │
│                ▼                                  ▼                                       ▼                               │
│    ┌───────────────────────┐       ┌───────────────────────┐         ┌───────────────────────────────────┐               │
│    │                       │       │                       │         │                                   │               │
│    │   PATTERN 1:          │       │   PATTERN 2:          │         │   PATTERN 3:                      │               │
│    │   STRUCTURED DATA     │       │   FILE TRANSFER       │         │   UNSTRUCTURED DATA               │               │
│    │                       │       │                       │         │                                   │               │
│    │  ┌─────────────────┐  │       │  ┌─────────────────┐  │         │  ┌─────────────────────────────┐  │               │
│    │  │  AWS GLUE       │  │       │  │  AWS TRANSFER   │  │         │  │  AMAZON TEXTRACT            │  │               │
│    │  │  CONNECTORS     │  │       │  │  FAMILY         │  │         │  │  (Document Processing)      │  │               │
│    │  │                 │  │       │  │                 │  │         │  │                             │  │               │
│    │  │  • JDBC         │  │       │  │  • SFTP         │  │         │  │  • PDF extraction           │  │               │
│    │  │  • Snowflake    │  │       │  │  • FTPS         │  │         │  │  • Form recognition         │  │               │
│    │  │  • Oracle       │  │       │  │  • FTP          │  │         │  │  • Table extraction         │  │               │
│    │  │  • SQL Server   │  │       │  │                 │  │         │  └─────────────────────────────┘  │               │
│    │  │  • PostgreSQL   │  │       │  └────────┬────────┘  │         │                                   │               │
│    │  └────────┬────────┘  │       │           │           │         │  ┌─────────────────────────────┐  │               │
│    │           │            │       │           ▼           │         │  │  AMAZON REKOGNITION         │  │               │
│    │           │            │       │  ┌─────────────────┐  │         │  │  (Image Analysis)           │  │               │
│    │           │            │       │  │  AMAZON S3      │  │         │  │                             │  │               │
│    │           │            │       │  │  (Landing Zone) │  │         │  │  • Defect detection         │  │               │
│    │           │            │       │  └────────┬────────┘  │         │  │  • Label verification       │  │               │
│    │           │            │       │           │           │         │  │  • Custom models            │  │               │
│    └───────────┼────────────┘       └───────────┼───────────┘         │  └─────────────────────────────┘  │               │
│                │                                │                     │                                   │               │
│                └────────────────────────────────┼─────────────────────┴───────────────┬───────────────────┘               │
│                                                 │                                     │                                   │
└─────────────────────────────────────────────────┼─────────────────────────────────────┼───────────────────────────────────┘
                                                  │                                     │
                                                  ▼                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                                                             │
│                                    DATA LAKE (MEDALLION ARCHITECTURE)                                                       │
│                                                                                                                             │
│    ┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│    │                                          AMAZON S3                                                                  │  │
│    │                                                                                                                     │  │
│    │    ┌──────────────────────┐           ┌──────────────────────┐           ┌──────────────────────┐                 │  │
│    │    │                      │           │                      │           │                      │                 │  │
│    │    │   BRONZE LAYER       │  ────▶    │   SILVER LAYER       │  ────▶    │   GOLD LAYER         │                 │  │
│    │    │   (Raw Data)         │           │   (Validated)        │           │   (Aggregated)       │                 │  │
│    │    │                      │           │                      │           │                      │                 │  │
│    │    │  • Raw ingestion     │           │  • Schema validated  │           │  • Business ready    │                 │  │
│    │    │  • Immutable         │           │  • Quality checked   │           │  • Aggregated        │                 │  │
│    │    │  • Partitioned       │           │  • Cleansed          │           │  • Optimized         │                 │  │
│    │    │  • Compressed        │           │  • Enriched          │           │  • Conformed         │                 │  │
│    │    │                      │           │                      │           │                      │                 │  │
│    │    └──────────┬───────────┘           └──────────┬───────────┘           └──────────┬───────────┘                 │  │
│    │               │                                  │                                  │                             │  │
│    └───────────────┼──────────────────────────────────┼──────────────────────────────────┼─────────────────────────────┘  │
│                    │                                  │                                  │                                │
└────────────────────┼──────────────────────────────────┼──────────────────────────────────┼────────────────────────────────┘
                     │                                  │                                  │
                     ▼                                  ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                                                             │
│                                    PROCESSING & ANALYTICS                                                                   │
│                                                                                                                             │
│    ┌──────────────────────┐           ┌──────────────────────┐           ┌──────────────────────┐                         │
│    │                      │           │                      │           │                      │                         │
│    │   AWS GLUE ETL       │           │   AMAZON ATHENA      │           │   AMAZON BEDROCK     │                         │
│    │                      │           │                      │           │                      │                         │
│    │  • Data validation   │           │  • SQL queries       │           │  • Gen AI Q&A        │                         │
│    │  • Transformation    │           │  • Ad-hoc analysis   │           │  • Document search   │                         │
│    │  • Quality checks    │           │  • Federated queries │           │  • Insights          │                         │
│    │  • Schema evolution  │           │  • JDBC/ODBC access  │           │  • Summarization     │                         │
│    │                      │           │                      │           │                      │                         │
│    └──────────────────────┘           └──────────────────────┘           └──────────────────────┘                         │
│                                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                                                             │
│                                    GOVERNANCE & SECURITY                                                                    │
│                                                                                                                             │
│    ┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐          │
│    │                      │    │                      │    │                      │    │                      │          │
│    │  AWS LAKE FORMATION  │    │     AWS KMS          │    │   AWS CLOUDTRAIL     │    │   AWS MACIE          │          │
│    │                      │    │                      │    │                      │    │                      │          │
│    │  • Access control    │    │  • Encryption        │    │  • Audit logging     │    │  • PII detection     │          │
│    │  • Row/column level  │    │  • Key management    │    │  • Compliance        │    │  • Data discovery    │          │
│    │  • Data catalog      │    │  • CMK per CMO       │    │  • Security events   │    │  • Sensitive data    │          │
│    │                      │    │                      │    │                      │    │                      │          │
│    └──────────────────────┘    └──────────────────────┘    └──────────────────────┘    └──────────────────────┘          │
│                                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                                                             │
│                                    MONITORING & ORCHESTRATION                                                               │
│                                                                                                                             │
│    ┌──────────────────────┐           ┌──────────────────────┐           ┌──────────────────────┐                         │
│    │                      │           │                      │           │                      │                         │
│    │  AMAZON CLOUDWATCH   │           │  AMAZON EVENTBRIDGE  │           │  AWS STEP FUNCTIONS  │                         │
│    │                      │           │                      │           │                      │                         │
│    │  • Metrics           │           │  • Event routing     │           │  • Workflow          │                         │
│    │  • Logs              │           │  • Triggers          │           │  • Error handling    │                         │
│    │  • Alarms            │           │  • Scheduling        │           │  • Retry logic       │                         │
│    │  • Dashboards        │           │  • Integration       │           │  • State management  │                         │
│    │                      │           │                      │           │                      │                         │
│    └──────────────────────┘           └──────────────────────┘           └──────────────────────┘                         │
│                                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                                                             │
│                                    API LAYER (DATA CONSUMPTION)                                                             │
│                                                                                                                             │
│                                    ┌──────────────────────┐                                                                │
│                                    │                      │                                                                │
│                                    │  AMAZON API GATEWAY  │                                                                │
│                                    │  (REST/GraphQL APIs) │                                                                │
│                                    │                      │                                                                │
│                                    └──────────┬───────────┘                                                                │
│                                               │                                                                            │
│                    ┌──────────────────────────┼──────────────────────────┐                                                │
│                    │                          │                          │                                                │
│                    ▼                          ▼                          ▼                                                │
│    ┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐                                        │
│    │                      │   │                      │   │                      │                                        │
│    │   AWS LAMBDA         │   │   AMAZON ATHENA      │   │   AMAZON BEDROCK     │                                        │
│    │   (API Logic)        │   │   (SQL Queries)      │   │   (Gen AI)           │                                        │
│    │                      │   │                      │   │                      │                                        │
│    └──────────────────────┘   └──────────────────────┘   └──────────────────────┘                                        │
│                                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                                                             │
│                                    INTERNAL MERCK SYSTEMS                                                                   │
│                                                                                                                             │
│         ┌──────────────┐         ┌──────────────┐         ┌──────────────┐         ┌──────────────┐                       │
│         │              │         │              │         │              │         │              │                       │
│         │   ERP (SAP)  │         │  QMS (Veeva) │         │     LIMS     │         │   REDSHIFT   │                       │
│         │              │         │              │         │              │         │              │                       │
│         └──────────────┘         └──────────────┘         └──────────────┘         └──────────────┘                       │
│                                                                                                                             │
│                                           ┌──────────────┐                                                                 │
│                                           │              │                                                                 │
│                                           │  QUICKSIGHT  │                                                                 │
│                                           │  (Dashboards)│                                                                 │
│                                           │              │                                                                 │
│                                           └──────────────┘                                                                 │
│                                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## KEY FLOWS

### 1. CMO ONBOARDING (One-time, ~30 minutes)
```
CMO User → AWS Amplify Portal → API Gateway → Lambda → 
  ├─ AWS Glue Schema Registry (register schema)
  ├─ DynamoDB (store data contract)
  └─ Step Functions (deploy pipeline) → EventBridge (schedule) → CloudWatch (monitor)
```

### 2. DATA INGESTION (Ongoing, automated)
```
CMO Data → Pattern 1/2/3 → S3 Bronze Layer → 
  AWS Glue ETL (validation) → S3 Silver Layer → 
  AWS Glue ETL (aggregation) → S3 Gold Layer
```

### 3. DATA CONSUMPTION (Self-service)
```
Gold Layer → 
  ├─ Athena (SQL queries) → API Gateway → Merck Systems (SAP, Veeva, LIMS, Redshift)
  └─ Bedrock (Gen AI) → QuickSight Dashboards
```

### 4. GOVERNANCE (Continuous)
```
All Data → 
  ├─ Lake Formation (access control)
  ├─ KMS (encryption at rest)
  ├─ CloudTrail (audit logging)
  └─ Macie (PII detection)
```

## AWS SERVICES USED

### Frontend & API
- **AWS Amplify** - Self-service portal frontend
- **Amazon API Gateway** - REST API management
- **AWS Lambda** - Portal logic and API handlers

### Data Registration
- **AWS Glue Schema Registry** - CMO schema storage and versioning
- **Amazon DynamoDB** - Data contracts and metadata

### Ingestion Patterns
- **AWS Glue Connectors** - Pattern 1 (JDBC, Snowflake, Oracle, SQL Server)
- **AWS Transfer Family** - Pattern 2 (SFTP/FTPS/FTP)
- **Amazon Textract** - Pattern 3 (Document processing)
- **Amazon Rekognition** - Pattern 3 (Image analysis)

### Data Lake
- **Amazon S3** - Bronze/Silver/Gold layers
- **AWS Glue Data Catalog** - Metadata management

### Processing & Analytics
- **AWS Glue ETL** - Data transformation and quality
- **Amazon Athena** - SQL queries
- **Amazon Bedrock** - Generative AI

### Governance & Security
- **AWS Lake Formation** - Access control
- **AWS KMS** - Encryption
- **AWS CloudTrail** - Audit logging
- **Amazon Macie** - PII detection

### Orchestration & Monitoring
- **AWS Step Functions** - Workflow orchestration
- **Amazon EventBridge** - Event routing
- **Amazon CloudWatch** - Monitoring and logging

### Data Consumption
- **Amazon QuickSight** - Dashboards
- **Amazon Redshift** - Data warehouse integration

## ARCHITECTURE HIGHLIGHTS

1. **Self-Service Onboarding**: CMOs register independently via Amplify portal
2. **Schema Registry**: Centralized schema management with versioning
3. **Data Contracts**: Stored in DynamoDB for governance
4. **Three Ingestion Patterns**: Structured (Glue), Files (Transfer Family), Unstructured (Textract/Rekognition)
5. **Medallion Architecture**: Bronze (raw) → Silver (validated) → Gold (aggregated)
6. **AI-Powered**: Textract for documents, Rekognition for images, Bedrock for Gen AI
7. **Governed by Default**: Lake Formation, KMS, CloudTrail, Macie
8. **API-First Consumption**: Internal systems integrate via API Gateway
