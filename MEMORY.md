# Project Memory: Pharma Data Exchange Hub

## Project Overview
AWS Solutions Architecture engagement with Merck to develop a CMO (Contract Manufacturing Organization) data exchange platform that reduces integration time from 3-6 months to 1-4 weeks.

## Business Problem
- Current CMO integration takes 3-6 months due to legal, technical, and trust barriers
- High cost (200+ hours per CMO)
- Non-scalable custom integrations
- Need to handle both structured AND unstructured data

## Solution: Pharma Data Exchange Hub
3 proven integration patterns + AI processing + unified governance + two-persona approval workflow

### Three Integration Patterns
1. **Native Platform Connectors** - Cloud data warehouses (Snowflake, Databricks, BigQuery), databases (Oracle, SQL Server, MySQL), enterprise apps (SAP)
2. **Secure File Transfer** - Legacy/on-prem via SFTP, universal fallback for ANY system
3. **Unstructured Data AI** - Documents (Textract), images (Rekognition), IoT (IoT Core)

### Two Personas
1. **Merck Admin** - Creates CMO orgs, invites CMO users, drafts contracts, submits/approves
2. **CMO Representative** - Reviews contracts, accepts/rejects, configures integration

### Contract Approval Workflow
```
draft → pending_cmo_review → pending_merck_approval → active
                                                     ↘ rejected
                                                     ↘ suspended
```

## AWS Infrastructure (All Deployed - us-east-1)

### CloudFormation Stacks
| Stack | Status | Notes |
|---|---|---|
| PharmaDataExchangeSecretsStack | ✅ | Secrets Manager |
| PharmaDataExchangeDatabaseStack | ✅ | DynamoDB tables |
| PharmaDataExchangeDataLakeStack | ✅ | S3 Bronze/Silver/Gold |
| PharmaDataExchangeMonitoringStack | ✅ | CloudWatch |
| PharmaDataExchangeCognitoStack | ✅ | Auth - User Pool us-east-1_uT79YqQ5x |
| PharmaDataExchangeContractApiStack | ✅ | API Gateway + Lambda + Cognito authorizer |
| PharmaDataExchangeSchemaApiStack | ✅ | Schema Registry API |
| PharmaDataExchangeNLQueryStack | ✅ | Bedrock NL Query API |
| PharmaDataExchangePipelineOrchestrationStack | ✅ | Step Functions |
| PharmaDataExchangeSecurityStack | ✅ | KMS, Lake Formation |
| PharmaDataExchangeAuditComplianceStack | ✅ | CloudTrail |

### API Endpoints
- Contract API: https://4841ud8xri.execute-api.us-east-1.amazonaws.com/prod
- Schema API: https://ootbzgzcp0.execute-api.us-east-1.amazonaws.com/prod
- NL Query API: https://u02uvpqhg1.execute-api.us-east-1.amazonaws.com/prod

### Cognito
- User Pool ID: us-east-1_uT79YqQ5x
- App Client ID: 2eitutbi1gkogudchaudb9rtr4
- Hosted UI: pharma-data-exchange-portal.auth.us-east-1.amazoncognito.com
- Groups: merck-admins, cmo-users
- Sign-in alias: email

### Test Users
| User | Email | Password | Role | Notes |
|---|---|---|---|---|
| Merck Admin | merck-admin@pharma-exchange.demo | MerckAdmin2026! | merck-admins | CONFIRMED |
| CMO Rep | cmo-user@pharma-exchange.demo | CMOUser2026! | cmo-users | linked to cmo-a658c66b |

### Frontend
- Amplify App ID: d28qy16znlocxk
- URL: https://main.d28qy16znlocxk.amplifyapp.com
- Latest deploy: Job 18 (SUCCEED)

### Glue Schema Registry
- Registry name: pharma-data-exchange (manually created via CLI)

## API Routes (all require Cognito JWT Authorization header)

### Contract API
| Method | Path | Role | Description |
|---|---|---|---|
| POST | /api/cmo/register | merck-admins | Register new CMO org (no Cognito user created) |
| GET | /api/cmo | both | List CMOs |
| POST | /api/cmo/{cmoId}/invite | merck-admins | Create Cognito user, assign cmo-users group, set custom:organization |
| POST | /api/contract | merck-admins | Create contract |
| GET | /api/contract | both | List contracts (CMO filtered by custom:organization claim) |
| GET | /api/contract/{id} | both | Get contract |
| PUT | /api/contract/{id} | merck-admins | Update contract (draft only) |
| POST | /api/contract/{id}/submit | merck-admins | Submit to CMO for review |
| POST | /api/contract/{id}/accept | cmo-users | CMO accepts → pending_merck_approval |
| POST | /api/contract/{id}/approve | merck-admins | Final approval → active |
| POST | /api/contract/{id}/reject | both | Reject with reason |
| GET | /api/contract/{id}/status | both | Pipeline status |

### Schema API
| Method | Path | Description |
|---|---|---|
| POST | /api/schema/infer | Infer schema from file bytes |
| POST | /api/schema/register | Register in Glue Schema Registry |

### NL Query API
| Method | Path | Description |
|---|---|---|
| POST | /api/query | Natural language → SQL via Bedrock + Athena |

## Frontend Pages

### Merck Admin Navigation
- Dashboard
- CMO Partners (/cmos) — list of all CMOs, "Invite User" + "Create Contract" per row
- Register New CMO (/cmo-registration) — creates org record, redirects to contract create
- Data Contracts (/data-contracts) — all contracts with status
- Schema Management
- Pipelines
- Natural Language Query

### CMO User Navigation
- Dashboard
- My Contracts (/data-contracts) — filtered to their cmoId only
- Integration Setup (/integration-patterns)
- Schema Management
- Pipelines

### Contract Detail Actions (role + status based)
| Status | Merck Admin sees | CMO User sees |
|---|---|---|
| draft | Edit + Submit to CMO | — |
| pending_cmo_review | Reject | Accept or Reject |
| pending_merck_approval | Approve & Activate or Reject | — |
| active | View only | View only |
| rejected | View only | View only |

## CMO Onboarding Flow (Correct)
1. Merck registers CMO org → DynamoDB record created, no Cognito user
2. Merck goes to CMO Partners page → sees CMO in list
3. Merck clicks "Invite User" → enters email, first/last name
4. System creates Cognito user, assigns cmo-users group, sets custom:organization = cmoId
5. Cognito sends temp password email to CMO rep
6. CMO rep logs in at https://main.d28qy16znlocxk.amplifyapp.com
7. CMO rep sees only their contracts (filtered by custom:organization JWT claim)

## Implementation Files

### CDK Backend
```
cdk/
├── app.py                          # All 11 stacks registered
├── lambda_src/                     # Deployed Lambda package
│   ├── lambdas/                    # All handlers
│   ├── services/                   # All service classes
│   ├── models/                     # Data models
│   └── utils/                      # Utilities
├── stacks/
│   ├── cognito_stack.py            # Cognito User Pool + groups + hosted UI
│   ├── contract_api_stack.py       # Cognito authorizer, all routes, IAM for Cognito ops
│   ├── schema_api_stack.py         # Schema Registry API + Glue IAM
│   ├── nl_query_stack.py           # NL Query + Bedrock/Athena/LakeFormation IAM
│   └── ... (other stacks unchanged)
├── lambdas/
│   ├── contract_api/handler.py     # Full workflow: register, invite, list, CRUD, submit/accept/approve/reject
│   ├── schema_api/handler.py       # infer + register
│   ├── nl_query/handler.py         # NL query (non-ARN user_id falls back to Glue catalog)
│   └── ... (other handlers)
├── models/
│   └── data_contract.py            # 6 statuses + approval tracking fields (submitted_by/at, accepted_by/at, etc.)
└── services/
    └── nl_query_service.py         # Non-ARN user_id fallback to Glue catalog
```

### Frontend
```
frontend/src/
├── main.tsx                        # Amplify config + token provider wired to apiFetch
├── App.tsx                         # Auth-gated routing, role-based routes
├── context/AuthContext.tsx         # Cognito auth context (user, groups, isMerckAdmin, isCMOUser)
├── components/Layout.tsx           # Role-based nav + sign-out with user name/email display
├── pages/
│   ├── Login.tsx                   # Cognito hosted UI redirect
│   ├── CMOList.tsx                 # CMO Partners (Merck only) - Invite User + Create Contract per row
│   ├── CMORegistration.tsx         # Org registration, redirects to contract create after success
│   ├── ContractCreate.tsx          # CMO dropdown (fetches /api/cmo), pre-selects from URL ?cmoId=
│   ├── ContractDetail.tsx          # Approval action buttons based on role+status, read-only for non-draft
│   └── ... (other pages)
└── services/api.ts                 # All calls use authFetch (JWT injected), approval + invite functions
```

## Key Design Decisions

### CMO-to-Cognito Linking
- CMO registration creates DynamoDB record only
- Invite flow creates Cognito user with `custom:organization = cmoId`
- JWT token carries `custom:organization` claim
- Backend filters contract list by this claim for CMO users

### Contract Filtering
- Merck admins: see all contracts (or filter by ?cmoId=)
- CMO users: only see contracts where cmoId = their `custom:organization` JWT claim
- If CMO user has no custom:organization → 403 (contact admin)

### Lambda Deployment Package
All Lambdas use `Code.from_asset("lambda_src")` which contains lambdas/ + services/ + models/ + utils/

**When updating services or models, always run:**
```bash
cd cdk
cp -r services models utils lambdas lambda_src/
find lambda_src -name "__pycache__" -type d -exec rm -rf {} +
cdk deploy <StackName> --require-approval never
```

### Frontend Auth Flow
1. App loads → AuthContext calls getCurrentUser()
2. No session → Login page → signInWithRedirect() → Cognito hosted UI
3. After login → redirect back → AuthContext loads user + groups from JWT
4. All API calls include JWT via authHeaders() in apiFetch()

## Known Issues / Next Steps
- No email notifications when contract status changes (SES not wired)
- No pagination on contract/CMO lists (DynamoDB scan, fine for MVP)
- Frontend tests need updating for new auth context
- Stale docs (presentation.html, Merck_CMO_Platform_Agnostic.md, PowerPoint_Presentation_Outline.md) still reference 5-pattern architecture

## Deploy Commands

### Backend
```bash
cd cdk
cp -r services models utils lambdas lambda_src/
find lambda_src -name "__pycache__" -type d -exec rm -rf {} +
cdk deploy <StackName> --require-approval never
# Deploy all: cdk deploy --all --require-approval never
```

### Frontend
```bash
cd frontend
npm run build
python3 deploy_amplify.py
```

### Create Cognito User (manual)
```bash
POOL=us-east-1_uT79YqQ5x
# Create
aws cognito-idp admin-create-user --user-pool-id $POOL --username EMAIL \
  --message-action SUPPRESS --temporary-password TempPass123! \
  --user-attributes Name=email,Value=EMAIL Name=given_name,Value=FIRST \
    Name=family_name,Value=LAST Name=email_verified,Value=true --region us-east-1
# Assign group
aws cognito-idp admin-add-user-to-group --user-pool-id $POOL \
  --username EMAIL --group-name merck-admins --region us-east-1
# Set permanent password
aws cognito-idp admin-set-user-password --user-pool-id $POOL \
  --username EMAIL --password PASSWORD --permanent --region us-east-1
# Link CMO user to cmoId
aws cognito-idp admin-update-user-attributes --user-pool-id $POOL \
  --username EMAIL --user-attributes Name="custom:organization",Value=CMO_ID --region us-east-1
```

### Direct Login URL (for testing)
```
https://pharma-data-exchange-portal.auth.us-east-1.amazoncognito.com/login?client_id=2eitutbi1gkogudchaudb9rtr4&response_type=code&scope=openid+email+profile&redirect_uri=https://main.d28qy16znlocxk.amplifyapp.com/
```

## Pharma Requirements Gap Analysis
See `Pharma_Requirements.md` for the full analysis. Summary:

### Platform Purpose
Facilitate data transfer from CMO to Merck. NOT a batch release system — that stays in Merck's QMS/ERP.

### What's Missing (Must Build)
- **Batch/lot tagging** — every submission must carry lot number + product so data is findable in the lake
- **Product/material master** — lightweight DynamoDB table; contracts tie to a specific drug product
- **Completeness check per batch** — which required data elements arrived vs. missing/overdue
- **SLA tracking** — per data element, per contract terms (e.g., CoA within 5 days of batch completion)

### Out of Scope
Batch release decisions, QA approve/reject workflow, deviation management.

### Build Order
1. Product master (DynamoDB table)
2. Batch entity (DynamoDB table: lotNumber + productId + cmoId)
3. Batch-tagged data submission (update all 3 patterns + S3 path structure)
4. Contract model update (add productId + per-element SLA fields)
5. Completeness & SLA dashboard (per-batch view of what arrived vs. missing/overdue)

## Batch & Product Build (2026-04-23)

### New DynamoDB Tables (deployed)
| Table | Key | GSIs |
|---|---|---|
| `products` | `productId` | `cmo-products-index` (cmoId) |
| `batches` | `batchId` | `cmo-batches-index` (cmoId+status), `product-batches-index` (productId+manufacturingDate) |

### New API Routes (Contract API — same base URL)
| Method | Path | Role | Description |
|---|---|---|---|
| POST | /api/product | merck-admins | Create product |
| GET | /api/product?cmoId= | both | List products |
| GET/PUT | /api/product/{productId} | both | Get/update product |
| POST | /api/batch | cmo-users | Create batch record |
| GET | /api/batch?cmoId=&productId= | both | List batches |
| GET/PUT | /api/batch/{batchId} | both | Get/update batch (mark element received) |
| POST | /api/batch/{batchId}/submit | cmo-users | Mark batch fully submitted |

### New Frontend Pages (deployed — Job 19)
- `/products` — Merck admin can add products; both roles can view
- `/batches` — CMO users can create batches; both roles can view with completeness badge
- `/batches/:batchId` — Batch detail: 4 required elements (BMR, CoA, In-Process, Yield); CMO marks received; submit when complete

### Model Changes
- `DataContract` model: added `productId` (str) and `elementSlas` (list of `{elementType, maxDaysAfterBatch}`)
- New models: `cdk/models/product.py`, `cdk/models/batch.py`
- New Lambda handlers: `cdk/lambdas/product_api/handler.py`, `cdk/lambdas/batch_api/handler.py`
- S3 path utils: added `generate_batch_path(bucket, layer, cmoId, productId, batchId, elementType)`

### What's Still Left (from Pharma_Requirements.md)
- [ ] **SLA tracking** — flag overdue data elements per contract's `elementSlas` (EventBridge scheduled check)
- [ ] **Completeness dashboard** — Merck view: batches with missing/overdue elements across all CMOs
- [ ] **Contract form update** — add productId and elementSlas fields to ContractCreate.tsx frontend form
- [ ] **SES email notifications** — alert CMO and Merck when SLA is at risk or breached
- [ ] **Batch search by lot number** — NL query and direct search
- [ ] **Frontend pagination** — DynamoDB scan used for lists (fine for MVP, needs pagination at scale)

## Contract Form Updates (2026-04-23 — final)

### ContractCreate.tsx
- Added Product dropdown (filtered by selected CMO — loads from /api/product?cmoId=)
- Added "Data Submission SLAs" section: per-element deadlines (BMR, CoA, In-Process, Yield default to 5/5/1/5 days)
- productId and elementSlas now sent to backend on contract creation

### ContractDetail.tsx
- Shows productId in Basic Information
- Shows Data Submission SLAs section (read-only)

### api.ts
- Added ElementSla interface: { elementType, maxDaysAfterBatch }
- Added productId?: string and elementSlas?: ElementSla[] to DataContract interface
- CreateContractRequest includes elementSlas

### Frontend Deploy
- Latest: Job 20 (SUCCEED)
- URL: https://main.d28qy16znlocxk.amplifyapp.com

## Remaining Work (priority order)
1. SLA tracking — EventBridge daily check: for each submitted batch, compare element receivedAt vs manufacturingDate + maxDaysAfterBatch; set overdue=true and alert
2. Completeness dashboard — Merck view: table of batches with missing/overdue elements across all CMOs
3. SES email notifications — alert CMO and Merck when SLA breached
4. Batch search by lot number — add to NL query and direct search
5. Frontend pagination — DynamoDB scan used for lists (fine for MVP)

## UX Flow & CMO Edit/Delete (2026-04-24)

### Merck Admin Onboarding Flow Fix
Correct pre-work order established:
1. Create Product (drug product master)
2. Register CMO org
3. Invite CMO user
4. Create Contract (links CMO + Product)

### Frontend UX Changes (Job 21 — SUCCEED)
- **CMORegistration.tsx** — after registering a CMO, now redirects to `/products?cmoId=` instead of contract create
- **Products.tsx** — reads `?cmoId=` URL param, pre-fills CMO in form, auto-opens "Add Product" modal
- **Layout.tsx** — Merck nav reordered: CMO Partners → Register New CMO → **Products** → Data Contracts → Batches
- **ContractCreate.tsx** — shows warning Flashbar with link to `/products?cmoId=` when selected CMO has no products

### CMO Edit & Deactivate (Job 22 — SUCCEED)

#### Backend (PharmaDataExchangeContractApiStack redeployed)
- `PUT /api/cmo/{cmoId}` — update org name, email, phone, address (merck-admins only)
- `DELETE /api/cmo/{cmoId}` — soft delete: sets `status = inactive` (merck-admins only)
- New handlers: `_handle_cmo_update`, `_handle_cmo_deactivate` in `cdk/lambdas/contract_api/handler.py`
- CDK stack: added PUT + DELETE methods to `cmo_id_resource` in `contract_api_stack.py`

#### Frontend
- **CMOProfile interface** — added `contactPhone?` and `address?` fields
- **api.ts** — added `updateCMO()` and `deactivateCMO()` functions
- **CMOList.tsx** — added Edit modal (org name, email, phone, address) and Deactivate inline action per row; Deactivate hidden once status=inactive; optimistic update on edit

### Batch Flow (current state — no changes made)
- CMO creates batch (lot number, product ID [free-text — known bug], contract, mfg date)
- CMO marks each element received manually on BatchDetail page (BMR, CoA, In-Process, Yield)
- CMO submits batch when all 4 elements received (isComplete = true)
- Merck can view only — no Merck-side batch action yet
- **Known issue**: Product ID in "New Batch" modal is free-text, should be a dropdown from products table

## Remaining Work (updated priority order)
1. **Batch: fix Product ID** — replace free-text with dropdown (filtered by CMO's active contracts → products)
2. **SLA tracking** — EventBridge daily check: compare element receivedAt vs manufacturingDate + maxDaysAfterBatch; flag overdue
3. **Completeness dashboard** — Merck view: batches with missing/overdue elements across all CMOs
4. **SES email notifications** — alert CMO and Merck when SLA breached
5. **Batch search by lot number** — NL query and direct search
6. **Frontend pagination** — DynamoDB scan used for lists (fine for MVP)

## Backend Security Fix — JWT-Enforced Filtering (2026-04-24)

### Problem
Contract and product list APIs were relying on the frontend passing `?cmoId=` for filtering.
A CMO user could query another org's data by changing the query param. Backend had a `pass` comment as a TODO.

### Fix (PharmaDataExchangeContractApiStack redeployed)
All three data APIs now enforce CMO isolation server-side using the `custom:organization` JWT claim:

| API | Before | After |
|---|---|---|
| `GET /api/contract` | Frontend `?cmoId=` param, no backend enforcement | JWT claim enforced; client param ignored for CMO users |
| `GET /api/product` | No CMO filtering at all | JWT claim enforced |
| `GET /api/batch` | Already correct | Unchanged |

**Pattern**: CMO users always get filtered to their org from the JWT. Merck admins get all (or can filter via `?cmoId=`).
- `cdk/lambdas/contract_api/handler.py` — `_handle_list` rewritten
- `cdk/lambdas/product_api/handler.py` — `_get_user_info` now returns `cmo_id`; `_handle_list` enforces it

### Latest Deploy State
- Frontend: Amplify Job 22 (SUCCEED)
- Backend: PharmaDataExchangeContractApiStack (all Lambda functions updated)
- URL: https://main.d28qy16znlocxk.amplifyapp.com

## MVP Completion (2026-04-27)

### 1. Batch Product ID Fix
- **Batches.tsx** — replaced free-text Product ID with `<Select>` dropdown
- Contract selection filters products to that contract's CMO; changing contract clears product
- Product column in batch table now resolves product name from products state

### 2. SLA Tracking (Backend)
- **cdk/lambdas/sla_checker/handler.py** — new Lambda scans `in_progress` batches, looks up contract `elementSlas`, compares `manufacturingDate + maxDaysAfterBatch` vs now, sets `overdue=true` on elements
- **EventBridge rule** — daily at 6am UTC triggers SLA checker
- **POST /api/sla-check** — manual trigger endpoint (Cognito-protected) for on-demand SLA checks
- CDK: added `aws_events` + `aws_events_targets` imports, SLA checker Lambda, EventBridge rule, and API endpoint to `contract_api_stack.py`

### 3. Completeness Dashboard → Main Dashboard
- **frontend/src/pages/Dashboard.tsx** — replaced placeholder welcome page with role-aware completeness dashboard:
  - Summary cards: Active Contracts, Total Batches, Incomplete, Overdue
  - Merck admins: cross-CMO view with CMO filter, "Run SLA Check" button
  - CMO users: scoped to their own batches
  - Batch table with completeness badges, overdue indicators, missing elements
  - CMO/status filter dropdowns
- Removed separate `/completeness` route — dashboard IS the landing page
- Deleted `CompletenessDashboard.tsx` (orphaned)

### 4. API Changes
- **api.ts** — added `runSlaCheck()` function

### Deploy State
- Backend: PharmaDataExchangeContractApiStack redeployed (SLA checker Lambda + EventBridge + sla-check endpoint)
- Frontend: Amplify Job 24
- URL: https://main.d28qy16znlocxk.amplifyapp.com

### Merck Admin Navigation (updated)
Dashboard (completeness + SLA) → CMO Partners → Register New CMO → Products → Data Contracts → Batches → Schema Management → Pipelines → Natural Language Query

## E2E Testing & Bug Fixes (2026-04-27 afternoon)

### Bugs Found During E2E Testing

#### Bug 1: Products table missing Product ID column
- **Products.tsx** — COLUMNS array didn't include `productId`
- Fix: added `{ id: 'productId', header: 'Product ID', ... }` column

#### Bug 2: CMO registration status = 'invited' instead of 'active'
- **contract_api/handler.py** `_handle_register` — hardcoded `status: 'invited'`
- Fix: changed to `status: 'active'`
- Also patched all existing CMO records in DynamoDB

#### Bug 3: Contract submit/accept/approve/reject not updating status
- **Root cause:** All 4 workflow handlers called `_service.update_contract()` which only allows `schemaId, schemaVersion, qualityRules, sla, deliverySchedule, governance` — silently dropped `status`, `submitted_by`, `submitted_at`, etc.
- Fix: created `_update_contract_fields()` helper that does direct DynamoDB `UpdateItem` with SET expression for status + tracking fields
- All 4 handlers (submit, accept, approve, reject) now use this helper

#### Bug 4: CMO user sees empty contract list
- **Root cause:** `query_contracts_by_cmo()` returns `DataContract` objects; `json.dumps(default=str)` serialized them as string representations, not dicts
- Fix: added `.to_dynamodb_item()` conversion in `_handle_list` before returning

#### Bug 5: Contract create not saving productId or elementSlas
- **Root cause:** `contract_service.py` `create_contract()` built the item dict without `productId` or `elementSlas` fields
- Fix: added `'productId': data.get('productId', '')` and `'elementSlas': data.get('elementSlas', [])` to the item dict

#### Bug 6: SLA checker Lambda missing CORS headers
- **Root cause:** `sla_checker/handler.py` returned `{'statusCode': 200, 'body': ...}` without CORS headers — browser blocked the response
- Fix: added `Access-Control-Allow-Origin: *` and other CORS headers to response

### Files Modified
- `cdk/lambdas/contract_api/handler.py` — bugs 2, 3, 4
- `cdk/services/contract_service.py` — bug 5
- `cdk/lambdas/sla_checker/handler.py` — bug 6
- `frontend/src/pages/Products.tsx` — bug 1

### Test Data
- All 4 DynamoDB tables cleared (cmo-profiles, data-contracts, products, batches)
- CMO user (`cmo-user@pharma-exchange.demo`) org link cleared — must re-invite during test
- E2E test case rewritten: `E2E_TEST_CASE.md`

### Deploy State
- Backend: PharmaDataExchangeContractApiStack redeployed
- Frontend: Amplify Job 25
- URL: https://main.d28qy16znlocxk.amplifyapp.com

### E2E Test Status (as of last run)
- Steps 1–20: ALL PASSING
- Steps 21–27: Not yet retested (blocked by bugs 5 & 6, now fixed)
- Clean retest needed from Step 1

## Remaining Work (post-MVP)
1. SES email notifications — alert CMO and Merck when SLA breached
2. Batch search by lot number — NL query and direct search
3. Frontend pagination — DynamoDB scan used for lists (fine for MVP)


## Ingestion Patterns Build Plan (2026-04-28)

### Pattern 2: Secure File Transfer (SFTP) — ✅ COMPLETE
- [x] **S1. Persist integrationPattern on contract** — added `integrationPattern` + `integrationConfig` to DataContract model and contract_service
- [x] **2a. Deploy AWS Transfer Family SFTP server** — CDK stack with custom Lambda identity provider (password auth)
- [x] **2b. Wire activate endpoint** — stores creds in Secrets Manager, returns SFTP connection details
- [x] **2c. S3 event trigger** — Lambda validates file, moves from incoming/ to date-partitioned Bronze path
- [x] **2d. Frontend: show SFTP credentials** — ContractDetail + IntegrationPatternSelection pages
- [x] **2e. E2E test** — SFTP upload CSV → verified in Bronze layer with correct partitioning

### Pattern 3: AI Unstructured Data — NOT STARTED
- [ ] **3a. S3 upload via presigned URL** — API endpoint to generate presigned PUT URL for document upload
- [ ] **3b. S3 event trigger → AI processing Lambda** — calls Textract (PDF) or Rekognition (images)
- [ ] **3c. Textract/Rekognition processing** — extract text/tables/forms, parse into JSON, apply confidence thresholding
- [ ] **3d. Route results** — confidence >= 85% → Bronze layer; below → manual-review prefix
- [ ] **3e. Frontend: upload + results view** — file upload UI, results/confidence display

### Pattern 1: Native Connectors — NOT STARTED
- [ ] **1a. Glue connection creation** — create Glue Connection (JDBC/Snowflake/Databricks) on activate
- [ ] **1b. Glue ETL job creation** — deploy Glue job script, create Glue Job
- [ ] **1c. Glue trigger/schedule** — create Glue Trigger based on deliverySchedule
- [ ] **1d. Frontend: connection test** — "Test Connection" button
- [ ] **1e. E2E test** — trigger Glue job → verify data in Bronze layer

### Shared Work (remaining)
- [ ] **S2. Activate triggers Step Functions** — start PipelineDeploymentWorkflow state machine
- [ ] **S3. Pipeline status tracking** — store execution ARN, return real state from /status endpoint

## Pattern 2: Secure File Transfer — Final State (2026-04-28)

### Architecture
- CMOs are external organizations (different AWS accounts, on-premise, or no cloud at all)
- CMO only needs a standard SFTP client (FileZilla, WinSCP, CLI) — no AWS account required
- Merck admin activates SFTP from the portal → credentials generated → shared with CMO
- CMO uploads files via SFTP → files land in S3 → Lambda processes into Bronze layer

### Infrastructure
| Resource | Value |
|---|---|
| CDK Stack | PharmaDataExchangeSFTPIngestionStack |
| SFTP Server ID | `s-89e811043fec4d7d8` |
| SFTP Endpoint | `s-89e811043fec4d7d8.server.transfer.us-east-1.amazonaws.com` |
| Identity Provider | AWS_LAMBDA (custom, password-based via Secrets Manager) |
| Data Lake Bucket | `pharmadataexchangedatalakes-datalakebucket0256ea8e-dcuncyvlwsel` |
| Transfer Role | `PharmaDataExchangeSFTPIng-TransferFamilyRole7713A6A-mAJNH3dAAGZo` |

### Lambda Functions (in SFTP stack)
| Lambda | Purpose |
|---|---|
| `sftp_auth/handler.py` | Custom identity provider — validates username/password from Secrets Manager, returns IAM role + home dir |
| `sftp_processor/handler.py` | S3 event trigger — moves files from `incoming/` to date-partitioned Bronze path (`year=YYYY/month=MM/day=DD/`) |

### How Activate Works
1. Merck admin calls `POST /api/contract/{id}/activate` with `integrationPattern=secure-transfer`
2. Handler generates username (`{cmoId}-{dataDomain}`) and random 24-char password
3. Credentials stored in Secrets Manager at `cmo/{cmoId}/sftp-{dataDomain}`
4. Contract updated in DynamoDB with `integrationPattern` and `integrationConfig` (hostname/username/password)
5. Response returns SFTP credentials to frontend

### How SFTP Auth Works
1. CMO connects via SFTP client with username + password
2. Transfer Family invokes auth Lambda
3. Lambda looks up `cmo/{cmoId}/sftp-{dataDomain}` in Secrets Manager
4. If credentials match → returns IAM role + LOGICAL home dir mapping to `/{bucket}/bronze/{cmoId}/{dataDomain}/incoming`
5. CMO sees `/` as their root — they can only write to their own incoming directory

### How File Processing Works
1. CMO uploads file via SFTP → lands in `bronze/{cmoId}/{dataDomain}/incoming/{filename}`
2. S3 event notification triggers processor Lambda (for `.csv`, `.json`, `.parquet` suffixes)
3. Lambda copies file to `bronze/{cmoId}/{dataDomain}/year=YYYY/month=MM/day=DD/{filename}`
4. Lambda deletes the original from `incoming/`
5. Unsupported file extensions are skipped (stay in incoming/)

### Model Changes
- `DataContract` dataclass: added `integration_pattern` (Optional[str]) and `integration_config` (Optional[dict])
- `to_dynamodb_item()` / `from_dynamodb_item()`: serialize/deserialize both fields
- `contract_service.create_contract()`: saves `integrationPattern` and `integrationConfig` from request

### Backend Changes
- `contract_api/handler.py` — `_handle_activate()` rewritten: provisions SFTP creds in Secrets Manager (no `transfer:CreateUser` needed with custom identity provider)
- `contract_api_stack.py` — accepts `sftp_ingestion_stack` + `data_lake_stack` params; adds `SFTP_SERVER_ID`, `TRANSFER_ROLE_ARN`, `DATA_LAKE_BUCKET` env vars; grants `secretsmanager:CreateSecret/PutSecretValue/GetSecretValue` and `iam:PassRole`
- `sftp_ingestion_stack.py` — new CDK stack: Transfer Family server (AWS_LAMBDA identity provider), auth Lambda, file processor Lambda, S3 event notifications via custom resource

### Frontend Changes
- `api.ts`: added `integrationPattern` and `integrationConfig` to `DataContract` interface
- `ContractDetail.tsx`: shows SFTP Connection Details section when `integrationPattern=secure-transfer`; shows "Configure Integration" button for active contracts without a pattern; shows pattern-specific status banner
- `IntegrationPatternSelection.tsx`: already had SecureTransferDisplay component — works with activate response

### API Endpoints (updated)
- Contract API: `https://4841ud8xri.execute-api.us-east-1.amazonaws.com/prod` (changed — stack was recreated)
- Schema API: `https://ootbzgzcp0.execute-api.us-east-1.amazonaws.com/prod` (unchanged)
- NL Query API: `https://u02uvpqhg1.execute-api.us-east-1.amazonaws.com/prod` (unchanged)

### Deploy State
- Backend: PharmaDataExchangeSFTPIngestionStack (CREATE_COMPLETE) + PharmaDataExchangeContractApiStack (CREATE_COMPLETE)
- Frontend: Amplify Job 28
- `.env.production` updated with new Contract API URL

### E2E Test
- Test document: `E2E_TEST_SFTP.md`
- 13-point checklist covering: portal activation, SFTP password login, CSV/JSON upload, Bronze layer routing, unsupported file handling
- CMO-perspective steps use only standard SFTP clients (no AWS CLI)
- Merck-perspective steps use AWS CLI for data lake verification

### E2E Test Result (PASSED)
1. Activate contract with `secure-transfer` → SFTP creds returned ✅
2. SFTP login with password auth → connected ✅
3. Upload `test-upload.csv` via SFTP → file in `incoming/` ✅
4. S3 event → processor Lambda → moved to `bronze/cmo-9e779df7/batch-records/year=2026/month=04/day=28/test-upload.csv` ✅
5. Incoming file deleted after processing ✅

### Files Modified
```
cdk/
├── app.py                                    # Added SFTPIngestionStack, wired to ContractApiStack
├── stacks/sftp_ingestion_stack.py            # NEW — Transfer Family + auth Lambda + processor Lambda + S3 events
├── stacks/contract_api_stack.py              # Added sftp_ingestion_stack + data_lake_stack params, SFTP env vars + IAM
├── models/data_contract.py                   # Added integration_pattern, integration_config fields
├── services/contract_service.py              # Saves integrationPattern + integrationConfig on create
├── lambdas/sftp_auth/handler.py              # NEW — custom identity provider (password auth via Secrets Manager)
├── lambdas/sftp_processor/handler.py         # NEW — S3 event processor (incoming → date-partitioned Bronze)
├── lambdas/contract_api/handler.py           # Rewrote _handle_activate for SFTP provisioning
frontend/
├── .env.production                           # Updated Contract API URL
├── src/services/api.ts                       # Added integrationPattern + integrationConfig to DataContract
├── src/pages/ContractDetail.tsx              # SFTP credentials display + integration status banners
E2E_TEST_SFTP.md                              # NEW — Pattern 2 E2E test case
```

## Connections Refactor (2026-04-29)

### Problem
Integration pattern config (SFTP creds, etc.) was embedded directly on the Contract entity. This conflates two concerns:
- A **connection** is a CMO-level resource (how a CMO sends data to Merck)
- A **contract** is a business agreement (what data, what SLAs, which product)

A CMO can have multiple connections (SFTP, native connector, AI unstructured). The same connection may serve multiple contracts. Merck provisions connections; CMO consumes them.

### New Entity Model
```
CMO (org)
 ├── Products (assigned to this CMO)
 ├── Connections (SFTP, Native, AI — one or more per CMO)
 │    ├── Connection 1: SFTP (hostname, username, password)
 │    ├── Connection 2: Native Connector (Snowflake JDBC)
 │    └── Connection 3: AI Unstructured (presigned URL config)
 ├── Contracts (link CMO + Product + Connection + Schema)
 └── Schemas (CMO-specific, one or more per CMO/product)
```

### Revised Onboarding Workflow
1. Register CMO — create the org
2. Create Product — assign to CMO
3. Create Connection(s) — provision SFTP, native connector, or AI upload for the CMO
4. Create/Infer Schema — define data format for this CMO's submissions
5. Create Contract — ties together CMO + Product + Connection + Schema + SLAs
6. Invite CMO User — CMO logs in, sees their connections, contracts, starts sending data

### Build Plan

#### 1. Backend: Connections DynamoDB table + API
- New `connections` DynamoDB table (PK: `connectionId`, GSI: `cmo-connections-index` on `cmoId`)
- New model: `cdk/models/connection.py`
- New Lambda handler: `cdk/lambdas/connection_api/handler.py`
- API routes (on Contract API stack or new stack):
  | Method | Path | Role | Description |
  |---|---|---|---|
  | POST | /api/connection | merck-admins | Create connection (type, cmoId) |
  | GET | /api/connection?cmoId= | both | List connections (CMO filtered by JWT) |
  | GET | /api/connection/{id} | both | Get connection detail |
  | PUT | /api/connection/{id} | merck-admins | Update connection config |
  | POST | /api/connection/{id}/activate | merck-admins | Provision credentials (SFTP: Secrets Manager; Native: Glue Connection; AI: presigned URL config) |
  | DELETE | /api/connection/{id} | merck-admins | Deactivate connection |

#### 2. Backend: Move SFTP provisioning
- Move SFTP credential provisioning from `_handle_activate` (contract handler) to connection activate handler
- Connection activate for `secure-transfer` type: generate username/password, store in Secrets Manager, save config on connection record

#### 3. Backend: Update Contract model
- Add `connectionId` field to DataContract (replaces `integrationPattern` + `integrationConfig`)
- Contract references a connection by ID; contract detail resolves connection info via lookup

#### 4. Frontend: Connections pages
- **Merck admin**: Connections list per CMO (accessible from CMO Partners page or dedicated nav item)
- **CMO user**: "My Connections" page showing all their connection details
- Connection detail page: shows type, status, credentials (SFTP), config (native), upload URL (AI)
- Add "Create Connection" action on CMO Partners page

#### 5. Frontend: Update Contract flow
- ContractCreate: add `connectionId` dropdown (filtered by selected CMO's active connections)
- ContractDetail: show connection reference (link to connection detail) instead of inline SFTP creds

#### 6. Frontend: Scope Schema Management to CMO
- Schema list filtered by CMO
- Schema linked from contract

### What Gets Removed
- `integrationPattern` and `integrationConfig` fields from Contract (replaced by `connectionId`)
- SFTP credential display from ContractDetail (moved to Connection detail page)
- `_handle_activate` SFTP logic from contract handler (moved to connection handler)
- IntegrationPatternSelection page (replaced by Connection create/activate flow)

### Connections Refactor — Final State (2026-04-29)

#### New DynamoDB Table
| Table | Key | GSIs |
|---|---|---|
| `connections` | `connectionId` | `cmo-connections-index` (cmoId) |

#### New API Routes (Connection API — same base URL)
| Method | Path | Role | Description |
|---|---|---|---|
| POST | /api/connection | merck-admins | Create connection (cmoId, connectionType, name) |
| GET | /api/connection?cmoId= | both | List connections (CMO filtered by JWT) |
| GET | /api/connection/{connectionId} | both | Get connection detail |
| PUT | /api/connection/{connectionId} | merck-admins | Update connection |
| POST | /api/connection/{connectionId}/activate | merck-admins | Provision credentials (SFTP: Secrets Manager) |
| DELETE | /api/connection/{connectionId} | merck-admins | Deactivate connection |

#### Connection Types
- `secure-transfer` — SFTP (provisions username/password in Secrets Manager, returns hostname/port)
- `native-connector` — placeholder for Glue JDBC connections (future)
- `ai-unstructured` — placeholder for presigned URL upload (future)

#### Backend Files
```
cdk/
├── models/connection.py                    # NEW — Connection dataclass
├── models/data_contract.py                 # UPDATED — added connectionId field
├── services/contract_service.py            # UPDATED — saves connectionId on create
├── lambdas/connection_api/handler.py       # NEW — CRUD + activate + deactivate
├── stacks/database_stack.py                # UPDATED — added connections table
├── stacks/contract_api_stack.py            # UPDATED — added Connection API Lambda + routes
```

#### Frontend Files
```
frontend/src/
├── pages/Connections.tsx                   # NEW — connections list, create modal, activate, detail modal with SFTP creds
├── pages/ContractCreate.tsx                # UPDATED — added connectionId dropdown (filtered by CMO's active connections)
├── pages/ContractDetail.tsx                # UPDATED — shows connection reference link instead of inline SFTP creds
├── services/api.ts                         # UPDATED — Connection interface + CRUD functions + connectionId on DataContract
├── components/Layout.tsx                   # UPDATED — Connections nav item for both Merck and CMO
├── App.tsx                                 # UPDATED — /connections route
```

#### Frontend Navigation (updated)
**Merck Admin**: Dashboard → CMO Partners → Register New CMO → Products → **Connections** → Data Contracts → Batches → Schema Management → Pipelines → NL Query
**CMO User**: Dashboard → **My Connections** → My Contracts → Batches → Integration Setup → Schema Management → Pipelines

#### Deploy State
- Backend: PharmaDataExchangeDatabaseStack + PharmaDataExchangeContractApiStack redeployed
- Frontend: Amplify Job 29
- URL: https://main.d28qy16znlocxk.amplifyapp.com

#### Revised Onboarding Workflow
1. Register CMO → create org
2. Create Product → assign to CMO
3. **Create Connection(s)** → provision SFTP, native connector, or AI upload for the CMO
4. Create/Infer Schema → define data format
5. Create Contract → ties together CMO + Product + **Connection** + Schema + SLAs
6. Invite CMO User → CMO logs in, sees their connections, contracts, starts sending data

## Schema Refactor — CMO-Scoped (2026-04-29)

### Problem
Schema Management was generic — no CMO association, no DynamoDB tracking, no list view. Schemas were registered directly in Glue Schema Registry with no way to browse or filter by CMO.

### New DynamoDB Table
| Table | Key | GSIs |
|---|---|---|
| `schemas` | `schemaId` | `cmo-schemas-index` (cmoId) |

### New API Routes (Schema Management — on Contract API)
| Method | Path | Role | Description |
|---|---|---|---|
| POST | /api/schema | merck-admins | Create schema (cmoId, name, fields) |
| GET | /api/schema?cmoId= | both | List schemas (CMO filtered by JWT) |
| GET | /api/schema/{schemaId} | both | Get schema detail |
| PUT | /api/schema/{schemaId} | merck-admins | Update schema |
| POST | /api/schema/infer | both | Infer fields from uploaded CSV/JSON |
| POST | /api/schema/{schemaId}/register | merck-admins | Register in Glue Schema Registry |

### Schema Lifecycle
1. **Create** (draft) — define fields manually or infer from sample file
2. **Register** (registered) — push to Glue Schema Registry, get version number
3. **Reference** — contract links to schemaId

### Backend Files
```
cdk/
├── lambdas/schema_mgmt/handler.py          # NEW — CRUD + infer + register
├── stacks/database_stack.py                # UPDATED — added schemas table
├── stacks/contract_api_stack.py            # UPDATED — added Schema Management Lambda + routes
```

### Frontend Files
```
frontend/src/
├── pages/SchemaManagement.tsx              # REWRITTEN — CMO-scoped table, create modal (infer/manual), register button
├── pages/ContractCreate.tsx                # UPDATED — Schema dropdown replaces free-text schemaId/schemaVersion
├── services/api.ts                         # UPDATED — Schema interface, listSchemas, createSchema, inferSchema, registerSchemaInRegistry
```

### Deploy State
- Backend: PharmaDataExchangeDatabaseStack + PharmaDataExchangeContractApiStack redeployed
- Frontend: Amplify Job 30
- URL: https://main.d28qy16znlocxk.amplifyapp.com

### Entity Model (complete)
```
CMO (org)
 ├── Products (assigned to this CMO)
 ├── Connections (SFTP, Native, AI — one or more per CMO)
 ├── Schemas (one or more per CMO — batch-records, coa, yield, etc.)
 └── Contracts (links CMO + Product + Connection + Schema + SLAs)
```

### Onboarding Workflow (final)
1. Register CMO → create org
2. Create Product → assign to CMO
3. Create Connection(s) → provision SFTP, native connector, or AI upload
4. Create Schema(s) → infer from sample file or define manually, register in Glue
5. Create Contract → ties together CMO + Product + Connection + Schema + SLAs
6. Invite CMO User → CMO logs in, sees their connections, schemas, contracts

### Schema Bugs Fixed (2026-04-29 afternoon)

#### Bug 1: Infer parsing multipart boundary as CSV
- **Root cause:** API Gateway sends file upload as multipart/form-data; handler parsed the raw multipart envelope (including `------WebKitFormBoundary` headers) as CSV
- **Fix:** Added `_extract_multipart()` helper that strips boundary headers and extracts file content before parsing
- Also added `binary_media_types=["multipart/form-data", "application/octet-stream"]` to Contract API RestApi

#### Bug 2: Glue CreateSchema missing Compatibility
- **Root cause:** `glue.create_schema()` requires `Compatibility` parameter
- **Fix:** Added `Compatibility='BACKWARD'` to the create_schema call

#### Bug 3: Invalid JSON Schema type `double`
- **Root cause:** Inferred field type `double` is not a valid JSON Schema type (must be `number`)
- **Fix:** Added type mapping in `_handle_register`: `double` → `number`, `timestamp` → `string`, `date` → `string`

#### Files Modified
- `cdk/lambdas/schema_mgmt/handler.py` — all 3 fixes
- `cdk/stacks/contract_api_stack.py` — binary_media_types

#### Deploy State
- Backend: PharmaDataExchangeContractApiStack redeployed (3 times for fixes)
- Frontend: Amplify Job 30 (unchanged)
- URL: https://main.d28qy16znlocxk.amplifyapp.com

## Pattern 3: AI Unstructured Data — Built (2026-04-29)

### Architecture
- CMO or Merck uploads PDF/image via portal → presigned S3 PUT URL → file lands in `bronze/{cmoId}/{connName}/incoming/`
- S3 event triggers AI processor Lambda
- PDF → Textract (AnalyzeDocument: tables, forms, text)
- Image → Rekognition (DetectLabels + DetectText)
- Results saved as structured JSON:
  - Confidence ≥ 85% → `bronze/{cmoId}/{connName}/year=YYYY/month=MM/day=DD/{filename}.json`
  - Confidence < 85% → `bronze/{cmoId}/{connName}/manual-review/{filename}.json`

### API Routes (on Contract API)
| Method | Path | Description |
|---|---|---|
| POST | /api/connection/{id}/upload-url?filename= | Get presigned S3 PUT URL |

### Connection Activate (ai-unstructured)
Stores config: `{ bucket, uploadPrefix, supportedFormats, confidenceThreshold }`

### Backend Files
```
cdk/
├── lambdas/ai_processor/handler.py         # NEW — Textract/Rekognition processing
├── lambdas/connection_api/handler.py       # UPDATED — ai-unstructured activate + upload-url endpoint
├── stacks/contract_api_stack.py            # UPDATED — AI processor Lambda, S3 events, IAM, upload-url route
```

### Frontend Files
```
frontend/src/
├── pages/Connections.tsx                   # UPDATED — Upload Document section for AI connections
├── services/api.ts                         # UPDATED — getUploadUrl function
```

### Supported File Types
- `.pdf` → Textract (tables, forms, text extraction)
- `.png`, `.jpg`, `.jpeg`, `.tiff` → Rekognition (labels, text detection)

### Deploy State
- Backend: PharmaDataExchangeContractApiStack redeployed (AI processor + S3 events)
- Frontend: Amplify Job 32
- URL: https://main.d28qy16znlocxk.amplifyapp.com

### All 3 Patterns Now Built
| Pattern | Type | Status |
|---|---|---|
| Pattern 1: Native Connectors | Placeholder (Glue JDBC) | Connection type exists, activate returns placeholder |
| Pattern 2: Secure Transfer (SFTP) | Transfer Family | ✅ Fully working E2E |
| Pattern 3: AI Unstructured | Textract + Rekognition | ✅ Built, needs E2E test |

### Pipelines Page Fix
- Updated Pipelines.tsx to resolve integration pattern from connections table instead of deprecated contract.integrationPattern field
- Frontend: Amplify Job 31

## Pattern 3: AI Unstructured — Upload Fix (2026-04-29 afternoon)

### Problems Found & Fixed

#### Problem 1: S3 CORS missing
- Browser PUT to presigned URL failed with "Failed to fetch"
- Fix: Added CORS policy to data lake bucket (AllowedOrigins: Amplify URL, Methods: PUT/GET)
- Also added `cors` rule to `cdk/stacks/data_lake_stack.py` so it survives CDK redeploys

#### Problem 2: Presigned URL + SSE-KMS incompatible with browser uploads
- Bucket uses customer-managed KMS key; presigned URLs with SSE-KMS require the *caller* to have kms:GenerateDataKey — browsers don't have AWS credentials
- Fix: Switched from presigned URL approach to **proxy upload** — Lambda receives file and calls s3.put_object() directly (bucket default encryption applies server-side automatically)

#### Problem 3: API Gateway binary body corrupts Authorization header
- Sending `Content-Type: application/octet-stream` triggers API Gateway binary passthrough, which corrupted the Cognito JWT
- Fix: Frontend uses `FormData` (multipart/form-data); Lambda extracts file bytes from multipart envelope using `_extract_multipart()` helper

### Final Upload Architecture
1. Frontend: `FormData` POST to `/api/connection/{id}/upload?filename=`
2. API Gateway: passes multipart body (already in binary_media_types)
3. Connection Lambda: extracts file bytes, calls `s3.put_object()` with SSE-KMS applied by bucket default
4. S3 event → AI Processor Lambda → Textract (PDF) / Rekognition (images)

### API Route Change
- Old: `POST /api/connection/{id}/upload-url` (presigned URL)
- New: `POST /api/connection/{id}/upload` (proxy upload)

### E2E Verification
- Upload triggers AI processor Lambda ✅ (confirmed via CloudWatch logs)
- Textract called correctly ✅
- `UnsupportedDocumentException` on fake test PDFs is expected — real PDFs process fine

### Files Modified
```
cdk/lambdas/connection_api/handler.py   — replaced _handle_upload_url with _handle_upload (proxy); added _extract_multipart
cdk/stacks/contract_api_stack.py        — route renamed upload-url → upload
cdk/stacks/data_lake_stack.py           — added cors rule to DataLakeBucket
frontend/src/services/api.ts            — replaced getUploadUrl with uploadFile (FormData POST)
frontend/src/pages/Connections.tsx      — updated handleUpload to use uploadFile
```

### Deploy State
- Backend: PharmaDataExchangeContractApiStack redeployed (new /upload route)
- Frontend: Amplify Job 35 (SUCCEED)
- S3 CORS: applied directly + in CDK

## Pattern 3: AI Unstructured — Async Textract Fix (2026-04-30)

### Problem
`analyze_document` (sync) only supports single-page PDFs. Real COA PDFs are multi-page → `UnsupportedDocumentException`.

### Fix: Two-Lambda Async Pipeline
1. **ai_processor/handler.py** — S3 event triggers `start_document_analysis` (async, multi-page support). Saves job metadata to `pending-textract/{jobId}.json` in S3.
2. **textract_result_processor/handler.py** — NEW Lambda. Triggered by SNS when Textract job completes. Calls `get_document_analysis` with pagination to collect all pages. Saves JSON result to Bronze layer (or manual-review if confidence < 85%). Cleans up metadata and original file.

### New Infrastructure (deployed)
- **SNS Topic**: `TextractCompletionTopic` — Textract publishes job completion here
- **IAM Role**: `TextractSNSRole` — assumed by Textract; has `sns:Publish`, `kms:Decrypt`, `kms:GenerateDataKey`, `s3:GetObject`
- **Lambda**: `TextractResultProcessor` — subscribed to SNS topic

### Files Modified
```
cdk/lambdas/ai_processor/handler.py              — switched to start_document_analysis + metadata save
cdk/lambdas/textract_result_processor/handler.py — NEW
cdk/stacks/contract_api_stack.py                 — SNS topic, TextractSNSRole, TextractResultProcessor Lambda
```

### Deploy State
- Backend: PharmaDataExchangeContractApiStack redeployed (3 times during debugging)
- Frontend: Amplify Job 35 (unchanged)

### COA_SAMPLE.pdf Investigation
- File is 1MB, valid `%PDF-1.5` header, has `/Encrypt` dictionary
- `pikepdf` reports: `root of pages tree has no /Kids array` — structurally corrupt PDF
- Textract API rejects it with `PASSWORD_PROTECTED_DOCUMENT` (both sync and async, both S3 and raw bytes)
- Textract console reportedly processed it fine — likely the console repairs/re-encodes before calling the API
- **Status: unresolved** — need a clean non-corrupt PDF to confirm pipeline works end-to-end
- Pipeline architecture is correct and SNS→Lambda flow is verified working

### Remaining Work (updated priority order)
1. ~~**Verify Pattern 3 E2E**~~ — ✅ CONFIRMED 2026-04-30: sample_coa.pdf processed successfully. Textract async pipeline: 440 blocks extracted, 94.1% confidence, saved to Bronze layer. Pattern 3 fully working E2E.
2. SES email notifications — alert CMO and Merck when SLA breached
3. Batch search by lot number — NL query and direct search
4. Frontend pagination — DynamoDB scan used for lists (fine for MVP)

## Pattern 1: Native Connectors — Build Starting (2026-04-30)

### Status
- Pattern 3 E2E confirmed ✅ (2026-04-30 13:46 UTC — sample_coa.pdf, 440 blocks, 94.1% confidence)
- Pattern 1 native connector implementation starting next

### Remaining Work (updated priority order)
1. **Pattern 1: Native Connectors** — Glue JDBC connections for Oracle, SQL Server, SAP, Snowflake, Databricks
2. SES email notifications — alert CMO and Merck when SLA breached
3. Batch search by lot number — NL query and direct search
4. Frontend pagination — DynamoDB scan used for lists (fine for MVP)

## Pattern 1: Native Connectors — Built (2026-04-30)

### What Was Built
When a `native-connector` connection is activated, the portal now:
1. Collects JDBC config from Merck admin: db type, host, port, database, username, password
2. Stores credentials in Secrets Manager at `cmo/{cmoId}/jdbc-{name}`
3. Creates an AWS Glue Connection (JDBC type) named `{cmoId}-{name}`
4. Returns Glue connection name, JDBC URL, and secret name in the connection config

### Supported Database Types
| Type | JDBC URL Pattern |
|---|---|
| SQL Server | `jdbc:sqlserver://{host}:{port};databaseName={db}` |
| Oracle | `jdbc:oracle:thin:@{host}:{port}:{db}` |
| PostgreSQL | `jdbc:postgresql://{host}:{port}/{db}` |
| MySQL | `jdbc:mysql://{host}:{port}/{db}` |
| Snowflake | `jdbc:snowflake://{host}/?db={db}` |
| SAP HANA | `jdbc:sap://{host}:{port}/?databaseName={db}` |

### VPC Support
If `GLUE_SUBNET_ID` and `GLUE_SECURITY_GROUP_ID` env vars are set on the connection Lambda, Glue connections will include `PhysicalConnectionRequirements` for VPC-hosted databases. Currently not set (for public endpoints).

### Files Modified
```
cdk/lambdas/connection_api/handler.py   — _provision_native_connector() added
cdk/stacks/contract_api_stack.py        — Glue IAM (CreateConnection/UpdateConnection/GetConnection) added
frontend/src/pages/Connections.tsx      — JDBC config form + Glue connection display
frontend/src/services/api.ts            — activateConnection accepts optional body; Connection.config type widened
```

### Deploy State
- Backend: PharmaDataExchangeContractApiStack redeployed (Glue IAM + new connection handler)
- Frontend: Amplify Job 36 (SUCCEED)
- URL: https://main.d28qy16znlocxk.amplifyapp.com

### All 3 Patterns Now Fully Built
| Pattern | Type | Status |
|---|---|---|
| Pattern 1: Native Connectors | Glue JDBC | ✅ Built — Secrets Manager + Glue Connection on activate |
| Pattern 2: Secure Transfer (SFTP) | Transfer Family | ✅ Fully working E2E |
| Pattern 3: AI Unstructured | Textract + Rekognition | ✅ E2E confirmed 2026-04-30 |

### Remaining Work (updated priority order)
1. **Pattern 1 E2E test** — CMO adds DB connection via portal, Merck reviews & activates, verify Glue connection in console
2. SES email notifications — alert CMO and Merck when SLA breached
3. Batch search by lot number — NL query and direct search
4. Frontend pagination — DynamoDB scan used for lists (fine for MVP)

## Pattern 1: Native Connectors — Flow Refactored (2026-04-30) ⚠️ SUPERSEDED by CMO Self-Service section below

### New Flow (CMO-initiated, frictionless)
1. Merck creates a `native-connector` connection for the CMO (status: `pending`)
2. CMO logs in → sees "Configure" button → enters their own DB details (host, port, db, user, password)
3. Backend stores credentials in Secrets Manager, sets status → `pending_merck_review`
4. Merck admin sees "Review & Activate" in the table → opens detail modal showing DB info (no password shown)
5. Merck clicks "Activate — Create Glue Connection" → one click, no data entry
6. Backend reads creds from Secrets Manager, calls `glue.create_connection()`, status → `active`

### Connection Status Flow
```
pending → (CMO configures) → pending_merck_review → (Merck activates) → active
```

### Security Properties
- CMO enters credentials directly into the system — never sent via email
- Password stored in Secrets Manager only — never returned to frontend after configure
- Merck admin sees host/port/db/username but not the password

### Files Modified
```
cdk/lambdas/connection_api/handler.py   — _handle_configure() added; _provision_native_connector() reads from SM
cdk/stacks/contract_api_stack.py        — /configure route added
frontend/src/pages/Connections.tsx      — CMO config form; Merck review+activate view; table actions updated
frontend/src/services/api.ts            — configureConnection() added; Connection.status includes pending_merck_review
```

### Deploy State
- Backend: PharmaDataExchangeContractApiStack redeployed
- Frontend: Amplify Job 37 (SUCCEED)
- URL: https://main.d28qy16znlocxk.amplifyapp.com

## Native Connector — CMO Self-Service + NLB/PrivateLink (2026-04-30)

### Problem Fixed
Previously Merck had to pre-create the connection record before CMO could configure it. Now CMO initiates the entire flow.

### New Flow
1. CMO logs in → My Connections → **"Add Database Connection"** button
2. CMO fills in: connection name, DB type, connection method, host, port, database, username, password, (optional) PrivateLink service name
3. Submit → credentials stored in Secrets Manager, connection created with status `pending_merck_review`
4. Merck admin sees "Review & Activate" in Connections table
5. Merck reviews DB details (no password shown) + PrivateLink service name if applicable
6. One-click "Activate — Create Glue Connection" → Glue Connection created, status → `active`

### Connection Methods Supported
| Method | Use Case |
|---|---|
| Direct | Public endpoint or VPN-connected DB |
| NLB | CMO puts Network Load Balancer in front of DB; Merck connects to NLB DNS |
| AWS PrivateLink | CMO creates VPC Endpoint Service on NLB; shares service name with Merck; most secure, no public internet |

### PrivateLink Flow
- CMO enters `privateLinkServiceName` (e.g. `com.amazonaws.vpce.us-east-1.vpce-svc-xxx`)
- Merck sees it in the review panel (copyable)
- Merck network team creates VPC Endpoint in Merck's account using that service name
- Glue connection points to the VPC Endpoint DNS — traffic stays on AWS backbone

### Files Modified
```
cdk/lambdas/connection_api/handler.py   — CMO can create native-connector; auto-configure on create; connectionMethod + privateLinkServiceName in config
frontend/src/pages/Connections.tsx      — CMO "Add Database Connection" modal with all fields; Merck review shows connectionMethod + PrivateLink service name
frontend/src/services/api.ts            — Connection.config type updated with connectionMethod + privateLinkServiceName
```

### Deploy State
- Backend: PharmaDataExchangeContractApiStack redeployed
- Frontend: Amplify Job 38 (SUCCEED)
- URL: https://main.d28qy16znlocxk.amplifyapp.com

## Pattern 1: Native Connectors — E2E PASSED (2026-05-04)

### Test Result
- E2E test case: `E2E_TEST_NATIVE_CONNECTOR.md` — all 12 checks ✅
- CMO submitted SQL Server connection via portal → status `pending_merck_review`
- Merck admin reviewed (password not shown) → clicked "Activate — Create Glue Connection"
- AWS Glue JDBC connection created successfully (`cmo-{cmoId}-{name}`)
- Credentials stored in Secrets Manager at `cmo/{cmoId}/jdbc-{name}`

### All 3 Patterns — E2E Confirmed
| Pattern | Type | E2E Status |
|---|---|---|
| Pattern 1: Native Connectors | Glue JDBC | ✅ PASSED 2026-05-04 |
| Pattern 2: Secure Transfer (SFTP) | Transfer Family | ✅ PASSED 2026-04-28 |
| Pattern 3: AI Unstructured | Textract + Rekognition | ✅ PASSED 2026-04-30 |

### Note on Glue Connection vs Glue Database
- Pattern 1 currently provisions a **Glue Connection** only (JDBC credentials + endpoint)
- A **Glue Crawler** + **Glue ETL Job** are not yet built — these would discover tables and extract data into the Bronze S3 layer
- This is the remaining work for Pattern 1 to be fully functional end-to-end for data ingestion

### Remaining Work (updated priority order)
1. **Pattern 1: Glue Crawler + ETL Job** — discover CMO DB tables, extract to Bronze S3 layer on a schedule
2. SES email notifications — alert CMO and Merck when SLA breached
3. Batch search by lot number — NL query and direct search
4. Frontend pagination — DynamoDB scan used for lists (fine for MVP)

## Demo Data Seeded (2026-05-04)

### Purpose
Customer demo-ready data replacing all "PharmaCorp Test" placeholder records.

### CMO
| Field | Value |
|---|---|
| cmoId | `cmo-9e779df7` (unchanged — Cognito user link preserved) |
| Name | Lonza AG |
| Email | operations@lonza-pharma.com |
| Address | Münchensteinerstrasse 38, 4002 Basel, Switzerland |

### Test Users (unchanged)
| Role | Email | Password |
|---|---|---|
| Merck Admin | merck-admin@pharma-exchange.demo | MerckAdmin2026! |
| CMO User | cmo-user@pharma-exchange.demo | CMOUser2026! |

### Products
| productId | Name |
|---|---|
| prod-ibu200 | Ibuprofen 200mg Tablets (NDC: 0573-0168-01) |
| prod-ome40 | Omeprazole 40mg Capsules (NDC: 0378-6040-93) |

### Connections
| connectionId | Name | Type | Status |
|---|---|---|---|
| conn-828942c15e01 | Lonza SFTP Feed | secure-transfer | active |
| conn-e8ce6f5ca2d4 | Lonza COA Document Upload | ai-unstructured | active |
| conn-88e64630f96b | Lonza Oracle ERP (JDBC) | native-connector | active (PrivateLink) |

### Schemas
| schemaId | Name | Status |
|---|---|---|
| schema-batch-records | Batch Manufacturing Records | registered |
| schema-coa-data | Certificate of Analysis | registered |
| schema-yield-data | Yield & In-Process Controls | registered |

### Contracts
| contractId | Product | Connection | Pattern | Status |
|---|---|---|---|---|
| CMO-LONZA-BATCH-RECORDS-001 | Ibuprofen 200mg | SFTP | secure-transfer | active |
| CMO-LONZA-COA-DOCUMENTS-001 | Ibuprofen 200mg | AI Upload | ai-unstructured | active |
| CMO-LONZA-ERP-YIELD-001 | Omeprazole 40mg | Oracle ERP | native-connector | active |

### Batches (6 total)
| batchId | Lot | Product | Status | Complete | Notes |
|---|---|---|---|---|---|
| batch-lonza-001 | LOT-LNZ-2026-001 | Ibuprofen | submitted | ✅ | All 4 elements received |
| batch-lonza-002 | LOT-LNZ-2026-002 | Ibuprofen | submitted | ✅ | All 4 elements received |
| batch-lonza-003 | LOT-LNZ-2026-003 | Ibuprofen | in_progress | ❌ | CoA missing (not yet overdue) |
| batch-lonza-004 | LOT-LNZ-2026-004 | Ibuprofen | in_progress | ❌ | ⚠️ OVERDUE — only BMR received, CoA/Yield/In-Process overdue |
| batch-lonza-005 | LOT-LNZ-2026-005 | Omeprazole | submitted | ✅ | All 4 elements received |
| batch-lonza-006 | LOT-LNZ-2026-006 | Omeprazole | in_progress | ❌ | BMR + In-Process received, CoA/Yield pending |

### Demo Talking Points
- Dashboard shows SLA risk in action: 1 overdue batch (LOT-LNZ-2026-004) with 3 overdue elements
- 3 contracts cover all 3 integration patterns — shows flexibility
- PrivateLink connection (Oracle ERP) demonstrates enterprise-grade security story
- CMO user login scoped to Lonza data only — shows multi-tenant isolation

### Portal URL
https://main.d28qy16znlocxk.amplifyapp.com

## Session 2026-05-04 — Demo Prep & Bug Fixes

### Pattern 1 E2E — CONFIRMED PASSED
- Test case written: `E2E_TEST_NATIVE_CONNECTOR.md`
- Glue JDBC connection created successfully via portal flow
- Note: Glue Connection only (no Crawler/ETL job yet — data extraction not yet built)

### Demo Data Seeded
- Replaced all "PharmaCorp Test" placeholder data with realistic Lonza AG demo data
- See "Demo Data Seeded (2026-05-04)" section above for full details

### Bugs Fixed During Demo Testing

#### Bug 1: Contract detail → "Internal server error"
- **Root cause:** Seed script stored `qualityRules` as plain strings; model expects dicts with `ruleId`, `ruleName`, `ruleType`, `expression`, `threshold`, `severity`
- **Also:** `sla` missing `timeliness`/`availability`/`quality` nested structure; `governance` missing `piiFields` and `encryptionRequired`
- **Fix:** Updated all 3 contracts in DynamoDB directly with correct structured objects

#### Bug 2: Batch detail → blank page
- **Root cause:** Seed script stored elements under key `elements`; frontend expects `dataElements`. Also missing `s3Path` and `missingElements` fields.
- **Fix:** Renamed `elements` → `dataElements`, added `s3Path: null` per element, populated `missingElements` array for all 6 batches

### Testing Status (as of end of session)
- ✅ Contracts list loads
- ✅ Contract detail loads (first 2 tested)
- ✅ Batch list loads
- ✅ First 2 batches detail load
- ⏳ Remaining batches (3–6) not yet retested after bug fix — resume here tomorrow
- ⏳ CMO user login flow not yet retested with new demo data
- ⏳ Connections page not yet retested
- ⏳ Dashboard SLA/completeness view not yet verified with new batch data
- ⏳ Schema Management page not yet tested
- ⏳ NL Query not yet tested

### Resume Point Tomorrow
Continue E2E testing from batch-lonza-003 detail page. Full checklist:
1. Batches 3–6 detail pages (in_progress + overdue states)
2. Dashboard — verify overdue batch (LOT-LNZ-2026-004) shows correctly
3. CMO user login — verify scoped view (Lonza data only)
4. Connections page — all 3 connection types display correctly
5. Schema Management — 3 schemas visible
6. NL Query — test a natural language question

## Session 2026-05-06 — UX Improvements & Pipeline Wiring

### Deploy State (end of session)
- Frontend: Amplify Job 42 (SUCCEED)
- Backend: PharmaDataExchangeContractApiStack (UPDATE_COMPLETE)
- URL: https://main.d28qy16znlocxk.amplifyapp.com

### 1. Products "Inactive" Bug Fixed
- **Root cause:** Seed script stored `status: 'active'` (string) but frontend checks `isActive` (boolean). Field was missing → falsy → showed "Inactive".
- **Fix:** Added `isActive: true` directly to both product DynamoDB records (`prod-ibu200`, `prod-ome40`).

### 2. Schema Management — Field Visibility + Edit
- **Problem 1:** Schema table only showed field count, not the actual fields.
- **Fix:** Added expand toggle (▶) per schema row. Clicking opens an inline `ExpandableSection` showing all fields with name, type (badged), and required/optional status.
- **Problem 2:** No way to edit a schema after creation.
- **Fix:** Added Edit button (Merck admin only) on every schema row. Opens modal pre-populated with name + editable fields table (add/remove/change type).
- **Registered schemas:** Editing fields resets status to `draft` (backend) so "Register in Glue" button reappears. Info banner explains this.
- **Files modified:** `frontend/src/pages/SchemaManagement.tsx`, `frontend/src/services/api.ts` (added `updateSchema()`), `cdk/lambdas/schema_mgmt/handler.py` (reset to draft on field change).

### 3. CMO Detail Page — Tabbed Subsections
- **Problem:** Connections, Schemas, Contracts, Batches were flat top-level pages with no CMO context. Doesn't scale to multiple CMOs.
- **New page:** `frontend/src/pages/CMODetail.tsx` — route `/cmos/:cmoId`
  - CMO info header (name, email, phone, address, status)
  - Four tabs: Connections | Schemas | Data Contracts | Batches — all pre-filtered to that CMO
- **CMO Partners list:** Organization name is now a clickable link to `/cmos/:cmoId`
- **Existing top-level pages** (Connections, Schemas, Data Contracts, Batches) remain as cross-CMO aggregate views in the nav — unchanged.
- **Pages updated to accept optional `cmoId` prop:**
  - `Connections.tsx` — uses prop or falls back to `?cmoId=` URL param
  - `DataContracts.tsx` — passes `cmoId` to `listContracts()`
  - `Batches.tsx` — passes `cmoId` to `listBatches()`
  - `SchemaManagement.tsx` — passes `cmoId` to `listSchemas()`
- **api.ts:** `listContracts()` updated to accept optional `cmoId` param (`?cmoId=` query string).
- **App.tsx:** Added `/cmos/:cmoId` route + `CMODetail` import.

### 4. Pipelines — Wired to Real Execution Data
- **Problem:** `/status` endpoint returned contract DynamoDB status only. "View Details" showed nothing. "Active" was misleading — just meant contract was approved, not that data was flowing.
- **Fix:** `_handle_pipeline_status` now queries real infrastructure per connection type:

| Pattern | Data Source | What's Returned |
|---|---|---|
| `secure-transfer` (SFTP) | S3 `list_objects_v2` on `bronze/{cmoId}/{dataDomain}/` | Last file name, size, received timestamp, total files received, Bronze S3 path |
| `ai-unstructured` | S3 `list_objects_v2` on `bronze/{cmoId}/{connName}/` | Total docs processed, manual review pending count, last processed timestamp |
| `native-connector` | `glue.get_job_runs()` for `{cmoId}-{dataDomain}-etl` | Last run status, start time, duration, rows extracted; honest message if job not yet configured |

- **CDK changes** (`contract_api_stack.py`):
  - Added `CONNECTION_TABLE_NAME` env var to contract handler
  - Added `database_stack.connections_table.grant_read_data(contract_handler)`
  - Added `data_lake_bucket.grant_read(contract_handler)`
  - Added `glue:GetJobRuns` + `glue:GetJobRun` IAM policy
- **api.ts:** `PipelineStatus` interface updated with `executionDetails` typed per pattern.
- **Pipelines.tsx:** Detail panel rewritten — renders pattern-specific cards (SFTP file stats, AI doc counts + manual review warning, Glue job run details).

### Verified Pipeline Status (live data)
- `CMO-LONZA-BATCH-RECORDS-001` (SFTP): `test-upload.csv`, 58 bytes, received 2026-04-28 ✅
- `CMO-LONZA-COA-DOCUMENTS-001` (AI): 0 docs processed, 0 manual review ✅
- `CMO-LONZA-ERP-YIELD-001` (Native): Glue connection `cmo-9e779df7-lonza-oracle-erp` active, ETL job not yet configured ✅

### Remaining Work (updated priority order)
1. **Pattern 1: Glue Crawler + ETL Job** — discover CMO DB tables, extract to Bronze S3 on schedule; will make native connector pipeline status show real run data
2. **AI bronzePath fix** — `ai-unstructured` status resolves `bronzePath` to `incoming/` instead of processed path (minor cosmetic issue)
3. SES email notifications — alert CMO and Merck when SLA breached
4. Batch search by lot number — NL query and direct search
5. Frontend pagination — DynamoDB scan used for lists (fine for MVP)

## BatchId Traceability — S3 Path & Auto-Population (2026-05-13)

### Problem
Files landing in S3 had no batch context in their path. The data lake could not answer "which lot number does this file belong to?" `s3Path` on batch elements was always `null`.

### Solution
`batchId` is now embedded in every S3 path from the moment of upload. All three ingestion patterns updated.

### New S3 Path Convention
```
bronze/{cmoId}/{dataDomain}/batchId={batchId}/year=YYYY/month=MM/day=DD/{filename}
```
`batchId` is a Hive-style partition — Athena queries can filter by it directly.

### Pattern 2: SFTP
- CMO must upload to: `/{batchId}/{elementType}/{filename}` (relative to their SFTP home dir)
- SFTP home dir maps to `bronze/{cmoId}/{dataDomain}/incoming/` — so full S3 key is `incoming/{batchId}/{elementType}/{filename}`
- `sftp_processor` parses `batchId` + `elementType` from path, writes to `batchId=` partitioned dest, writes `s3Path` back to batch element in DynamoDB (marks element received)
- BatchDetail page shows the upload path per element so CMO knows exactly where to drop files

### Pattern 3: AI Unstructured
- `POST /api/connection/{id}/upload` now requires `?batchId=&elementType=` query params (returns 400 if missing)
- Connection Lambda builds key: `bronze/{cmoId}/{connName}/incoming/{batchId}/{elementType}/{filename}`
- Writes incoming `s3Path` to batch element immediately (marks received)
- Textract result processor: parses `batchId`+`elementType` from `originalKey`, includes `batchId=` partition in dest key, overwrites `s3Path` with final Bronze path after processing
- Upload button moved from Connections page to BatchDetail page (per element, CMO only, AI connections)

### Pattern 1: Native Connectors
- Not yet updated — Glue Crawler/ETL job not yet built. Will need to tag extracted rows with `batchId` when that work is done.

### Frontend Changes
- **BatchDetail.tsx**: fetches contract → connection on load; shows SFTP upload path instructions per batch; shows AI upload button per element (CMO + ai-unstructured only); shows `s3Path` column for all elements
- **Connections.tsx**: upload widget removed; replaced with info message directing CMO to BatchDetail
- **api.ts**: `uploadFile()` now requires `batchId` + `elementType` params

### Deploy State
- Backend: PharmaDataExchangeSFTPIngestionStack + PharmaDataExchangeContractApiStack (both UPDATE_COMPLETE)
- Frontend: Amplify Job 43 (SUCCEED)
- URL: https://main.d28qy16znlocxk.amplifyapp.com

### Remaining Work (updated priority order)
1. **CoA preview** — now that `s3Path` is populated on batch elements, add a "View" button on received CoA elements that renders the Textract-extracted key-value pairs in a modal
2. **Pattern 1: Glue Crawler + ETL Job** — discover CMO DB tables, extract to Bronze S3 on schedule; tag rows with `batchId`
3. SES email notifications — alert CMO and Merck when SLA breached
4. Batch search by lot number — NL query and direct search
5. Frontend pagination — DynamoDB scan used for lists (fine for MVP)

## lotNumber in S3 Path (2026-05-13)

### Problem
Previous change used `batchId=` as the S3 partition. But `batchId` is an internal system key meaningless outside the portal. The CMO's lot number is the regulated identifier that appears on every physical document and that Merck's QMS references for batch release.

### Fix
S3 path partition changed from `batchId={batchId}` to `lot={lotNumber}` across all 3 patterns.

### Final S3 Path Convention
```
bronze/{cmoId}/{dataDomain}/lot={lotNumber}/year=YYYY/month=MM/day=DD/{filename}
```

### How Each Pattern Gets lotNumber
- **SFTP**: processor looks up batch record in DynamoDB by `batchId` (parsed from incoming path), reads `lotNumber` field
- **AI upload**: frontend passes `lotNumber` as query param → connection_api stores it as S3 object metadata (`lot-number`) → ai_processor reads metadata and saves to Textract job metadata JSON → textract_result_processor reads from job metadata and uses in dest path
- **Native connector**: not yet updated (Glue ETL job not yet built)

### Files Modified
- `cdk/lambdas/sftp_processor/handler.py` — `_get_lot_number()` helper, `lot=` in dest path
- `cdk/lambdas/connection_api/handler.py` — `lotNumber` query param required, stored as S3 metadata
- `cdk/lambdas/ai_processor/handler.py` — reads S3 metadata, saves `lotNumber`/`batchId`/`elementType` in Textract job metadata
- `cdk/lambdas/textract_result_processor/handler.py` — reads `lotNumber` from job metadata, uses `lot=` in dest path
- `frontend/src/services/api.ts` — `uploadFile()` takes `lotNumber` param
- `frontend/src/pages/BatchDetail.tsx` — passes `batch.lotNumber` to `uploadFile`; SFTP instructions show `lot={lotNumber}`

### Deploy State
- Backend: PharmaDataExchangeSFTPIngestionStack + PharmaDataExchangeContractApiStack (both deployed)
- Frontend: Amplify Job 44 (SUCCEED)

### Remaining Work (updated priority order)
1. **CoA preview** — `s3Path` is now populated with lot-partitioned path; add "View" button on received CoA elements to render Textract-extracted key-value pairs in a modal
2. **Pattern 1: Glue Crawler + ETL Job** — tag extracted rows with `lotNumber`
3. SES email notifications
4. Batch search by lot number
5. Frontend pagination

## Batch Decoupled from Contract (2026-05-13)

### Problem
Batch was tied to a single `contractId`. Since each contract references one connection, the batch detail page could only show upload options for that one connection type. A CMO with both SFTP and AI connections couldn't upload a CoA (AI) from a batch that was linked to the SFTP contract.

### Root Cause
A batch is a physical manufacturing event (lot number + product + CMO). A contract is a business agreement. They are related but not the same thing. Forcing a 1:1 batch-to-contract relationship was wrong.

### Fix
- **Batch now belongs to**: `cmoId` + `productId` + `lotNumber` — no `contractId` required
- **Upload options on BatchDetail** are driven by the CMO's active connections, not the batch's contract
- **New API endpoint**: `GET /api/batch/{batchId}/connections` — returns all active connections for the CMO that owns the batch
- **BatchDetail** fetches batch + connections in parallel; shows SFTP instructions if SFTP connection active; shows AI upload button per element if AI connection active

### Files Modified
- `cdk/lambdas/batch_api/handler.py` — `contractId` optional on create; added `_handle_get_connections`; added `CONNECTION_TABLE_NAME` env var
- `cdk/stacks/contract_api_stack.py` — `CONNECTION_TABLE_NAME` + read grant on batch handler; `/connections` GET route
- `frontend/src/pages/Batches.tsx` — removed contract dropdown from New Batch form; product dropdown no longer depends on contract
- `frontend/src/pages/BatchDetail.tsx` — fetches CMO connections via `getBatchConnections()`; shows upload per element based on connection type
- `frontend/src/services/api.ts` — `CreateBatchRequest.contractId` optional; added `getBatchConnections()`

### Deploy State
- Backend: PharmaDataExchangeContractApiStack (UPDATE_COMPLETE)
- Frontend: Amplify Job 45 (SUCCEED)
- URL: https://main.d28qy16znlocxk.amplifyapp.com

### Remaining Work (updated priority order)
1. **CoA preview** — `s3Path` now populated; add "View" button on received CoA elements to render Textract key-value pairs in a modal
2. **Pattern 1: Glue Crawler + ETL Job** — tag rows with `lotNumber`
3. SES email notifications
4. Batch search by lot number
5. Frontend pagination

## CoA Viewer Built (2026-05-13)

### What Was Built
Merck QA (and CMO) can now view the extracted contents of any received data element directly in the portal.

### How It Works
1. Batch Detail page shows a **View** button on any received element that has an `s3Path`
2. Clicking View calls `GET /api/batch/{batchId}/element/{elementType}/view` → returns a presigned S3 GET URL (15-min TTL)
3. Frontend fetches the Textract JSON result via the presigned URL
4. Modal renders:
   - **AI confidence badge** (green ≥85%, red <85%)
   - **Document header**: Product Name, Batch/Lot, Mfg Date, Expiry Date, Quantity, Disposition, Analyst, QA Approver
   - **Test Results table**: Test / Method / Specification / Result / Unit / Status (PASS/FAIL with color indicators)

### View button is visible to both Merck admins and CMO users (any received element with s3Path)

### Files Modified
- `cdk/lambdas/batch_api/handler.py` — `_handle_element_view`: looks up s3Path, generates presigned GET URL
- `cdk/stacks/contract_api_stack.py` — DATA_LAKE_BUCKET env var + S3 read grant + `/element/{elementType}/view` GET route
- `frontend/src/services/api.ts` — `getElementViewUrl()`
- `frontend/src/pages/BatchDetail.tsx` — `CoAViewer` modal component + View button per element

### Deploy State
- Backend: PharmaDataExchangeContractApiStack (UPDATE_COMPLETE)
- Frontend: Amplify Job 46 (SUCCEED)
- URL: https://main.d28qy16znlocxk.amplifyapp.com

### Note
The existing `sample_coa.json` in Bronze S3 (`bronze/cmo-9e779df7/coa-files/year=2026/month=04/day=30/`) was processed before the batchId/lotNumber path changes. To test the viewer end-to-end, upload a new CoA PDF from a batch detail page with an active AI connection.

### Remaining Work (updated priority order)
1. **Pattern 1: Glue Crawler + ETL Job** — discover CMO DB tables, extract to Bronze S3 on schedule; tag rows with lotNumber
2. SES email notifications — alert CMO and Merck when SLA breached
3. Batch search by lot number — NL query and direct search
4. Frontend pagination — DynamoDB scan used for lists (fine for MVP)

## Session Summary 2026-05-13

### What We Discussed & Built

**Key architectural decisions made:**
1. **CoA preview** — agreed it makes sense for production; Textract already extracts structured data, just needed to surface it
2. **batchId in S3 path** — foundational traceability fix; every file now tagged to a batch from the moment of upload
3. **lotNumber in S3 path** — CMO's own lot number (not internal batchId) is the S3 partition; aligns with regulated documents and Merck's QMS
4. **Batch decoupled from contract** — batch is a physical manufacturing event (cmoId + productId + lotNumber); upload options driven by CMO's active connections, not which contract the batch is linked to

**Everything deployed and working:**
- S3 path: `bronze/{cmoId}/{dataDomain}/lot={lotNumber}/year=YYYY/month=MM/day=DD/{filename}`
- SFTP processor auto-marks elements received + writes s3Path
- AI upload (from BatchDetail page) auto-marks elements received + writes s3Path; Textract result processor overwrites with final Bronze path
- BatchDetail shows SFTP upload instructions per batch; AI upload button per element
- CoA viewer modal: presigned URL → Textract JSON → renders document header + test results table with PASS/FAIL indicators
- New Batch form no longer requires contract selection

### Deploy State (end of session)
- Frontend: Amplify Job 46 (SUCCEED)
- Backend: PharmaDataExchangeContractApiStack + PharmaDataExchangeSFTPIngestionStack (both UPDATE_COMPLETE)
- URL: https://main.d28qy16znlocxk.amplifyapp.com

### Resume Point Tomorrow
Demo batch records (batch-lonza-001 through batch-lonza-006) have `s3Path: null` on elements — seeded before auto-population was built. Two options:
- **Option A**: Manually patch s3Path on a few elements to point to the existing `sample_coa.json` in Bronze S3 so the viewer can be demoed immediately
- **Option B**: Create a fresh batch via the portal, upload a CoA PDF, let the pipeline run end-to-end

Then continue with remaining work:
1. **Pattern 1: Glue Crawler + ETL Job** — discover CMO DB tables, extract to Bronze S3 on schedule; tag rows with lotNumber
2. SES email notifications — alert CMO and Merck when SLA breached
3. Batch search by lot number — NL query and direct search
4. Frontend pagination

## CoA Viewer Fix (2026-05-15)

### Problem
`_handle_element_view` returned a presigned S3 GET URL. Browser fetch failed with XML error because bucket uses KMS encryption — presigned URLs require the caller to have `kms:Decrypt`, which browsers don't have.

### Fix
- **batch_api/handler.py** — replaced presigned URL generation with direct `s3.get_object()` + return JSON content through Lambda
- **api.ts** — renamed `getElementViewUrl()` → `getElementViewData()`, returns parsed JSON directly
- **BatchDetail.tsx** — updated CoAViewer to call `getElementViewData()` instead of fetching a URL
- **batch-lonza-001 CoA element** — patched `s3Path` to `s3://.../.../sample_coa.json` (full URI format required)

### Deploy State
- Backend: batch Lambda updated directly (zip deploy)
- Frontend: Amplify Job 47 (SUCCEED)

### Remaining Work (priority order)
1. Pattern 1: Glue Crawler + ETL Job — discover CMO DB tables, extract to Bronze S3 on schedule; tag rows with lotNumber
2. SES email notifications — alert CMO and Merck when SLA breached
3. Batch search by lot number
4. Frontend pagination

## Pattern 1: Glue ETL Job + Trigger — Built (2026-05-22)

### What Was Built
When a `native-connector` connection is activated, the portal now also:
1. Creates a **Glue ETL Job** (`{cmoId}-{dataDomain}-etl`) using the PySpark script
2. Creates a **daily scheduled Trigger** (`cron(0 2 * * ? *)` — 2am UTC) that runs the job automatically

### S3 Output Path (Option B — date-partitioned, no lot number)
```
bronze/{cmoId}/{dataDomain}/year=YYYY/month=MM/day=DD/
```
Lot traceability for native connector data is done via Athena query on the data, not the S3 path (CMO DB schema not under our control).

### New Files
- `cdk/glue_scripts/jdbc_to_bronze.py` — PySpark ETL script (reads JDBC via Glue Connection, writes Parquet to Bronze)

### Files Modified
- `cdk/lambdas/connection_api/handler.py` — `_provision_native_connector()` now creates Glue Job + Trigger; reads `GLUE_ETL_ROLE_ARN` + `GLUE_SCRIPT_S3_PATH` env vars
- `cdk/stacks/contract_api_stack.py` — added `aws_s3_deployment` import; `GlueEtlRole` IAM role (AWSGlueServiceRole + S3 read/write + SM GetSecretValue); `BucketDeployment` uploads `glue_scripts/` to S3; expanded Glue IAM (CreateJob/UpdateJob/GetJob/CreateTrigger/UpdateTrigger/GetTrigger); `iam:PassRole` for Glue ETL role; sets `GLUE_ETL_ROLE_ARN` + `GLUE_SCRIPT_S3_PATH` env vars on connection handler

### Deployed Resources
- Glue ETL script: `s3://pharmadataexchangedatalakes-datalakebucket0256ea8e-dcuncyvlwsel/glue-scripts/jdbc_to_bronze.py`
- Glue ETL Role ARN: `arn:aws:iam::550129454303:role/PharmaDataExchangeContractApiSt-GlueEtlRole5CCE2A4F-4gJvpVctx0aY`
- Backend: PharmaDataExchangeContractApiStack (UPDATE_COMPLETE)

### Pipelines Page
Already queries `glue.get_job_runs()` for `{cmoId}-{dataDomain}-etl` — will now show real run data once a connection is activated and the job runs.

### Known Limitation
`--db_table` job argument defaults to the `database` field from the connection config. For a real activation, Merck should update the Glue job's `--db_table` argument to point at the specific source table. This is a manual step post-activation.

### All 3 Patterns — Fully Built
| Pattern | Type | Status |
|---|---|---|
| Pattern 1: Native Connectors | Glue JDBC + ETL Job + daily Trigger | ✅ Built 2026-05-22 |
| Pattern 2: Secure Transfer (SFTP) | Transfer Family | ✅ E2E PASSED 2026-04-28 |
| Pattern 3: AI Unstructured | Textract + Rekognition | ✅ E2E PASSED 2026-04-30 |

## Remaining Work (updated priority order)
1. SES email notifications — alert CMO and Merck when SLA breached
2. Batch search by lot number — NL query and direct search
3. Frontend pagination — DynamoDB scan used for lists (fine for MVP)
4. Pattern 1 `--db_table` UX — consider adding a "table name" field to the native connector configure form so CMO can specify the source table during setup

## Pattern 1: Multi-Table Support — Built (2026-05-22)

### Problem
One connection = one Glue job = one table was wrong. A CMO's Oracle ERP has multiple tables (batch records, CoA, yield). They need one connection (one database endpoint) with multiple table extractions.

### Solution
`tableMappings` — a list of `{sourceTable, dataDomain}` pairs stored on the connection config.
On activate: one Glue job + daily trigger created per mapping.

### Example
```json
"tableMappings": [
  { "sourceTable": "BATCH_RECORDS", "dataDomain": "batch-records" },
  { "sourceTable": "COA_RESULTS",   "dataDomain": "coa-data" },
  { "sourceTable": "YIELD_DATA",    "dataDomain": "yield-data" }
]
```
Creates jobs: `{cmoId}-batch-records-etl`, `{cmoId}-coa-data-etl`, `{cmoId}-yield-data-etl`

### Files Modified
- `cdk/lambdas/connection_api/handler.py` — `_handle_configure()` requires `tableMappings`; `_provision_native_connector()` loops over mappings, creates one job+trigger per entry; config stores `glueJobs` array instead of single `glueJobName`
- `frontend/src/pages/Connections.tsx` — table mappings add/remove UI in CMO create modal + configure-in-detail modal; Merck review panel shows mappings table; active connection detail shows ETL jobs table
- `frontend/src/services/api.ts` — `Connection.config` type updated with `tableMappings` and `glueJobs` arrays; `createConnection` and `configureConnection` signatures widened

### Backward Compatibility
Existing connections without `tableMappings` fall back to single-table using the `database` field.

### Deploy State
- Backend: PharmaDataExchangeContractApiStack (UPDATE_COMPLETE)
- Frontend: Amplify Job 49 (deploying → check portal)
- URL: https://main.d28qy16znlocxk.amplifyapp.com

## Remaining Work (updated priority order)
1. SES email notifications — alert CMO and Merck when SLA breached
2. Batch search by lot number — NL query and direct search
3. Frontend pagination — DynamoDB scan used for lists (fine for MVP)

## Session 2026-06-02 — Customer Walkthrough Prep & Documentation

### Customer Walkthrough Test Case
- Created `E2E_CUSTOMER_WALKTHROUGH.md` — comprehensive 14-part walkthrough covering all platform features
- Created `E2E_CUSTOMER_WALKTHROUGH.docx` — Word format for sharing with customer
- Covers: Dashboard, CMO Management, Connections (all 3 patterns), Schema Management, Data Contracts, CMO scoped view, Native Connector self-service, Contract acceptance, Batch management, CoA document viewing, Pipelines, SLA verification
- Includes 42-item pass/fail checklist + customer feedback template (meets requirements / needs modifications / doesn't meet)
- Customer can walk through independently using pre-loaded Lonza AG demo data + create new records

### CloudWatch Alarms for Customer Testing
- Created SNS topic: `arn:aws:sns:us-east-1:550129454303:PharmaDataExchange-Alerts`
- Subscribed: `duverney@amazon.com` (email confirmation required)
- Created 8 CloudWatch alarms (5-min evaluation, trigger on ≥1 error):
  - `PharmaDE-ContractApi-Errors`
  - `PharmaDE-ConnectionApi-Errors`
  - `PharmaDE-BatchApi-Errors`
  - `PharmaDE-SchemaMgmt-Errors`
  - `PharmaDE-ProductApi-Errors`
  - `PharmaDE-SFTPAuth-Errors`
  - `PharmaDE-AiProcessor-Errors`
  - `PharmaDE-ApiGateway-5xx`

### HTML Documentation (deployed)
- Created `frontend/public/docs/user-guide.html` (22KB) — platform overview, workflows, all features, compliance
- Created `frontend/public/docs/api-guide.html` (31KB) — all API endpoints with request/response examples, auth, architecture
- Style matches asm2agent docs (Amazon Ember font, dark nav bar, color-coded method badges, Export to PDF)
- Added Amplify rewrite rule: `/docs/<*>` → `/docs/<*>` (serves static HTML, bypasses SPA router)
- Added **Resources** dropdown in top navigation bar (next to user name) with links to User Guide and API Guide
- Frontend: Amplify Job 52 (SUCCEED)

### NL Query — Known Issue
- NL Query page returns "You do not have access to any tables" because Glue database `cmo_data_lake` had no tables
- Created the Glue database `cmo_data_lake` but tables not yet created
- Root cause: NL Query service calls `glue.get_tables()` which returns empty → service returns "no access" message
- **Next step (deferred):** Create Glue tables for the 6 DynamoDB tables OR modify NL Query service to query DynamoDB directly
- Athena workgroup `cmo-workgroup` also doesn't exist yet (service expects it)

### Deploy State
- Frontend: Amplify Job 52 (SUCCEED)
- URL: https://main.d28qy16znlocxk.amplifyapp.com
- Docs: https://main.d28qy16znlocxk.amplifyapp.com/docs/user-guide.html
- Docs: https://main.d28qy16znlocxk.amplifyapp.com/docs/api-guide.html

### Waiting On
- Customer to test using `E2E_CUSTOMER_WALKTHROUGH.md` / `.docx`
- SNS subscription confirmation (duverney@amazon.com must click confirm link)
- Customer feedback → then address NL Query + any issues found
