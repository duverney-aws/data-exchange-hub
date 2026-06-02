# End-to-End Test Case: Pharma Data Exchange Hub

**Portal URL:** https://main.d28qy16znlocxk.amplifyapp.com  
**Direct Login:** https://pharma-data-exchange-portal.auth.us-east-1.amazoncognito.com/login?client_id=2eitutbi1gkogudchaudb9rtr4&response_type=code&scope=openid+email+profile&redirect_uri=https://main.d28qy16znlocxk.amplifyapp.com/

## Test Accounts

| Role | Email | Password |
|------|-------|----------|
| Merck Admin | merck-admin@pharma-exchange.demo | MerckAdmin2026! |
| CMO User | cmo-user@pharma-exchange.demo | CMOUser2026! |

> **Note:** Data tables have been cleared. The CMO user's org link is cleared — you MUST run Step 5 (Invite User) to re-link them.

---

## PART 1: MERCK ADMIN WORKFLOW

### Step 1 — Login as Merck Admin
1. Open the portal URL above
2. Click "Sign In" (redirects to Cognito hosted UI)
3. Enter: `merck-admin@pharma-exchange.demo` / `MerckAdmin2026!`
4. **Expected:** Redirected to Dashboard. You see:
   - Summary cards: Active Contracts, Total Batches, Incomplete, Overdue (all 0)
   - Batch Completeness table (empty)
   - Left nav: Dashboard, CMO Partners, Register New CMO, Products, Data Contracts, Batches, Schema Management, Pipelines, NL Query

Successful

### Step 2 — Register a New CMO
1. Click **Register New CMO** in the left nav
2. Fill in:
   - Organization Name: `PharmaCorp Test`
   - Contact Email: `test@pharmacorp.demo`
   - Contact Phone: `555-0100`
   - Address: `100 Pharma Way, Boston, MA`
   - GxP Certified: Yes
3. Click **Register CMO**
4. **Expected:** Success message, redirected to Products page with `?cmoId=` in URL and "Add Product" modal auto-opens
5. **Write down the cmoId** from the URL (e.g., `cmo-xxxxxxxx`)

Successful

CMOID = cmo-9e779df7


### Step 3 — Create a Product for the New CMO
1. You should already be on the Products page with the modal open
2. Fill in:
   - Product Name: `Ibuprofen 200mg`
   - Strength: `200mg`
   - Dosage Form: `Tablet`
   - CMO: should be pre-selected to PharmaCorp Test
   - Description: `Test product for E2E validation`
3. Click **Create Product**
4. **Expected:** Product appears in the table with a Product ID column visible

Successful
ProductID prod-933d044c4b4d

### Step 4 — Go to CMO Partners and Verify
1. Click **CMO Partners** in the left nav
2. **Expected:** You see PharmaCorp Test in the list with status **active**
3. Verify actions available: Invite User, Create Contract, Edit, Deactivate

Success

### Step 5 — Invite CMO User (REQUIRED)
1. On the CMO Partners page, click **Invite User** next to PharmaCorp Test
2. Enter:
   - Email: `cmo-user@pharma-exchange.demo`
   - First Name: `CMO`
   - Last Name: `User`
3. Click **Invite**
4. **Expected:** Success message. This links the existing CMO user account to PharmaCorp Test.

Successful


### Step 6 — Create a Data Contract
1. Click **Data Contracts** in the left nav
2. Click **Create Contract**
3. Fill in:
   - CMO: Select **PharmaCorp Test**
   - Product: Select **Ibuprofen 200mg**
   - Data Domain: `batch-records`
   - Schema ID: `batch-records-schema`
   - Schema Version: `1`
   - Quality Rules: leave defaults or add one
   - Delivery Frequency: `daily`
   - Delivery Timezone: `America/New_York`
   - Governance — Classification: `confidential`
   - Governance — Retention Years: `7`
   - Governance — Encryption Required: Yes
   - **Data Submission SLAs:**
     - BMR: `5` days
     - CoA: `5` days
     - In-Process: `1` day
     - Yield: `5` days
4. Click **Create**
5. **Expected:** Contract created in `draft` status, redirected to contract detail page
6. **Expected:** Product ID and Data Submission SLAs sections are visible on the detail page
7. **Write down the contractId**

Success - It redirects to the Data Contracts List - I have to click on the contract to launc the Data Contrat details
Contract ID = CMO-CMO-9E779DF7-BATCH-RECORDS-001

### Step 7 — Submit Contract to CMO for Review
1. On the contract detail page, you should see a **Submit to CMO** button
2. Click **Submit to CMO**
3. **Expected:** Status changes to `pending_cmo_review`. The Submit to CMO button disappears and a Reject button appears.
4. Note: The "Save Changes" button at the bottom is for editing draft fields only — it disappears after submit.

Success


### Step 8 — Sign Out
1. Click your name in the top-right corner → **Sign out**

---
Success

## PART 2: CMO USER WORKFLOW

### Step 9 — Login as CMO User
1. Open the portal URL
2. Sign in with: `cmo-user@pharma-exchange.demo` / `CMOUser2026!`
3. **Expected:** Redirected to Dashboard. You see:
   - Summary cards scoped to YOUR batches only
   - Left nav: Dashboard, My Contracts, Batches, Integration Setup, Schema Management, Pipelines
   - **No** CMO Partners, Register New CMO, or Products links

Success - Dashboard is empty

### Step 10 — Review and Accept the Contract
1. Click **My Contracts** in the left nav
2. **Expected:** You see ONLY contracts for PharmaCorp Test
3. Find the contract — status should be `pending_cmo_review`
4. Click on it to open the detail page
5. **Expected:** You see **Accept** and **Reject** buttons. Product ID and SLAs are visible.
6. Click **Accept**
7. **Expected:** Status changes to `pending_merck_approval`
8. You should now see NO action buttons (waiting for Merck to approve)


Success


### Step 11 — Sign Out

---

## PART 3: MERCK ADMIN — FINAL APPROVAL

### Step 12 — Login as Merck Admin Again

### Step 13 — Approve the Contract
1. Click **Data Contracts** in the left nav
2. Find the contract — status should be `pending_merck_approval`
3. Click on it
4. **Expected:** You see **Approve & Activate** and **Reject** buttons
5. Click **Approve & Activate**
6. **Expected:** Status changes to `active`

Success

### Step 14 — Sign Out

---

## PART 4: CMO USER — CREATE BATCH & SUBMIT DATA

### Step 15 — Login as CMO User Again

### Step 16 — Create a New Batch
1. Click **Batches** in the left nav
2. Click **New Batch**
3. Fill in:
   - Lot Number: `LOT-TEST-001`
   - Contract: Select the contract you just activated (should be the only active one)
   - Product: **Expected:** This is a DROPDOWN (not free text). Select Ibuprofen 200mg.
   - Manufacturing Date: `2026-04-20` (use a past date to test SLA overdue)
   - Notes: `E2E test batch`
4. Click **Create**
5. **Expected:** Redirected to Batch Detail page showing:
   - Status: `In Progress`
   - 4 required elements: BMR, CoA, In-Process, Yield — all showing "Not Received" / "Mark Received"
   - Completeness: 0/4

Success

### Step 17 — Mark Data Elements as Received
1. On the Batch Detail page, mark elements received one at a time:
   - Click **Mark Received** next to **BMR** → Expected: 1/4
   - Click **Mark Received** next to **CoA** → Expected: 2/4
   - Click **Mark Received** next to **In-Process** → Expected: 3/4
2. **Do NOT mark Yield yet** — leave it missing for SLA testing


Success

### Step 18 — Verify Dashboard Shows Incomplete Batch
1. Click **Dashboard** in the left nav
2. **Expected:** You see your batch with:
   - Completeness: 3/4 (blue badge)
   - Missing: Yield
   - Overdue: None (not yet checked)

Success


### Step 19 — Sign Out

---

## PART 5: MERCK ADMIN — SLA CHECK & DASHBOARD

### Step 20 — Login as Merck Admin

### Step 21 — Run SLA Check from Dashboard
1. You should be on the Dashboard
2. **Expected:** You see the batch from Step 16 in the table
3. Click **Run SLA Check** button
4. **Expected:** 
   - Success message: "SLA check complete: 1 batches checked, 1 elements flagged overdue"
   - The batch's Yield element should now show as **Overdue** (mfg date 2026-04-20 + 5 days = 2026-04-25, today is past that)
   - In-Process was already received, so it should NOT be overdue
   - Only unreceived elements get flagged

Success


### Step 22 — Use Dashboard Filters
1. Try the **CMO filter** dropdown — select **PharmaCorp Test**
   - **Expected:** Only batches from that CMO shown
2. Try the **Status filter** — select "Has Overdue Elements"
   - **Expected:** Only the batch with overdue Yield shown
3. Select "Has Missing Elements"
   - **Expected:** Same batch (Yield is missing)
4. Reset both filters to "All"

Success


### Step 23 — Click Into Batch Detail
1. Click on the batch row in the Dashboard table
2. **Expected:** Navigates to batch detail showing:
   - BMR, CoA, In-Process: Received ✓
   - Yield: Not Received, Overdue indicator

Success - Status shows Pending
---

## PART 6: CMO USER — COMPLETE THE BATCH

### Step 24 — Login as CMO User

### Step 25 — Complete the Batch
1. Click **Batches** → click on `LOT-TEST-001`
2. Click **Mark Received** next to **Yield**
3. **Expected:** 4/4 elements received, completeness badge turns green
4. Click **Submit Batch**
5. **Expected:** Status changes to `Submitted`

Success


### Step 26 — Verify Dashboard
1. Click **Dashboard**
2. **Expected:** Batch shows:
   - Completeness: 4/4 (green)
   - Status: Submitted
   - Overdue: Yield still shows overdue (it was late, even though now received)

---
Success


## PART 7: MERCK ADMIN — FINAL VERIFICATION

### Step 27 — Login as Merck Admin
1. Sign in and go to Dashboard
2. **Expected:** 
   - Summary cards: at least 1 active contract, 1 batch
   - Batch shows 4/4 complete, submitted status
3. Run SLA Check again
4. **Expected:** No new elements flagged (all received)

Success - 

## TEST PASS CRITERIA

| # | Check | Pass? |
|---|-------|-------|
| 1 | Merck admin can register CMO (status = active) | ☐ |
| 2 | Merck admin can create product for CMO (productId visible) | ☐ |
| 3 | Merck admin can create contract with product + SLAs | ☐ |
| 4 | Merck admin can submit contract to CMO (status updates) | ☐ |
| 5 | CMO user sees ONLY their contracts | ☐ |
| 6 | CMO user can accept contract | ☐ |
| 7 | Merck admin can approve contract → active | ☐ |
| 8 | CMO batch form: Product is a dropdown (not free text) | ☐ |
| 9 | CMO can create batch with lot number + product + contract | ☐ |
| 10 | CMO can mark individual data elements received | ☐ |
| 11 | Dashboard shows completeness badges correctly | ☐ |
| 12 | Run SLA Check flags overdue elements | ☐ |
| 13 | Dashboard filters work (CMO, status) | ☐ |
| 14 | CMO can submit completed batch | ☐ |
| 15 | Both roles see appropriate nav items | ☐ |
