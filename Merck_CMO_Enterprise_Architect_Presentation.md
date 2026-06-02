# Pharma Data Exchange Hub - Enterprise Architecture Presentation

## Technical Deep Dive for Enterprise Architects

**Audience:** Merck Enterprise Architecture Team
**Duration:** 45-60 minutes
**Objective:** Demonstrate technical feasibility, architectural soundness, and alignment with EA principles

---

## Slide 1: Title Slide

**Title:** Pharma Data Exchange Hub
**Subtitle:** Technical Architecture & Implementation Strategy

**Presented by:** AWS Solutions Architecture Team
**Date:** [Date]

**Focus:** Architecture patterns, integration strategies, security, scalability, and operational excellence

---

## Slide 2: Agenda

1. Current State Architecture Analysis
2. Proposed Solution Architecture
3. Three Integration Patterns - Technical Deep Dive
4. Data Architecture & Governance
5. Security & Compliance Architecture
6. Scalability & Performance
7. Operational Model & DevOps
8. Integration with Existing Merck Systems
9. Technology Stack & Service Selection
10. Implementation Roadmap & Risk Mitigation
11. Total Cost of Ownership
12. Q&A and Technical Discussion

---

## Slide 3: Current State Architecture Analysis

**Title:** Understanding the Integration Challenge

**Current Integration Pattern (Per CMO):**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   CMO System                    Integration Layer           Merck Systems   │
│                                                                              │
│   ┌─────────────┐              ┌─────────────┐              ┌────────────┐ │
│   │             │              │             │              │            │ │
│   │  CMO ERP/   │──────────────│  Custom     │──────────────│  Merck ERP │ │
│   │  MES/LIMS   │   Manual     │  Point-to-  │   Manual     │  QMS/LIMS  │ │
│   │             │   Mapping    │  Point      │   Mapping    │            │ │
│   │             │              │  Integration│              │            │ │
│   └─────────────┘              └─────────────┘              └────────────┘ │
│                                                                              │
│   Problems:                                                                  │
│   • No reusable components                                                   │
│   • No standard data models                                                  │
│   • No centralized governance                                                │
│   • Manual data transformation                                               │
│   • No audit trail                                                           │
│   • 3-6 months per integration                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Technical Root Causes:**
- No integration platform or middleware
- No canonical data model for pharma manufacturing
- No API standardization
- No automated data quality checks
- No centralized security/access control


---

## Slide 4: The Real Challenge - Data Movement, Not Integration

**Title:** Customer Insight: Focus on Data Movement Automation

**Key Insight from Customer:**
> "The biggest challenge is not technical integration complexity, but **how to move data from CMOs to Merck efficiently and consistently**."

**Traditional Approach (What We're Avoiding):**
```
CMO contacts Merck → Merck IT creates custom integration → 3-6 months
```

**Our Approach (Self-Service):**
```
CMO receives URL → Self-service onboarding → Schema registration → 
Merck approves → Pipeline auto-deployed → CMO publishes data → < 1 week
```

**Core Components:**

1. **Data Contracts**
   - Formal agreement between CMO and Merck
   - Defines schema, quality expectations, SLAs
   - Stored in DynamoDB, versioned

2. **Schema Registry (Glue Schema Registry)**
   - Centralized repository for all CMO schemas
   - Version control (1.0, 1.1, 2.0)
   - Automatic validation

3. **Self-Service Onboarding Portal**
   - CMO registers via web UI
   - Selects pattern (1, 2, or 3)
   - Defines/uploads schema
   - Tests with sample data
   - Merck approves → Pipeline auto-deployed

4. **Automated Pipeline Activation**
   - Step Functions orchestrates deployment
   - Glue job created from template
   - Schema + mappings injected
   - Monitoring auto-configured
   - < 5 minutes to activate

**Result:** CMO onboarding time: 3-6 months → 30 minutes (self-service) + Merck approval

---

## Slide 5: Proposed Solution Architecture

**Title:** Hub-and-Spoke Architecture with Canonical Data Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                        CMO ECOSYSTEM (Spokes)                                │
│                                                                              │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│   │  CMO A   │  │  CMO B   │  │  CMO C   │  │  CMO D   │  │  CMO E   │    │
│   │Snowflake │  │  Oracle  │  │SQL Server│  │   SAP    │  │  Legacy  │    │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│        │             │             │             │             │           │
│        └─────────────┴─────────────┴─────────────┴─────────────┘           │
│                                    │                                        │
│                                    ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    INTEGRATION HUB (AWS)                              │  │
│  │                                                                       │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │  INGESTION LAYER                                               │  │  │
│  │  │  • Pattern 1: AWS Glue (Native Connectors)                     │  │  │
│  │  │  • Pattern 2: AWS Transfer Family (SFTP)                       │  │  │
│  │  │  • Pattern 3: AI Services (Textract, Rekognition, IoT Core)   │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │                              ▼                                        │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │  DATA LAKE (S3 + Lake Formation)                               │  │  │
│  │  │  • Bronze: Raw data (immutable)                                │  │  │
│  │  │  • Silver: Validated & standardized (canonical model)          │  │  │
│  │  │  • Gold: Business-ready aggregates                             │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │                              ▼                                        │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │  PROCESSING & ANALYTICS                                        │  │  │
│  │  │  • Glue ETL (data transformation)                              │  │  │
│  │  │  • Athena (SQL queries)                                        │  │  │
│  │  │  • Bedrock (Gen AI / RAG)                                      │  │  │
│  │  │  • QuickSight (visualization)                                  │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  │                              ▼                                        │  │
│  │  ┌────────────────────────────────────────────────────────────────┐  │  │
│  │  │  GOVERNANCE & SECURITY                                         │  │  │
│  │  │  • Lake Formation (access control)                             │  │  │
│  │  │  • Glue Data Catalog (metadata)                                │  │  │
│  │  │  • Glue Data Quality (validation)                              │  │  │
│  │  │  • KMS (encryption)                                            │  │  │
│  │  │  • CloudTrail (audit)                                          │  │  │
│  │  └────────────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    MERCK SYSTEMS (Consumers)                          │  │
│  │  • ERP / QMS / LIMS (via APIs)                                        │  │
│  │  • Data Warehouse / Analytics                                         │  │
│  │  • Business Intelligence Tools                                        │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Architecture Principles:**
- Decoupled integration (hub isolates CMOs from Merck systems)
- Canonical data model (consistent regardless of source)
- Multi-tenancy (isolated per CMO with shared infrastructure)
- Event-driven processing (real-time and batch)
- Immutable data lake (audit trail preserved)

---

## Slide 5: Self-Service CMO Onboarding Flow

**Title:** Automated Onboarding: 30 Minutes vs. 3-6 Months

**Onboarding Flow:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   STEP 1: CMO RECEIVES INVITATION (Merck sends)                             │
│   • Email with onboarding URL: https://cmo-onboarding.merck.com/register    │
│   • Unique token for authentication                                         │
│                                                                              │
│   STEP 2: CMO SELF-SERVICE REGISTRATION (15 minutes)                        │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │ a) Basic Info: CMO name, contact, authentication                     │  │
│   │ b) Pattern Selection: Choose Pattern 1, 2, or 3                      │  │
│   │ c) Schema Definition:                                                 │  │
│   │    • Upload sample data (auto-infer schema) OR                        │  │
│   │    • Select from standard templates (batch, quality, materials)      │  │
│   │    • Edit schema in visual editor                                     │  │
│   │ d) Field Mapping: Map CMO fields → Canonical model                   │  │
│   │    Example: CMO "lot_number" → Merck "batch_id"                      │  │
│   │ e) Connection Config:                                                 │  │
│   │    • Pattern 1: Database connection string                            │  │
│   │    • Pattern 2: SFTP credentials auto-generated                       │  │
│   │    • Pattern 3: S3 upload URL auto-generated                          │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   STEP 3: TEST & VALIDATE (10 minutes)                                      │
│   • CMO uploads test data                                                   │
│   • System validates against schema                                         │
│   • Real-time feedback on errors                                            │
│   • Data quality score displayed                                            │
│                                                                              │
│   STEP 4: MERCK APPROVAL (5 minutes)                                        │
│   • Merck receives notification                                             │
│   • Reviews data contract and test results                                  │
│   • One-click approval                                                      │
│                                                                              │
│   STEP 5: AUTOMATED PIPELINE ACTIVATION (< 5 minutes)                       │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │ Step Functions Workflow (fully automated):                            │  │
│   │ 1. Create S3 bucket prefix for CMO                                    │  │
│   │ 2. Register schema in Glue Schema Registry                            │  │
│   │ 3. Create data contract in DynamoDB                                   │  │
│   │ 4. Deploy Glue job from template (with CMO config)                    │  │
│   │ 5. Configure Transfer Family (if SFTP)                                │  │
│   │ 6. Setup monitoring dashboard                                         │  │
│   │ 7. Send confirmation email to CMO                                     │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   STEP 6: CMO PUBLISHES DATA (Ongoing)                                      │
│   • CMO starts sending data via selected pattern                            │
│   • Automatic validation on arrival                                         │
│   • Data flows: Bronze → Silver → Gold                                      │
│   • Merck can query immediately                                             │
│                                                                              │
│   TOTAL TIME: 30 minutes (CMO) + 5 minutes (Merck) = 35 minutes             │
│   vs. Current: 3-6 months                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Enablers:**

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Onboarding Portal** | React + Amplify | CMO-facing UI |
| **Schema Registry** | Glue Schema Registry | Schema versioning & validation |
| **Data Contracts** | DynamoDB | Store agreements & mappings |
| **Pipeline Templates** | Glue job templates | Reusable ETL code |
| **Orchestration** | Step Functions | Automated deployment |
| **IaC** | CloudFormation/CDK | Infrastructure provisioning |

---

## Slide 6: Data Contract Architecture

**Title:** Formal Agreements for Data Movement

**What is a Data Contract?**

A formal, machine-readable agreement between CMO (producer) and Merck (consumer) that defines:
- **Schema:** Fields, types, constraints
- **Quality:** Completeness, accuracy, uniqueness
- **Delivery:** Frequency, format, schedule
- **SLA:** Latency, availability targets
- **Versioning:** How schema evolves

**Example Data Contract (YAML):**

```yaml
data_contract:
  version: "1.0"
  cmo_id: "cmo-alpha"
  data_domain: "batch-manufacturing"
  
  schema:
    fields:
      - name: batch_id
        type: string
        required: true
        unique: true
        
      - name: product_code
        type: string
        required: true
        pattern: "^[A-Z]{3}-[0-9]{4}$"
        
      - name: yield_percentage
        type: decimal
        required: true
        min: 0
        max: 100
  
  data_quality:
    completeness: 100%
    uniqueness: [batch_id]
    timeliness: "< 24 hours"
    accuracy: "> 95% pass rate"
  
  delivery:
    frequency: "daily"
    schedule: "02:00 UTC"
    format: "parquet"
  
  sla:
    availability: "99.5%"
    max_latency: "2 hours"
    
  mapping:
    # CMO field → Canonical field
    lot_number: batch_id
    prod_code: product_code
    yield_pct: yield_percentage
```

**Data Contract Storage & Usage:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   DynamoDB Table: data-contracts                                            │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │ PK: cmo-alpha#batch-manufacturing                                     │  │
│   │ SK: v1.0                                                              │  │
│   │ contract: { ... full contract ... }                                   │  │
│   │ status: active                                                        │  │
│   │ created_at: 2026-02-16T10:00:00Z                                      │  │
│   │ approved_by: john.doe@merck.com                                       │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    │ Referenced by                          │
│                                    ▼                                        │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │ Glue Job: cmo-alpha-batch-manufacturing-etl                           │  │
│   │ • Reads contract from DynamoDB                                        │  │
│   │ • Applies field mappings                                              │  │
│   │ • Validates data quality rules                                        │  │
│   │ • Enforces SLA targets                                                │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Benefits:**

1. **Clarity:** Both parties know exactly what to expect
2. **Automation:** Machine-readable enables automated validation
3. **Versioning:** Track changes over time
4. **Governance:** Centralized repository of all agreements
5. **Accountability:** SLAs define success criteria

---

## Slide 7: Schema Registry & Validation

**Title:** Centralized Schema Management with Glue Schema Registry

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   GLUE SCHEMA REGISTRY                                                      │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │ Registry: merck-cmo-schemas                                           │  │
│   │                                                                       │  │
│   │ Schema: batch-manufacturing                                           │  │
│   │ ├── v1.0 (2024-01-15) - Initial release                              │  │
│   │ ├── v1.1 (2024-03-20) - Added yield_percentage (backward compatible) │  │
│   │ └── v2.0 (2024-06-10) - Renamed fields (breaking change)             │  │
│   │                                                                       │  │
│   │ Schema: quality-control                                               │  │
│   │ ├── v1.0 (2024-01-15) - Initial release                              │  │
│   │ └── v1.1 (2024-04-01) - Added test_method (backward compatible)      │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    │ Validation                             │
│                                    ▼                                        │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │ VALIDATION LAYER (Lambda)                                             │  │
│   │                                                                       │  │
│   │ When data arrives:                                                    │  │
│   │ 1. Retrieve schema from registry (by version)                         │  │
│   │ 2. Validate data structure (fields, types)                            │  │
│   │ 3. Check constraints (required, unique, range)                        │  │
│   │ 4. Apply data quality rules (from contract)                           │  │
│   │ 5. Calculate quality score (0-100)                                    │  │
│   │                                                                       │  │
│   │ If valid (score > 95):                                                │  │
│   │   → Bronze layer → Silver layer                                       │  │
│   │                                                                       │  │
│   │ If invalid (score < 95):                                              │  │
│   │   → Quarantine bucket                                                 │  │
│   │   → Alert CMO via email                                               │  │
│   │   → Create ticket in portal                                           │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Schema Evolution Strategy:**

| Change Type | Version Bump | Backward Compatible? | Action |
|-------------|--------------|---------------------|--------|
| **Add optional field** | Minor (1.0 → 1.1) | Yes | Auto-deploy |
| **Add required field** | Major (1.0 → 2.0) | No | Requires CMO update |
| **Rename field** | Major (1.0 → 2.0) | No | Requires CMO update |
| **Change type** | Major (1.0 → 2.0) | No | Requires CMO update |
| **Remove field** | Major (1.0 → 2.0) | No | Requires CMO update |

**Validation Example:**

```python
# Lambda function: validate-cmo-data

import boto3
import json

glue_client = boto3.client('glue')
dynamodb = boto3.resource('dynamodb')

def lambda_handler(event, context):
    # Extract CMO ID and data domain from S3 event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    
    # Parse: s3://bucket/bronze/cmo-alpha/batch-manufacturing/file.parquet
    cmo_id = key.split('/')[1]
    data_domain = key.split('/')[2]
    
    # Retrieve schema from Glue Schema Registry
    schema = glue_client.get_schema_version(
        SchemaId={'RegistryName': 'merck-cmo-schemas', 
                  'SchemaName': data_domain},
        SchemaVersionNumber={'LatestVersion': True}
    )
    
    # Retrieve data contract from DynamoDB
    contracts_table = dynamodb.Table('data-contracts')
    contract = contracts_table.get_item(
        Key={'pk': f"{cmo_id}#{data_domain}", 'sk': schema['VersionNumber']}
    )
    
    # Read data from S3
    df = spark.read.parquet(f"s3://{bucket}/{key}")
    
    # Validate against schema
    validation_results = validate_schema(df, schema)
    
    # Apply data quality rules from contract
    quality_score = apply_quality_rules(df, contract['data_quality'])
    
    if quality_score >= 95:
        # Move to Silver layer
        move_to_silver(df, cmo_id, data_domain)
        return {'status': 'success', 'quality_score': quality_score}
    else:
        # Move to quarantine
        move_to_quarantine(df, cmo_id, data_domain)
        alert_cmo(cmo_id, validation_results)
        return {'status': 'quarantine', 'quality_score': quality_score}
```

---

## Slide 8: Proposed Solution Architecture

**Title:** Direct Integration via AWS Glue Connectors

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   CMO Data Source                                                            │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  Snowflake / Databricks / Oracle / SQL Server / SAP                  │  │
│   └────────────────────────────────────────┬─────────────────────────────┘  │
│                                             │                                │
│                                             │ JDBC/ODBC/Native API           │
│                                             ▼                                │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  AWS GLUE CONNECTOR                                                   │  │
│   │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐         │  │
│   │  │ Connection     │  │ Crawler        │  │ ETL Job        │         │  │
│   │  │ (credentials   │  │ (schema        │  │ (extract &     │         │  │
│   │  │  in Secrets    │  │  discovery)    │  │  transform)    │         │  │
│   │  │  Manager)      │  │                │  │                │         │  │
│   │  └────────────────┘  └────────────────┘  └────────────────┘         │  │
│   └──────────────────────────────────────────┬───────────────────────────┘  │
│                                               │                              │
│                                               ▼                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  DATA LAKE (S3)                                                       │  │
│   │  s3://merck-cmo-hub/bronze/cmo-alpha/batch-records/                  │  │
│   │  • Partitioned by: CMO / data-type / year / month / day              │  │
│   │  • Format: Parquet (columnar, compressed)                            │  │
│   │  • Metadata: Glue Data Catalog                                       │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Technical Details:**

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Connectivity** | AWS Glue JDBC/Native Connectors | Direct database/warehouse access |
| **Credentials** | AWS Secrets Manager | Secure credential storage, rotation |
| **Schema Discovery** | Glue Crawler | Automatic schema inference |
| **Data Extraction** | Glue ETL (PySpark) | Scalable data extraction |
| **Incremental Load** | Glue Job Bookmarks | Track processed data |
| **Data Catalog** | Glue Data Catalog | Centralized metadata repository |

**Supported Platforms:**
- Cloud DW: Snowflake, Databricks, BigQuery, Redshift, Synapse
- RDBMS: Oracle, SQL Server, MySQL, PostgreSQL, MariaDB
- NoSQL: MongoDB, Cassandra, DynamoDB
- SaaS: SAP (via AppFlow), Salesforce, ServiceNow

**Performance:**
- Parallel extraction (auto-scaling Glue workers)
- Predicate pushdown (filter at source)
- Columnar format (Parquet) for efficient storage/query


---

## Slide 6: Pattern 2 - Secure File Transfer (Technical)

**Title:** Universal SFTP Integration for Any System

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   CMO On-Prem / Legacy System                                               │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  Any system capable of file export (CSV, XML, JSON, PDF)             │  │
│   └────────────────────────────────────────┬─────────────────────────────┘  │
│                                             │                                │
│                                             │ SFTP/FTPS (TLS 1.2+)           │
│                                             ▼                                │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  AWS TRANSFER FAMILY (Managed SFTP)                                   │  │
│   │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐         │  │
│   │  │ SFTP Endpoint  │  │ Authentication │  │ S3 Integration │         │  │
│   │  │ (VPC or public)│  │ (IAM / AD /    │  │ (direct write) │         │  │
│   │  │                │  │  custom)       │  │                │         │  │
│   │  └────────────────┘  └────────────────┘  └────────────────┘         │  │
│   └──────────────────────────────────────────┬───────────────────────────┘  │
│                                               │                              │
│                                               ▼                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  S3 LANDING ZONE                                                      │  │
│   │  s3://merck-cmo-hub/landing/cmo-beta/                                │  │
│   │  • Per-CMO prefix isolation                                          │  │
│   │  • S3 Event Notifications → Lambda                                   │  │
│   └──────────────────────────────────────────┬───────────────────────────┘  │
│                                               │                              │
│                                               ▼                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  AUTOMATED PROCESSING PIPELINE                                        │  │
│   │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐         │  │
│   │  │ Lambda         │  │ Glue ETL       │  │ Data Quality   │         │  │
│   │  │ (file          │  │ (parse &       │  │ (validation)   │         │  │
│   │  │  validation)   │  │  transform)    │  │                │         │  │
│   │  └────────────────┘  └────────────────┘  └────────────────┘         │  │
│   └──────────────────────────────────────────┬───────────────────────────┘  │
│                                               │                              │
│                                               ▼                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  DATA LAKE (S3 Bronze)                                                │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Technical Details:**

| Component | Technology | Purpose |
|-----------|------------|---------|
| **SFTP Server** | AWS Transfer Family | Fully managed SFTP/FTPS/FTP |
| **Authentication** | IAM, Active Directory, Custom | Flexible auth integration |
| **Network** | VPC Endpoint or Public | Private or internet-facing |
| **File Validation** | Lambda + S3 Events | Real-time file validation |
| **Parsing** | Glue ETL (PySpark) | CSV/XML/JSON parsing |
| **Error Handling** | SQS Dead Letter Queue | Failed file processing |

**Supported File Formats:**
- Structured: CSV, TSV, JSON, XML, Parquet
- Unstructured: PDF, DOCX, images (routed to Pattern 3)
- Compressed: ZIP, GZIP, BZIP2 (auto-decompression)

**Operational Features:**
- Automatic file archival (S3 Glacier after 90 days)
- File integrity checks (MD5/SHA256)
- Idempotency (duplicate detection)
- Retry logic with exponential backoff

---

## Slide 7: Pattern 3 - Unstructured Data AI (Technical)

**Title:** AI-Powered Document & Image Processing

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   Unstructured Data Sources                                                 │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                     │
│   │ PDF Docs     │  │ Images       │  │ IoT Sensors  │                     │
│   │ (CoA, batch  │  │ (visual QC,  │  │ (temp, RH,   │                     │
│   │  records)    │  │  labels)     │  │  pressure)   │                     │
│   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                     │
│          │                 │                 │                              │
│          │ S3 Upload       │ S3 Upload       │ MQTT/HTTPS                   │
│          ▼                 ▼                 ▼                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  S3 UNSTRUCTURED DATA BUCKET                                          │  │
│   │  • Event-driven processing (S3 → EventBridge → Lambda)               │  │
│   └──────────────────────────────────────────┬───────────────────────────┘  │
│                                               │                              │
│          ┌────────────────────────────────────┼────────────────────────┐     │
│          │                                    │                        │     │
│          ▼                                    ▼                        ▼     │
│   ┌──────────────┐                    ┌──────────────┐        ┌──────────┐  │
│   │  TEXTRACT    │                    │ REKOGNITION  │        │ IOT CORE │  │
│   │              │                    │              │        │          │  │
│   │ • OCR        │                    │ • Object     │        │ • Rules  │  │
│   │ • Forms      │                    │   detection  │        │ • Actions│  │
│   │ • Tables     │                    │ • Custom     │        │          │  │
│   │ • Key-value  │                    │   labels     │        │          │  │
│   │   pairs      │                    │ • Defect     │        │          │  │
│   │              │                    │   detection  │        │          │  │
│   └──────┬───────┘                    └──────┬───────┘        └────┬─────┘  │
│          │                                   │                     │        │
│          └───────────────────┬───────────────┘                     │        │
│                              ▼                                     ▼        │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  STRUCTURED OUTPUT                                                    │  │
│   │  • JSON metadata                                                      │  │
│   │  • Extracted entities                                                 │  │
│   │  • Confidence scores                                                  │  │
│   └──────────────────────────────────────────┬───────────────────────────┘  │
│                                               │                              │
│                                               ▼                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  DATA LAKE (S3 Silver)                                                │  │
│   │  • Original files preserved in Bronze                                 │  │
│   │  • Extracted structured data in Silver                                │  │
│   │  • Indexed in OpenSearch for full-text search                         │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Technical Details:**

| Data Type | AWS Service | Extraction Capability |
|-----------|-------------|----------------------|
| **PDF Documents** | Textract | Forms, tables, key-value pairs, OCR |
| **Images** | Rekognition | Object detection, custom labels, defect detection |
| **Text** | Comprehend | Entity recognition, sentiment, PII detection |
| **IoT Sensors** | IoT Core + Timestream | Real-time ingestion, time-series storage |

**AI Processing Pipeline:**
1. File uploaded to S3 → EventBridge rule triggers Lambda
2. Lambda invokes Textract/Rekognition (async for large files)
3. Results stored as JSON in S3 Silver layer
4. Glue ETL normalizes to canonical schema
5. OpenSearch indexes for full-text search
6. Bedrock RAG enables natural language queries

**Performance & Cost:**
- Async processing for large documents (>1000 pages)
- Batch processing for cost optimization
- Caching of frequently accessed results
- Confidence thresholds for human review


---

## Slide 8: Data Architecture & Canonical Model

**Title:** Medallion Architecture with Pharma-Specific Data Model

**Data Lake Layers:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   BRONZE LAYER (Raw / Immutable)                                            │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  • Exact copy of source data (no transformation)                      │  │
│   │  • Partitioned by: CMO / source-system / date                        │  │
│   │  • Retention: 7 years (GxP compliance)                               │  │
│   │  • Format: Original (CSV, JSON, Parquet)                             │  │
│   │  • Immutable (S3 Object Lock - WORM)                                 │  │
│   │                                                                       │  │
│   │  s3://merck-cmo-hub/bronze/cmo-alpha/erp/2026/02/16/batch-001.json  │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼ Glue ETL                               │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │   SILVER LAYER (Validated / Standardized)                            │  │
│   │  • Canonical pharma data model (CDISC, HL7 FHIR concepts)           │  │
│   │  • Data quality checks applied                                       │  │
│   │  • Schema enforcement                                                │  │
│   │  • Partitioned by: data-domain / CMO / date                          │  │
│   │  • Format: Parquet (columnar, Snappy compression)                    │  │
│   │                                                                       │  │
│   │  Domains:                                                             │  │
│   │  • batch-manufacturing (batch ID, product, dates, yields)            │  │
│   │  • quality-control (test results, specifications, deviations)        │  │
│   │  • materials (raw materials, lot numbers, suppliers)                 │  │
│   │  • equipment (equipment ID, maintenance, calibration)                │  │
│   │  • environmental (temp, humidity, pressure, cleanroom class)         │  │
│   │  • documents (CoA, batch records, deviations, CAPAs)                 │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼ Glue ETL                               │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │   GOLD LAYER (Business-Ready / Aggregated)                           │  │
│   │  • Pre-aggregated metrics                                            │  │
│   │  • Cross-CMO analytics                                               │  │
│   │  • Optimized for BI tools                                            │  │
│   │  • Partitioned by: metric-type / time-period                         │  │
│   │                                                                       │  │
│   │  Examples:                                                            │  │
│   │  • cmo-performance-scorecard (OEE, yield, quality by CMO)            │  │
│   │  • deviation-trends (by type, CMO, product)                          │  │
│   │  • material-traceability (end-to-end supply chain)                   │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Canonical Data Model - Example (Batch Manufacturing):**

```json
{
  "batch_id": "string (unique)",
  "cmo_id": "string",
  "product_code": "string",
  "product_name": "string",
  "manufacturing_start_date": "ISO 8601 datetime",
  "manufacturing_end_date": "ISO 8601 datetime",
  "batch_size": {
    "value": "decimal",
    "unit": "string (kg, L, units)"
  },
  "yield": {
    "actual": "decimal",
    "theoretical": "decimal",
    "percentage": "decimal"
  },
  "quality_status": "enum (released, quarantine, rejected)",
  "deviations": [
    {
      "deviation_id": "string",
      "type": "string",
      "severity": "enum (critical, major, minor)",
      "description": "string"
    }
  ],
  "metadata": {
    "source_system": "string",
    "ingestion_timestamp": "ISO 8601 datetime",
    "data_quality_score": "decimal (0-100)"
  }
}
```

**Data Governance:**
- Glue Data Catalog: Central metadata repository
- Lake Formation: Fine-grained access control (column/row level)
- Glue Data Quality: Automated validation rules
- Data lineage: Track data from source to consumption

---

## Slide 9: Security Architecture

**Title:** Defense-in-Depth Security Model

**Multi-Layer Security:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   LAYER 1: NETWORK SECURITY                                                 │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  • VPC with private subnets (no internet gateway for data processing)│  │
│   │  • VPC Endpoints (S3, Glue, Secrets Manager - no internet traffic)   │  │
│   │  • Security Groups (least privilege, port restrictions)              │  │
│   │  • NACLs (network-level filtering)                                   │  │
│   │  • AWS PrivateLink (CMO private connectivity option)                 │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   LAYER 2: IDENTITY & ACCESS                                                │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  • IAM Identity Center (SSO with Merck AD/Okta)                      │  │
│   │  • IAM Roles (no long-term credentials)                              │  │
│   │  • Attribute-Based Access Control (ABAC) - tag-based permissions    │  │
│   │  • Service Control Policies (SCP) - organization-wide guardrails    │  │
│   │  • MFA required for all human access                                │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   LAYER 3: DATA PROTECTION                                                  │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  • Encryption at rest (S3, EBS, RDS) - KMS customer-managed keys    │  │
│   │  • Encryption in transit (TLS 1.2+ everywhere)                       │  │
│   │  • Per-CMO encryption keys (key isolation)                           │  │
│   │  • S3 Object Lock (WORM - immutable audit trail)                    │  │
│   │  • S3 Bucket Keys (cost-optimized encryption)                        │  │
│   │  • Macie (PII/PHI detection and alerting)                            │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   LAYER 4: DATA GOVERNANCE                                                  │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  • Lake Formation (column/row-level access control)                  │  │
│   │  • Glue Data Catalog (centralized metadata + permissions)            │  │
│   │  • Resource tags (CMO, data-classification, compliance-scope)        │  │
│   │  • Data masking (PII/PHI redaction for non-privileged users)         │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   LAYER 5: MONITORING & AUDIT                                               │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  • CloudTrail (all API calls logged, immutable)                      │  │
│   │  • CloudWatch Logs (application logs, 90-day retention)              │  │
│   │  • Security Hub (centralized security findings)                      │  │
│   │  • GuardDuty (threat detection)                                      │  │
│   │  • Config (compliance monitoring, resource inventory)                │  │
│   │  • Audit Manager (21 CFR Part 11 compliance framework)               │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   LAYER 6: INCIDENT RESPONSE                                                │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  • EventBridge (real-time security event routing)                    │  │
│   │  • SNS (security team notifications)                                 │  │
│   │  • Lambda (automated remediation)                                    │  │
│   │  • S3 Versioning (data recovery)                                     │  │
│   │  • Backup (automated backups to separate account)                    │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Multi-Account Strategy:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  AWS ORGANIZATION                                                            │
│                                                                              │
│  ┌────────────────────┐                                                     │
│  │ Management Account │  (Billing, SCPs, no workloads)                      │
│  └──────────┬─────────┘                                                     │
│             │                                                                │
│    ┌────────┴────────┬────────────┬────────────┬────────────┐              │
│    │                 │            │            │            │              │
│    ▼                 ▼            ▼            ▼            ▼              │
│  ┌──────┐  ┌──────────────┐  ┌────────┐  ┌────────┐  ┌──────────┐        │
│  │ Dev  │  │ Prod (Hub)   │  │ CMO-A  │  │ CMO-B  │  │ Security │        │
│  │      │  │ (shared infra│  │ (data  │  │ (data  │  │ Tooling  │        │
│  │      │  │  + processing│  │  only) │  │  only) │  │          │        │
│  └──────┘  └──────────────┘  └────────┘  └────────┘  └──────────┘        │
│                                                                              │
│  • Per-CMO accounts for data isolation (optional for high-security CMOs)   │
│  • Cross-account access via IAM roles (no credentials sharing)             │
│  • Centralized logging to Security account                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Compliance Alignment:**
- 21 CFR Part 11 (electronic records/signatures)
- GxP (Good Manufacturing Practice)
- GDPR (if EU CMOs involved)
- SOC 2 Type II (AWS services certified)
- ISO 27001 (AWS services certified)


---

## Slide 10: Scalability & Performance Architecture

**Title:** Auto-Scaling, Serverless, and Performance Optimization

**Scalability Design:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   COMPUTE SCALABILITY                                                        │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  AWS Glue (Serverless ETL)                                            │  │
│   │  • Auto-scaling workers (2 to 100+ DPUs)                             │  │
│   │  • Pay per second of execution                                        │  │
│   │  • Automatic retry on failure                                         │  │
│   │  • Concurrent job execution (up to 1000 jobs)                        │  │
│   │                                                                       │  │
│   │  Lambda (Event Processing)                                            │  │
│   │  • Auto-scaling (0 to 1000+ concurrent executions)                   │  │
│   │  • Sub-second response time                                           │  │
│   │  • Reserved concurrency for critical functions                        │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   STORAGE SCALABILITY                                                        │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  S3 (Data Lake)                                                       │  │
│   │  • Unlimited storage capacity                                         │  │
│   │  • 5,500 GET/3,500 PUT requests per second per prefix               │  │
│   │  • Intelligent-Tiering (auto cost optimization)                      │  │
│   │  • S3 Transfer Acceleration (global uploads)                          │  │
│   │                                                                       │  │
│   │  OpenSearch (Full-Text Search)                                        │  │
│   │  • Auto-scaling nodes (3 to 100+ nodes)                              │  │
│   │  • Read replicas for query performance                                │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   QUERY PERFORMANCE                                                          │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  Athena (SQL Queries)                                                 │  │
│   │  • Serverless, auto-scaling                                           │  │
│   │  • Columnar format (Parquet) - 10x faster than CSV                   │  │
│   │  • Partition pruning (query only relevant data)                      │  │
│   │  • Result caching (repeated queries instant)                          │  │
│   │                                                                       │  │
│   │  QuickSight (BI / Dashboards)                                         │  │
│   │  • SPICE in-memory engine (sub-second queries)                       │  │
│   │  • Auto-scaling capacity                                              │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Performance Benchmarks (Estimated):**

| Workload | Volume | Performance Target | AWS Service |
|----------|--------|-------------------|-------------|
| **Batch ingestion** | 1 TB/day per CMO | < 2 hours | Glue (50 DPUs) |
| **Real-time file processing** | 1000 files/hour | < 5 min per file | Lambda + Glue |
| **SQL queries (Athena)** | 100 GB scan | < 10 seconds | Athena (Parquet) |
| **Document AI (Textract)** | 1000 pages/hour | < 30 sec per doc | Textract async |
| **Gen AI queries (Bedrock)** | 100 queries/min | < 3 seconds | Bedrock (Claude) |
| **Dashboard refresh** | 10 GB dataset | < 5 seconds | QuickSight SPICE |

**Cost Optimization Strategies:**
- S3 Intelligent-Tiering (auto-move to cheaper storage)
- Glue job bookmarks (incremental processing only)
- Athena result caching (avoid re-scanning data)
- Spot instances for non-critical Glue jobs (70% cost savings)
- Reserved capacity for predictable workloads

---

## Slide 11: Operational Model & DevOps

**Title:** Infrastructure as Code & CI/CD Pipeline

**DevOps Architecture:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   SOURCE CONTROL                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  Git Repository (GitHub / GitLab / CodeCommit)                        │  │
│   │  • Infrastructure code (Terraform / CDK)                              │  │
│   │  • Glue ETL scripts (PySpark)                                         │  │
│   │  • Lambda functions (Python)                                          │  │
│   │  • Configuration files (YAML)                                         │  │
│   └────────────────────────────────────┬─────────────────────────────────┘  │
│                                         │                                    │
│                                         ▼ Git Push                           │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  CI/CD PIPELINE (CodePipeline / GitHub Actions)                      │  │
│   │                                                                       │  │
│   │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐    │  │
│   │  │ 1. Build   │→ │ 2. Test    │→ │ 3. Deploy  │→ │ 4. Verify  │    │  │
│   │  │            │  │            │  │   (Dev)    │  │            │    │  │
│   │  │ • Lint     │  │ • Unit     │  │            │  │ • Smoke    │    │  │
│   │  │ • Package  │  │ • Integration│ │            │  │   tests    │    │  │
│   │  └────────────┘  └────────────┘  └────────────┘  └────────────┘    │  │
│   │                                         │                             │  │
│   │                                         ▼ Manual Approval             │  │
│   │  ┌────────────┐  ┌────────────┐                                      │  │
│   │  │ 5. Deploy  │→ │ 6. Verify  │                                      │  │
│   │  │   (Prod)   │  │            │                                      │  │
│   │  │            │  │ • Smoke    │                                      │  │
│   │  │            │  │   tests    │                                      │  │
│   │  └────────────┘  └────────────┘                                      │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   INFRASTRUCTURE AS CODE                                                     │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  AWS CDK (TypeScript) or Terraform                                    │  │
│   │  • Declarative infrastructure definition                              │  │
│   │  • Version controlled                                                 │  │
│   │  • Automated drift detection                                          │  │
│   │  • Multi-environment (dev, test, prod)                               │  │
│   │                                                                       │  │
│   │  Example structure:                                                   │  │
│   │  ├── stacks/                                                          │  │
│   │  │   ├── network-stack.ts      (VPC, subnets, endpoints)            │  │
│   │  │   ├── data-lake-stack.ts    (S3, Lake Formation)                 │  │
│   │  │   ├── ingestion-stack.ts    (Glue, Transfer Family)              │  │
│   │  │   ├── processing-stack.ts   (Lambda, Step Functions)             │  │
│   │  │   └── security-stack.ts     (KMS, IAM, CloudTrail)               │  │
│   │  ├── config/                                                          │  │
│   │  │   ├── dev.yaml                                                    │  │
│   │  │   └── prod.yaml                                                   │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│   MONITORING & OBSERVABILITY                                                │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  CloudWatch (Metrics, Logs, Alarms)                                   │  │
│   │  • Custom dashboards per CMO                                          │  │
│   │  • Automated alerting (SNS → PagerDuty / Slack)                      │  │
│   │  • Log aggregation and analysis                                       │  │
│   │                                                                       │  │
│   │  X-Ray (Distributed Tracing)                                          │  │
│   │  • End-to-end request tracing                                         │  │
│   │  • Performance bottleneck identification                              │  │
│   │                                                                       │  │
│   │  AWS Health Dashboard                                                 │  │
│   │  • Service health monitoring                                          │  │
│   │  • Proactive notifications                                            │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Operational Runbooks:**
- CMO onboarding (automated via CDK/Terraform)
- Incident response procedures
- Disaster recovery playbooks
- Performance tuning guides
- Cost optimization reviews (monthly)

**SLA Targets:**

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Availability** | 99.9% | CloudWatch uptime |
| **Data ingestion latency** | < 2 hours (batch) | Custom metric |
| **Query response time** | < 10 seconds (p95) | Athena metrics |
| **Incident response** | < 15 min (critical) | PagerDuty |
| **Data quality** | > 95% pass rate | Glue Data Quality |


---

## Slide 12: Integration with Existing Merck Systems

**Title:** API-First Integration Strategy

**Integration Architecture:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   PHARMA DATA EXCHANGE HUB (AWS)                                            │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  Data Lake (S3 + Lake Formation)                                      │  │
│   └────────────────────────────────────┬─────────────────────────────────┘  │
│                                         │                                    │
│                                         ▼                                    │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  API GATEWAY (REST / GraphQL)                                         │  │
│   │  • Authentication (IAM, Cognito, API Keys)                            │  │
│   │  • Rate limiting (per consumer)                                       │  │
│   │  • Request/response transformation                                    │  │
│   │  • API versioning (v1, v2)                                            │  │
│   └────────────────────────────────────┬─────────────────────────────────┘  │
│                                         │                                    │
│          ┌──────────────────────────────┼──────────────────────────────┐     │
│          │                              │                              │     │
│          ▼                              ▼                              ▼     │
│   ┌──────────────┐              ┌──────────────┐              ┌──────────┐  │
│   │  Lambda      │              │  Lambda      │              │ Lambda   │  │
│   │  (Query)     │              │  (Batch)     │              │ (Stream) │  │
│   │              │              │              │              │          │  │
│   │ • Athena SQL │              │ • S3 Select  │              │ • Kinesis│  │
│   │ • Real-time  │              │ • Bulk export│              │ • Events │  │
│   └──────────────┘              └──────────────┘              └──────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTPS / VPC PrivateLink
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   MERCK ENTERPRISE SYSTEMS                                                  │
│                                                                              │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│   │  ERP         │  │  QMS         │  │  LIMS        │  │  Data        │  │
│   │  (SAP)       │  │  (Veeva)     │  │  (LabWare)   │  │  Warehouse   │  │
│   │              │  │              │  │              │  │  (Snowflake) │  │
│   │ • Batch data │  │ • Deviations │  │ • Test       │  │ • Analytics  │  │
│   │ • Materials  │  │ • CAPAs      │  │   results    │  │ • BI         │  │
│   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**API Patterns:**

| API Type | Use Case | Technology | Example |
|----------|----------|------------|---------|
| **REST API** | Synchronous queries | API Gateway + Lambda | GET /batches/{id} |
| **GraphQL** | Flexible queries | AppSync | Query specific fields only |
| **Batch Export** | Bulk data transfer | S3 + Presigned URLs | Download 1M records |
| **Event Stream** | Real-time updates | EventBridge + Kinesis | New batch notification |
| **Webhook** | Push notifications | API Gateway + SNS | Deviation alert |

**API Examples:**

```
GET /api/v1/cmos/{cmo-id}/batches
  → Returns list of batches for a CMO

GET /api/v1/batches/{batch-id}
  → Returns detailed batch information

GET /api/v1/batches/{batch-id}/quality-results
  → Returns quality test results for a batch

GET /api/v1/cmos/{cmo-id}/deviations?status=open
  → Returns open deviations for a CMO

POST /api/v1/query
  Body: { "sql": "SELECT * FROM batches WHERE yield < 90" }
  → Execute custom SQL query (authorized users only)

GET /api/v1/documents/{document-id}/download
  → Download original document (PDF, image)

POST /api/v1/ai/query
  Body: { "question": "What was the yield for batch X?" }
  → Natural language query via Bedrock
```

**Integration Patterns:**

1. **Pull (Merck systems query hub):**
   - Scheduled batch jobs (nightly ETL)
   - On-demand queries (user-initiated)
   - API polling (every 5 minutes)

2. **Push (Hub notifies Merck systems):**
   - EventBridge rules → SNS → Merck webhook
   - Real-time alerts (deviations, quality failures)
   - Data availability notifications

3. **Hybrid:**
   - Hub publishes events to EventBridge
   - Merck systems subscribe to relevant events
   - Merck systems query hub for details

**Authentication & Authorization:**
- IAM roles for service-to-service (no credentials)
- API keys for external systems (rotated quarterly)
- OAuth 2.0 for user-facing applications
- Fine-grained permissions (per CMO, per data domain)

---

## Slide 13: Technology Stack & Service Selection

**Title:** AWS Service Selection Rationale

**Core Services:**

| Service | Purpose | Why Selected | Alternatives Considered |
|---------|---------|--------------|------------------------|
| **S3** | Data lake storage | Industry standard, unlimited scale, 99.999999999% durability | Azure Blob, GCS |
| **Glue** | ETL & data catalog | Serverless, 20+ connectors, integrated with Lake Formation | Databricks, Informatica |
| **Transfer Family** | SFTP server | Fully managed, scales automatically, S3 integration | Self-managed SFTP on EC2 |
| **Lake Formation** | Data governance | Fine-grained access control, centralized permissions | Custom IAM policies |
| **Athena** | SQL queries | Serverless, pay-per-query, Presto-based | Redshift, Snowflake |
| **Textract** | Document AI | Best-in-class OCR, forms/tables extraction | Google Document AI, Azure Form Recognizer |
| **Rekognition** | Image AI | Custom labels, defect detection | Google Vision AI, Azure Computer Vision |
| **Bedrock** | Generative AI | Multiple models (Claude, Titan), enterprise guardrails | OpenAI, Azure OpenAI |
| **Lambda** | Event processing | Serverless, auto-scaling, sub-second response | Fargate, ECS |
| **EventBridge** | Event routing | Decoupled architecture, 100+ AWS integrations | SNS/SQS, Kafka |
| **CloudTrail** | Audit logging | Immutable logs, compliance-ready | Splunk, Datadog |
| **KMS** | Encryption | Customer-managed keys, per-CMO isolation | HashiCorp Vault |

**Service Selection Criteria:**

1. **Serverless-first:** Minimize operational overhead
2. **Managed services:** Reduce undifferentiated heavy lifting
3. **GxP-qualified:** Compliance with pharma regulations
4. **Proven at scale:** Used by other pharma companies
5. **Cost-effective:** Pay-per-use pricing model
6. **Integration:** Native AWS service integration

**Technology Decisions:**

| Decision | Rationale |
|----------|-----------|
| **Parquet over CSV** | 10x faster queries, 5x smaller storage, columnar format |
| **Serverless over containers** | No server management, auto-scaling, pay-per-use |
| **Multi-account over single account** | Security isolation, blast radius containment |
| **Lake Formation over IAM only** | Fine-grained access (column/row level), centralized governance |
| **Glue over Databricks** | Lower cost for batch ETL, native AWS integration |
| **Athena over Redshift** | No cluster management, pay-per-query, sufficient for use case |

---

## Slide 14: Implementation Roadmap

**Title:** Phased Implementation with Risk Mitigation

**Detailed Roadmap:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  PHASE 0: DISCOVERY & DESIGN (Weeks 1-4)                                    │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Week 1-2: CMO Discovery                                                 │ │
│  │ • Interview 5 CMOs (platforms, data types, volumes)                    │ │
│  │ • Document current integration pain points                             │ │
│  │ • Validate pattern selection                                           │ │
│  │                                                                         │ │
│  │ Week 2-3: Architecture Design                                          │ │
│  │ • Finalize canonical data model                                        │ │
│  │ • Design security architecture                                         │ │
│  │ • Define API contracts                                                 │ │
│  │                                                                         │ │
│  │ Week 3-4: Legal & Compliance                                           │ │
│  │ • Develop DPA templates                                                │ │
│  │ • Security addendum templates                                          │ │
│  │ • GxP compliance review                                                │ │
│  │                                                                         │ │
│  │ Deliverables:                                                           │ │
│  │ • Architecture design document                                         │ │
│  │ • Canonical data model specification                                   │ │
│  │ • Legal template library                                               │ │
│  │ • 2 pilot CMOs selected                                                │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  PHASE 1: FOUNDATION (Weeks 5-10)                                           │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Week 5-6: Infrastructure Setup                                         │ │
│  │ • AWS account structure (multi-account)                                │ │
│  │ • Network (VPC, subnets, endpoints)                                    │ │
│  │ • Security baseline (KMS, CloudTrail, Config)                          │ │
│  │ • CI/CD pipeline (CodePipeline or GitHub Actions)                      │ │
│  │                                                                         │ │
│  │ Week 7-8: Pattern 2 Implementation (SFTP)                              │ │
│  │ • Transfer Family setup                                                │ │
│  │ • S3 landing zone                                                      │ │
│  │ • Lambda file processing                                               │ │
│  │ • Glue ETL for CSV/JSON parsing                                        │ │
│  │                                                                         │ │
│  │ Week 9-10: Pilot CMO Integration                                       │ │
│  │ • Onboard 2 pilot CMOs (1 modern, 1 legacy)                           │ │
│  │ • Data quality validation                                              │ │
│  │ • User acceptance testing                                              │ │
│  │                                                                         │ │
│  │ Milestone: First 2 CMOs live, basic structured data flowing            │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  PHASE 2: EXPANSION (Weeks 11-16)                                           │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Week 11-12: Pattern 1 Implementation (Native Connectors)               │ │
│  │ • Glue connectors for Snowflake, Oracle, SQL Server                   │ │
│  │ • Incremental load strategy                                            │ │
│  │ • Performance optimization                                             │ │
│  │                                                                         │ │
│  │ Week 13-14: Pattern 3 Implementation (AI)                              │ │
│  │ • Textract integration (PDF processing)                                │ │
│  │ • Rekognition integration (image analysis)                             │ │
│  │ • OpenSearch for full-text search                                      │ │
│  │                                                                         │ │
│  │ Week 15-16: Scale to 10 CMOs                                           │ │
│  │ • Onboard 8 additional CMOs                                            │ │
│  │ • Self-service portal (CMO onboarding UI)                              │ │
│  │ • Monitoring dashboards                                                │ │
│  │                                                                         │ │
│  │ Milestone: 10 CMOs integrated, all 3 patterns operational              │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  PHASE 3: SCALE & AI (Weeks 17-24)                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Week 17-18: Generative AI (Bedrock)                                    │ │
│  │ • RAG implementation (Bedrock Knowledge Base)                          │ │
│  │ • Natural language query interface                                     │ │
│  │ • Guardrails configuration                                             │ │
│  │                                                                         │ │
│  │ Week 19-20: Advanced Analytics                                         │ │
│  │ • Cross-CMO analytics (Gold layer)                                     │ │
│  │ • QuickSight dashboards                                                │ │
│  │ • Automated reporting                                                  │ │
│  │                                                                         │ │
│  │ Week 21-22: Integration with Merck Systems                             │ │
│  │ • API Gateway setup                                                    │ │
│  │ • ERP/QMS/LIMS integration                                             │ │
│  │ • Event-driven notifications                                           │ │
│  │                                                                         │ │
│  │ Week 23-24: Scale to 20+ CMOs                                          │ │
│  │ • Onboard remaining CMOs                                               │ │
│  │ • Performance tuning                                                   │ │
│  │ • Operational runbook finalization                                     │ │
│  │                                                                         │ │
│  │ Milestone: Production platform with 20+ CMOs, full AI capabilities     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Risk Mitigation:**

| Risk | Mitigation Strategy |
|------|---------------------|
| **CMO adoption resistance** | Start with 2 pilot CMOs, demonstrate value, multiple pattern options |
| **Data quality issues** | Automated validation (Glue Data Quality), Bronze layer preserves raw data |
| **Integration complexity** | Phased approach, Pattern 2 (SFTP) as universal fallback |
| **Security concerns** | Multi-layer security, per-CMO encryption keys, audit trail |
| **Cost overruns** | Pay-as-you-go pricing, cost monitoring, monthly reviews |
| **Performance issues** | Serverless auto-scaling, performance testing in Phase 1 |
| **Vendor lock-in** | Open formats (Parquet), standard APIs, multi-cloud data model |


---

## Slide 15: Total Cost of Ownership (TCO)

**Title:** Cost Model & ROI Analysis

**Monthly Cost Estimate (20 CMOs at steady state):**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  INFRASTRUCTURE COSTS (Monthly)                                             │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Storage (S3)                                                            │ │
│  │ • 100 TB data lake (Standard)              $2,300                       │ │
│  │ • 50 TB archived (Glacier)                 $200                         │ │
│  │ • S3 requests (1M PUT, 10M GET)            $50                          │ │
│  │                                            ─────                         │ │
│  │ Subtotal:                                  $2,550                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Compute (Glue, Lambda, Athena)                                          │ │
│  │ • Glue ETL (500 DPU-hours/month)           $2,200                       │ │
│  │ • Lambda (10M invocations)                 $200                         │ │
│  │ • Athena (10 TB scanned/month)             $50                          │ │
│  │                                            ─────                         │ │
│  │ Subtotal:                                  $2,450                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ AI Services (Textract, Rekognition, Bedrock)                           │ │
│  │ • Textract (10K pages/month)               $150                         │ │
│  │ • Rekognition (5K images/month)            $60                          │ │
│  │ • Bedrock (100K tokens/day)                $900                         │ │
│  │                                            ─────                         │ │
│  │ Subtotal:                                  $1,110                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Integration & Networking                                                │ │
│  │ • Transfer Family (2 endpoints)            $440                         │ │
│  │ • API Gateway (1M requests)                $35                          │ │
│  │ • VPC Endpoints (5 endpoints)              $75                          │ │
│  │ • Data transfer out (5 TB)                 $450                         │ │
│  │                                            ─────                         │ │
│  │ Subtotal:                                  $1,000                       │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Security & Governance                                                   │ │
│  │ • KMS (20 keys, 1M requests)               $40                          │ │
│  │ • CloudTrail (management events)           $0 (free)                    │ │
│  │ • Config (20 resources)                    $40                          │ │
│  │ • Security Hub                             $10                          │ │
│  │ • GuardDuty                                $50                          │ │
│  │                                            ─────                         │ │
│  │ Subtotal:                                  $140                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Analytics & Visualization                                               │ │
│  │ • OpenSearch (3-node cluster)              $600                         │ │
│  │ • QuickSight (10 users)                    $240                         │ │
│  │                                            ─────                         │ │
│  │ Subtotal:                                  $840                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│  TOTAL MONTHLY INFRASTRUCTURE COST:          $8,090                         │
│  ANNUAL INFRASTRUCTURE COST:                 $97,080                        │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Operational Costs (Annual):**

| Cost Category | Annual Cost | Notes |
|---------------|-------------|-------|
| **AWS Infrastructure** | $97,000 | See breakdown above |
| **DevOps/Platform Team** | $400,000 | 2 FTE (architect + engineer) |
| **Support (AWS Enterprise)** | $15,000 | 3% of spend (optional) |
| **Training** | $10,000 | AWS certifications, workshops |
| **Contingency (10%)** | $52,000 | Buffer for growth |
| **TOTAL ANNUAL TCO** | **$574,000** | |

**Cost Per CMO:**
- $574,000 / 20 CMOs = **$28,700 per CMO per year**
- Compare to current: $200+ hours × $150/hour = **$30,000+ per integration**

**ROI Analysis:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  CURRENT STATE (Per CMO Integration)                                        │
│  • Time: 3-6 months                                                          │
│  • Merck effort: 200 hours × $150/hour = $30,000                            │
│  • CMO effort: 100 hours × $150/hour = $15,000                              │
│  • Opportunity cost: 4 months delay = $50,000 (estimated)                   │
│  • TOTAL COST PER CMO: $95,000                                               │
│                                                                              │
│  FUTURE STATE (With Platform)                                               │
│  • Time: 1-4 weeks                                                           │
│  • Merck effort: 20 hours × $150/hour = $3,000                              │
│  • CMO effort: 10 hours × $150/hour = $1,500                                │
│  • Platform cost: $28,700/year = $2,400/month                               │
│  • TOTAL COST PER CMO: $6,900 (first month) + $2,400/month ongoing          │
│                                                                              │
│  SAVINGS PER CMO:                                                            │
│  • One-time: $95,000 - $6,900 = $88,100                                     │
│  • Ongoing: Faster access to data, AI insights (unquantified)               │
│                                                                              │
│  BREAK-EVEN ANALYSIS:                                                        │
│  • Platform annual cost: $574,000                                            │
│  • Savings per CMO: $88,100                                                  │
│  • Break-even: 574,000 / 88,100 = 6.5 CMOs                                  │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│  CONCLUSION: Platform pays for itself after 7 CMO integrations              │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Cost Optimization Opportunities:**

1. **Reserved Capacity:** Save 30-50% on predictable workloads (OpenSearch, Transfer Family)
2. **Savings Plans:** Commit to Glue/Lambda usage for 20-40% discount
3. **S3 Intelligent-Tiering:** Automatic cost optimization (5-10% savings)
4. **Spot Instances:** Use for non-critical Glue jobs (70% savings)
5. **Data Lifecycle:** Auto-archive to Glacier after 90 days (80% storage savings)

**Estimated Savings with Optimization:** $15,000-25,000/year (15-25% reduction)

---

## Slide 16: Architecture Principles & Best Practices

**Title:** Alignment with Enterprise Architecture Standards

**AWS Well-Architected Framework Alignment:**

| Pillar | Implementation | Benefit |
|--------|----------------|---------|
| **Operational Excellence** | IaC (CDK/Terraform), CI/CD, automated monitoring | Consistent deployments, faster iterations |
| **Security** | Defense-in-depth, encryption, least privilege | GxP compliance, audit-ready |
| **Reliability** | Multi-AZ, automated backups, retry logic | 99.9% availability target |
| **Performance Efficiency** | Serverless, auto-scaling, caching | Sub-second queries, cost-effective |
| **Cost Optimization** | Pay-per-use, right-sizing, lifecycle policies | 30-50% lower than alternatives |
| **Sustainability** | Serverless (no idle resources), S3 Intelligent-Tiering | Reduced carbon footprint |

**Enterprise Architecture Principles:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  1. API-FIRST DESIGN                                                         │
│     • All data access via APIs (no direct database access)                  │
│     • Versioned APIs (backward compatibility)                               │
│     • OpenAPI specification for documentation                               │
│                                                                              │
│  2. EVENT-DRIVEN ARCHITECTURE                                                │
│     • Decoupled components (EventBridge)                                    │
│     • Asynchronous processing (SQS, Lambda)                                 │
│     • Real-time notifications (SNS)                                         │
│                                                                              │
│  3. IMMUTABLE DATA                                                           │
│     • Bronze layer never modified (audit trail)                             │
│     • S3 Object Lock (WORM compliance)                                      │
│     • Versioning enabled (data recovery)                                    │
│                                                                              │
│  4. SEPARATION OF CONCERNS                                                   │
│     • Ingestion ≠ Processing ≠ Consumption                                  │
│     • Multi-account isolation (blast radius)                                │
│     • Microservices pattern (Lambda functions)                              │
│                                                                              │
│  5. SECURITY BY DESIGN                                                       │
│     • Encryption everywhere (at rest, in transit)                           │
│     • Least privilege access (IAM, Lake Formation)                          │
│     • Defense-in-depth (network, identity, data, audit)                     │
│                                                                              │
│  6. OBSERVABILITY                                                            │
│     • Centralized logging (CloudWatch)                                      │
│     • Distributed tracing (X-Ray)                                           │
│     • Custom metrics (business KPIs)                                        │
│                                                                              │
│  7. AUTOMATION                                                               │
│     • Infrastructure as Code (no manual changes)                            │
│     • Automated testing (unit, integration, E2E)                            │
│     • Self-healing (automated remediation)                                  │
│                                                                              │
│  8. VENDOR NEUTRALITY                                                        │
│     • Open formats (Parquet, JSON)                                          │
│     • Standard protocols (SFTP, HTTPS, SQL)                                 │
│     • Portable data model (not AWS-specific)                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Design Patterns Used:**

- **Hub-and-Spoke:** Centralized integration hub, decoupled CMOs
- **Medallion Architecture:** Bronze → Silver → Gold data layers
- **Strangler Fig:** Gradual migration from legacy integrations
- **Circuit Breaker:** Fault tolerance in API calls
- **Retry with Exponential Backoff:** Resilient data ingestion
- **Idempotency:** Duplicate detection and handling
- **CQRS:** Separate read/write paths for performance

---

## Slide 17: Disaster Recovery & Business Continuity

**Title:** High Availability & DR Strategy

**DR Architecture:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  PRIMARY REGION (us-east-1)                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  • Active data ingestion                                                │ │
│  │  • Real-time processing                                                 │ │
│  │  • User queries                                                         │ │
│  │  • S3 (primary data lake)                                               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                          │                                                   │
│                          │ S3 Cross-Region Replication (CRR)                │
│                          ▼                                                   │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  DR REGION (us-west-2)                                                  │ │
│  │  • Passive (standby)                                                    │ │
│  │  • S3 replica (read-only)                                               │ │
│  │  • Infrastructure pre-deployed (IaC)                                    │ │
│  │  • Can be activated in < 1 hour                                         │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**DR Metrics:**

| Metric | Target | Implementation |
|--------|--------|----------------|
| **RTO (Recovery Time Objective)** | < 4 hours | Pre-deployed infrastructure, automated failover |
| **RPO (Recovery Point Objective)** | < 15 minutes | S3 CRR (near real-time replication) |
| **Data Durability** | 99.999999999% | S3 standard (11 nines) |
| **Availability** | 99.9% | Multi-AZ services, automated failover |

**Backup Strategy:**

| Data Type | Backup Frequency | Retention | Location |
|-----------|------------------|-----------|----------|
| **Bronze (raw data)** | Continuous (S3 CRR) | 7 years | DR region |
| **Silver/Gold** | Daily snapshot | 90 days | DR region |
| **Glue Data Catalog** | Daily export | 90 days | S3 + DR region |
| **Configuration** | Git (version control) | Indefinite | GitHub/GitLab |
| **Secrets** | Automatic (Secrets Manager) | N/A | Multi-region |

**Failover Procedure:**

1. **Detection:** CloudWatch alarm triggers (< 5 minutes)
2. **Notification:** SNS → PagerDuty → On-call engineer
3. **Assessment:** Determine if failover needed (< 15 minutes)
4. **Activation:** Run failover script (Terraform/CDK) (< 30 minutes)
5. **Validation:** Smoke tests, health checks (< 15 minutes)
6. **Communication:** Notify stakeholders (< 5 minutes)
7. **Total RTO:** < 70 minutes (well under 4-hour target)

**Failback Procedure:**

1. Resolve primary region issue
2. Sync data from DR to primary (S3 CRR reverse)
3. Validate data consistency
4. Redirect traffic back to primary
5. Deactivate DR region (cost savings)


---

## Slide 18: Comparison with Alternative Approaches

**Title:** Why This Architecture vs. Alternatives

**Alternative 1: Point-to-Point Integrations (Current State)**

| Aspect | Point-to-Point | Hub Architecture (Proposed) |
|--------|----------------|----------------------------|
| **Integration time** | 3-6 months per CMO | 1-4 weeks per CMO |
| **Scalability** | Linear (N×M connections) | Hub-and-spoke (N connections) |
| **Reusability** | None (custom every time) | High (3 patterns, canonical model) |
| **Maintenance** | High (each integration unique) | Low (centralized, standardized) |
| **Data consistency** | Inconsistent formats | Canonical model (Silver layer) |
| **Governance** | Decentralized, manual | Centralized (Lake Formation) |
| **Cost per CMO** | $95,000 one-time | $28,700/year ongoing |

**Alternative 2: Commercial iPaaS (Informatica, MuleSoft, Boomi)**

| Aspect | Commercial iPaaS | AWS Native (Proposed) |
|--------|------------------|----------------------|
| **Licensing cost** | $200K-500K/year | $97K/year (infrastructure only) |
| **Vendor lock-in** | High (proprietary) | Low (open formats, standard APIs) |
| **AI capabilities** | Limited or extra cost | Native (Textract, Bedrock) |
| **GxP qualification** | Requires validation | AWS services pre-qualified |
| **Scalability** | License-based limits | Unlimited (serverless) |
| **Integration** | Good (100+ connectors) | Excellent (native AWS services) |
| **Operational overhead** | Medium (platform management) | Low (serverless, managed) |

**Alternative 3: Self-Managed Data Lake (Databricks, Snowflake)**

| Aspect | Databricks/Snowflake | AWS Native (Proposed) |
|--------|---------------------|----------------------|
| **Compute cost** | $15K-30K/month | $2,450/month (serverless) |
| **Storage cost** | Similar | Similar |
| **Operational complexity** | Medium (cluster management) | Low (serverless) |
| **AI integration** | Requires additional tools | Native (Textract, Bedrock) |
| **SFTP capability** | Not included | Native (Transfer Family) |
| **Total cost** | $200K-400K/year | $97K/year |

**Alternative 4: Hybrid (AWS + Databricks)**

| Aspect | Consideration |
|--------|---------------|
| **When to consider** | If Merck already has Databricks investment |
| **Architecture** | Use Databricks for complex transformations, AWS for ingestion/storage |
| **Cost** | Higher than AWS-only, but leverages existing investment |
| **Complexity** | Medium (two platforms to manage) |
| **Recommendation** | Only if Databricks is already enterprise-standard at Merck |

**Decision Matrix:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                    EVALUATION CRITERIA                                       │
│                                                                              │
│   Criteria          Weight   Point-to-  iPaaS   Databricks  AWS Native      │
│                              Point                          (Proposed)       │
│   ─────────────────────────────────────────────────────────────────────     │
│   Cost               20%       2         2         3           5            │
│   Time to value      20%       1         3         3           5            │
│   Scalability        15%       2         4         5           5            │
│   AI capabilities    15%       1         2         3           5            │
│   Operational        15%       2         3         3           5            │
│   GxP compliance     10%       3         3         4           5            │
│   Vendor neutrality   5%       4         2         3           4            │
│   ─────────────────────────────────────────────────────────────────────     │
│   WEIGHTED SCORE              1.95      2.75      3.45        4.85          │
│                                                                              │
│   RECOMMENDATION: AWS Native Architecture                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Differentiators of Proposed Solution:**

1. **Serverless-first:** No infrastructure to manage, auto-scaling
2. **AI-native:** Textract, Rekognition, Bedrock integrated
3. **Cost-effective:** 50-70% lower than alternatives
4. **GxP-ready:** AWS services pre-qualified for pharma
5. **Flexible:** 3 patterns cover 100% of CMO scenarios
6. **Fast:** First CMO live in 6 weeks

---

## Slide 19: Technical Q&A Preparation

**Title:** Anticipated Technical Questions

**Q1: How do you handle schema evolution?**

**A:** Multi-pronged approach:
- Bronze layer: Preserve original data (no schema enforcement)
- Silver layer: Schema-on-read with Glue crawlers (auto-detect changes)
- Glue Schema Registry: Version control for schemas
- Backward compatibility: New fields added as optional, never remove fields
- Migration strategy: Glue ETL jobs updated via CI/CD

**Q2: What about data quality issues from CMOs?**

**A:** Automated validation:
- Glue Data Quality: Define rules (completeness, uniqueness, range checks)
- Quarantine zone: Failed records isolated for review
- Alerting: SNS notifications for quality failures
- Human-in-the-loop: Dashboard for data stewards to review/approve
- Feedback loop: Quality reports sent to CMOs

**Q3: How do you prevent one CMO from accessing another's data?**

**A:** Multi-layer isolation:
- S3 bucket prefixes: Per-CMO isolation (s3://bucket/cmo-alpha/)
- Lake Formation: Column/row-level permissions
- IAM policies: Attribute-based access control (ABAC) using tags
- Encryption: Per-CMO KMS keys (optional for high-security CMOs)
- Audit: CloudTrail logs all access attempts

**Q4: What if a CMO has 10 TB of historical data to migrate?**

**A:** Bulk migration strategy:
- AWS Snowball: Physical device for large datasets (> 1 TB)
- AWS DataSync: Automated transfer for on-prem data
- Parallel transfers: Multi-part upload (S3 Transfer Acceleration)
- Incremental: Migrate historical data in batches (oldest first)
- Timeline: 10 TB via Snowball = 1 week (vs. 2-3 weeks over internet)

**Q5: How do you handle PII/PHI in CMO data?**

**A:** Comprehensive approach:
- Amazon Macie: Automatic PII/PHI detection
- Data masking: Lake Formation cell-level filtering
- Encryption: All data encrypted at rest (KMS)
- Access control: Role-based access (only authorized users see PII)
- Audit: CloudTrail logs all PII access
- Compliance: GDPR, HIPAA controls via AWS Audit Manager

**Q6: What's the disaster recovery plan?**

**A:** See Slide 17 for details:
- RTO: < 4 hours
- RPO: < 15 minutes
- S3 Cross-Region Replication (CRR)
- Pre-deployed infrastructure in DR region
- Automated failover procedures

**Q7: How do you integrate with existing Merck data warehouse (Snowflake)?**

**A:** Multiple options:
- Option 1: Glue connector to Snowflake (push data from hub to Snowflake)
- Option 2: Snowflake external tables (query S3 directly from Snowflake)
- Option 3: API Gateway (Snowflake queries hub via REST API)
- Recommendation: Option 2 (external tables) for cost-effectiveness

**Q8: What about real-time data streaming?**

**A:** Event-driven architecture:
- Kinesis Data Streams: Real-time ingestion (IoT sensors, events)
- Kinesis Firehose: Automatic delivery to S3
- Lambda: Real-time processing and alerting
- EventBridge: Event routing to downstream systems
- Latency: < 1 second from source to S3

**Q9: How do you handle CMO-specific customizations?**

**A:** Configuration-driven approach:
- Per-CMO configuration files (YAML/JSON)
- Glue job parameters (no code changes)
- Lambda environment variables
- DynamoDB: Store CMO-specific mappings
- Example: CMO A uses "batch_number", CMO B uses "lot_id" → mapped to canonical "batch_id"

**Q10: What's the vendor lock-in risk with AWS?**

**A:** Mitigation strategies:
- Open formats: Parquet (not AWS-specific)
- Standard protocols: SFTP, HTTPS, SQL
- Portable data model: Based on CDISC/HL7 (industry standards)
- IaC: Terraform (multi-cloud) or CDK (AWS-specific but exportable)
- Exit strategy: S3 data exportable to any cloud (S3 API compatible with MinIO, GCS)

---

## Slide 20: Success Criteria & KPIs

**Title:** Measuring Success

**Technical KPIs:**

| KPI | Target | Measurement Method |
|-----|--------|-------------------|
| **Integration time** | < 4 weeks per CMO | Project tracking (Jira) |
| **Data ingestion latency** | < 2 hours (batch) | CloudWatch custom metric |
| **Query performance (p95)** | < 10 seconds | Athena query metrics |
| **System availability** | > 99.9% | CloudWatch uptime |
| **Data quality score** | > 95% pass rate | Glue Data Quality |
| **API response time (p95)** | < 500ms | API Gateway metrics |
| **Cost per CMO** | < $30K/year | AWS Cost Explorer |
| **Security incidents** | 0 critical | Security Hub |

**Business KPIs:**

| KPI | Target | Measurement Method |
|-----|--------|-------------------|
| **CMOs onboarded** | 20 in 6 months | Project tracking |
| **Merck effort per CMO** | < 20 hours | Time tracking |
| **CMO satisfaction** | > 4.0/5.0 | Quarterly survey |
| **Data-driven decisions** | 50% increase | User interviews |
| **Time to insight** | Hours → Seconds | User feedback |
| **ROI** | Positive after 7 CMOs | Financial analysis |

**Operational KPIs:**

| KPI | Target | Measurement Method |
|-----|--------|-------------------|
| **Deployment frequency** | Weekly | CI/CD metrics |
| **Mean time to recovery (MTTR)** | < 1 hour | Incident tracking |
| **Change failure rate** | < 5% | CI/CD metrics |
| **Infrastructure drift** | 0 instances | AWS Config |
| **Security compliance** | 100% | AWS Audit Manager |

**Quarterly Review Metrics:**

- Cost trends (actual vs. budget)
- Performance trends (query latency, ingestion time)
- Adoption metrics (CMOs onboarded, API usage)
- Quality metrics (data quality scores, incident count)
- User satisfaction (surveys, feedback)

---

## Slide 21: Next Steps & Decision Points

**Title:** Path Forward

**Immediate Actions (Week 1-2):**

1. **Architecture Review Session**
   - Deep dive with Merck EA team
   - Address technical concerns
   - Validate design decisions
   - Owner: AWS Solutions Architect + Merck EA

2. **CMO Discovery Interviews**
   - Interview 5 representative CMOs
   - Document platforms, data types, volumes
   - Validate pattern selection
   - Owner: Merck Supply Chain + AWS

3. **Security & Compliance Review**
   - Review with Merck InfoSec team
   - Validate security architecture
   - Confirm GxP compliance approach
   - Owner: AWS Security Architect + Merck InfoSec

4. **Cost Validation**
   - Validate TCO model with actual data volumes
   - Confirm budget allocation
   - Owner: Merck Finance + AWS

**Decision Points:**

| Decision | Options | Recommendation | Timeline |
|----------|---------|----------------|----------|
| **IaC Tool** | CDK vs. Terraform | CDK (AWS-native, TypeScript) | Week 2 |
| **Multi-account strategy** | Single vs. Multi | Multi (security isolation) | Week 2 |
| **DR region** | us-west-2 vs. eu-west-1 | us-west-2 (lower latency) | Week 2 |
| **Pilot CMOs** | Which 2 CMOs? | 1 modern + 1 legacy | Week 3 |
| **Go/No-Go** | Proceed to Phase 1? | TBD | Week 4 |

**Approval Required:**

- [ ] Enterprise Architecture approval (technical design)
- [ ] Information Security approval (security architecture)
- [ ] Finance approval (budget allocation)
- [ ] Legal approval (DPA templates)
- [ ] Business sponsor approval (project charter)

**Timeline to Kickoff:**

- Week 1-2: Reviews and approvals
- Week 3-4: Finalize design, select pilot CMOs
- Week 5: Project kickoff (Phase 1 start)

---

## Slide 22: Summary & Recommendations

**Title:** Executive Summary for Enterprise Architects

**Architecture Highlights:**

✅ **Hub-and-spoke design** - Decoupled, scalable, maintainable
✅ **3 proven patterns** - Cover 100% of CMO scenarios
✅ **Serverless-first** - Minimal operational overhead
✅ **AI-native** - Textract, Rekognition, Bedrock integrated
✅ **Security by design** - Defense-in-depth, GxP-ready
✅ **Cost-effective** - 50-70% lower than alternatives

**Technical Strengths:**

1. **Scalability:** Serverless auto-scaling, unlimited storage
2. **Performance:** Sub-second queries, < 2 hour batch ingestion
3. **Reliability:** 99.9% availability, < 4 hour RTO
4. **Security:** Multi-layer defense, per-CMO isolation
5. **Maintainability:** IaC, CI/CD, automated monitoring
6. **Flexibility:** 3 patterns, open formats, standard APIs

**Risk Mitigation:**

- Phased approach (value in 6 weeks)
- Pilot CMOs (validate before scaling)
- Pattern 2 (SFTP) as universal fallback
- Multi-layer security (defense-in-depth)
- Automated testing (CI/CD)
- Disaster recovery (< 4 hour RTO)

**Recommendation:**

**Proceed with Phase 0 (Discovery & Design) for 4 weeks:**
- Validate architecture with CMO interviews
- Finalize security design with InfoSec
- Confirm budget and resource allocation
- Select 2 pilot CMOs
- Go/No-Go decision at end of Week 4

**Expected Outcomes:**

- First 2 CMOs live in 10 weeks
- 10 CMOs integrated in 16 weeks
- 20+ CMOs at scale in 24 weeks
- 90% reduction in integration time
- Platform pays for itself after 7 CMOs

---

## Slide 23: Appendix - Technical Deep Dives

**Available for Discussion:**

1. **Glue ETL Job Examples** (PySpark code samples)
2. **Lake Formation Permissions Model** (detailed RBAC)
3. **API Specifications** (OpenAPI/Swagger docs)
4. **Data Model Details** (full canonical schema)
5. **Security Controls Matrix** (21 CFR Part 11 mapping)
6. **Performance Test Results** (benchmark data)
7. **Cost Breakdown by Service** (detailed AWS bill)
8. **Disaster Recovery Runbook** (step-by-step procedures)
9. **CI/CD Pipeline Details** (GitHub Actions workflow)
10. **Monitoring Dashboard Examples** (CloudWatch screenshots)

---

## Slide 24: Contact & Next Steps

**Title:** Let's Discuss

**AWS Team:**
- Solutions Architect: [Name] - [email]
- Security Architect: [Name] - [email]
- Data & Analytics Specialist: [Name] - [email]

**Proposed Next Meeting:**
- **Architecture Deep Dive** (2 hours)
  - Detailed Q&A on technical design
  - Whiteboarding session
  - Security architecture review

**Resources:**
- Architecture diagrams (Lucidchart/draw.io)
- Sample code repository (GitHub)
- AWS Well-Architected Review
- Reference architectures (AWS Solutions Library)

**Questions?**

---

## Presentation Notes for Delivery

**Audience Considerations:**
- Enterprise Architects care about: scalability, maintainability, standards compliance
- Focus on: architecture patterns, technology decisions, operational model
- De-emphasize: business value, ROI (they assume business case is validated)
- Emphasize: technical rigor, risk mitigation, alignment with EA principles

**Key Messages:**
1. This is a **well-architected** solution (AWS Well-Architected Framework)
2. **Proven patterns** (hub-and-spoke, medallion, event-driven)
3. **Low operational overhead** (serverless, managed services)
4. **Secure by design** (defense-in-depth, GxP-ready)
5. **Cost-effective** (50-70% lower than alternatives)

**Anticipated Pushback:**
- "Why not use our existing Databricks/Snowflake?"
  - Response: Can integrate, but serverless is more cost-effective for this use case
- "This seems like vendor lock-in to AWS"
  - Response: Open formats, standard APIs, portable data model
- "What about operational complexity?"
  - Response: Serverless = minimal ops, IaC = consistent deployments
- "How do we know this will scale?"
  - Response: AWS services proven at scale (Netflix, Airbnb use same services)

**Success Criteria for This Meeting:**
- [ ] EA team understands the architecture
- [ ] Technical concerns addressed
- [ ] Agreement on next steps (Discovery phase)
- [ ] Commitment to follow-up deep dive sessions
