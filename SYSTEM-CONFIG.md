# Pharma Data Exchange Hub — System Configuration

Reference document for engineers onboarding to this system. For the running change log, see `MEMORY.md`.

---

## What This System Does

A self-service data integration platform that allows Merck to onboard Contract Manufacturing Organizations (CMOs) and receive pharmaceutical manufacturing data (batch records, certificates of analysis, yield data, etc.) through three integration patterns. Reduces CMO onboarding from 3–6 months to 1–4 weeks.

---

## AWS Account & Region

- **Region:** `us-east-1`
- **Deployment tool:** AWS CDK (Python) — all infrastructure is in `cdk/`

---

## Live URLs

| Resource | URL |
|---|---|
| Frontend portal | https://main.d28qy16znlocxk.amplifyapp.com |
| Contract API | https://4841ud8xri.execute-api.us-east-1.amazonaws.com/prod |
| Schema API | https://ootbzgzcp0.execute-api.us-east-1.amazonaws.com/prod |
| NL Query API | https://u02uvpqhg1.execute-api.us-east-1.amazonaws.com/prod |
| Cognito Hosted UI | https://pharma-data-exchange-portal.auth.us-east-1.amazoncognito.com |

---

## Test Credentials

| Role | Email | Password |
|---|---|---|
| Merck Admin | merck-admin@pharma-exchange.demo | MerckAdmin2026! |
| CMO User (Lonza) | cmo-user@pharma-exchange.demo | CMOUser2026! |

Direct login URL:
```
https://pharma-data-exchange-portal.auth.us-east-1.amazoncognito.com/login?client_id=2eitutbi1gkogudchaudb9rtr4&response_type=code&scope=openid+email+profile&redirect_uri=https://main.d28qy16znlocxk.amplifyapp.com/
```

---

## CloudFormation Stacks (all UPDATE_COMPLETE)

| Stack | Purpose |
|---|---|
| PharmaDataExchangeSecretsStack | Secrets Manager baseline |
| PharmaDataExchangeDatabaseStack | All DynamoDB tables |
| PharmaDataExchangeDataLakeStack | S3 Bronze/Silver/Gold + Athena |
| PharmaDataExchangeMonitoringStack | CloudWatch dashboards + alarms |
| PharmaDataExchangeCognitoStack | User Pool, groups, hosted UI |
| PharmaDataExchangeContractApiStack | Main API — contracts, CMOs, connections, schemas, batches, products, SLA checker |
| PharmaDataExchangeSFTPIngestionStack | AWS Transfer Family SFTP server + auth Lambda + file processor Lambda |
| PharmaDataExchangeSchemaApiStack | Legacy schema infer/register API (superseded by schema_mgmt in ContractApiStack) |
| PharmaDataExchangeNLQueryStack | Bedrock + Athena natural language query API |
| PharmaDataExchangePipelineOrchestrationStack | Step Functions pipeline workflow |
| PharmaDataExchangeSecurityStack | KMS keys, Lake Formation |
| PharmaDataExchangeAuditComplianceStack | CloudTrail audit logging (21 CFR Part 11) |

---

## Cognito

| Setting | Value |
|---|---|
| User Pool ID | `us-east-1_uT79YqQ5x` |
| App Client ID | `2eitutbi1gkogudchaudb9rtr4` |
| Groups | `merck-admins`, `cmo-users` |
| Sign-in alias | Email |
| Custom attribute | `custom:organization` — stores `cmoId` for CMO users; used for server-side data isolation |

All API calls require a Cognito JWT in the `Authorization` header. The backend enforces role and CMO isolation from the JWT claim — never trust client-supplied `cmoId` params for CMO users.

---

## DynamoDB Tables

| Table | Partition Key | GSIs | Purpose |
|---|---|---|---|
| `cmo-profiles` | `cmoId` | — | CMO organization records |
| `data-contracts` | `contractId` | `cmo-contracts-index` (cmoId) | Data contracts with approval workflow |
| `connections` | `connectionId` | `cmo-connections-index` (cmoId) | Integration connections per CMO |
| `schemas` | `schemaId` | `cmo-schemas-index` (cmoId) | Data schemas per CMO |
| `products` | `productId` | `cmo-products-index` (cmoId) | Drug product master |
| `batches` | `batchId` | `cmo-batches-index`, `product-batches-index` | Manufacturing batch submissions |
| `pipeline-executions` | — | — | Step Functions execution tracking (future) |

---

## S3 Buckets

| Bucket | Purpose |
|---|---|
| `pharmadataexchangedatalakes-datalakebucket0256ea8e-dcuncyvlwsel` | Main data lake — Bronze/Silver/Gold layers |
| `pharmadataexchangedatalak-athenaresultsbucket87993-nmt2dvrsz7ad` | Athena query results |
| `pharmadataexchangedatalak-qualityresultsbucket9219-4sp0g4telz6w` | Glue Data Quality results |
| `pharmadataexchangedatalake-auditlogsbucket963995a4-k8ryl35hya2r` | Audit logs |

### Data Lake Path Structure
```
s3://data-lake-bucket/
  bronze/{cmoId}/{dataDomain}/
    incoming/          ← SFTP drop zone (files moved out after processing)
    year=YYYY/month=MM/day=DD/   ← date-partitioned processed files
    manual-review/     ← AI docs with confidence < 85%
    pending-textract/  ← async Textract job metadata
  silver/              ← validated + cleansed (future)
  gold/                ← business-ready aggregated (future)
```

---

## Integration Patterns

### Pattern 1: Native Connectors (`native-connector`)
- CMO submits DB credentials via portal → stored in Secrets Manager at `cmo/{cmoId}/jdbc-{name}`
- Merck reviews (password not shown) → one-click activates → creates AWS Glue JDBC Connection
- Supported DB types: SQL Server, Oracle, PostgreSQL, MySQL, Snowflake, SAP HANA
- Connection methods: Direct, NLB, AWS PrivateLink
- **Status:** Glue Connection provisioned ✅ | Glue Crawler + ETL Job **not yet built** ⚠️

### Pattern 2: Secure Transfer (`secure-transfer`)
- Merck activates connection → generates SFTP username/password → stored in Secrets Manager
- CMO uploads files via any SFTP client (FileZilla, WinSCP, CLI) — no AWS account needed
- SFTP server: `s-89e811043fec4d7d8.server.transfer.us-east-1.amazonaws.com` (port 22)
- Identity provider: custom Lambda (`sftp_auth/handler.py`) — validates against Secrets Manager
- File processor Lambda (`sftp_processor/handler.py`) — S3 event trigger, moves `incoming/` → date-partitioned Bronze
- **Status:** Fully working E2E ✅

### Pattern 3: AI Unstructured (`ai-unstructured`)
- CMO uploads PDF/image via portal → Lambda proxy upload → S3 → AI processor Lambda
- PDF → Textract `start_document_analysis` (async, multi-page) → SNS completion → `textract_result_processor` Lambda
- Image → Rekognition `detect_labels` + `detect_text`
- Confidence ≥ 85% → Bronze layer | < 85% → `manual-review/` prefix
- **Status:** Fully working E2E ✅

---

## Lambda Functions

All Lambdas use `Code.from_asset("lambda_src")` which is a copy of `cdk/` with all shared code.

| Handler | Stack | Purpose |
|---|---|---|
| `lambdas/contract_api/handler.py` | ContractApiStack | CMO CRUD, contract workflow, connections, schemas, products, batches, SLA check, pipeline status |
| `lambdas/connection_api/handler.py` | ContractApiStack | Connection CRUD, activate (SFTP/Glue/AI), configure, upload proxy |
| `lambdas/product_api/handler.py` | ContractApiStack | Product CRUD |
| `lambdas/batch_api/handler.py` | ContractApiStack | Batch CRUD, submit |
| `lambdas/schema_mgmt/handler.py` | ContractApiStack | Schema CRUD, infer from file, register in Glue |
| `lambdas/sla_checker/handler.py` | ContractApiStack | Daily SLA check (EventBridge 6am UTC) + manual trigger |
| `lambdas/sftp_auth/handler.py` | SFTPIngestionStack | Transfer Family custom identity provider |
| `lambdas/sftp_processor/handler.py` | SFTPIngestionStack | S3 event → move incoming file to Bronze |
| `lambdas/ai_processor/handler.py` | ContractApiStack | S3 event → start Textract/Rekognition |
| `lambdas/textract_result_processor/handler.py` | ContractApiStack | SNS → collect Textract results → Bronze |
| `lambdas/nl_query/handler.py` | NLQueryStack | Natural language → SQL via Bedrock + Athena |

---

## API Routes (Contract API)

All routes require `Authorization: <Cognito JWT>` header.

### CMO Management
| Method | Path | Role | Description |
|---|---|---|---|
| POST | /api/cmo/register | merck-admins | Register new CMO org |
| GET | /api/cmo | both | List CMOs |
| PUT | /api/cmo/{cmoId} | merck-admins | Update CMO |
| DELETE | /api/cmo/{cmoId} | merck-admins | Deactivate CMO (soft delete) |
| POST | /api/cmo/{cmoId}/invite | merck-admins | Create Cognito user for CMO rep |

### Contracts
| Method | Path | Role | Description |
|---|---|---|---|
| POST | /api/contract | merck-admins | Create contract |
| GET | /api/contract?cmoId= | both | List contracts (CMO users auto-filtered by JWT) |
| GET | /api/contract/{id} | both | Get contract |
| PUT | /api/contract/{id} | merck-admins | Update contract (draft only) |
| POST | /api/contract/{id}/submit | merck-admins | Submit to CMO for review |
| POST | /api/contract/{id}/accept | cmo-users | CMO accepts |
| POST | /api/contract/{id}/approve | merck-admins | Final approval → active |
| POST | /api/contract/{id}/reject | both | Reject with reason |
| GET | /api/contract/{id}/status | both | Pipeline status (real S3/Glue data) |

### Connections
| Method | Path | Role | Description |
|---|---|---|---|
| POST | /api/connection | merck-admins | Create connection |
| GET | /api/connection?cmoId= | both | List connections |
| GET | /api/connection/{id} | both | Get connection |
| PUT | /api/connection/{id} | merck-admins | Update connection |
| POST | /api/connection/{id}/activate | merck-admins | Provision SFTP creds or Glue connection |
| POST | /api/connection/{id}/configure | cmo-users | CMO submits DB credentials |
| POST | /api/connection/{id}/upload | both | Proxy file upload for AI processing |
| DELETE | /api/connection/{id} | merck-admins | Deactivate connection |

### Schemas, Products, Batches
| Method | Path | Description |
|---|---|---|
| POST/GET | /api/schema | Create / list schemas |
| GET/PUT | /api/schema/{id} | Get / update schema |
| POST | /api/schema/infer | Infer fields from CSV/JSON file |
| POST | /api/schema/{id}/register | Register in Glue Schema Registry |
| POST/GET | /api/product | Create / list products |
| GET/PUT | /api/product/{id} | Get / update product |
| POST/GET | /api/batch | Create / list batches |
| GET/PUT | /api/batch/{id} | Get / update batch |
| POST | /api/batch/{id}/submit | Mark batch fully submitted |
| POST | /api/sla-check | Manual SLA check trigger |

---

## Contract Approval Workflow

```
draft → pending_cmo_review → pending_merck_approval → active
                                                     ↘ rejected
                                                     ↘ suspended
```

---

## Glue Schema Registry

- Registry name: `pharma-data-exchange`
- Schemas registered: `lonza-batch-records`, `lonza-coa-data`, `lonza-yield-data`
- Format: JSON Schema
- Compatibility: BACKWARD

---

## Frontend

- **Framework:** React + TypeScript + Vite
- **UI library:** AWS Cloudscape Design System
- **Auth:** AWS Amplify (`aws-amplify` v6) — Cognito hosted UI redirect flow
- **Amplify App ID:** `d28qy16znlocxk`
- **Deploy script:** `frontend/deploy_amplify.py` — zips `dist/`, creates Amplify deployment, uploads

### Key Pages

| Route | Component | Access |
|---|---|---|
| /dashboard | Dashboard.tsx | Both — completeness + SLA overview |
| /cmos | CMOList.tsx | Merck admin |
| /cmos/:cmoId | CMODetail.tsx | Merck admin — tabbed: Connections, Schemas, Contracts, Batches |
| /cmo-registration | CMORegistration.tsx | Merck admin |
| /products | Products.tsx | Both |
| /connections | Connections.tsx | Both — cross-CMO aggregate view |
| /data-contracts | DataContracts.tsx | Both — cross-CMO aggregate view |
| /data-contracts/create | ContractCreate.tsx | Merck admin |
| /data-contracts/:id | ContractDetail.tsx | Both |
| /batches | Batches.tsx | Both — cross-CMO aggregate view |
| /batches/:id | BatchDetail.tsx | Both |
| /schema-management | SchemaManagement.tsx | Both |
| /pipelines | Pipelines.tsx | Both — real pipeline execution status |
| /nl-query | NLQuery.tsx | Both |

### Merck Admin Navigation Order
Dashboard → CMO Partners → Register New CMO → Products → Connections → Data Contracts → Batches → Schema Management → Pipelines → NL Query

### CMO User Navigation Order
Dashboard → My Connections → My Contracts → Batches → Integration Setup → Schema Management → Pipelines

---

## CMO Onboarding Workflow (Correct Order)

1. **Register CMO** — Merck creates org record in DynamoDB (`POST /api/cmo/register`)
2. **Create Product** — assign drug product to CMO (`POST /api/product`)
3. **Create Connection** — provision SFTP, native connector, or AI upload (`POST /api/connection` + activate)
4. **Create Schema** — infer from sample file or define manually, register in Glue (`POST /api/schema`)
5. **Create Contract** — links CMO + Product + Connection + Schema + SLAs (`POST /api/contract`)
6. **Contract Approval** — Merck submits → CMO accepts → Merck approves → `active`
7. **Invite CMO User** — creates Cognito account, sets `custom:organization = cmoId` (`POST /api/cmo/{id}/invite`)
8. **CMO logs in** — sees their connections, contracts, can create batches and upload data

---

## Deploy Commands

### Backend (after any Lambda or CDK change)
```bash
cd cdk
cp -r services models utils lambdas lambda_src/
find lambda_src -name "__pycache__" -type d -exec rm -rf {} +
cdk deploy PharmaDataExchangeContractApiStack --require-approval never
# Deploy all stacks:
# cdk deploy --all --require-approval never
```

### Frontend
```bash
cd frontend
npm run build
python3 deploy_amplify.py
```

### Check Amplify deploy status
```bash
aws amplify get-job --app-id d28qy16znlocxk --branch-name main --job-id <JOB_ID> \
  --region us-east-1 --query 'job.summary.status' --output text
```

### Create/manage Cognito users manually
```bash
POOL=us-east-1_uT79YqQ5x

# Create user
aws cognito-idp admin-create-user --user-pool-id $POOL --username EMAIL \
  --message-action SUPPRESS --temporary-password TempPass123! \
  --user-attributes Name=email,Value=EMAIL Name=given_name,Value=FIRST \
    Name=family_name,Value=LAST Name=email_verified,Value=true --region us-east-1

# Assign to group (merck-admins or cmo-users)
aws cognito-idp admin-add-user-to-group --user-pool-id $POOL \
  --username EMAIL --group-name merck-admins --region us-east-1

# Set permanent password
aws cognito-idp admin-set-user-password --user-pool-id $POOL \
  --username EMAIL --password PASSWORD --permanent --region us-east-1

# Link CMO user to a cmoId
aws cognito-idp admin-update-user-attributes --user-pool-id $POOL \
  --username EMAIL --user-attributes Name="custom:organization",Value=CMO_ID --region us-east-1
```

---

## Known Gaps / Remaining Work

| Priority | Item | Notes |
|---|---|---|
| 1 | Pattern 1: Glue Crawler + ETL Job | Glue Connection exists; need Crawler to discover tables and ETL job to extract to Bronze S3 on schedule |
| 2 | AI bronzePath in pipeline status | Resolves to `incoming/` instead of processed path — cosmetic fix |
| 3 | SES email notifications | Alert CMO and Merck when SLA is breached |
| 4 | Batch search by lot number | Add to NL query and direct search |
| 5 | Frontend pagination | DynamoDB scan used for all lists — fine for MVP, needs pagination at scale |

---

## Security Notes

- All CMO data is isolated server-side using the `custom:organization` JWT claim — CMO users cannot access other CMOs' data by manipulating query params
- SFTP passwords stored in Secrets Manager at `cmo/{cmoId}/sftp-{dataDomain}` — never returned after initial activation
- JDBC passwords stored in Secrets Manager at `cmo/{cmoId}/jdbc-{name}` — never returned to frontend after CMO submits
- Data lake bucket uses customer-managed KMS key — encryption applied server-side by Lambda (not presigned URLs, which are incompatible with SSE-KMS from browsers)
- CloudTrail enabled for 21 CFR Part 11 audit compliance
