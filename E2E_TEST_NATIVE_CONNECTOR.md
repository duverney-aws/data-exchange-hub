# End-to-End Test Case: Pattern 1 — Native Database Connector

**Portal URL:** https://main.d28qy16znlocxk.amplifyapp.com  
**Direct Login:** https://pharma-data-exchange-portal.auth.us-east-1.amazoncognito.com/login?client_id=2eitutbi1gkogudchaudb9rtr4&response_type=code&scope=openid+email+profile&redirect_uri=https://main.d28qy16znlocxk.amplifyapp.com/

## Context

Pattern 1 (Native Connectors) allows CMOs with modern database platforms (SQL Server, Oracle, PostgreSQL, MySQL, Snowflake, SAP HANA) to share data directly via JDBC. The CMO self-configures their database credentials in the portal; Merck reviews and activates the AWS Glue connection with one click. No file transfer or manual data export is required on the CMO side.

**Connection flow:**
```
CMO submits DB credentials → pending_merck_review → Merck activates → active (Glue Connection created)
```

**Three connectivity methods are supported:**
- **Direct** — public endpoint or VPN-connected DB
- **NLB** — CMO puts a Network Load Balancer in front of their DB; Merck connects to the NLB DNS
- **AWS PrivateLink** — most secure; CMO creates a VPC Endpoint Service, shares the service name with Merck; traffic stays on the AWS backbone

## Prerequisites

- An active contract exists for the CMO (complete E2E_TEST_CASE.md through Step 13, or use an existing active contract)
- A real or test database endpoint is available (see Test Database Options below)

## Test Accounts

| Role | Email | Password |
|------|-------|----------|
| Merck Admin | merck-admin@pharma-exchange.demo | MerckAdmin2026! |
| CMO User | cmo-user@pharma-exchange.demo | CMOUser2026! |

## Test Database Options

Use any of the following for testing. The Glue connection will be created but connectivity is only verified if the DB is reachable from Glue's network.

**Option A — Existing MySQL RDS in this account (reachable from Glue with VPC config):**
- Host: `tpc-database.cbf3v6irjuur.us-east-1.rds.amazonaws.com`
- Port: `3306`
- Database: `tpc`
- Type: `mysql`

**Option B — Dummy endpoint (tests portal flow and Glue connection creation only; connection test will fail but the Glue object is created):**
- Host: `test-db.example.com`
- Port: `1433`
- Database: `pharma_db`
- Type: `sqlserver`
- Username: `testuser`
- Password: `TestPass123!`

> For a full E2E including data extraction, use Option A with valid credentials and ensure the Glue subnet/security group env vars are set on the Lambda.

---

## PART 1: CMO USER — SUBMIT DATABASE CONNECTION

### Step 1 — Login as CMO User
1. Open the portal URL
2. Sign in with: `cmo-user@pharma-exchange.demo` / `CMOUser2026!`
3. **Expected:** Dashboard loads showing CMO-scoped view

### Step 2 — Navigate to My Connections
1. Click **My Connections** in the left nav
2. **Expected:** Connections list loads. You may see existing SFTP or AI connections for this CMO.

### Step 3 — Add a Database Connection
1. Click **Add Database Connection**
2. **Expected:** A modal opens with fields for:
   - Connection Name
   - Database Type (SQL Server, Oracle, PostgreSQL, MySQL, Snowflake, SAP HANA)
   - Connection Method (Direct, NLB, AWS PrivateLink)
   - Host / Endpoint
   - Port (auto-fills based on DB type)
   - Database Name
   - Username
   - Password

### Step 4 — Fill in Connection Details
Fill in the form using Option B (dummy endpoint) or Option A (real DB):

| Field | Value (Option B) |
|-------|-----------------|
| Connection Name | `test-sqlserver-connector` |
| Database Type | SQL Server |
| Connection Method | Direct |
| Host | `test-db.example.com` |
| Port | `1433` |
| Database | `pharma_db` |
| Username | `testuser` |
| Password | `TestPass123!` |

Click **Submit**.

**Expected:**
- Modal closes
- New connection appears in the table with status **`pending_merck_review`** (shown as in-progress indicator)
- No "Review & Activate" button visible to CMO (that's Merck-only)

### Step 5 — Sign Out

---

## PART 2: MERCK ADMIN — REVIEW AND ACTIVATE

### Step 6 — Login as Merck Admin
1. Sign in with: `merck-admin@pharma-exchange.demo` / `MerckAdmin2026!`
2. **Expected:** Dashboard loads

### Step 7 — Navigate to Connections
1. Click **Connections** in the left nav
2. **Expected:** Connections list shows the new connection with:
   - Status: `pending_merck_review`
   - A **Review & Activate** button in the Actions column

### Step 8 — Review Connection Details
1. Click **Review & Activate** on the `test-sqlserver-connector` row
2. **Expected:** A detail panel opens showing:
   - Status: `pending_merck_review`
   - An info alert: *"The CMO has submitted their database credentials. Review the details below and click Activate to create the AWS Glue connection."*
   - Database Type: `SQLSERVER`
   - Connection Method: `Direct`
   - Host: `test-db.example.com`
   - Port: `1433`
   - Database: `pharma_db`
   - Username: `testuser`
   - **Password is NOT shown** (stored in Secrets Manager only)
   - If PrivateLink was selected: PrivateLink Service Name with a copy button

### Step 9 — Activate the Connection
1. Click **Activate — Create Glue Connection**
2. **Expected:**
   - Button shows loading spinner briefly
   - Status changes to **`active`**
   - A new section appears: **Glue Connection Details** with:
     - Glue Connection Name: `cmo-{cmoId}-test-sqlserver-connector` (e.g., `cmo-9e779df7-test-sqlserver-connector`)
     - Database Type: `SQLSERVER`
     - JDBC URL: `jdbc:sqlserver://test-db.example.com:1433;databaseName=pharma_db`

### Step 10 — Verify Glue Connection in AWS
```bash
# Verify the Glue connection was created
aws glue get-connection --name "cmo-9e779df7-test-sqlserver-connector" --region us-east-1

# Or list all cmo- prefixed connections
aws glue get-connections --region us-east-1 \
  --query "ConnectionList[?starts_with(Name, 'cmo-')].[Name,ConnectionType,ConnectionProperties.JDBC_CONNECTION_URL]" \
  --output table
```

**Expected:** A JDBC connection exists with:
- `ConnectionType: JDBC`
- `JDBC_CONNECTION_URL: jdbc:sqlserver://test-db.example.com:1433;databaseName=pharma_db`
- `USERNAME: testuser`

### Step 11 — Verify Credentials in Secrets Manager
```bash
# Verify the secret was created (do NOT print the value)
aws secretsmanager describe-secret \
  --secret-id "cmo/cmo-9e779df7/jdbc-test-sqlserver-connector" \
  --region us-east-1 \
  --query "{Name:Name,ARN:ARN,LastChangedDate:LastChangedDate}"
```

**Expected:** Secret exists with the correct name.

---

## PART 3: CMO USER — VERIFY ACTIVE CONNECTION

### Step 12 — Login as CMO User
1. Sign in as `cmo-user@pharma-exchange.demo` / `CMOUser2026!`
2. Click **My Connections**
3. **Expected:** The connection now shows status **`active`**
4. Click on the connection row to open the detail panel
5. **Expected:** Glue Connection Details section is visible with the Glue connection name and JDBC URL

---

## PART 4: PRIVATELINK FLOW (Optional)

> Skip this if not testing PrivateLink connectivity.

### Step 13 — CMO Creates a PrivateLink Connection
1. Login as CMO user → **Add Database Connection**
2. Set Connection Method to **AWS PrivateLink**
3. Fill in:
   - Host: VPC Endpoint DNS (e.g., `vpce-xxx.vpce-svc-xxx.us-east-1.vpce.amazonaws.com`)
   - PrivateLink Service Name: `com.amazonaws.vpce.us-east-1.vpce-svc-xxxxxxxxxxxxxxx`
4. Submit

### Step 14 — Merck Reviews PrivateLink Details
1. Login as Merck admin → Connections → **Review & Activate**
2. **Expected:** PrivateLink Service Name is shown with a **copy button**
3. Merck network team would use this service name to create a VPC Endpoint in Merck's account
4. Click **Activate — Create Glue Connection**
5. **Expected:** Glue connection created pointing to the VPC Endpoint DNS

---

## TEST PASS CRITERIA

| # | Check | Pass? |
|---|-------|-------|
| 1 | CMO sees "Add Database Connection" button in My Connections | ✅ |
| 2 | CMO modal shows all fields: DB type, connection method, host, port, db, user, password | ✅ |
| 3 | Port auto-fills when DB type changes (SQL Server → 1433, MySQL → 3306, etc.) | ✅ |
| 4 | After CMO submits, connection appears with status `pending_merck_review` | ✅ |
| 5 | CMO does NOT see "Review & Activate" button (Merck-only action) | ✅ |
| 6 | Merck admin sees "Review & Activate" button for `pending_merck_review` connections | ✅ |
| 7 | Merck review panel shows DB details but NOT the password | ✅ |
| 8 | Clicking "Activate — Create Glue Connection" changes status to `active` | ✅ |
| 9 | Active connection shows Glue Connection Name and JDBC URL in portal | ✅ |
| 10 | `aws glue get-connection` confirms JDBC connection exists with correct URL | ✅ |
| 11 | `aws secretsmanager describe-secret` confirms credentials secret exists | ✅ |
| 12 | CMO user sees `active` status after Merck activates | ✅ |

---

## Cleanup (After Testing)

```bash
CMO_ID="cmo-9e779df7"
CONN_NAME="test-sqlserver-connector"

# Delete Glue connection
aws glue delete-connection --connection-name "${CMO_ID}-${CONN_NAME}" --region us-east-1

# Delete secret
aws secretsmanager delete-secret \
  --secret-id "cmo/${CMO_ID}/jdbc-${CONN_NAME}" \
  --force-delete-without-recovery --region us-east-1
```
