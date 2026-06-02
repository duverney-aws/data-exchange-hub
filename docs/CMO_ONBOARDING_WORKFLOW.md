# CMO Onboarding Workflow — Pharma Data Exchange Hub

## Overview

This document describes the end-to-end workflow for onboarding a Contract Manufacturing Organization (CMO) onto the Pharma Data Exchange Hub. The platform is designed as a self-service experience — CMOs drive the process, and automated guardrails ensure data quality and compliance without manual Merck approval gates.

**Traditional onboarding**: 3–6 months
**With this platform**: 1–4 weeks

---

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CMO ONBOARDING WORKFLOW                         │
└─────────────────────────────────────────────────────────────────────────┘

  CMO Administrator                    Platform (Automated)                 Merck Users
  ─────────────────                    ────────────────────                 ──────────
        │                                      │                                │
        │  1. REGISTER                         │                                │
        ├─────────────────────────────────────►│                                │
        │  Fill org details, GxP cert          │  Generate CMO ID               │
        │                                      │  Create credentials            │
        │                                      │  Store in Secrets Manager      │
        │◄─────────────────────────────────────┤                                │
        │  Receive CMO ID (cmo-{name})         │                                │
        │                                      │                                │
        │  2. DEFINE SCHEMA                    │                                │
        ├─────────────────────────────────────►│                                │
        │  Upload sample data (CSV/JSON/       │  Infer schema (field names,    │
        │  Parquet) OR define manually         │  types, constraints)           │
        │                                      │                                │
        │  Review & edit inferred schema       │                                │
        ├─────────────────────────────────────►│                                │
        │  Approve schema                      │  Register in Glue Schema       │
        │                                      │  Registry (version 1.0)        │
        │                                      │                                │
        │  3. CREATE DATA CONTRACT             │                                │
        ├─────────────────────────────────────►│                                │
        │  Define:                             │  Validate:                     │
        │  • Schema reference                  │  • Schema format (AVRO/JSON)   │
        │  • Quality rules (DQDL)              │  • Rules are executable DQDL   │
        │  • SLAs (timeliness, quality)        │  • SLA thresholds measurable   │
        │  • Delivery schedule                 │  • All required fields present │
        │  • Governance (PII, retention)       │                                │
        │                                      │  Generate contract ID          │
        │◄─────────────────────────────────────┤  (CMO-{NAME}-{DOMAIN}-{NUM})  │
        │  Contract saved as DRAFT             │  Store in DynamoDB             │
        │                                      │                                │
        │  4. SELECT INTEGRATION PATTERN       │                                │
        ├─────────────────────────────────────►│                                │
        │                                      │                                │
        │  ┌─ Pattern 1: Native Connectors ──┐ │                                │
        │  │ Provide JDBC/connection details  │ │                                │
        │  │ (Snowflake, Oracle, SQL Server,  │ │                                │
        │  │  PostgreSQL, SAP, Databricks)    │ │                                │
        │  └──────────────────────────────────┘ │                                │
        │                                      │                                │
        │  ┌─ Pattern 2: Secure Transfer ─────┐│                                │
        │  │ No config needed — SFTP creds    ││  Provision AWS Transfer Family │
        │  │ are auto-provisioned             ││  Generate SFTP credentials     │
        │  └──────────────────────────────────┘│                                │
        │                                      │                                │
        │  ┌─ Pattern 3: AI Unstructured ─────┐│                                │
        │  │ Select doc type (PDF/image)      ││  Configure Textract/           │
        │  │ Set confidence threshold (85%)   ││  Rekognition pipelines         │
        │  └──────────────────────────────────┘│                                │
        │                                      │                                │
        │  5. ACTIVATE PIPELINE                │                                │
        ├─────────────────────────────────────►│                                │
        │  Click "Activate"                    │  Step Functions workflow:       │
        │                                      │  ┌──────────────────────────┐  │
        │                                      │  │ ValidateContract         │  │
        │                                      │  │ DeterminePattern         │  │
        │                                      │  │ ConfigurePattern         │  │
        │                                      │  │ CreateETLJob             │  │
        │                                      │  │ SetupMonitoring          │  │
        │                                      │  └──────────────────────────┘  │
        │                                      │  (retries 3x with backoff)     │
        │◄─────────────────────────────────────┤                                │
        │  Pipeline status: ACTIVE             │                                │
        │  Connection details displayed        │                                │
        │                                      │                                │
  ══════╪══════════════════════════════════════╪════════════════════════════════╪══
        │         DATA FLOWS (ONGOING)         │                                │
  ══════╪══════════════════════════════════════╪════════════════════════════════╪══
        │                                      │                                │
        │  6. DATA INGESTION                   │                                │
        ├─────────────────────────────────────►│                                │
        │  P1: Merck pulls from CMO DB         │                                │
        │  P2: CMO pushes files via SFTP       │                                │
        │  P3: CMO uploads documents           │                                │
        │                                      │                                │
        │                                      │  7. AUTOMATED PROCESSING       │
        │                                      ├───────────────────────────────►│
        │                                      │                                │
        │                                      │  Bronze Layer (raw data)       │
        │                                      │  ├─ Schema validation          │
        │                                      │  ├─ Quality rules (DQDL)       │
        │                                      │  ├─ Deduplication              │
        │                                      │  │                             │
        │                                      │  ├─ PASS ──► Silver Layer      │
        │                                      │  │            (validated)       │
        │                                      │  │            ├─ Glue Catalog   │
        │                                      │  │            ├─ PII masking    │
        │                                      │  │            └─ Lake Formation │
        │                                      │  │                             │
        │                                      │  └─ FAIL ──► Quarantine        │
        │                                      │              (separate prefix)  │
        │                                      │                                │
        │                                      │  Gold Layer (aggregated)       │
        │                                      │  ├─ Daily/weekly/monthly       │
        │                                      │  ├─ CMO performance summaries  │
        │                                      │  └─ Optimized for analytics    │
        │                                      │                                │
        │                                      │  8. MONITORING & ALERTS        │
        │  ◄── SLA breach notification ────────┤──── SLA breach notification ──►│
        │  ◄── Quality threshold alert ────────┤──── Quality threshold alert ──►│
        │                                      │                                │
        │                                      │                                │
        │                                      │  9. CONSUMPTION                │
        │                                      │                                │
        │                                      │         QuickSight ───────────►│
        │                                      │         Dashboards             │
        │                                      │                                │
        │                                      │         NL Query ─────────────►│
        │                                      │         (Bedrock + Athena)     │
        │                                      │                                │
        │                                      │         Athena SQL ───────────►│
        │                                      │         (direct queries)       │
        │                                      │                                │
```

---

## Phase Details

### Phase 1: CMO Registration

**Who**: CMO Administrator
**Where**: Self-Service Portal → CMO Registration page
**Time**: ~5 minutes

| Step | Action | System Response |
|------|--------|-----------------|
| 1 | Navigate to CMO Registration | Registration form displayed |
| 2 | Enter organization name, contact email, phone, address | Fields validated in real-time |
| 3 | Check GxP certification (if applicable) | — |
| 4 | Click "Register CMO" | CMO profile created in DynamoDB |
| | | Credentials generated and stored in Secrets Manager |
| | | CMO ID assigned: `cmo-{name}` |
| 5 | Note the CMO ID from success banner | — |

**Output**: CMO profile with unique ID, stored credentials

---

### Phase 2: Schema Definition

**Who**: CMO Administrator
**Where**: Self-Service Portal → Schema Management page
**Time**: 15–30 minutes

**Option A — Automatic Inference (recommended)**

| Step | Action | System Response |
|------|--------|-----------------|
| 1 | Upload sample data file (CSV, JSON, or Parquet) | File analyzed |
| 2 | — | Schema inferred: field names, types, constraints |
| 3 | Review inferred schema in editable table | — |
| 4 | Edit field names, types, or constraints as needed | — |
| 5 | Enter schema name (e.g., `cmo-alpha-batch-records`) | — |
| 6 | Click "Approve & Register Schema" | Schema registered in Glue Schema Registry (v1.0) |

**Option B — Manual Definition**

| Step | Action | System Response |
|------|--------|-----------------|
| 1 | Switch to "Manual Definition" tab | Empty schema table displayed |
| 2 | Add fields one by one (name, type, constraints) | — |
| 3 | Enter schema name | — |
| 4 | Click "Approve & Register Schema" | Schema registered in Glue Schema Registry (v1.0) |

**Schema versioning**: When updating an existing schema, the system checks backward compatibility. Incompatible changes (removing required fields, changing types) are rejected.

**Output**: Versioned schema in Glue Schema Registry

---

### Phase 3: Data Contract Creation

**Who**: CMO Administrator
**Where**: Self-Service Portal → Data Contracts → Create Contract
**Time**: 30–60 minutes

The data contract is the formal agreement that defines everything about the data exchange:

| Component | What the CMO Defines | Automated Validation |
|-----------|---------------------|---------------------|
| Schema | Reference to registered schema + version | Schema exists in registry |
| Quality Rules | DQDL expressions (completeness, accuracy, uniqueness, consistency) with thresholds | Rules are executable by Glue Data Quality |
| SLAs | Max delay hours, uptime %, min quality score | Thresholds are measurable |
| Delivery Schedule | Frequency (real-time/hourly/daily/weekly/monthly), cron, timezone | Valid cron expression |
| Governance | Data classification, retention years, allowed users/groups, PII fields, encryption | All required fields present |

**Example quality rules (DQDL)**:
```
Completeness "batch_id" > 0.99          — 99% of records must have batch_id
Uniqueness "batch_id" > 0.99            — 99% of batch_ids must be unique
ColumnValues "quality_status" in ["PASS","FAIL","PENDING"]
ColumnValues "batch_id" matches "[A-Z0-9]{10}"
```

**Contract ID format**: `CMO-{NAME}-{DOMAIN}-{NUMBER}` (e.g., `CMO-ALPHA-BATCH-001`)

**Output**: Draft contract stored in DynamoDB

---

### Phase 4: Integration Pattern Selection

**Who**: CMO Administrator
**Where**: Self-Service Portal → Integration Patterns page
**Time**: 10–30 minutes (depends on pattern)

#### Pattern 1: Native Database Connectors

**Best for**: CMOs with modern database platforms

| Supported Platform | Connection Type |
|-------------------|-----------------|
| Snowflake | Native connector |
| Oracle | JDBC |
| SQL Server | JDBC |
| PostgreSQL | JDBC |
| SAP HANA | JDBC |
| Databricks | Native connector |

**CMO provides**: Connection URL, username, password, database, schema, table/query
**How it works**: Merck pulls data directly from the CMO's database on the delivery schedule

#### Pattern 2: Secure File Transfer (SFTP)

**Best for**: CMOs with legacy systems or file-based exports

**CMO provides**: Nothing — credentials are auto-provisioned
**System provides**: SFTP hostname, username, password
**Supported formats**: CSV, JSON, Parquet
**How it works**: CMO pushes files to SFTP → S3 event triggers processing → files validated and moved to Bronze

#### Pattern 3: AI-Powered Unstructured Data

**Best for**: CMOs sharing PDFs, scanned documents, or images

**CMO provides**: Document type selection, confidence threshold (default 85%)
**Supported formats**: PDF, PNG, JPEG, TIFF
**How it works**: Documents uploaded → Textract extracts text/tables/forms → Rekognition processes images → structured JSON written to Bronze
**Manual review**: Records below confidence threshold are flagged for human review

**Output**: Pattern configured, ready for activation

---

### Phase 5: Pipeline Activation

**Who**: CMO Administrator
**Where**: Self-Service Portal → Pipelines page
**Time**: 2–5 minutes (automated)

| Step | What Happens | AWS Service |
|------|-------------|-------------|
| 1 | Contract validated (schema, rules, SLAs) | Lambda |
| 2 | Integration pattern determined | Step Functions |
| 3 | Pattern resources configured | Lambda + Glue/Transfer Family/Textract |
| 4 | Glue ETL jobs created | Glue |
| 5 | S3 paths configured: `s3://bucket/{layer}/{cmo-id}/{data-domain}/` | S3 |
| 6 | CloudWatch monitoring set up | CloudWatch |
| 7 | Pipeline status updated to ACTIVE | DynamoDB |

**Retry logic**: Each step retries 3 times with exponential backoff (1s → 2s → 4s). If all retries fail, the CMO receives an error notification with actionable guidance.

**Pipeline statuses**:
- **Draft** — Contract created, not yet activated
- **Deploying** — Step Functions workflow in progress
- **Active** — Pipeline running, data flowing
- **Failed** — Deployment failed (see error details)
- **Suspended** — Pipeline paused

**Output**: Active pipeline, data flowing through Bronze → Silver → Gold

---

### Phase 6: Data Ingestion (Ongoing)

Once the pipeline is active, data flows according to the delivery schedule:

| Pattern | Trigger | Flow |
|---------|---------|------|
| Pattern 1 | Scheduled (cron) or real-time | Glue connector extracts from CMO DB → Parquet → Bronze |
| Pattern 2 | CMO uploads file to SFTP | S3 event → Lambda validates format → Bronze |
| Pattern 3 | CMO uploads document | Lambda → Textract/Rekognition → JSON → Bronze |

All data lands in Bronze as immutable Parquet files, partitioned by date: `year=YYYY/month=MM/day=DD/`

---

### Phase 7: Automated Processing (Ongoing)

```
Bronze (Raw)                Silver (Validated)           Gold (Business-Ready)
─────────────               ──────────────────           ─────────────────────
Raw Parquet files    ──►    Schema validation     ──►    Daily aggregations
Date-partitioned            Quality rules (DQDL)         Weekly summaries
Immutable                   Deduplication                Monthly trends
                            Type conversions             CMO performance
                            Null handling                Denormalized for queries
                                │
                                ├── PASS → Silver layer
                                │          Glue Catalog registered
                                │          Lake Formation permissions
                                │          PII fields masked (Macie)
                                │
                                └── FAIL → Quarantine
                                           s3://bucket/bronze/quarantine/{contract-id}/{timestamp}/
                                           SNS notification sent
```

**Quality checks run on every batch**:
- Completeness (are required fields present?)
- Accuracy (do values match expected patterns?)
- Uniqueness (are there duplicates?)
- Consistency (do cross-field rules hold?)

---

### Phase 8: Monitoring & Alerting (Ongoing)

| Metric | Tracked By | Alert Threshold |
|--------|-----------|-----------------|
| Pipeline execution time | CloudWatch | Warning at 80% of SLA, Critical at 100% |
| Data quality score | CloudWatch | Warning < 95%, Critical < 90% |
| Pipeline success rate | CloudWatch | Warning < 99%, Critical < 95% |
| Records processed | CloudWatch | — |
| SLA timeliness | CloudWatch | Breach of max delay hours |
| SLA availability | CloudWatch | Below uptime percentage |

**Alert channels**: SNS topics → email/PagerDuty/Slack
- `pharma-data-exchange-critical-alerts` — Pager/on-call
- `pharma-data-exchange-warning-alerts` — Dev team
- `pharma-data-exchange-sla-breach` — SLA team

**Dashboard**: CloudWatch dashboard `PharmaDataExchangeHub` shows real-time compliance trends per CMO.

---

### Phase 9: Data Consumption (Ongoing)

**Who**: Merck quality teams, business analysts, data engineers

| Channel | Technology | Access Control |
|---------|-----------|---------------|
| QuickSight Dashboards | QuickSight → Athena → Gold layer | Row-level security via Lake Formation |
| Natural Language Query | Portal → Bedrock (Claude 3) → Athena | Lake Formation permissions enforced |
| Direct SQL | Athena → Silver/Gold layers | Lake Formation permissions enforced |
| Programmatic | Athena API / Glue Data Catalog | IAM + Lake Formation |

**Access control**: Every query passes through Lake Formation, which enforces:
- Row-level filtering: Users only see data from authorized CMOs (`WHERE cmo_id = '{cmo_id}'`)
- Column-level filtering: Sensitive columns hidden based on user role
- PII masking: Fields marked as PII are hashed/redacted

---

## Security & Compliance Throughout

| Requirement | How It's Enforced |
|-------------|------------------|
| Data encryption at rest | KMS with CMO-specific customer-managed keys |
| Data encryption in transit | TLS/SSL enforced on all S3 buckets and APIs |
| Audit trail | CloudTrail logs every action (7-year retention, immutable S3) |
| Electronic signatures | Captured for critical actions (21 CFR Part 11) |
| Data isolation | Lake Formation row/column filters per CMO |
| PII protection | Amazon Macie detection + automatic masking |
| Least privilege | CMO-specific IAM roles scoped to their resources |
| Credential security | All credentials in Secrets Manager, never in code/logs |

---

## Timeline Summary

| Phase | Duration | Who Drives |
|-------|----------|-----------|
| 1. Registration | 5 min | CMO |
| 2. Schema Definition | 15–30 min | CMO |
| 3. Contract Creation | 30–60 min | CMO |
| 4. Pattern Selection | 10–30 min | CMO |
| 5. Pipeline Activation | 2–5 min | Automated |
| 6–9. Data Flow & Consumption | Ongoing | Automated + Merck |
| **Total onboarding** | **~1–2 hours** (active work) | |

The 1–4 week estimate accounts for the CMO's internal preparation time (gathering connection details, preparing sample data, defining quality rules with their data team) — not platform wait time.
