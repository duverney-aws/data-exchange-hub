# End-to-End Test Case: Pattern 2 — SFTP Ingestion

**Portal URL:** https://main.d28qy16znlocxk.amplifyapp.com  
**Direct Login:** https://pharma-data-exchange-portal.auth.us-east-1.amazoncognito.com/login?client_id=2eitutbi1gkogudchaudb9rtr4&response_type=code&scope=openid+email+profile&redirect_uri=https://main.d28qy16znlocxk.amplifyapp.com/

## Context

CMOs are external organizations — they may be on-premise, on a different cloud, or have no cloud infrastructure at all. Pattern 2 (SFTP) is designed so the CMO only needs a standard SFTP client (FileZilla, WinSCP, `sftp` CLI, or any legacy system that can push files over SFTP). No AWS account, CLI, or SDK required on the CMO side.

## Prerequisites

- Complete the main E2E test (E2E_TEST_CASE.md) through Step 13 (contract is `active`)
- OR have an active contract with a known contractId

## Test Accounts

| Role | Email | Password | Perspective |
|------|-------|----------|-------------|
| Merck Admin | merck-admin@pharma-exchange.demo | MerckAdmin2026! | Merck internal (AWS) |
| CMO User | cmo-user@pharma-exchange.demo | CMOUser2026! | External partner (portal only) |

---

## PART 1: MERCK ADMIN — ACTIVATE SFTP INTEGRATION

### Step 1 — Login as Merck Admin
1. Open the portal URL
2. Sign in with: `merck-admin@pharma-exchange.demo` / `MerckAdmin2026!`
3. **Expected:** Dashboard loads

### Step 2 — Navigate to Active Contract
1. Click **Data Contracts** in the left nav
2. Find the active contract (e.g., `CMO-CMO-9E779DF7-BATCH-RECORDS-001`)
3. Click on it to open the detail page
4. **Expected:** Status is `active`. You see either:
   - An **"Integration not configured"** info banner with a **Configure Integration** button, OR
   - An **SFTP Connection Details** section (if already activated)
5. If you see the info banner, click **Configure Integration**

Success

### Step 3 — Select SFTP Pattern and Activate
1. On the Integration Pattern Selection page, you should see 3 pattern cards:
   - Pattern 1: Native Database Connectors
   - Pattern 2: Secure File Transfer (SFTP)
   - Pattern 3: AI-Powered Unstructured Data
2. Select **Pattern 2: Secure File Transfer (SFTP)**
3. **Expected:** An info alert appears: "SFTP credentials will be provisioned automatically when you activate the pipeline."
4. Click **Activate Pipeline**
5. **Expected:** Success message. The SFTP Connection Details section appears with:
   - **Hostname:** `s-XXXXXXXXX.server.transfer.us-east-1.amazonaws.com`
   - **Username:** `{cmoId}-{dataDomain}` (e.g., `cmo-9e779df7-batch-records`)
   - **Password:** a 24-character random string
6. **Write down the hostname, username, and password** — these will be shared with the CMO

Failed.  When clicking on activate pipeline i get error Pipeline activation failed: Access denied. Required role: merck-admins

### Step 4 — Verify SFTP Credentials on Contract Detail
1. Click **Data Contracts** → click on the same contract
2. **Expected:** You now see:
   - Status banner: "This contract is active using **Secure File Transfer (SFTP)**"
   - **SFTP Connection Details** section with hostname, username, password fields
   - A note: "Supported formats: CSV, JSON, Parquet"

### Step 5 — Sign Out

---

## PART 2: CMO USER — SFTP FILE UPLOAD

> **This simulates the CMO's experience.** The CMO receives SFTP credentials from Merck (via email, portal, or secure channel) and uses any standard SFTP client to upload files. No AWS account or tooling needed.

### Step 6 — (Optional) CMO Views Credentials in Portal
1. Login as CMO user: `cmo-user@pharma-exchange.demo` / `CMOUser2026!`
2. Click **My Contracts** → click on the active contract
3. **Expected:** SFTP Connection Details section is visible with hostname, username, password
4. Sign out

> In production, the CMO may never use the portal — Merck would send them the SFTP credentials directly.

### Step 7 — Prepare Test Files
Create these files on the CMO's machine (your local machine):

**batch-data-001.csv:**
```csv
batch_id,product_name,lot_number,quantity,unit,manufacturing_date,expiry_date,status
B-2026-001,Ibuprofen 200mg,LOT-TEST-001,50000,tablets,2026-04-20,2028-04-20,released
B-2026-002,Ibuprofen 200mg,LOT-TEST-002,75000,tablets,2026-04-22,2028-04-22,in_progress
```

**batch-data-002.json:**
```json
[
  {"batch_id": "B-2026-003", "product": "Ibuprofen 200mg", "lot": "LOT-TEST-003", "qty": 60000}
]
```

### Step 8 — Connect via SFTP and Upload Files

**Using FileZilla / WinSCP (most CMOs will use this):**
1. Host: hostname from Step 3
2. Port: `22`
3. Protocol: SFTP
4. Username: from Step 3
5. Password: from Step 3
6. Upload `batch-data-001.csv` and `batch-data-002.json`

**Using command-line `sftp`:**
```bash
sftp USERNAME@HOSTNAME
# Enter password when prompted
put batch-data-001.csv
put batch-data-002.json
ls
bye
```

**Expected:**
- Connection succeeds with password authentication
- Files upload successfully
- `ls` may show files briefly (they get moved by the processor within seconds)

### Step 9 — Upload an Unsupported File
1. Upload a file with an unsupported extension (e.g., `notes.txt` or `report.xlsx`)
2. **Expected:** File uploads without error (SFTP doesn't reject it), but it will NOT be processed into the data lake. It stays in the incoming directory.

---

## PART 3: MERCK ADMIN — VERIFY INGESTION

> **Only Merck has access to the AWS data lake.** This is where Merck verifies that CMO data arrived correctly.

### Step 10 — Login as Merck Admin

### Step 11 — Verify Files Were Processed (AWS CLI)
```bash
BUCKET="pharmadataexchangedatalakes-datalakebucket0256ea8e-dcuncyvlwsel"
CMO_ID="cmo-9e779df7"
DOMAIN="batch-records"

# Incoming should be empty (processed files are moved)
echo "=== Incoming (should be empty for CSV/JSON, may contain unsupported files) ==="
aws s3 ls "s3://$BUCKET/bronze/$CMO_ID/$DOMAIN/incoming/" --region us-east-1

# Date-partitioned Bronze layer should have the files
echo "=== Bronze Layer ==="
aws s3 ls "s3://$BUCKET/bronze/$CMO_ID/$DOMAIN/" --recursive --region us-east-1
```

**Expected:**
- `incoming/` is empty for CSV/JSON files (they were moved)
- `incoming/` may contain the unsupported `.txt`/`.xlsx` file (not processed)
- Bronze layer contains:
  - `bronze/{cmoId}/{dataDomain}/year=2026/month=04/day=28/batch-data-001.csv`
  - `bronze/{cmoId}/{dataDomain}/year=2026/month=04/day=28/batch-data-002.json`

### Step 12 — Verify File Contents
```bash
# Download and inspect a processed file
aws s3 cp "s3://$BUCKET/bronze/$CMO_ID/$DOMAIN/year=2026/month=04/day=28/batch-data-001.csv" /tmp/verify.csv --region us-east-1
cat /tmp/verify.csv
```

**Expected:** File contents match exactly what the CMO uploaded.

---

## TEST PASS CRITERIA

| # | Check | Pass? |
|---|-------|-------|
| 1 | Active contract shows "Integration not configured" banner | ☐ |
| 2 | Integration Pattern Selection page shows 3 pattern cards | ☐ |
| 3 | Selecting SFTP and clicking Activate returns credentials | ☐ |
| 4 | Contract detail shows SFTP Connection Details after activation | ☐ |
| 5 | Contract detail shows "active using Secure File Transfer" banner | ☐ |
| 6 | CMO user can see SFTP credentials on their contract detail | ☐ |
| 7 | SFTP login with password succeeds (no AWS account needed) | ☐ |
| 8 | CSV file upload via SFTP succeeds | ☐ |
| 9 | JSON file upload via SFTP succeeds | ☐ |
| 10 | Processed files appear in date-partitioned Bronze path | ☐ |
| 11 | incoming/ directory is empty after processing | ☐ |
| 12 | Unsupported file extensions are NOT processed (stay in incoming/) | ☐ |
| 13 | File contents are preserved exactly (no corruption) | ☐ |

---

## Quick-Test Script (Merck Admin Only)

Run this after Step 3 to test the full flow from the command line:

```bash
#!/bin/bash
set -e

# --- Fill in from Step 3 ---
SFTP_HOST="s-89e811043fec4d7d8.server.transfer.us-east-1.amazonaws.com"
SFTP_USER="cmo-9e779df7-batch-records"
SFTP_PASS="YOUR_PASSWORD"
BUCKET="pharmadataexchangedatalakes-datalakebucket0256ea8e-dcuncyvlwsel"
CMO_ID="cmo-9e779df7"
DOMAIN="batch-records"

# Create test files
echo "batch_id,product,qty" > /tmp/sftp-test.csv
echo "B001,DrugX,1000" >> /tmp/sftp-test.csv
echo '[{"id":"B002"}]' > /tmp/sftp-test.json
echo "this should not be processed" > /tmp/sftp-test.txt

# Upload CSV
echo "=== 1. Uploading CSV ==="
sshpass -p "$SFTP_PASS" sftp -o StrictHostKeyChecking=no "${SFTP_USER}@${SFTP_HOST}" <<< "put /tmp/sftp-test.csv"

# Upload JSON
echo "=== 2. Uploading JSON ==="
sshpass -p "$SFTP_PASS" sftp -o StrictHostKeyChecking=no "${SFTP_USER}@${SFTP_HOST}" <<< "put /tmp/sftp-test.json"

# Upload unsupported file
echo "=== 3. Uploading TXT (should NOT be processed) ==="
sshpass -p "$SFTP_PASS" sftp -o StrictHostKeyChecking=no "${SFTP_USER}@${SFTP_HOST}" <<< "put /tmp/sftp-test.txt"

# Wait for processing
echo "=== Waiting 10s for Lambda processing ==="
sleep 10

# Verify
echo "=== 4. Incoming dir (should only have .txt) ==="
aws s3 ls "s3://$BUCKET/bronze/$CMO_ID/$DOMAIN/incoming/" --region us-east-1

echo "=== 5. Bronze layer (should have .csv and .json) ==="
aws s3 ls "s3://$BUCKET/bronze/$CMO_ID/$DOMAIN/" --recursive --region us-east-1

echo "=== DONE ==="
```
