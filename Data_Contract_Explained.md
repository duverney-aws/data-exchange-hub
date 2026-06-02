# Data Contract Explained

## What is a Data Contract?

A **data contract** is a formal agreement between the data producer (CMO) and data consumer (Merck) that defines:

1. **What data** will be shared (schema, fields, data types)
2. **How often** data will be delivered (frequency, schedule)
3. **Quality expectations** (completeness, accuracy, timeliness)
4. **SLAs** (service level agreements - uptime, latency)
5. **Governance** (who can access, retention policies, compliance)

Think of it as a "terms of service" for data exchange.

## Why Data Contracts Matter

### Without Data Contracts:
- ❌ CMO changes schema → Merck pipelines break
- ❌ No clear ownership when data quality issues occur
- ❌ Unclear expectations on delivery frequency
- ❌ No accountability for SLA violations

### With Data Contracts:
- ✅ Schema changes are versioned and communicated
- ✅ Clear ownership and escalation paths
- ✅ Automated validation against agreed standards
- ✅ Measurable SLAs with alerts

## How It Works in the Platform

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  STEP 1: CMO ONBOARDS VIA PORTAL                               │
│                                                                 │
│  CMO fills out form:                                           │
│  • Company name: "Alpha Pharma CMO"                            │
│  • Data type: "Batch Records"                                  │
│  • Delivery frequency: "Daily at 2 AM UTC"                     │
│  • Schema: Upload JSON schema or select template              │
│  • Quality rules: "No null values in batch_id"                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  STEP 2: LAMBDA CREATES DATA CONTRACT                          │
│                                                                 │
│  Lambda function:                                              │
│  1. Validates schema against Glue Schema Registry              │
│  2. Generates unique contract ID                               │
│  3. Stores contract in DynamoDB                                │
│  4. Creates IAM policies based on access rules                 │
│  5. Deploys Step Functions workflow                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  STEP 3: DATA INGESTION ENFORCES CONTRACT                      │
│                                                                 │
│  When data arrives:                                            │
│  1. Glue ETL reads contract from DynamoDB                      │
│  2. Validates schema matches registered version                │
│  3. Runs quality checks defined in contract                    │
│  4. Measures SLA compliance (timeliness)                       │
│  5. Alerts if contract violated                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  STEP 4: MONITORING & GOVERNANCE                               │
│                                                                 │
│  CloudWatch dashboard shows:                                   │
│  • Contract compliance rate (% of deliveries on time)          │
│  • Schema validation pass rate                                 │
│  • Quality check failures                                      │
│  • SLA violations with alerts                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Data Contract Storage (DynamoDB)

Contracts are stored in DynamoDB with this structure:

**Primary Key:** `contract_id` (unique identifier)
**Sort Key:** `version` (for versioning)

**Attributes:**
- CMO metadata (name, contact, legal entity)
- Schema reference (pointer to Glue Schema Registry)
- Delivery schedule (frequency, time, timezone)
- Quality rules (validation logic)
- SLAs (uptime, latency, completeness)
- Access policies (who can read this data)
- Retention policies (how long to keep data)
- Status (active, suspended, terminated)

## Schema Registry Integration

The **schema** itself is stored in **AWS Glue Schema Registry**, not DynamoDB.

**Why separate?**
- Schema Registry provides versioning, compatibility checks, and integration with Glue ETL
- DynamoDB stores the business rules and SLAs
- Contract references the schema by ID

```
DynamoDB Contract:
{
  "contract_id": "CMO-ALPHA-001",
  "schema_registry_id": "arn:aws:glue:us-east-1:123456789:schema/batch-records/v1.2",
  "quality_rules": [...],
  "sla": {...}
}

Glue Schema Registry:
{
  "schema_id": "arn:aws:glue:us-east-1:123456789:schema/batch-records/v1.2",
  "schema_definition": { JSON schema },
  "compatibility": "BACKWARD"
}
```

## Contract Lifecycle

1. **Draft** → CMO fills out portal, contract created but not active
2. **Review** → Merck quality team reviews and approves
3. **Active** → Data ingestion begins, contract enforced
4. **Modified** → CMO requests change, new version created
5. **Suspended** → Temporary pause (e.g., CMO maintenance)
6. **Terminated** → Contract ended, data access revoked

## Example Scenarios

### Scenario 1: Schema Change
- CMO wants to add new field "operator_name" to batch records
- CMO submits change request via portal
- Lambda creates new contract version (v1.2 → v1.3)
- Glue Schema Registry validates backward compatibility
- If compatible, auto-approved; if breaking change, requires Merck approval
- Old data still readable, new data uses new schema

### Scenario 2: SLA Violation
- Contract says: "Data delivered daily by 2 AM UTC"
- EventBridge rule checks at 3 AM UTC
- No data received → CloudWatch alarm triggered
- SNS notification sent to CMO contact and Merck quality team
- Incident logged in DynamoDB contract history

### Scenario 3: Quality Failure
- Contract says: "batch_id cannot be null"
- Data arrives with null batch_id
- Glue Data Quality detects violation
- Data moved to quarantine S3 bucket
- CMO notified via email
- Data not promoted to Silver layer until fixed

---

# Data Contract Template (JSON)

Below is a complete template showing what gets stored in DynamoDB.

```json
{
  "contract_id": "CMO-ALPHA-BATCH-001",
  "version": "1.2",
  "status": "active",
  "created_date": "2024-01-15T10:30:00Z",
  "last_modified": "2024-02-20T14:22:00Z",
  "effective_date": "2024-02-21T00:00:00Z",
  
  "cmo_info": {
    "cmo_id": "CMO-ALPHA",
    "cmo_name": "Alpha Pharma Manufacturing",
    "legal_entity": "Alpha Pharma Inc.",
    "contact_email": "data-ops@alphapharma.com",
    "contact_phone": "+1-555-0100",
    "technical_contact": "john.smith@alphapharma.com"
  },
  
  "data_product": {
    "name": "Batch Manufacturing Records",
    "description": "Daily batch production data including yields, parameters, and quality metrics",
    "domain": "Manufacturing",
    "classification": "Confidential",
    "data_type": "structured"
  },
  
  "schema": {
    "schema_registry_arn": "arn:aws:glue:us-east-1:123456789012:schema/batch-records/v1.2",
    "schema_name": "batch-records",
    "schema_version": "1.2",
    "format": "JSON",
    "compatibility_mode": "BACKWARD",
    "fields_count": 25,
    "sample_record_s3": "s3://contracts/CMO-ALPHA-001/sample.json"
  },
  
  "delivery": {
    "pattern": "pattern_1_glue_connector",
    "frequency": "daily",
    "schedule": "0 2 * * *",
    "timezone": "UTC",
    "delivery_method": "push",
    "target_location": "s3://data-lake-bronze/cmo-alpha/batch-records/",
    "file_format": "parquet",
    "compression": "snappy",
    "partitioning": ["year", "month", "day"],
    "expected_volume_mb": 500,
    "expected_record_count": 10000
  },
  
  "quality_rules": [
    {
      "rule_id": "QR-001",
      "rule_name": "batch_id_not_null",
      "rule_type": "completeness",
      "severity": "critical",
      "description": "Batch ID must not be null",
      "validation": "batch_id IS NOT NULL",
      "action_on_failure": "reject"
    },
    {
      "rule_id": "QR-002",
      "rule_name": "yield_percentage_range",
      "rule_type": "validity",
      "severity": "high",
      "description": "Yield percentage must be between 0 and 100",
      "validation": "yield_percentage >= 0 AND yield_percentage <= 100",
      "action_on_failure": "quarantine"
    },
    {
      "rule_id": "QR-003",
      "rule_name": "timestamp_freshness",
      "rule_type": "timeliness",
      "severity": "medium",
      "description": "Batch timestamp must be within last 48 hours",
      "validation": "batch_timestamp >= CURRENT_DATE - INTERVAL '48 HOURS'",
      "action_on_failure": "warn"
    },
    {
      "rule_id": "QR-004",
      "rule_name": "product_code_format",
      "rule_type": "format",
      "severity": "high",
      "description": "Product code must match pattern PRD-XXXX-XXXX",
      "validation": "REGEXP_LIKE(product_code, '^PRD-[0-9]{4}-[0-9]{4}$')",
      "action_on_failure": "quarantine"
    },
    {
      "rule_id": "QR-005",
      "rule_name": "duplicate_batch_check",
      "rule_type": "uniqueness",
      "severity": "critical",
      "description": "Batch ID must be unique within delivery",
      "validation": "COUNT(DISTINCT batch_id) = COUNT(*)",
      "action_on_failure": "reject"
    }
  ],
  
  "sla": {
    "availability": {
      "uptime_percentage": 99.5,
      "measurement_period": "monthly",
      "allowed_downtime_hours": 3.6
    },
    "timeliness": {
      "delivery_window_hours": 2,
      "late_delivery_threshold_minutes": 30,
      "max_late_deliveries_per_month": 2
    },
    "completeness": {
      "min_completeness_percentage": 99.0,
      "critical_fields": ["batch_id", "product_code", "batch_timestamp", "yield_percentage"]
    },
    "accuracy": {
      "max_error_rate_percentage": 0.5,
      "validation_sample_size": 100
    }
  },
  
  "governance": {
    "data_owner": "Merck Quality Operations",
    "data_steward": "jane.doe@merck.com",
    "access_control": {
      "read_access": ["merck-quality-team", "merck-analytics-team"],
      "write_access": ["cmo-alpha-service-account"],
      "admin_access": ["merck-data-platform-admin"]
    },
    "retention": {
      "bronze_layer_days": 90,
      "silver_layer_days": 1825,
      "gold_layer_days": 3650,
      "archive_after_days": 3650,
      "delete_after_days": 7300
    },
    "compliance": {
      "regulations": ["21 CFR Part 11", "GDPR", "GxP"],
      "data_classification": "Confidential",
      "encryption_required": true,
      "audit_logging_required": true,
      "pii_present": false
    },
    "lineage_tracking": true,
    "change_management": {
      "approval_required": true,
      "approvers": ["merck-quality-lead", "merck-data-governance"],
      "notification_list": ["data-platform-team@merck.com"]
    }
  },
  
  "monitoring": {
    "cloudwatch_dashboard": "https://console.aws.amazon.com/cloudwatch/dashboards/CMO-ALPHA-001",
    "alerts": [
      {
        "alert_id": "ALT-001",
        "alert_name": "Late Delivery",
        "condition": "delivery_time > scheduled_time + 30 minutes",
        "severity": "high",
        "notification_channels": ["email", "sns"],
        "recipients": ["data-ops@alphapharma.com", "merck-quality-team@merck.com"]
      },
      {
        "alert_id": "ALT-002",
        "alert_name": "Quality Check Failure",
        "condition": "quality_check_pass_rate < 95%",
        "severity": "critical",
        "notification_channels": ["email", "sns", "pagerduty"],
        "recipients": ["data-ops@alphapharma.com", "merck-quality-lead@merck.com"]
      },
      {
        "alert_id": "ALT-003",
        "alert_name": "Schema Validation Failure",
        "condition": "schema_validation_failed = true",
        "severity": "critical",
        "notification_channels": ["email", "sns"],
        "recipients": ["john.smith@alphapharma.com", "data-platform-team@merck.com"]
      }
    ],
    "metrics": {
      "delivery_success_rate": true,
      "quality_pass_rate": true,
      "sla_compliance_rate": true,
      "data_volume_trend": true,
      "processing_duration": true
    }
  },
  
  "cost_allocation": {
    "cost_center": "CMO-ALPHA",
    "billing_account": "123456789012",
    "tags": {
      "Environment": "Production",
      "CMO": "Alpha-Pharma",
      "DataProduct": "Batch-Records",
      "CostCenter": "Manufacturing-Ops"
    }
  },
  
  "metadata": {
    "contract_template_version": "2.0",
    "created_by": "john.smith@alphapharma.com",
    "approved_by": "jane.doe@merck.com",
    "approval_date": "2024-02-20T16:00:00Z",
    "next_review_date": "2024-08-20T00:00:00Z",
    "review_frequency_months": 6,
    "change_history": [
      {
        "version": "1.0",
        "date": "2024-01-15T10:30:00Z",
        "changed_by": "john.smith@alphapharma.com",
        "changes": "Initial contract creation"
      },
      {
        "version": "1.1",
        "date": "2024-02-01T09:15:00Z",
        "changed_by": "john.smith@alphapharma.com",
        "changes": "Added quality rule QR-005 for duplicate checking"
      },
      {
        "version": "1.2",
        "date": "2024-02-20T14:22:00Z",
        "changed_by": "john.smith@alphapharma.com",
        "changes": "Updated schema to v1.2, added operator_name field"
      }
    ]
  }
}
```

---

# How to Use This Template

## For CMOs (During Onboarding):
1. Fill out the portal form
2. Upload sample data file
3. Define quality expectations
4. Specify delivery schedule
5. Submit for Merck approval

## For Merck (Contract Management):
1. Review submitted contract
2. Validate schema compatibility
3. Approve or request changes
4. Monitor compliance via dashboard
5. Renew/update every 6 months

## For the Platform (Automated):
1. Store contract in DynamoDB
2. Register schema in Glue Schema Registry
3. Create IAM policies from access_control
4. Deploy Glue ETL with quality_rules
5. Setup CloudWatch alarms from monitoring.alerts
6. Enforce SLAs via EventBridge rules

---

# Benefits of Data Contracts

| Benefit | Description |
|---------|-------------|
| **Prevents Breaking Changes** | Schema changes are versioned and validated |
| **Clear Accountability** | SLA violations trigger alerts to responsible parties |
| **Automated Quality** | Quality rules enforced automatically, no manual checks |
| **Self-Service** | CMOs onboard without Merck IT involvement |
| **Auditability** | All changes tracked in change_history |
| **Cost Transparency** | Cost allocation tags enable chargeback |
| **Compliance** | Retention and encryption policies enforced |

---

# Next Steps

1. **Create DynamoDB table** with contract schema
2. **Build Amplify portal** with contract form
3. **Implement Lambda** to validate and store contracts
4. **Integrate with Glue Schema Registry** for schema validation
5. **Deploy Glue ETL** that reads contracts and enforces rules
6. **Setup CloudWatch dashboards** for contract monitoring
