# Pharma Manufacturing Data Exchange — Requirements & Gap Analysis

## Platform Purpose

**This platform facilitates data transfer from CMO to Merck.** It is not a batch release system. Batch release decisions happen in Merck's existing QMS/ERP (e.g., Veeva Vault, SAP QM). This platform's job is to ensure that data arrives reliably, on time, in the right place, and in a usable format — so those downstream systems and teams have what they need.

---

## The Real Engagement Model

**Direction of data flow:** CMO → Merck

The CMO manufactures on behalf of Merck and must submit manufacturing data back to Merck per the terms of their **Quality Agreement** — which defines what data is required, in what format, and within what SLA per batch.

**The unit of work is the BATCH (lot number).** Merck's QA team needs to find all data associated with a specific batch. Without batch context, the data lake is just files.

---

## Data the CMO Must Submit Per Batch

| Data Type | Format | Source System | Typical SLA |
|-----------|--------|---------------|-------------|
| Batch Manufacturing Record (BMR) | PDF / structured | MES (Rockwell, Siemens) | Within 5 days of batch completion |
| Certificate of Analysis (CoA) | PDF / structured | LIMS (LabWare, STARLIMS) | Within 5 days of batch completion |
| In-process test results | Structured (CSV/JSON) | LIMS | Same day |
| Deviation reports | PDF / structured | QMS (Veeva, MasterControl) | Within 2 days of occurrence |
| Environmental monitoring data | Structured | EMS / LIMS | Daily during manufacturing |
| Equipment logs / calibration records | PDF / structured | CMMS / MES | On request |
| Yield / reconciliation data | Structured | ERP (SAP) | Within 5 days of batch completion |

---

## Platform Requirements

### R1 — Batch/Lot as a Tag on Every Submission ❌ NOT YET BUILT
Every data submission must carry a **batch/lot number** and **product** so Merck can find all data for a specific batch in the data lake.
- A batch record has: `batchId`, `lotNumber`, `productId`, `cmoId`, `manufacturingDate`
- All files and records ingested must link to a batch
- S3 path structure: `/{layer}/{cmoId}/{productId}/{batchId}/{dataType}/`
- Pattern 2 (SFTP): enforce folder structure `/{cmoId}/{productId}/{batchId}/`
- Pattern 1 (Native Connectors): Glue job extracts lot number from source data
- Pattern 3 (Unstructured AI): Textract extracts lot number from PDF

### R2 — Product/Material Master ❌ NOT YET BUILT
Data contracts must be tied to a specific drug product.
- A product has: `productId`, `productName`, `strength`, `dosageForm`
- A CMO can manufacture multiple products for Merck
- A data contract covers: "CMO Alpha manufactures Product X and must submit these data elements per batch"

### R3 — Data Contract Maps to Quality Agreement ⚠️ PARTIALLY BUILT
The current contract is a technical schema contract. It also needs:
- Which product(s) it covers (`productId`)
- Which data elements are required per batch (from the table above)
- SLA per data element (e.g., CoA within 5 business days of batch completion)

### R4 — Completeness & SLA Tracking ❌ NOT YET BUILT
Merck needs to know: *Did all required data for Batch X arrive? Was it on time?*
- Per-batch completeness check: which required data elements have arrived vs. are missing
- SLA tracking: flag data elements that are overdue per the contract
- Dashboard view: batches with missing or overdue submissions
- Alerts: notify CMO and Merck when an SLA is at risk or breached

---

## What We Have vs. What We Need

| Capability | Current State | Required State |
|------------|--------------|----------------|
| CMO registration & onboarding | ✅ Built | ✅ Sufficient |
| Contract approval workflow | ✅ Built | ⚠️ Add product + SLA fields |
| Schema registry & validation | ✅ Built | ✅ Sufficient |
| Data ingestion (3 patterns) | ✅ Built | ⚠️ Add batch/lot tagging |
| Medallion data lake | ✅ Built | ⚠️ Add batch partitioning to S3 paths |
| Audit trail (CloudTrail) | ✅ Built | ✅ Sufficient |
| Natural language query | ✅ Built | ⚠️ More useful once batch context exists |
| **Batch/lot tagging on submissions** | ❌ Missing | ❌ Must build |
| **Product/material master** | ❌ Missing | ❌ Must build |
| **Completeness check per batch** | ❌ Missing | ❌ Must build |
| **SLA tracking per data element** | ❌ Missing | ❌ Must build |

## Out of Scope
- Batch release decisions (belongs in Merck's QMS/ERP)
- QA review queue / approve/reject workflow
- Deviation management
- Change control

---

## Priority Build Order

1. **Product master** — lightweight DynamoDB table; prerequisite for batch tagging
2. **Batch entity** — DynamoDB table linking lot number + product + CMO
3. **Batch-tagged data submission** — update all 3 patterns to require batch context; update S3 path structure
4. **Contract model update** — add `productId` and per-element SLA fields
5. **Completeness & SLA dashboard** — per-batch view of what arrived, what's missing, what's overdue

---

## Definition of Done

The platform is genuinely useful when a Merck data engineer or QA coordinator can:

1. Search for a batch/lot number and find all associated data in the data lake
2. See which required data elements have arrived and which are missing or overdue
3. Confirm data passed schema validation and quality checks before it reached the Gold layer
4. Trust that the audit trail is complete and 21 CFR Part 11 compliant

The batch release decision itself happens outside this platform.
