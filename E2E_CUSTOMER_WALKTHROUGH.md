# Customer Walkthrough: Pharma Data Exchange Hub — Complete Platform Validation

**Portal URL:** https://main.d28qy16znlocxk.amplifyapp.com  
**Direct Login:** https://pharma-data-exchange-portal.auth.us-east-1.amazoncognito.com/login?client_id=2eitutbi1gkogudchaudb9rtr4&response_type=code&scope=openid+email+profile&redirect_uri=https://main.d28qy16znlocxk.amplifyapp.com/

## Objective

Walk through the complete Pharma Data Exchange Hub portal as both a **Merck Administrator** and a **CMO Representative**. This validates the full onboarding workflow, all 3 integration patterns, batch management with SLA tracking, CoA document viewing, and multi-tenant data isolation.

**At the end of this walkthrough, you should be able to determine:**
1. Does this platform meet your requirements for CMO data exchange?
2. What additional features or modifications are needed?
3. Are there any workflow gaps that need to be addressed?

## Test Accounts

| Role | Email | Password | Description |
|------|-------|----------|-------------|
| Merck Admin | merck-admin@pharma-exchange.demo | MerckAdmin2026! | Full platform administration |
| CMO User | cmo-user@pharma-exchange.demo | CMOUser2026! | CMO representative (Lonza AG) |

## Pre-Loaded Demo Data

The portal comes pre-loaded with realistic demo data for **Lonza AG** (CMO) including:
- 2 products (Ibuprofen 200mg Tablets, Omeprazole 40mg Capsules)
- 3 connections (SFTP, AI Document Upload, Oracle ERP via PrivateLink)
- 3 schemas (Batch Manufacturing Records, Certificate of Analysis, Yield & In-Process Controls)
- 3 active contracts (one per integration pattern)
- 6 batches (mix of complete, in-progress, and overdue states)

You can explore this existing data first, then create new records to validate the workflow end-to-end.

---

## PART 1: MERCK ADMIN — LOGIN & DASHBOARD

### Step 1 — Login as Merck Admin
1. Open the portal URL above
2. Click **Sign In** (redirects to Cognito hosted UI)
3. Enter: `merck-admin@pharma-exchange.demo` / `MerckAdmin2026!`
4. **Expected:** Redirected to the **Dashboard** showing:
   - **Summary cards** at the top: Active Contracts, Total Batches, Incomplete Batches, Overdue Elements
   - **Batch Completeness table** showing batches with their status, completeness badges, and overdue indicators
   - A **Run SLA Check** button
   - **Left navigation:** Dashboard, CMO Partners, Register New CMO, Products, Connections, Data Contracts, Batches, Schema Management, Pipelines, NL Query

### Step 2 — Review Dashboard Data
1. Note the summary cards — you should see existing active contracts and batches from demo data
2. Look at the Batch Completeness table:
   - **Expected:** Batches with 4/4 elements show a green badge; incomplete batches show blue; overdue elements are flagged in red
   - You should see LOT-LNZ-2026-004 flagged as overdue (3 elements past SLA deadline)
3. Try the **CMO filter dropdown** — select a CMO to filter the table
4. Try the **Status filter** — filter by "Has Overdue Elements"
5. **Expected:** Filters narrow the table results correctly
6. Click **Run SLA Check**
7. **Expected:** Success message confirming how many batches were checked and how many elements flagged overdue

| Pass? | Check |
|-------|-------|
| ☐ | Dashboard loads with summary cards showing correct counts |
| ☐ | Batch completeness table displays with color-coded badges |
| ☐ | Overdue batch (LOT-LNZ-2026-004) is visually flagged |
| ☐ | CMO and Status filters work correctly |
| ☐ | Run SLA Check button executes and returns results |

---

## PART 2: MERCK ADMIN — CMO MANAGEMENT

### Step 3 — View Existing CMO Partners
1. Click **CMO Partners** in the left nav
2. **Expected:** You see **Lonza AG** in the table with:
   - Status: `active`
   - Email, phone, address visible
   - Actions available: **Invite User**, **Create Contract**, **Edit**, **Deactivate**
3. Click on the **Lonza AG** organization name (it's a clickable link)
4. **Expected:** Opens the **CMO Detail Page** with:
   - CMO info header (name, email, phone, address, status)
   - **Four tabs:** Connections | Schemas | Data Contracts | Batches
   - All tabs are pre-filtered to show only Lonza AG's data

### Step 4 — Explore CMO Detail Tabs
1. Click the **Connections** tab
   - **Expected:** Shows Lonza's 3 connections (SFTP, AI Upload, Oracle ERP) with their statuses
2. Click the **Schemas** tab
   - **Expected:** Shows Lonza's 3 schemas (Batch Records, CoA, Yield)
3. Click the **Data Contracts** tab
   - **Expected:** Shows Lonza's 3 active contracts
4. Click the **Batches** tab
   - **Expected:** Shows all 6 Lonza batches with lot numbers, status, and completeness

### Step 5 — Register a New CMO
1. Click **Register New CMO** in the left nav
2. Fill in:
   - Organization Name: `Catalent Biologics`
   - Contact Email: `data-ops@catalent.demo`
   - Contact Phone: `555-0200`
   - Address: `725 Chesterbrook Blvd, Wayne, PA 19087`
   - GxP Certified: Yes
3. Click **Register CMO**
4. **Expected:** Success message, redirected to **Products page** with `?cmoId=` in the URL and "Add Product" modal auto-opens
5. Note the `cmoId` from the URL for later use

### Step 6 — Create a Product
1. The "Add Product" modal should already be open from Step 5
2. Fill in:
   - Product Name: `Adalimumab 40mg Pre-filled Syringe`
   - Strength: `40mg/0.8mL`
   - Dosage Form: `Injectable`
   - CMO: Should be pre-selected to Catalent Biologics
   - Description: `Biosimilar adalimumab for auto-immune conditions`
3. Click **Create Product**
4. **Expected:** Product appears in the table with a visible **Product ID** column

### Step 7 — Verify CMO in Partners List
1. Click **CMO Partners** in the left nav
2. **Expected:** Catalent Biologics now appears in the list with status `active`
3. Verify you can click **Edit** to modify the org details
4. Verify the **Deactivate** option is available (do not click it)

| Pass? | Check |
|-------|-------|
| ☐ | CMO Partners lists existing CMOs with correct status |
| ☐ | CMO Detail page loads with 4 tabs (Connections, Schemas, Contracts, Batches) |
| ☐ | Each tab shows CMO-filtered data |
| ☐ | Register New CMO creates org and redirects to Products with modal open |
| ☐ | Product creation works with all fields |
| ☐ | Edit and Deactivate actions are available on CMO rows |

---

## PART 3: MERCK ADMIN — CONNECTIONS (ALL 3 PATTERNS)

### Step 8 — View Existing Connections
1. Click **Connections** in the left nav
2. **Expected:** You see all connections across all CMOs, including Lonza's 3:
   - `Lonza SFTP Feed` — Type: secure-transfer, Status: active
   - `Lonza COA Document Upload` — Type: ai-unstructured, Status: active
   - `Lonza Oracle ERP (JDBC)` — Type: native-connector, Status: active (PrivateLink)
3. Click on an active SFTP connection to open the detail panel
4. **Expected:** Shows SFTP Connection Details:
   - Hostname (`s-XXXXXXXXX.server.transfer.us-east-1.amazonaws.com`)
   - Username
   - Password
   - Supported formats: CSV, JSON, Parquet

### Step 9 — Create an SFTP Connection for the New CMO
1. On the Connections page, click **Create Connection** (Merck admin action)
2. Fill in:
   - CMO: Select **Catalent Biologics**
   - Connection Name: `Catalent Batch Data Feed`
   - Connection Type: `Secure File Transfer (SFTP)`
3. Click **Create**
4. **Expected:** Connection created with status `pending`
5. Click **Activate** on the new connection
6. **Expected:** Status changes to `active`. SFTP credentials are generated and displayed:
   - Hostname: Transfer Family endpoint
   - Username: `{cmoId}-catalent-batch-data-feed` format
   - Password: 24-character random string

### Step 10 — Create an AI Unstructured Connection
1. Click **Create Connection**
2. Fill in:
   - CMO: Select **Catalent Biologics**
   - Connection Name: `Catalent CoA Upload`
   - Connection Type: `AI Unstructured Data`
3. Click **Create**
4. Click **Activate** on the new connection
5. **Expected:** Status → `active`. Config shows supported formats (PDF, PNG, JPG, TIFF) and confidence threshold (85%)

### Step 11 — Review the Native Connector Detail (Lonza Oracle ERP)
1. Find the `Lonza Oracle ERP (JDBC)` connection in the table
2. Click to open the detail panel
3. **Expected:** Shows:
   - Status: `active`
   - Database Type: Oracle
   - Connection Method: AWS PrivateLink
   - JDBC URL
   - Glue Connection Name
   - **Table Mappings** showing source tables → data domains (e.g., BATCH_RECORDS → batch-records)
   - **ETL Jobs** table showing one Glue job per table mapping with daily schedule

| Pass? | Check |
|-------|-------|
| ☐ | Connections page shows all connections across CMOs |
| ☐ | SFTP connection detail shows hostname, username, password |
| ☐ | Creating + activating SFTP connection generates credentials |
| ☐ | Creating + activating AI connection shows supported formats |
| ☐ | Native connector detail shows JDBC URL, Glue connection, table mappings, ETL jobs |
| ☐ | Connection status transitions work (pending → active) |

---

## PART 4: MERCK ADMIN — SCHEMA MANAGEMENT

### Step 12 — View Existing Schemas
1. Click **Schema Management** in the left nav
2. **Expected:** You see Lonza's 3 schemas:
   - `Batch Manufacturing Records` — status: registered
   - `Certificate of Analysis` — status: registered
   - `Yield & In-Process Controls` — status: registered
3. Click the **expand toggle (▶)** on any schema row
4. **Expected:** Expands to show all field definitions:
   - Field name, data type (badged), and required/optional status

### Step 13 — Create a Schema by Manual Definition
1. Click **Create Schema**
2. Fill in:
   - CMO: Select **Catalent Biologics**
   - Schema Name: `Biologics Batch Records`
   - Add fields manually:
     - `lot_number` — Type: string — Required: Yes
     - `product_name` — Type: string — Required: Yes
     - `fill_volume_ml` — Type: number — Required: Yes
     - `manufacturing_date` — Type: date — Required: Yes
     - `sterility_test_result` — Type: string — Required: Yes
     - `endotoxin_level` — Type: number — Required: No
3. Click **Create**
4. **Expected:** Schema appears in the table with status `draft`

### Step 14 — Create a Schema by File Inference (Optional)
1. Click **Create Schema** again
2. Select **Infer from file**
3. Upload a sample CSV file with headers like:
   ```
   lot_number,product,quantity,manufacturing_date,expiry_date,status
   LOT-001,Drug X,50000,2026-01-15,2028-01-15,released
   ```
4. **Expected:** Schema fields are automatically inferred from the CSV headers with appropriate types detected
5. Review and adjust field types if needed, then click **Create**

### Step 15 — Register a Schema in Glue
1. Find the `Biologics Batch Records` schema (status: `draft`)
2. Click **Register in Glue**
3. **Expected:** Status changes to `registered`. Schema is now in AWS Glue Schema Registry with version number.

### Step 16 — Edit a Schema
1. Click **Edit** on any schema (Merck admin only)
2. **Expected:** Modal opens pre-populated with schema name and editable fields table
3. Make a change (e.g., add a new field)
4. Click **Save**
5. **Expected:** If the schema was previously `registered`, status resets to `draft` with an info banner explaining it needs to be re-registered

| Pass? | Check |
|-------|-------|
| ☐ | Schema list shows existing schemas with correct statuses |
| ☐ | Expand toggle shows field definitions with types and required status |
| ☐ | Manual schema creation works with multiple fields |
| ☐ | Schema inference from CSV file detects field types correctly |
| ☐ | Register in Glue transitions schema to `registered` status |
| ☐ | Edit resets registered schema to `draft` |

---

## PART 5: MERCK ADMIN — DATA CONTRACTS

### Step 17 — View Existing Contracts
1. Click **Data Contracts** in the left nav
2. **Expected:** You see Lonza's 3 contracts with statuses (all `active`):
   - `CMO-LONZA-BATCH-RECORDS-001` — Ibuprofen 200mg, SFTP
   - `CMO-LONZA-COA-DOCUMENTS-001` — Ibuprofen 200mg, AI Upload
   - `CMO-LONZA-ERP-YIELD-001` — Omeprazole 40mg, Native Connector
3. Click on any contract to view the detail page
4. **Expected:** Contract detail shows:
   - Basic Information: CMO, Product, Data Domain, Status
   - Connection reference (link to connection)
   - Schema reference
   - Quality Rules section
   - Delivery Schedule
   - Governance section (classification, retention, encryption)
   - **Data Submission SLAs** section with per-element deadlines (BMR, CoA, In-Process, Yield)

### Step 18 — Create a New Contract
1. Click **Data Contracts** → **Create Contract**
2. Fill in:
   - CMO: Select **Catalent Biologics**
   - Product: Select **Adalimumab 40mg Pre-filled Syringe** (dropdown filtered by CMO)
   - Connection: Select **Catalent Batch Data Feed** (dropdown filtered by CMO's active connections)
   - Schema: Select **Biologics Batch Records** (dropdown filtered by CMO's schemas)
   - Data Domain: `batch-records`
   - Quality Rules: leave defaults
   - Delivery Frequency: `daily`
   - Delivery Timezone: `America/New_York`
   - Governance — Classification: `confidential`
   - Governance — Retention Years: `7`
   - Governance — Encryption Required: Yes
   - **Data Submission SLAs:**
     - BMR: `5` days
     - CoA: `5` days
     - In-Process: `2` days
     - Yield: `5` days
3. Click **Create**
4. **Expected:** Contract created in `draft` status

### Step 19 — Submit Contract to CMO
1. Open the newly created contract
2. Click **Submit to CMO**
3. **Expected:** Status changes to `pending_cmo_review`
4. The Submit button disappears; a Reject button appears

### Step 20 — Sign Out

| Pass? | Check |
|-------|-------|
| ☐ | Contract list shows all contracts with correct statuses |
| ☐ | Contract detail shows all sections (SLAs, quality rules, governance) |
| ☐ | Contract create form has dropdowns for Product, Connection, and Schema (filtered by CMO) |
| ☐ | Contract created in `draft` status |
| ☐ | Submit to CMO changes status to `pending_cmo_review` |

---

## PART 6: CMO USER — LOGIN & SCOPED VIEW

### Step 21 — Login as CMO User
1. Open the portal URL
2. Sign in with: `cmo-user@pharma-exchange.demo` / `CMOUser2026!`
3. **Expected:** Redirected to **Dashboard** showing:
   - Summary cards scoped to **Lonza AG's data only**
   - Batch completeness for Lonza's batches only
   - **Left navigation:** Dashboard, My Connections, My Contracts, Batches, Schema Management, Pipelines
   - **NOT visible:** CMO Partners, Register New CMO, Products (these are Merck-admin only)

### Step 22 — Verify Multi-Tenant Isolation
1. **Expected:** All data shown is ONLY for Lonza AG (the CMO user's organization)
2. You should NOT see Catalent Biologics contracts, connections, or batches
3. This confirms JWT-enforced data isolation — the CMO can only access their own organization's data

| Pass? | Check |
|-------|-------|
| ☐ | CMO user sees reduced navigation (no admin pages) |
| ☐ | Dashboard data is scoped to CMO's organization only |
| ☐ | No data from other CMOs is visible (multi-tenant isolation) |

---

## PART 7: CMO USER — CONNECTIONS & NATIVE CONNECTOR FLOW

### Step 23 — View My Connections
1. Click **My Connections** in the left nav
2. **Expected:** Shows only Lonza's connections:
   - `Lonza SFTP Feed` — active
   - `Lonza COA Document Upload` — active
   - `Lonza Oracle ERP (JDBC)` — active
3. Click on the SFTP connection to view details
4. **Expected:** SFTP credentials are visible (hostname, username, password)

### Step 24 — CMO Self-Service: Add a Database Connection
1. Click **Add Database Connection**
2. **Expected:** Modal opens with fields:
   - Connection Name
   - Database Type (SQL Server, Oracle, PostgreSQL, MySQL, Snowflake, SAP HANA)
   - Connection Method (Direct, NLB, AWS PrivateLink)
   - Host / Endpoint
   - Port (auto-fills based on DB type)
   - Database Name
   - Username
   - Password
   - (Optional) PrivateLink Service Name
   - Table Mappings (source table → data domain)
3. Fill in:
   - Connection Name: `Catalent SAP HANA`
   - Database Type: SAP HANA
   - Connection Method: AWS PrivateLink
   - Host: `vpce-example.us-east-1.vpce.amazonaws.com`
   - Port: `30015` (auto-fills for SAP HANA)
   - Database: `PHARMA_PROD`
   - Username: `catalent_readonly`
   - Password: `SecurePass456!`
   - PrivateLink Service Name: `com.amazonaws.vpce.us-east-1.vpce-svc-0123456789abcdef`
   - Add table mapping: Source Table `BATCH_HEADER` → Data Domain `batch-records`
4. Click **Submit**
5. **Expected:** Connection appears with status `pending_merck_review`
6. **CMO does NOT see** a "Review & Activate" button — that's a Merck-admin action

| Pass? | Check |
|-------|-------|
| ☐ | My Connections shows only the CMO's own connections |
| ☐ | SFTP connection detail shows credentials |
| ☐ | "Add Database Connection" opens with all required fields |
| ☐ | Port auto-fills when DB type is selected |
| ☐ | PrivateLink service name field appears when PrivateLink method selected |
| ☐ | Table mappings can be added (source table → data domain) |
| ☐ | After submit, status is `pending_merck_review` |
| ☐ | CMO cannot activate their own connection (Merck-only action) |

---

## PART 8: CMO USER — CONTRACT REVIEW & ACCEPTANCE

### Step 25 — Review and Accept the New Contract
1. Click **My Contracts** in the left nav
2. **Expected:** You see ONLY Lonza AG's contracts (including the new one from Step 19 if the CMO user was invited to the new CMO — otherwise you'll see Lonza's existing contracts)
3. Find a contract with status `pending_cmo_review` (if testing with Lonza's existing data, you may need to go back and submit one as Merck admin)
4. Click on it to open the detail page
5. **Expected:** You see:
   - **Accept** and **Reject** buttons
   - Full contract details including Product, SLAs, Quality Rules, Governance
   - Connection reference
   - Schema reference
6. Click **Accept**
7. **Expected:** Status changes to `pending_merck_approval`. Action buttons disappear (waiting for Merck).

| Pass? | Check |
|-------|-------|
| ☐ | CMO sees only their own contracts |
| ☐ | Contract in `pending_cmo_review` shows Accept and Reject buttons |
| ☐ | Accepting changes status to `pending_merck_approval` |
| ☐ | No action buttons visible after accepting (waiting for Merck) |

---

## PART 9: CMO USER — BATCH MANAGEMENT & DATA SUBMISSION

### Step 26 — View Existing Batches
1. Click **Batches** in the left nav
2. **Expected:** Shows Lonza's 6 batches with:
   - Lot numbers (LOT-LNZ-2026-001 through 006)
   - Product name
   - Status (submitted / in_progress)
   - Completeness badge (4/4 green or X/4 blue)

### Step 27 — Create a New Batch
1. Click **New Batch**
2. **Expected:** Form shows:
   - Lot Number (free text — CMO's own lot identifier)
   - Product (dropdown from CMO's products)
   - Manufacturing Date (date picker)
   - Notes (optional)
3. Fill in:
   - Lot Number: `LOT-LNZ-2026-007`
   - Product: Select **Ibuprofen 200mg Tablets**
   - Manufacturing Date: Choose a date 10 days ago (to trigger SLA overdue later)
   - Notes: `Customer walkthrough test batch`
4. Click **Create**
5. **Expected:** Redirected to Batch Detail page showing:
   - Status: `in_progress`
   - 4 required data elements: BMR, CoA, In-Process, Yield — all "Not Received"
   - Completeness: 0/4
   - **SFTP upload instructions** showing the exact path for each element
   - **AI upload button** per element (for CoA documents via the AI connection)

### Step 28 — View Batch Detail with Upload Instructions
1. On the Batch Detail page, examine the upload instructions:
   - **Expected (SFTP):** Shows the folder structure: `/{batchId}/{elementType}/{filename}` with the specific batchId pre-filled
   - **Expected (AI Upload):** Shows an **Upload** button next to CoA element (since Lonza has an active AI connection)
2. The `s3Path` column should show "—" for all elements (nothing received yet)

### Step 29 — Upload a CoA Document (AI Pattern)
1. On the Batch Detail page, find the **CoA** element row
2. Click the **Upload** button (visible for elements where an AI connection is active)
3. Select a PDF file (a real Certificate of Analysis PDF works best; any valid PDF will process)
4. **Expected:**
   - Upload progress indicator
   - After a few seconds, the CoA element status changes to **Received**
   - The `s3Path` column populates with the Bronze layer path: `bronze/{cmoId}/{connName}/lot={lotNumber}/...`
5. If you don't have a PDF handy, skip to Step 30 and mark the element manually

### Step 30 — Mark Elements Received Manually
1. For the remaining elements (BMR, In-Process, Yield), click **Mark Received** one at a time:
   - Mark **BMR** → Expected: 1/4 (or 2/4 if CoA was uploaded)
   - Mark **In-Process** → Expected: 2/4 (or 3/4)
2. **Leave Yield as Not Received** — this will become overdue for SLA testing

### Step 31 — Submit a Completed Batch (from existing data)
1. Go back to **Batches** list
2. Find a batch that shows 4/4 elements received but status is still `in_progress` (if any exist)
3. Click into it, then click **Submit Batch**
4. **Expected:** Status changes to `submitted`

| Pass? | Check |
|-------|-------|
| ☐ | Batch list shows all CMO batches with lot numbers and completeness |
| ☐ | New Batch form has Product as dropdown (not free text) |
| ☐ | Batch Detail shows 4 required elements with status |
| ☐ | SFTP upload instructions display correct paths per element |
| ☐ | AI upload button appears for elements with active AI connection |
| ☐ | PDF upload triggers AI processing and marks element received |
| ☐ | s3Path populates after upload with lot-partitioned Bronze path |
| ☐ | Manual "Mark Received" works per element |
| ☐ | Submit Batch changes status to `submitted` |

---

## PART 10: CMO USER — VIEW CoA DOCUMENT (AI-EXTRACTED DATA)

### Step 32 — Open a Batch with Received CoA
1. Click **Batches** → find a batch with CoA marked as **Received** and an `s3Path` value
   - Use `LOT-LNZ-2026-001` (pre-loaded demo data with CoA received) or the batch you just uploaded to
2. Click into the batch detail page

### Step 33 — View CoA Extracted Content
1. Find the **CoA** element row — it should show a **View** button (visible when s3Path is populated)
2. Click **View**
3. **Expected:** A modal opens showing the AI-extracted CoA document content:
   - **Confidence badge** at the top (green ≥85% = auto-processed; red <85% = manual review needed)
   - **Document header section:**
     - Product Name
     - Batch/Lot Number
     - Manufacturing Date
     - Expiry Date
     - Quantity
     - Disposition (Released/Quarantine)
     - Analyst name
     - QA Approver name
   - **Test Results table:**
     - Columns: Test | Method | Specification | Result | Unit | Status
     - Each row shows an individual quality test
     - Status column shows **PASS** (green) or **FAIL** (red) indicators
4. Close the modal

### Step 34 — Verify View Button Behavior
1. Check other elements (BMR, In-Process, Yield) that are marked received
2. **Expected:** The **View** button only appears on elements that have a valid `s3Path`
3. Elements marked received manually (without an actual file upload) may not have an s3Path and won't show the View button

| Pass? | Check |
|-------|-------|
| ☐ | View button appears on elements with s3Path |
| ☐ | CoA viewer modal opens and displays extracted content |
| ☐ | Confidence badge shows correct percentage with color coding |
| ☐ | Document header shows product/lot/dates/disposition |
| ☐ | Test Results table shows individual tests with PASS/FAIL status |
| ☐ | View button does NOT appear on elements without s3Path |

---

## PART 11: CMO USER — SCHEMA MANAGEMENT & PIPELINES

### Step 35 — View Schemas
1. Click **Schema Management** in the left nav
2. **Expected:** Shows only Lonza's schemas (CMO-scoped view)
3. Click the expand toggle on any schema
4. **Expected:** Shows field definitions with types and required/optional status

### Step 36 — View Pipelines
1. Click **Pipelines** in the left nav
2. **Expected:** Shows pipeline status for each active contract:
   - **SFTP pipelines:** Shows last file received, file size, timestamp, total files count, Bronze S3 path
   - **AI pipelines:** Shows documents processed count, manual review pending count, last processed timestamp
   - **Native connector pipelines:** Shows Glue connection status, ETL job info (or "not yet configured" message)
3. Click **View Details** on any pipeline
4. **Expected:** Detail panel opens with pattern-specific execution information

### Step 37 — Sign Out

| Pass? | Check |
|-------|-------|
| ☐ | Schema Management shows CMO-scoped schemas with field details |
| ☐ | Pipelines page shows status for each active contract |
| ☐ | SFTP pipeline shows file stats (last file, count, S3 path) |
| ☐ | AI pipeline shows document processing counts |
| ☐ | Native connector pipeline shows Glue connection status |
| ☐ | View Details opens pattern-specific detail panel |

---

## PART 12: MERCK ADMIN — FINAL APPROVAL & SLA VERIFICATION

### Step 38 — Login as Merck Admin

### Step 39 — Approve the Contract (if tested in Part 8)
1. Click **Data Contracts**
2. Find the contract with status `pending_merck_approval`
3. Click on it
4. **Expected:** You see **Approve & Activate** and **Reject** buttons
5. Click **Approve & Activate**
6. **Expected:** Status changes to `active`

### Step 40 — Activate CMO-Submitted Native Connector (from Step 24)
1. Click **Connections**
2. Find the connection with status `pending_merck_review` (the one the CMO submitted in Step 24)
3. Click **Review & Activate**
4. **Expected:** Detail panel shows:
   - Database details (type, host, port, database, username)
   - **Password is NOT shown** (stored in Secrets Manager only)
   - Connection method: AWS PrivateLink
   - **PrivateLink Service Name** displayed with copy button
   - Table Mappings showing source tables → data domains
5. Click **Activate — Create Glue Connection**
6. **Expected:** Status changes to `active`. Shows:
   - Glue Connection Name
   - JDBC URL
   - ETL Jobs created (one per table mapping)

### Step 41 — Run SLA Check and Verify Overdue
1. Go to **Dashboard**
2. Click **Run SLA Check**
3. **Expected:** The batch created in Step 27 (manufacturing date 10 days ago, Yield not received) should now show:
   - Yield element flagged as **Overdue** (mfg date + 5 days SLA = past due)
   - The batch appears in the overdue filter
4. Use the **Status filter** → "Has Overdue Elements"
5. **Expected:** Only batches with overdue elements are shown

### Step 42 — View Batch Detail from Dashboard
1. Click on an overdue batch row in the Dashboard
2. **Expected:** Navigates to batch detail showing which specific elements are overdue with visual indicators

| Pass? | Check |
|-------|-------|
| ☐ | Merck admin can approve contract → status becomes `active` |
| ☐ | Merck review panel for native connector shows DB details (no password) |
| ☐ | PrivateLink service name visible with copy button |
| ☐ | Activate creates Glue Connection + ETL jobs for each table mapping |
| ☐ | SLA Check correctly flags overdue elements based on manufacturing date + SLA days |
| ☐ | Dashboard overdue filter shows only affected batches |
| ☐ | Clicking batch in Dashboard navigates to batch detail |

---

## PART 13: MERCK ADMIN — PIPELINES & DATA LAKE VISIBILITY

### Step 43 — Review Pipelines Page (Merck View)
1. Click **Pipelines** in the left nav
2. **Expected:** Shows ALL pipeline statuses across all CMOs (cross-CMO view):
   - SFTP: file stats from S3
   - AI: document processing stats
   - Native: Glue job run history
3. Click **View Details** on the SFTP pipeline (Lonza Batch Records)
4. **Expected:** Shows:
   - Last file received (name, size, timestamp)
   - Total files in Bronze layer
   - Bronze S3 path
5. Click **View Details** on the Native Connector pipeline (Lonza Oracle ERP)
6. **Expected:** Shows either:
   - Glue job run details (status, start time, duration, rows extracted) if job has run, OR
   - Message: "ETL job configured, awaiting first scheduled run" or similar

| Pass? | Check |
|-------|-------|
| ☐ | Pipelines shows cross-CMO view for Merck admin |
| ☐ | SFTP pipeline detail shows real file statistics from S3 |
| ☐ | AI pipeline detail shows processing counts |
| ☐ | Native connector pipeline shows Glue job status |

---

## PART 14: WORKFLOW SUMMARY — COMPLETE ONBOARDING SEQUENCE

This section summarizes the correct end-to-end onboarding order for adding a new CMO:

| # | Action | Role | Portal Page |
|---|--------|------|-------------|
| 1 | Register CMO organization | Merck Admin | Register New CMO |
| 2 | Create product(s) | Merck Admin | Products |
| 3 | Create connection(s) — SFTP / AI / Native | Merck Admin or CMO | Connections |
| 4 | Activate connection(s) | Merck Admin | Connections |
| 5 | Create or infer schema(s) | Merck Admin | Schema Management |
| 6 | Register schema in Glue | Merck Admin | Schema Management |
| 7 | Create data contract (links CMO + Product + Connection + Schema + SLAs) | Merck Admin | Data Contracts |
| 8 | Submit contract to CMO | Merck Admin | Contract Detail |
| 9 | Invite CMO user | Merck Admin | CMO Partners |
| 10 | CMO reviews & accepts contract | CMO User | My Contracts |
| 11 | Merck approves contract → active | Merck Admin | Contract Detail |
| 12 | CMO creates batches and submits data | CMO User | Batches / Batch Detail |
| 13 | Monitor SLA compliance | Merck Admin | Dashboard |

---

## OVERALL TEST PASS CRITERIA

### Platform Access & Navigation
| # | Check | Pass? |
|---|-------|-------|
| 1 | Portal loads and login works for both roles | ☐ |
| 2 | Merck admin sees full navigation (10 items) | ☐ |
| 3 | CMO user sees limited navigation (6 items, no admin pages) | ☐ |
| 4 | Multi-tenant isolation: CMO sees only their own data | ☐ |

### CMO Management
| # | Check | Pass? |
|---|-------|-------|
| 5 | Register new CMO with full details | ☐ |
| 6 | CMO Detail page with 4 tabs (Connections, Schemas, Contracts, Batches) | ☐ |
| 7 | Edit CMO details | ☐ |
| 8 | Invite CMO user | ☐ |

### Connections (3 Patterns)
| # | Check | Pass? |
|---|-------|-------|
| 9 | Create + activate SFTP connection (credentials generated) | ☐ |
| 10 | Create + activate AI Unstructured connection | ☐ |
| 11 | CMO self-service: submit native connector with DB details | ☐ |
| 12 | Merck review: native connector details shown (no password) | ☐ |
| 13 | Merck activate: Glue Connection + ETL jobs created | ☐ |
| 14 | PrivateLink service name displayed correctly | ☐ |

### Schema Management
| # | Check | Pass? |
|---|-------|-------|
| 15 | Create schema manually with typed fields | ☐ |
| 16 | Infer schema from CSV/JSON file | ☐ |
| 17 | Register schema in Glue Schema Registry | ☐ |
| 18 | Edit schema (resets to draft if previously registered) | ☐ |
| 19 | Field expansion shows types and required status | ☐ |

### Data Contracts
| # | Check | Pass? |
|---|-------|-------|
| 20 | Create contract with Product + Connection + Schema + SLAs | ☐ |
| 21 | Contract approval workflow: draft → pending_cmo_review → pending_merck_approval → active | ☐ |
| 22 | CMO can accept or reject | ☐ |
| 23 | Merck can approve or reject | ☐ |
| 24 | Contract detail shows all sections (SLAs, governance, quality rules) | ☐ |

### Batch Management & Data Submission
| # | Check | Pass? |
|---|-------|-------|
| 25 | Create batch with lot number + product (dropdown) | ☐ |
| 26 | Batch detail shows 4 required elements with status | ☐ |
| 27 | SFTP upload path instructions displayed per batch | ☐ |
| 28 | AI upload button works per element (PDF → Textract) | ☐ |
| 29 | s3Path populated with lot-partitioned Bronze path after upload | ☐ |
| 30 | Mark elements received manually | ☐ |
| 31 | Submit completed batch | ☐ |

### CoA Document Viewing
| # | Check | Pass? |
|---|-------|-------|
| 32 | View button appears on elements with s3Path | ☐ |
| 33 | CoA modal: confidence badge (green/red) | ☐ |
| 34 | CoA modal: document header (product, lot, dates, disposition) | ☐ |
| 35 | CoA modal: test results table with PASS/FAIL indicators | ☐ |

### SLA & Compliance
| # | Check | Pass? |
|---|-------|-------|
| 36 | Dashboard summary cards show correct counts | ☐ |
| 37 | Run SLA Check flags overdue elements correctly | ☐ |
| 38 | Dashboard filters work (CMO, status) | ☐ |
| 39 | Overdue visual indicators on batches and elements | ☐ |

### Pipelines
| # | Check | Pass? |
|---|-------|-------|
| 40 | SFTP pipeline shows real file stats from S3 | ☐ |
| 41 | AI pipeline shows document processing counts | ☐ |
| 42 | Native connector pipeline shows Glue job status | ☐ |

---

## FEEDBACK TEMPLATE

After completing this walkthrough, please provide your assessment:

### Overall Assessment
- [ ] **Meets requirements** — ready to proceed
- [ ] **Meets requirements with modifications** — see notes below
- [ ] **Does not meet requirements** — see notes below

### What works well?
_List features or workflows that meet or exceed expectations:_



### What's missing or needs changes?
_List any gaps, additional features needed, or workflow modifications:_



### Priority items for next iteration:
_If modifications are needed, what's most important?_



### Additional comments:


