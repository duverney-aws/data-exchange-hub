"""
Sample test data for integration tests.

All identifiers use a ``test-`` prefix to avoid collisions with real data.
"""
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# CMO Profiles
# ---------------------------------------------------------------------------

CMO_ALPHA = {
    "cmoId": "cmo-test-alpha",
    "organizationName": "Test Alpha Pharmaceuticals",
    "contactEmail": "admin@test-alpha-pharma.example.com",
    "contactPhone": "+1-555-0100",
    "address": "100 Test Alpha Way, Boston, MA 02101",
    "gxpCertified": True,
    "createdAt": datetime(2024, 1, 15, tzinfo=timezone.utc).isoformat(),
    "status": "active",
}

CMO_BETA = {
    "cmoId": "cmo-test-beta",
    "organizationName": "Test Beta BioManufacturing",
    "contactEmail": "admin@test-beta-bio.example.com",
    "contactPhone": "+1-555-0200",
    "address": "200 Test Beta Blvd, Cambridge, MA 02139",
    "gxpCertified": False,
    "createdAt": datetime(2024, 2, 1, tzinfo=timezone.utc).isoformat(),
    "status": "active",
}

ALL_CMO_PROFILES = [CMO_ALPHA, CMO_BETA]

# ---------------------------------------------------------------------------
# Data Contracts
# ---------------------------------------------------------------------------

CONTRACT_ALPHA_BATCH = {
    "contractId": "CMO-TEST-ALPHA-BATCH-001",
    "cmoId": "cmo-test-alpha",
    "dataDomain": "batch-records",
    "schemaId": "test-alpha-batch-records",
    "schemaVersion": "1.0",
    "qualityRules": [
        {
            "ruleId": "qr-001",
            "ruleName": "batch_id_completeness",
            "ruleType": "completeness",
            "expression": 'Completeness "batch_id" > 0.99',
            "threshold": 99.0,
            "severity": "error",
        },
        {
            "ruleId": "qr-002",
            "ruleName": "batch_id_uniqueness",
            "ruleType": "uniqueness",
            "expression": 'Uniqueness "batch_id" > 0.99',
            "threshold": 99.0,
            "severity": "error",
        },
    ],
    "sla": {
        "timeliness": {"maxDelayHours": 24, "measurementWindow": "daily"},
        "availability": {"uptimePercentage": 99.5, "measurementWindow": "monthly"},
        "quality": {"minQualityScore": 95.0, "measurementWindow": "daily"},
    },
    "deliverySchedule": {"frequency": "daily", "cronExpression": "0 2 * * *", "timezone": "UTC"},
    "governance": {
        "dataClassification": "confidential",
        "retentionYears": 7,
        "allowedUsers": ["merck-quality-team"],
        "allowedGroups": ["pharma-analysts"],
        "piiFields": [],
        "encryptionRequired": True,
    },
    "status": "draft",
    "createdAt": datetime(2024, 1, 20, tzinfo=timezone.utc).isoformat(),
    "updatedAt": datetime(2024, 1, 20, tzinfo=timezone.utc).isoformat(),
}

CONTRACT_BETA_QUALITY = {
    "contractId": "CMO-TEST-BETA-QUALITY-001",
    "cmoId": "cmo-test-beta",
    "dataDomain": "quality-data",
    "schemaId": "test-beta-quality-data",
    "schemaVersion": "1.0",
    "qualityRules": [
        {
            "ruleId": "qr-010",
            "ruleName": "sample_id_completeness",
            "ruleType": "completeness",
            "expression": 'Completeness "sample_id" > 0.99',
            "threshold": 99.0,
            "severity": "error",
        },
    ],
    "sla": {
        "timeliness": {"maxDelayHours": 48, "measurementWindow": "weekly"},
        "availability": {"uptimePercentage": 99.0, "measurementWindow": "monthly"},
        "quality": {"minQualityScore": 90.0, "measurementWindow": "weekly"},
    },
    "deliverySchedule": {"frequency": "weekly", "timezone": "UTC"},
    "governance": {
        "dataClassification": "restricted",
        "retentionYears": 7,
        "allowedUsers": ["merck-quality-team"],
        "allowedGroups": ["pharma-analysts"],
        "piiFields": ["operator_name"],
        "encryptionRequired": True,
    },
    "status": "draft",
    "createdAt": datetime(2024, 2, 5, tzinfo=timezone.utc).isoformat(),
    "updatedAt": datetime(2024, 2, 5, tzinfo=timezone.utc).isoformat(),
}

ALL_CONTRACTS = [CONTRACT_ALPHA_BATCH, CONTRACT_BETA_QUALITY]

# ---------------------------------------------------------------------------
# Pipeline Execution Records
# ---------------------------------------------------------------------------

EXECUTION_ALPHA_SUCCESS = {
    "contractId": "CMO-TEST-ALPHA-BATCH-001",
    "executionTimestamp": 1705363200000,  # 2024-01-16T00:00:00Z
    "executionId": "exec-test-alpha-001",
    "status": "succeeded",
    "recordsProcessed": 1500,
    "recordsFailed": 3,
    "executionTimeSeconds": 120.5,
    "qualityScore": 97.8,
    "metadata": {"source": "integration-test"},
    "ttl": 1705363200000 + (90 * 24 * 60 * 60 * 1000),
}

EXECUTION_BETA_FAILED = {
    "contractId": "CMO-TEST-BETA-QUALITY-001",
    "executionTimestamp": 1706572800000,  # 2024-01-30T00:00:00Z
    "executionId": "exec-test-beta-001",
    "status": "failed",
    "recordsProcessed": 0,
    "recordsFailed": 0,
    "executionTimeSeconds": 5.2,
    "qualityScore": 0.0,
    "errorMessage": "Schema validation failed: missing required field sample_id",
    "metadata": {"source": "integration-test"},
    "ttl": 1706572800000 + (90 * 24 * 60 * 60 * 1000),
}

ALL_EXECUTIONS = [EXECUTION_ALPHA_SUCCESS, EXECUTION_BETA_FAILED]

# ---------------------------------------------------------------------------
# Sample files for integration patterns
# ---------------------------------------------------------------------------

# Pattern 2 (Secure Transfer) – CSV content
SAMPLE_CSV_CONTENT = (
    "batch_id,product_name,manufacture_date,quantity,unit,quality_status\n"
    "BATCH00001,Aspirin 500mg,2024-01-15,10000,tablets,PASS\n"
    "BATCH00002,Ibuprofen 200mg,2024-01-16,5000,tablets,PASS\n"
    "BATCH00003,Amoxicillin 250mg,2024-01-17,8000,capsules,PENDING\n"
)

# Pattern 1 (Native Connector) – JSON records
SAMPLE_JSON_RECORDS = [
    {
        "batch_id": "BATCH00010",
        "product_name": "Metformin 500mg",
        "manufacture_date": "2024-02-01",
        "quantity": 20000,
        "unit": "tablets",
        "quality_status": "PASS",
    },
    {
        "batch_id": "BATCH00011",
        "product_name": "Lisinopril 10mg",
        "manufacture_date": "2024-02-02",
        "quantity": 15000,
        "unit": "tablets",
        "quality_status": "PASS",
    },
]
