# AWS Glue Schema Registry Explained

## Great Questions! Let's Clarify

### Question 1: If CMO has a modern database, do we still need Schema Registry?

**Short Answer:** YES - but for a different reason than you might think.

---

## Why Schema Registry is Needed (Even with Modern Databases)

### The Problem We're Solving

```
┌─────────────────────────────────────────────────────────────────┐
│  WITHOUT SCHEMA REGISTRY                                        │
│                                                                 │
│  CMO's Oracle DB has schema:                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Table: BATCH_RECORDS                                      │  │
│  │ - BATCH_ID (VARCHAR2)                                     │  │
│  │ - PRODUCT_CODE (VARCHAR2)                                 │  │
│  │ - YIELD_PCT (NUMBER)                                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  One day, CMO adds a new column:                               │
│  - OPERATOR_NAME (VARCHAR2)                                    │
│                                                                 │
│  ❌ Merck's pipeline breaks (unexpected column)                │
│  ❌ No notification to Merck                                   │
│  ❌ No version history                                         │
│  ❌ No compatibility check                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  WITH SCHEMA REGISTRY                                           │
│                                                                 │
│  CMO's Oracle DB has schema (same as above)                    │
│                                                                 │
│  BUT: Schema is REGISTERED in Glue Schema Registry:            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Schema Name: cmo-alpha-batch-records                      │  │
│  │ Version: 1.0                                              │  │
│  │ Compatibility: BACKWARD                                   │  │
│  │ Fields: [batch_id, product_code, yield_pct]              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  CMO wants to add OPERATOR_NAME:                               │
│  1. CMO submits schema change via portal                       │
│  2. Schema Registry validates compatibility                    │
│  3. If compatible → Auto-approve, create version 1.1           │
│  4. If breaking change → Requires Merck approval               │
│  5. Merck notified of change                                   │
│  6. Pipeline updated to handle new field                       │
│                                                                 │
│  ✅ No pipeline breakage                                       │
│  ✅ Merck notified automatically                               │
│  ✅ Version history maintained                                 │
│  ✅ Compatibility enforced                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## What Schema Registry Actually Does

### It's NOT a replacement for the database schema
### It's a CONTRACT and VERSION CONTROL system

Think of it like this:

| Component | Purpose | Analogy |
|-----------|---------|---------|
| **CMO's Database Schema** | Defines structure in Oracle/SQL Server | The actual product |
| **Glue Schema Registry** | Defines what Merck expects to receive | The contract/specification |
| **Data Contract (DynamoDB)** | Business rules, SLAs, quality checks | Terms of service |

---

## Schema Registry Use Cases

### Use Case 1: Structured Data from Database (Pattern 1)

```
┌─────────────────────────────────────────────────────────────────┐
│  CMO: Alpha Pharma                                              │
│  Source: Oracle Database                                        │
│  Table: BATCH_RECORDS                                           │
│                                                                 │
│  STEP 1: CMO Onboarding                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Portal asks: "Upload sample data or provide schema"      │  │
│  │                                                           │  │
│  │ CMO uploads: sample_batch_records.csv                    │  │
│  │ OR                                                        │  │
│  │ CMO provides: Oracle table DDL                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Lambda extracts schema:                                  │  │
│  │ {                                                        │  │
│  │   "type": "record",                                      │  │
│  │   "name": "BatchRecord",                                 │  │
│  │   "fields": [                                            │  │
│  │     {"name": "batch_id", "type": "string"},              │  │
│  │     {"name": "product_code", "type": "string"},          │  │
│  │     {"name": "yield_pct", "type": "double"}              │  │
│  │   ]                                                      │  │
│  │ }                                                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Stored in Glue Schema Registry:                          │  │
│  │ - Schema Name: cmo-alpha-batch-records                   │  │
│  │ - Version: 1.0                                           │  │
│  │ - Format: AVRO                                           │  │
│  │ - Compatibility: BACKWARD                                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  STEP 2: Data Ingestion (Daily)                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Glue ETL Job:                                            │  │
│  │ 1. Connects to Oracle via JDBC                           │  │
│  │ 2. Reads BATCH_RECORDS table                             │  │
│  │ 3. Fetches schema from Registry (version 1.0)            │  │
│  │ 4. Validates data matches schema                         │  │
│  │ 5. If mismatch → Alert + Quarantine                      │  │
│  │ 6. If match → Write to Bronze layer                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Point:** Even though Oracle has its own schema, we register it in Glue Schema Registry so we can:
- Track changes over time
- Validate compatibility
- Enforce contracts
- Alert on schema drift

---

### Use Case 2: Unstructured Data (Pattern 3)

**This is where it gets interesting!**

For unstructured data (PDFs, images), Schema Registry stores the **EXTRACTED** schema, not the document structure.

```
┌─────────────────────────────────────────────────────────────────┐
│  CMO: Beta Manufacturing                                        │
│  Source: PDF Batch Records                                      │
│                                                                 │
│  STEP 1: CMO Onboarding                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Portal asks: "Upload sample PDF"                         │  │
│  │                                                           │  │
│  │ CMO uploads: sample_batch_record.pdf                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Lambda sends PDF to Textract:                            │  │
│  │                                                           │  │
│  │ Textract extracts:                                       │  │
│  │ - Batch ID: ABC-12345                                    │  │
│  │ - Product: Aspirin 500mg                                 │  │
│  │ - Yield: 98.5%                                           │  │
│  │ - Manufacturing Date: 2024-01-15                         │  │
│  │ - Operator: John Smith                                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Lambda creates schema for EXTRACTED data:                │  │
│  │ {                                                        │  │
│  │   "type": "record",                                      │  │
│  │   "name": "ExtractedBatchRecord",                        │  │
│  │   "fields": [                                            │  │
│  │     {"name": "batch_id", "type": "string"},              │  │
│  │     {"name": "product", "type": "string"},               │  │
│  │     {"name": "yield_pct", "type": "double"},             │  │
│  │     {"name": "mfg_date", "type": "string"},              │  │
│  │     {"name": "operator", "type": "string"}               │  │
│  │   ]                                                      │  │
│  │ }                                                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Stored in Glue Schema Registry:                          │  │
│  │ - Schema Name: cmo-beta-extracted-batch-records          │  │
│  │ - Version: 1.0                                           │  │
│  │ - Format: JSON                                           │  │
│  │ - Source Type: UNSTRUCTURED (PDF)                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  STEP 2: Data Ingestion (Daily)                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Lambda/Glue Job:                                         │  │
│  │ 1. Receives PDF from CMO                                 │  │
│  │ 2. Sends to Textract for extraction                      │  │
│  │ 3. Fetches schema from Registry (version 1.0)            │  │
│  │ 4. Validates extracted data matches schema               │  │
│  │ 5. If fields missing → Alert                             │  │
│  │ 6. If match → Write JSON to Bronze layer                 │  │
│  │ 7. Store original PDF in S3 for audit                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Point:** For unstructured data, Schema Registry stores the schema of the **extracted/structured output**, not the PDF/image itself.

---

## Schema Registry for Different Data Types

| Data Type | What Gets Registered | Example |
|-----------|---------------------|---------|
| **Structured (Database)** | Table schema from source DB | Oracle table DDL → AVRO schema |
| **Structured (Files)** | File format schema | CSV columns → JSON schema |
| **Unstructured (PDF)** | Extracted fields schema | Textract output → JSON schema |
| **Unstructured (Images)** | Metadata + labels schema | Rekognition output → JSON schema |
| **IoT/Sensors** | Time-series data schema | Sensor readings → JSON schema |

---

## Real Example: Schema Evolution

### Scenario: CMO wants to add a new field

**Initial Schema (v1.0):**
```json
{
  "type": "record",
  "name": "BatchRecord",
  "namespace": "com.merck.cmo.alpha",
  "fields": [
    {"name": "batch_id", "type": "string"},
    {"name": "product_code", "type": "string"},
    {"name": "yield_pct", "type": "double"}
  ]
}
```

**CMO wants to add operator_name:**

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: CMO submits change via portal                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ "I want to add field: operator_name (string)"            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│  STEP 2: Schema Registry validates compatibility               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Compatibility Mode: BACKWARD                             │  │
│  │                                                           │  │
│  │ Check: Can old consumers read new data?                  │  │
│  │ - Adding optional field: ✅ COMPATIBLE                   │  │
│  │ - Removing field: ❌ BREAKING CHANGE                     │  │
│  │ - Changing field type: ❌ BREAKING CHANGE                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          │                                      │
│                          ▼                                      │
│  STEP 3: Auto-approve or require approval                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Result: COMPATIBLE                                       │  │
│  │ Action: Auto-approve                                     │  │
│  │ New Version: 1.1                                         │  │
│  │ Notification: Email to Merck data team                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**New Schema (v1.1):**
```json
{
  "type": "record",
  "name": "BatchRecord",
  "namespace": "com.merck.cmo.alpha",
  "fields": [
    {"name": "batch_id", "type": "string"},
    {"name": "product_code", "type": "string"},
    {"name": "yield_pct", "type": "double"},
    {"name": "operator_name", "type": ["null", "string"], "default": null}
  ]
}
```

**Result:**
- Old data (without operator_name) still valid
- New data (with operator_name) accepted
- Merck's pipelines continue working
- No downtime

---

## Schema Registry vs Data Contract

### They Work Together But Serve Different Purposes

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  GLUE SCHEMA REGISTRY                                           │
│  (Technical Schema)                                             │
│                                                                 │
│  Stores:                                                        │
│  - Field names and data types                                  │
│  - Schema versions                                             │
│  - Compatibility rules                                         │
│                                                                 │
│  Example:                                                       │
│  {                                                              │
│    "fields": [                                                  │
│      {"name": "batch_id", "type": "string"},                   │
│      {"name": "yield_pct", "type": "double"}                   │
│    ]                                                            │
│  }                                                              │
│                                                                 │
│  Answers: "What fields exist and what are their types?"        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ Referenced by
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  DATA CONTRACT (DynamoDB)                                       │
│  (Business Rules)                                               │
│                                                                 │
│  Stores:                                                        │
│  - Quality rules                                               │
│  - SLAs                                                        │
│  - Delivery schedule                                           │
│  - Access policies                                             │
│  - Reference to schema                                         │
│                                                                 │
│  Example:                                                       │
│  {                                                              │
│    "schema_arn": "arn:aws:glue:schema/batch-records/v1.0",     │
│    "quality_rules": [                                           │
│      "batch_id IS NOT NULL",                                   │
│      "yield_pct BETWEEN 0 AND 100"                             │
│    ],                                                           │
│    "delivery_schedule": "daily at 2 AM UTC"                    │
│  }                                                              │
│                                                                 │
│  Answers: "What are the business rules and expectations?"      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## When Schema Registry is NOT Needed

### Scenario: CMO sends completely unstructured data with no extraction

Example: CMO sends training videos, equipment manuals (PDFs that won't be extracted)

```
CMO → Transfer Family (SFTP) → S3 → No processing → Just storage

In this case:
- No schema needed (it's just files)
- No Schema Registry entry
- Data Contract still exists (for SLAs, retention, access)
```

---

## Summary

### Question 1: Do we need Schema Registry if CMO has modern database?

**YES**, because:
1. ✅ Tracks schema changes over time (version control)
2. ✅ Validates compatibility before breaking pipelines
3. ✅ Enforces contracts between CMO and Merck
4. ✅ Enables automated schema evolution
5. ✅ Provides single source of truth for expected data structure

**The CMO's database schema is the source, Schema Registry is the contract.**

### Question 2: How does Schema Registry work for unstructured data?

**It stores the schema of the EXTRACTED data, not the document itself:**

| Source | What's Registered | Example |
|--------|------------------|---------|
| PDF | Extracted fields from Textract | `{batch_id, product, yield_pct}` |
| Image | Metadata + Rekognition labels | `{image_id, defect_detected, confidence}` |
| IoT | Sensor reading structure | `{sensor_id, timestamp, temperature, humidity}` |

**Key Insight:** For unstructured data, Schema Registry ensures the **output** of AI processing (Textract/Rekognition) is consistent and validated.

---

## Recommendation for Presentation

**Simplify the message:**

"Schema Registry is like GitHub for data schemas - it tracks versions, prevents breaking changes, and ensures everyone agrees on what the data should look like, whether it comes from a database, a PDF, or an image."
