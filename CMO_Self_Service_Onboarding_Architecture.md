# CMO Self-Service Onboarding & Data Contract Architecture

## The Real Challenge: Data Movement, Not Integration

**Customer Insight:** The biggest challenge is not technical integration complexity, but **how to move data from CMOs to Merck efficiently and consistently**.

**Solution:** Self-service CMO onboarding portal with data contracts and automated pipeline activation.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   CMO ONBOARDING FLOW                                                        │
│                                                                              │
│   ┌──────────────┐                                                           │
│   │  CMO         │  1. Receives onboarding URL from Merck                   │
│   │  Receives    │     https://cmo-onboarding.merck.com/register            │
│   │  Email       │                                                           │
│   └──────┬───────┘                                                           │
│          │                                                                   │
│          ▼                                                                   │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  SELF-SERVICE ONBOARDING PORTAL (Web UI)                              │  │
│   │                                                                       │  │
│   │  Step 1: CMO Registration                                             │  │
│   │  • CMO name, contact info                                             │  │
│   │  • Authentication setup (credentials)                                 │  │
│   │                                                                       │  │
│   │  Step 2: Pattern Selection                                            │  │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │  │
│   │  │ Pattern 1   │  │ Pattern 2   │  │ Pattern 3   │                  │  │
│   │  │ Native      │  │ SFTP        │  │ Unstructured│                  │  │
│   │  │ Connector   │  │             │  │ AI          │                  │  │
│   │  └─────────────┘  └─────────────┘  └─────────────┘                  │  │
│   │  CMO selects based on their capabilities                              │  │
│   │                                                                       │  │
│   │  Step 3: Data Contract Definition                                     │  │
│   │  • Upload sample data OR                                              │  │
│   │  • Select from standard templates (batch, quality, materials)         │  │
│   │  • Define schema (fields, types, constraints)                         │  │
│   │  • Map to canonical model                                             │  │
│   │                                                                       │  │
│   │  Step 4: Connection Configuration                                     │  │
│   │  • Pattern 1: Database connection string, credentials                 │  │
│   │  • Pattern 2: SFTP credentials generated                              │  │
│   │  • Pattern 3: S3 upload URL generated                                 │  │
│   │                                                                       │  │
│   │  Step 5: Test & Validate                                              │  │
│   │  • CMO uploads test data                                              │  │
│   │  • System validates against schema                                    │  │
│   │  • CMO sees validation results                                        │  │
│   │                                                                       │  │
│   │  Step 6: Activate Pipeline                                            │  │
│   │  • Merck approves (1-click)                                           │  │
│   │  • Pipeline auto-deployed via IaC                                     │  │
│   │  • CMO receives confirmation                                          │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  AUTOMATED PIPELINE ACTIVATION                                        │  │
│   │  • Glue job auto-created from template                                │  │
│   │  • Schema registered in Glue Data Catalog                             │  │
│   │  • Data quality rules auto-generated                                  │  │
│   │  • Monitoring dashboard auto-created                                  │  │
│   │  • CMO can start publishing data immediately                          │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Contract Architecture

**What is a Data Contract?**

A formal agreement between CMO (data producer) and Merck (data consumer) that defines:
- Schema (fields, types, constraints)
- Data quality expectations (completeness, accuracy)
- Delivery frequency (real-time, daily, weekly)
- SLA (latency, availability)
- Versioning strategy

**Data Contract Components:**

```yaml
# Example: Batch Manufacturing Data Contract
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
        description: "Unique batch identifier"
        
      - name: product_code
        type: string
        required: true
        pattern: "^[A-Z]{3}-[0-9]{4}$"
        description: "Merck product code"
        
      - name: manufacturing_start_date
        type: timestamp
        required: true
        format: "ISO 8601"
        
      - name: manufacturing_end_date
        type: timestamp
        required: true
        validation: "must be >= manufacturing_start_date"
        
      - name: batch_size_kg
        type: decimal
        required: true
        min: 0
        max: 10000
        
      - name: yield_percentage
        type: decimal
        required: true
        min: 0
        max: 100
        
      - name: quality_status
        type: enum
        required: true
        values: ["released", "quarantine", "rejected"]
  
  data_quality:
    completeness: 100%  # All required fields must be present
    uniqueness: 
      - batch_id  # No duplicate batch IDs
    timeliness: "< 24 hours from manufacturing_end_date"
    accuracy: "> 95% pass rate"
  
  delivery:
    frequency: "daily"
    schedule: "02:00 UTC"
    format: "parquet"  # or CSV, JSON
    compression: "snappy"
  
  sla:
    availability: "99.5%"
    max_latency: "2 hours"
    
  mapping:
    # Map CMO fields to canonical model
    cmo_field_name: canonical_field_name
    lot_number: batch_id
    prod_code: product_code
    start_dt: manufacturing_start_date
```


---

## Schema Registry Architecture

**Purpose:** Centralized repository for all CMO schemas with versioning and validation.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   SCHEMA REGISTRY (AWS Glue Schema Registry)                                │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  Registry: merck-cmo-schemas                                          │  │
│   │                                                                       │  │
│   │  Schema: batch-manufacturing                                          │  │
│   │  ├── Version 1.0 (2024-01-15) - Initial                              │  │
│   │  ├── Version 1.1 (2024-03-20) - Added yield_percentage               │  │
│   │  └── Version 2.0 (2024-06-10) - Breaking change (renamed fields)     │  │
│   │                                                                       │  │
│   │  Schema: quality-control                                              │  │
│   │  ├── Version 1.0 (2024-01-15) - Initial                              │  │
│   │  └── Version 1.1 (2024-04-01) - Added test_method field              │  │
│   │                                                                       │  │
│   │  Schema: materials                                                    │  │
│   │  └── Version 1.0 (2024-01-15) - Initial                              │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    │ Schema validation                      │
│                                    ▼                                        │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  SCHEMA VALIDATION LAYER                                              │  │
│   │                                                                       │  │
│   │  When CMO publishes data:                                             │  │
│   │  1. Retrieve schema from registry                                     │  │
│   │  2. Validate data against schema                                      │  │
│   │  3. Check data quality rules                                          │  │
│   │  4. If valid → Bronze layer                                           │  │
│   │  5. If invalid → Quarantine + alert CMO                               │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Schema Registry Benefits:**

1. **Version Control:** Track schema evolution over time
2. **Backward Compatibility:** Ensure new versions don't break existing pipelines
3. **Validation:** Automatic data validation against registered schema
4. **Discovery:** CMOs can browse available schemas
5. **Reusability:** Standard schemas shared across CMOs

**Schema Registration Flow:**

```
CMO Onboarding Portal
    ↓
1. CMO uploads sample data OR selects template
    ↓
2. System infers schema (Glue Crawler)
    ↓
3. CMO reviews/edits schema in UI
    ↓
4. System validates schema (syntax, types)
    ↓
5. CMO maps fields to canonical model
    ↓
6. System registers schema in Glue Schema Registry
    ↓
7. Schema version assigned (e.g., 1.0)
    ↓
8. Data contract created and stored (DynamoDB)
    ↓
9. Pipeline template populated with schema
    ↓
10. Merck approves → Pipeline deployed
```

---

## CMO Self-Service Portal - Technical Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   FRONTEND (React / Angular)                                                │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  • CMO registration wizard                                            │  │
│   │  • Pattern selection UI                                               │  │
│   │  • Schema editor (JSON/YAML)                                          │  │
│   │  • Field mapping interface (drag-and-drop)                            │  │
│   │  • Test data upload                                                   │  │
│   │  • Validation results dashboard                                       │  │
│   │  • Pipeline status monitoring                                         │  │
│   └────────────────────────────────────┬─────────────────────────────────┘  │
│                                         │                                    │
│                                         │ HTTPS / API Gateway                │
│                                         ▼                                    │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  API LAYER (API Gateway + Lambda)                                     │  │
│   │                                                                       │  │
│   │  POST /cmo/register                                                   │  │
│   │  • Create CMO record in DynamoDB                                      │  │
│   │  • Generate credentials (Secrets Manager)                             │  │
│   │  • Send welcome email (SES)                                           │  │
│   │                                                                       │  │
│   │  POST /cmo/{id}/schema                                                │  │
│   │  • Validate schema syntax                                             │  │
│   │  • Register in Glue Schema Registry                                   │  │
│   │  • Create data contract (DynamoDB)                                    │  │
│   │                                                                       │  │
│   │  POST /cmo/{id}/test-data                                             │  │
│   │  • Upload to S3 test bucket                                           │  │
│   │  • Trigger validation Lambda                                          │  │
│   │  • Return validation results                                          │  │
│   │                                                                       │  │
│   │  POST /cmo/{id}/activate                                              │  │
│   │  • Trigger pipeline deployment (Step Functions)                       │  │
│   │  • Create Glue job from template                                      │  │
│   │  • Configure Transfer Family (if SFTP)                                │  │
│   │  • Create monitoring dashboard                                        │  │
│   └────────────────────────────────────┬─────────────────────────────────┘  │
│                                         │                                    │
│                                         ▼                                    │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  BACKEND SERVICES                                                     │  │
│   │                                                                       │  │
│   │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐         │  │
│   │  │ DynamoDB       │  │ Glue Schema    │  │ Secrets        │         │  │
│   │  │ (CMO registry, │  │ Registry       │  │ Manager        │         │  │
│   │  │  data contracts│  │ (schemas)      │  │ (credentials)  │         │  │
│   │  └────────────────┘  └────────────────┘  └────────────────┘         │  │
│   │                                                                       │  │
│   │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐         │  │
│   │  │ Step Functions │  │ CodePipeline   │  │ CloudFormation │         │  │
│   │  │ (orchestration)│  │ (CI/CD)        │  │ (IaC)          │         │  │
│   │  └────────────────┘  └────────────────┘  └────────────────┘         │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Portal Features:**

1. **CMO Registration**
   - Self-service account creation
   - Email verification
   - Credential generation

2. **Pattern Selection**
   - Visual comparison of 3 patterns
   - Recommendation engine based on CMO capabilities
   - Pattern-specific configuration

3. **Schema Management**
   - Upload sample data (auto-infer schema)
   - Select from standard templates
   - Visual schema editor
   - Field mapping to canonical model
   - Schema validation

4. **Test & Validate**
   - Upload test data
   - Real-time validation feedback
   - Data quality scoring
   - Error reporting with suggestions

5. **Pipeline Activation**
   - One-click activation (after Merck approval)
   - Real-time deployment status
   - Connection details (SFTP credentials, API keys)
   - Monitoring dashboard

6. **Ongoing Management**
   - View data quality metrics
   - Update schema (new version)
   - Pause/resume pipeline
   - Download reports

---

## Automated Pipeline Activation

**When Merck clicks "Activate":**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   STEP FUNCTIONS WORKFLOW (Pipeline Deployment)                             │
│                                                                              │
│   Step 1: Validate Prerequisites                                            │
│   • Data contract exists                                                    │
│   • Schema registered                                                       │
│   • CMO credentials created                                                 │
│   • Test data validated successfully                                        │
│                                                                              │
│   Step 2: Create Infrastructure (CloudFormation)                            │
│   • S3 bucket prefix for CMO (s3://bucket/cmo-alpha/)                      │
│   • IAM role for CMO (least privilege)                                      │
│   • KMS key for CMO (optional, for high-security)                           │
│   • Transfer Family user (if Pattern 2)                                     │
│   • Glue connection (if Pattern 1)                                          │
│                                                                              │
│   Step 3: Deploy Data Pipeline                                              │
│   • Create Glue job from template                                           │
│   • Populate with CMO-specific config:                                      │
│     - Schema from registry                                                  │
│     - Field mappings from data contract                                     │
│     - Data quality rules                                                    │
│   • Create Glue trigger (schedule or event-driven)                          │
│   • Create EventBridge rules (for notifications)                            │
│                                                                              │
│   Step 4: Setup Monitoring                                                  │
│   • Create CloudWatch dashboard for CMO                                     │
│   • Configure alarms (data quality, latency)                                │
│   • Setup SNS topic for alerts                                              │
│                                                                              │
│   Step 5: Notify CMO                                                        │
│   • Send email with connection details                                      │
│   • Provide documentation link                                              │
│   • Include monitoring dashboard URL                                        │
│                                                                              │
│   Step 6: Enable Data Flow                                                  │
│   • CMO starts publishing data                                              │
│   • Automatic validation on arrival                                         │
│   • Data flows to Bronze → Silver → Gold                                    │
│                                                                              │
│   Total Time: < 5 minutes (fully automated)                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Pipeline Template (Glue Job):**

```python
# Auto-generated Glue job for CMO-Alpha
# Generated from template on 2026-02-16

import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

# CMO-specific configuration (injected from data contract)
CMO_ID = "cmo-alpha"
SCHEMA_VERSION = "1.0"
SOURCE_PATTERN = "Pattern2-SFTP"  # or Pattern1-Glue, Pattern3-AI
DATA_CONTRACT_ID = "dc-12345"

# Schema from Glue Schema Registry
SCHEMA = {
    "batch_id": "string",
    "product_code": "string",
    "manufacturing_start_date": "timestamp",
    "manufacturing_end_date": "timestamp",
    "batch_size_kg": "decimal",
    "yield_percentage": "decimal",
    "quality_status": "string"
}

# Field mappings from data contract
FIELD_MAPPINGS = {
    "lot_number": "batch_id",
    "prod_code": "product_code",
    "start_dt": "manufacturing_start_date",
    "end_dt": "manufacturing_end_date",
    "size": "batch_size_kg",
    "yield_pct": "yield_percentage",
    "status": "quality_status"
}

# Data quality rules from data contract
DATA_QUALITY_RULES = [
    "batch_id is not null",
    "batch_id is unique",
    "product_code matches '^[A-Z]{3}-[0-9]{4}$'",
    "yield_percentage between 0 and 100",
    "quality_status in ['released', 'quarantine', 'rejected']"
]

# Initialize Glue context
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)

# Read data from Bronze layer
source_path = f"s3://merck-cmo-hub/bronze/{CMO_ID}/"
df = spark.read.parquet(source_path)

# Apply field mappings
for cmo_field, canonical_field in FIELD_MAPPINGS.items():
    df = df.withColumnRenamed(cmo_field, canonical_field)

# Validate against schema
# (Glue Data Quality integration)

# Write to Silver layer
target_path = f"s3://merck-cmo-hub/silver/batch-manufacturing/{CMO_ID}/"
df.write.mode("append").partitionBy("year", "month", "day").parquet(target_path)

# Update Glue Data Catalog
glueContext.write_dynamic_frame.from_catalog(
    frame=df,
    database="merck_cmo_hub",
    table_name=f"batch_manufacturing_{CMO_ID}"
)

job.commit()
```

---

## Data Movement Flow (End-to-End)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   1. CMO ONBOARDS (One-time, 30 minutes)                                    │
│      • Receives URL from Merck                                              │
│      • Completes onboarding wizard                                          │
│      • Selects pattern, defines schema                                      │
│      • Tests with sample data                                               │
│      • Merck approves → Pipeline auto-deployed                              │
│                                                                              │
│   2. CMO PUBLISHES DATA (Ongoing, automated)                                │
│      ┌────────────────────────────────────────────────────────────────────┐ │
│      │ Pattern 1 (Native Connector):                                      │ │
│      │ • Glue job runs on schedule (e.g., daily 2am)                      │ │
│      │ • Connects to CMO database                                         │ │
│      │ • Extracts new/changed records (incremental)                       │ │
│      │ • Writes to S3 Bronze layer                                        │ │
│      └────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│      ┌────────────────────────────────────────────────────────────────────┐ │
│      │ Pattern 2 (SFTP):                                                  │ │
│      │ • CMO uploads file to SFTP (manual or automated)                   │ │
│      │ • S3 event triggers Lambda                                         │ │
│      │ • Lambda validates file format                                     │ │
│      │ • File moved to S3 Bronze layer                                    │ │
│      └────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│      ┌────────────────────────────────────────────────────────────────────┐ │
│      │ Pattern 3 (Unstructured):                                          │ │
│      │ • CMO uploads PDF/image to S3 (presigned URL)                      │ │
│      │ • EventBridge triggers Textract/Rekognition                        │ │
│      │ • Extracted data written to S3 Bronze layer                        │ │
│      └────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│   3. AUTOMATIC VALIDATION (Real-time)                                       │
│      • Data arrives in Bronze layer                                         │
│      • EventBridge triggers validation Lambda                               │
│      • Lambda retrieves schema from registry                                │
│      • Validates data against schema + data quality rules                   │
│      • If valid → proceed to Silver                                         │
│      • If invalid → quarantine + alert CMO                                  │
│                                                                              │
│   4. TRANSFORMATION (Automated)                                             │
│      • Glue job applies field mappings                                      │
│      • Converts to canonical model                                          │
│      • Writes to Silver layer (Parquet)                                     │
│      • Updates Glue Data Catalog                                            │
│                                                                              │
│   5. MERCK CONSUMES DATA (Self-service)                                     │
│      • Athena queries (SQL)                                                 │
│      • QuickSight dashboards                                                │
│      • API calls (REST/GraphQL)                                             │
│      • Bedrock Gen AI queries                                               │
│      • Export to Merck systems (ERP, QMS, LIMS)                             │
│                                                                              │
│   Total Time: CMO publishes → Merck consumes = < 2 hours                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Benefits of This Approach

**For CMOs:**
1. **Self-service:** No waiting for Merck IT
2. **Flexible:** Choose pattern that fits their capabilities
3. **Transparent:** Real-time validation feedback
4. **Simple:** Upload data, system handles the rest
5. **Fast:** Onboarding in 30 minutes vs. 3-6 months

**For Merck:**
1. **Automated:** No manual pipeline creation
2. **Consistent:** All CMOs use same canonical model
3. **Scalable:** Onboard 100+ CMOs without linear effort
4. **Governed:** Data contracts enforce quality
5. **Fast:** Activate pipeline in < 5 minutes

**For Both:**
1. **Data contract:** Clear expectations and SLAs
2. **Schema registry:** Version control and validation
3. **Automated validation:** Catch errors early
4. **Monitoring:** Real-time visibility into data flow
5. **Audit trail:** Complete lineage from source to consumption

---

## Technology Stack for Portal

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Frontend** | React + Amplify | CMO-facing UI |
| **API** | API Gateway + Lambda | Backend logic |
| **Database** | DynamoDB | CMO registry, data contracts |
| **Schema Registry** | Glue Schema Registry | Schema versioning |
| **Credentials** | Secrets Manager | Secure credential storage |
| **Orchestration** | Step Functions | Pipeline deployment workflow |
| **IaC** | CloudFormation/CDK | Infrastructure provisioning |
| **Monitoring** | CloudWatch | Dashboards and alerts |
| **Notifications** | SNS + SES | Email alerts |

---

## Implementation Priority

**Phase 1 (Weeks 1-6): Manual Onboarding**
- Merck manually creates pipelines
- Document data contracts in spreadsheet
- Validate approach with 2 pilot CMOs

**Phase 2 (Weeks 7-12): Semi-Automated**
- Build schema registry
- Create pipeline templates
- Automate pipeline deployment (Step Functions)
- Merck still manually triggers activation

**Phase 3 (Weeks 13-20): Self-Service Portal**
- Build CMO onboarding portal (React UI)
- Integrate with schema registry
- Enable CMO self-service onboarding
- Merck approval workflow (1-click)

**Phase 4 (Weeks 21+): Advanced Features**
- Schema evolution (automatic migration)
- AI-powered schema inference
- Predictive data quality monitoring
- Self-healing pipelines
