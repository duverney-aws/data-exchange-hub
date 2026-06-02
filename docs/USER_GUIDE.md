# Pharma Data Exchange Hub — User Guide

Welcome to the Pharma Data Exchange Hub. This guide walks you through everything you need to get started as a CMO (Contract Manufacturing Organization) administrator — from registering your organization to querying your data with plain English.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [CMO Onboarding Guide](#2-cmo-onboarding-guide)
3. [Data Contract Creation Guide](#3-data-contract-creation-guide)
4. [Integration Pattern Selection Guide](#4-integration-pattern-selection-guide)
5. [Schema Management](#5-schema-management)
6. [Pipeline Activation and Monitoring](#6-pipeline-activation-and-monitoring)
7. [Natural Language Query Guide](#7-natural-language-query-guide)
8. [Dashboard and Reporting](#8-dashboard-and-reporting)
9. [FAQ](#9-faq)

---

## 1. Getting Started

### What Is the Pharma Data Exchange Hub?

The Pharma Data Exchange Hub is a self-service platform that lets CMOs share pharmaceutical manufacturing data with Merck — securely, quickly, and without lengthy manual setup. Instead of the traditional 3–6 month integration cycle, you can be up and running in 1–4 weeks.

### What Can You Do on the Platform?

- **Register your organization** and get unique credentials
- **Define data contracts** that describe what data you'll share, how often, and at what quality level
- **Choose an integration pattern** that fits your systems (direct database connection, file upload, or AI-powered document extraction)
- **Upload sample data** to automatically infer schemas
- **Activate pipelines** that move your data through Bronze → Silver → Gold layers automatically
- **Monitor pipeline health** and SLA compliance
- **Query your data** using natural language — no SQL required

### Navigating the Portal

When you log in, you'll see a top navigation bar with the title "Pharma Data Exchange Hub" and a side navigation panel on the left. The side navigation includes:

| Menu Item              | What It Does                                      |
|------------------------|---------------------------------------------------|
| Dashboard              | Overview of your integrations and pipeline health  |
| CMO Registration       | Register your organization                         |
| Data Contracts         | View, create, and manage data contracts            |
| Integration Patterns   | Choose how your data reaches Merck                 |
| Schema Management      | Define or infer data schemas                       |
| Pipelines              | Monitor active data pipelines                      |
| Natural Language Query  | Ask questions about your data in plain English     |

> 📸 *Screenshot placeholder: The portal home screen showing the side navigation panel on the left with all menu items listed, and the Dashboard page in the main content area with a welcome message.*

---

## 2. CMO Onboarding Guide

### Before You Begin

Have the following information ready:

- Your organization's legal name
- A primary contact email address
- A primary contact phone number
- Your organization's physical address
- Whether your organization holds GxP certification

### Step-by-Step Registration

1. Click **CMO Registration** in the side navigation.

2. You'll see a page titled "CMO Registration" with the description "Register a new Contract Manufacturing Organization."

> 📸 *Screenshot placeholder: The CMO Registration page showing the "Organization Details" form with empty fields for Organization Name, Contact Email, Contact Phone, Address, and a GxP Certification checkbox.*

3. Fill in the form fields under the "Organization Details" section:

   - **Organization Name** — Enter the legal name of your CMO (e.g., "Acme Pharma Manufacturing"). This field is required.
   - **Contact Email** — Enter your primary contact email (e.g., `admin@acmepharma.com`). Must be a valid email format.
   - **Contact Phone** — Enter your phone number (e.g., `+1-555-000-0000`).
   - **Address** — Enter your organization's full physical address.
   - **GxP Certification** — Check the box if your organization is GxP certified.

4. Click the blue **Register CMO** button at the bottom of the form.

5. If registration succeeds, a green success banner appears at the top of the page with your new CMO ID (e.g., `cmo-acme-pharma`). Save this ID — you'll need it when creating data contracts.

6. If any required fields are missing or invalid, red error text appears below the relevant field explaining what needs to be corrected.

### What Happens After Registration

- A CMO profile is created and stored securely.
- Unique credentials are generated and stored in AWS Secrets Manager.
- Your CMO ID is assigned in the format `cmo-{name}`.
- You can now proceed to create data contracts and select an integration pattern.

---

## 3. Data Contract Creation Guide

A data contract is a formal agreement that defines exactly what data you'll share, how it should be validated, how often it arrives, and who can access it.

### What's in a Data Contract?

| Component          | Purpose                                                        |
|--------------------|----------------------------------------------------------------|
| Basic Information  | Links the contract to your CMO and data domain                 |
| Quality Rules      | Validation logic (completeness, accuracy, uniqueness, etc.)    |
| SLAs               | Timeliness, availability, and quality thresholds               |
| Delivery Schedule  | How often data is delivered (daily, hourly, etc.)              |
| Governance         | Data classification, retention, access control, PII fields     |

### Creating a Contract Step by Step

1. Click **Data Contracts** in the side navigation.

2. On the Data Contracts list page, click the blue **Create Contract** button in the top-right corner.

> 📸 *Screenshot placeholder: The Data Contracts list page showing a table with columns for Contract ID, CMO ID, Data Domain, Status, and Created At. The blue "Create Contract" button is visible in the header.*

3. You'll land on the "Create Data Contract" page with several sections to fill out.

#### Basic Information

Fill in these required fields:

- **CMO ID** — Your CMO identifier (e.g., `cmo-alpha`). This must match the ID you received during registration.
- **Data Domain** — The type of data you're sharing (e.g., `batch-records`, `quality-data`).
- **Schema ID** — The identifier for your data schema (e.g., `cmo-alpha-batch-records`). You can create schemas on the Schema Management page first.
- **Schema Version** — The version of the schema (e.g., `1.0`).

> 📸 *Screenshot placeholder: The "Basic Information" section of the Create Contract form showing four input fields: CMO ID, Data Domain, Schema ID, and Schema Version.*

#### Quality Rules

Quality rules define how your data is validated. Each rule uses AWS Glue Data Quality Definition Language (DQDL).

Click **Add Rule** to add more rules. Each rule has:

- **Rule ID** — A unique identifier (e.g., `rule-001`).
- **Rule Name** — A human-readable name (e.g., "Batch ID completeness").
- **Rule Type** — Choose from the dropdown: Completeness, Accuracy, Uniqueness, or Consistency.
- **DQDL Expression** — The validation expression. See examples below.
- **Threshold (0–100)** — The minimum passing percentage (e.g., `95` means 95% of records must pass).
- **Severity** — Choose Warning or Error. Errors block data promotion; warnings are logged.

**Example DQDL Expressions:**

| Rule Type     | Example Expression                                          | What It Checks                              |
|---------------|-------------------------------------------------------------|---------------------------------------------|
| Completeness  | `Completeness "batch_id" > 0.99`                           | 99%+ of records have a batch_id             |
| Uniqueness    | `Uniqueness "batch_id" > 0.99`                             | 99%+ of batch_id values are unique          |
| Accuracy      | `ColumnValues "quality_status" in ["PASS","FAIL","PENDING"]`| quality_status only contains valid values   |
| Consistency   | `ColumnValues "batch_id" matches "[A-Z0-9]{10}"`           | batch_id matches the expected format        |

> 📸 *Screenshot placeholder: The "Quality Rules" section showing one rule card with fields for Rule ID, Rule Name, Rule Type dropdown, DQDL Expression, Threshold, and Severity dropdown. An "Add Rule" button is visible in the section header.*

#### Service Level Agreements (SLAs)

Define your performance commitments:

- **Max Delay Hours** — Maximum acceptable delay for data delivery (e.g., `24` hours).
- **Timeliness Measurement Window** — How often timeliness is measured (e.g., `daily`).
- **Uptime Percentage** — Target availability (e.g., `99.5`%).
- **Availability Measurement Window** — How often availability is measured (e.g., `monthly`).
- **Min Quality Score** — Minimum acceptable quality score (e.g., `95`).
- **Quality Measurement Window** — How often quality is measured (e.g., `daily`).

#### Delivery Schedule

- **Frequency** — Select from the dropdown: Real-time, Hourly, Daily, Weekly, or Monthly.
- **Cron Expression (optional)** — For custom schedules (e.g., `0 2 * * *` for 2:00 AM daily).
- **Timezone** — Defaults to `UTC`. Change if your schedule is in a different timezone.

#### Governance

- **Data Classification** — Select from: Public, Internal, Confidential, or Restricted.
- **Retention Years** — How long data must be retained (default: `7` years for GxP compliance).
- **Allowed Users** — Comma-separated list of users who can access this data (e.g., `user1, user2`).
- **Allowed Groups** — Comma-separated list of groups (e.g., `quality-team, data-team`).
- **PII Fields** — Comma-separated list of fields containing personally identifiable information (e.g., `patient_name, ssn`). These fields will be automatically masked.
- **Encryption Required** — Checked by default. Leave checked to encrypt data with CMO-specific keys.

4. Click the blue **Create Contract** button at the bottom. Click **Cancel** to discard.

5. On success, a green banner shows your new contract ID (format: `CMO-{NAME}-{DOMAIN}-{NUMBER}`, e.g., `CMO-ALPHA-BATCH-001`). You'll be redirected to the Data Contracts list after a moment.

### Viewing and Editing Contracts

- On the **Data Contracts** page, click any row to view contract details.
- Use the text filter at the top of the table to search by contract ID, CMO, or domain.
- The table supports sorting by clicking column headers and pagination at the bottom.

---

## 4. Integration Pattern Selection Guide

The platform offers three ways to get your data to Merck. Choose the one that best fits your systems.

### Quick Comparison

| Feature                  | Pattern 1: Native Connectors       | Pattern 2: Secure Transfer (SFTP) | Pattern 3: AI Unstructured         |
|--------------------------|-------------------------------------|------------------------------------|------------------------------------|
| Best for                 | Modern databases                    | Any system that can export files   | PDFs, images, scanned documents    |
| Supported sources        | Snowflake, Oracle, SQL Server, PostgreSQL, SAP, Databricks | CSV, JSON, Parquet files | PDF, PNG, JPEG, TIFF              |
| Setup complexity         | Medium (need connection details)    | Low (SFTP credentials provided)    | Low (upload documents)             |
| Data extraction          | Merck pulls from your database      | You push files to SFTP             | AI extracts structured data        |
| Real-time capable        | Yes                                 | No (batch only)                    | No (batch only)                    |

### How to Select a Pattern

1. Navigate to **Integration Patterns** in the side navigation (or click **Activate** on a draft contract from the Pipelines page).

2. You'll see three cards describing each pattern. Click a card to select it.

> 📸 *Screenshot placeholder: The Integration Pattern Selection page showing three selectable cards side by side — "Pattern 1: Native Database Connectors", "Pattern 2: Secure File Transfer (SFTP)", and "Pattern 3: AI-Powered Unstructured Data". Each card shows a description and supported technologies.*

---

### Pattern 1: Native Database Connectors

Choose this if your data lives in a modern database platform.

**Supported platforms:** Snowflake, Oracle (JDBC), SQL Server (JDBC), PostgreSQL (JDBC), SAP HANA (JDBC), Databricks

**What you'll need:**
- Connection type (select from dropdown)
- Connection URL / JDBC string (e.g., `jdbc:oracle:thin:@host:1521:orcl`)
- Database username
- Database password
- Database name
- Schema name (optional, e.g., `public`)
- Table or query (optional, e.g., `batch_records`)

**Configuration steps:**

1. Select the "Pattern 1: Native Database Connectors" card.
2. A configuration form appears below with fields for connection details.
3. Choose your **Connection type** from the dropdown.
4. Enter your **Connection URL** — this is the JDBC URL or native connection string for your database.
5. Enter your **Username** and **Password**. These are stored securely in AWS Secrets Manager.
6. Enter the **Database** name.
7. Optionally fill in **Schema** and **Table or query**.
8. Click the blue **Activate Pipeline** button.

The system tests connectivity before activation. If the connection fails, you'll see an error message with details about what went wrong.

> 📸 *Screenshot placeholder: The Native Connector Configuration form showing dropdown for Connection type (set to "Snowflake"), and input fields for Connection URL, Username, Password, Database, Schema, and Table or query.*

---

### Pattern 2: Secure File Transfer (SFTP)

Choose this if your systems can export files (CSV, JSON, or Parquet) but don't support direct database connections.

**Supported file formats:** CSV, JSON, Parquet

**How it works:**

1. Select the "Pattern 2: Secure File Transfer (SFTP)" card.
2. You'll see an info message: "SFTP credentials will be provisioned automatically when you activate the pipeline."
3. Click the blue **Activate Pipeline** button.
4. Once activated, SFTP connection details appear:
   - **Hostname** — The SFTP server address
   - **Username** — Your CMO-specific username
   - **Password** — Your generated password

5. Use any SFTP client (FileZilla, WinSCP, command-line `sftp`) to connect and upload files.
6. Files uploaded to the SFTP endpoint are automatically detected and processed.

> 📸 *Screenshot placeholder: The SFTP Connection Details section showing a green success alert and read-only fields for Hostname, Username, and Password, with a note about supported file formats.*

**File requirements:**
- Files must match the schema defined in your data contract.
- Supported formats: `.csv`, `.json`, `.parquet`
- Files are automatically validated, moved to the Bronze layer, and archived after processing.

---

### Pattern 3: AI-Powered Unstructured Data

Choose this if you need to share data from PDFs, scanned documents, or images.

**Supported document types:** PDF, PNG, JPEG, TIFF

**How AI extraction works:**
- **PDFs and forms** are processed by Amazon Textract, which extracts text, tables, and form fields.
- **Images** are processed by Amazon Rekognition, which detects labels, text, and defects.
- Extracted data is automatically mapped to your contract schema as structured JSON.

**Configuration steps:**

1. Select the "Pattern 3: AI-Powered Unstructured Data" card.
2. A configuration form appears:
   - **Document type** — Select from: PDF Documents, PNG Images, JPEG Images, TIFF Images.
   - **Confidence threshold (%)** — Records extracted below this confidence level are flagged for manual review. Default is 85%.
   - **Upload documents** — Click to select files from your computer. You can select multiple files.
   - **Processing notes (optional)** — Add instructions for extraction (e.g., "Focus on tables in section 3, ignore headers").
3. Click the blue **Activate Pipeline** button.

> 📸 *Screenshot placeholder: The AI Document Processing Configuration form showing a Document type dropdown (set to "PDF Documents"), a Confidence threshold input (set to "85"), a file upload input, and a Processing notes textarea.*

**Understanding confidence thresholds:**
- Records with confidence ≥ 85% are automatically promoted to the Bronze layer.
- Records with confidence < 85% are flagged for manual review and stored separately.
- You can adjust the threshold based on your quality requirements.

---

## 5. Schema Management

Schemas define the structure of your data — field names, types, and constraints. You can either let the system infer a schema from sample data or define one manually.

### Inferring a Schema from Sample Data

1. Click **Schema Management** in the side navigation.
2. You'll see two tabs: "Infer from Sample" (selected by default) and "Manual Definition."

> 📸 *Screenshot placeholder: The Schema Management page showing the "Infer from Sample" tab selected, with an "Upload Sample Data" section containing a file upload input and a blue "Infer Schema" button.*

3. Under "Upload Sample Data," click the file input to select a sample file.
   - Supported formats: `.csv`, `.json`, `.parquet`
4. Click the blue **Infer Schema** button.
5. A loading indicator ("Analyzing file…") appears while the system processes your file.
6. Once complete, the inferred schema appears in an editable table with columns:
   - **Field Name** — The detected column/field name
   - **Type** — The inferred data type (String, Integer, Double, Boolean, Timestamp, Date, Array, Object)
   - **Nullable** — Whether the field can be empty
   - **Constraints** — Any detected constraints
   - **Actions** — Remove button to delete a field

7. Review the inferred fields. Click any cell to edit it inline (field name, type, or constraints).
8. Enter a **Schema Name** (e.g., `cmo-alpha-batch-records`).
9. Click the blue **Approve & Register Schema** button.
10. A green success banner confirms registration with the schema version.

If inference fails, an error alert appears with guidance to try a different file or switch to manual definition.

### Manually Defining a Schema

1. Click the **Manual Definition** tab.
2. Click **Add field** to add rows to the schema table.
3. For each field, enter the name, select the type, and optionally add constraints.
4. Enter a **Schema Name**.
5. Click **Approve & Register Schema**.

### Schema Versioning

When you update a schema for an existing contract, the system checks backward compatibility with the previous version. This ensures existing pipelines continue to work. Incompatible changes (like removing a required field) are rejected.

---

## 6. Pipeline Activation and Monitoring

### Activating a Pipeline

Once you have a data contract and have selected an integration pattern, your pipeline is ready to activate.

1. Navigate to **Pipelines** in the side navigation.
2. You'll see a table listing all your contracts with their pipeline status.

> 📸 *Screenshot placeholder: The Pipelines page showing a table with columns for Contract ID, CMO, Data Domain, Integration Pattern, Pipeline Status (with colored status indicators), and Actions. One row shows a "Draft" status with a blue "Activate" button.*

3. For contracts in "Draft" status, click the blue **Activate** button. This takes you to the Integration Pattern Selection page to configure and activate.
4. Click **View Details** on any row to expand connection details and status information.
5. Click the **Refresh** button in the table header to update pipeline statuses.

### What Happens During Deployment

When you activate a pipeline, the system:

1. Validates your data contract (schema, quality rules, SLAs).
2. Determines the integration pattern and configures the appropriate resources.
3. Creates AWS Glue ETL jobs for data processing.
4. Sets up S3 paths following the pattern: `s3://bucket/{layer}/{cmo-id}/{data-domain}/`
5. Configures monitoring and alerting.
6. Updates the pipeline status.

The status indicator shows the current state:

| Status     | Indicator | Meaning                                          |
|------------|-----------|--------------------------------------------------|
| Draft      | Grey      | Contract created but pipeline not yet activated   |
| Deploying  | Spinning  | Pipeline is being set up (auto-refreshes)         |
| Active     | Green     | Pipeline is running and processing data           |
| Failed     | Red       | Deployment failed — see error details             |
| Suspended  | Grey      | Pipeline has been paused                          |

### Monitoring Pipeline Status

- The Pipelines page auto-refreshes every 10 seconds when any pipeline is in "Deploying" status.
- Click **View Details** to see connection details (hostname, username, endpoint) for active pipelines.
- For failed pipelines, an error alert appears with actionable guidance.

### Understanding Error Messages

If a pipeline fails, the error details include guidance based on the type of failure:

| Error Type         | Guidance                                                                 |
|--------------------|--------------------------------------------------------------------------|
| Timeout            | Try activating again. Check network connectivity if the issue persists.  |
| Credential/Auth    | Verify your connection credentials and permissions.                      |
| Schema             | Review your data contract schema definition.                             |
| Other              | Review the error details and try again. Contact support if it persists.  |

The system automatically retries failed operations up to 3 times with increasing delays before reporting a failure.

---

## 7. Natural Language Query Guide

The Natural Language Query page lets you ask questions about your CMO data in plain English — no SQL knowledge required.

### How to Use It

1. Click **Natural Language Query** in the side navigation.

> 📸 *Screenshot placeholder: The Natural Language Query page showing a text area labeled "Your question" with placeholder text "e.g. What was the average quality score for CMO Alpha last month?", and a blue "Submit Query" button below it.*

2. Type your question in the text area. Be specific about what data you want and any time ranges or filters.
3. Click the blue **Submit Query** button (or press **Ctrl+Enter** as a shortcut).
4. A loading spinner appears while the system processes your query.
5. Results appear in a "Results" section below with a natural language answer.
6. Optionally, expand the "Generated SQL" section to see the SQL query that was generated and executed.

### Example Queries

Here are some questions you can ask:

| Question                                                          | What You'll Get                                    |
|-------------------------------------------------------------------|----------------------------------------------------|
| "What was the average quality score for CMO Alpha last month?"    | Average quality score with trend context            |
| "How many batches did CMO Beta produce this quarter?"             | Batch count for the specified period                |
| "Show me all failed quality checks in the last 7 days"           | List of failed validations with details             |
| "Which CMO has the highest yield percentage?"                     | Ranking of CMOs by yield                            |
| "What is the SLA compliance rate for batch-records contracts?"    | Compliance percentage across contracts              |
| "Compare quality scores between CMO Alpha and CMO Beta"           | Side-by-side comparison                             |

### Tips for Better Results

- **Be specific about time ranges** — "last month" or "in Q1 2024" helps narrow results.
- **Name the data domain** — Mention "batch records" or "quality data" to target the right tables.
- **Use CMO names** — Reference specific CMOs (e.g., "CMO Alpha") for targeted results.
- **Ask one question at a time** — Complex multi-part questions may produce less accurate results.
- **Check the generated SQL** — If results seem off, expand the SQL section to verify the query logic.

### Understanding Responses

- The system converts your question to SQL, runs it against your authorized data via Amazon Athena, and formats the results back into natural language.
- Access controls are enforced automatically — you'll only see data from CMOs you're authorized to access.
- If your question is ambiguous, the system may ask a clarifying question before generating results.

### Limitations

- Queries are read-only. You cannot modify data through the query interface.
- Very complex analytical questions may require multiple simpler queries.
- The system only queries data you have permission to access based on Lake Formation policies.

---

## 8. Dashboard and Reporting

### Dashboard Overview

Click **Dashboard** in the side navigation to see a high-level overview of your CMO integrations and pipeline health.

> 📸 *Screenshot placeholder: The Dashboard page showing a welcome message and overview of CMO integrations. The side navigation is visible on the left.*

The dashboard provides a starting point for navigating to other sections of the portal.

### QuickSight Dashboards

For detailed analytics and visualizations, the platform integrates with Amazon QuickSight. QuickSight dashboards provide:

- **Batch Records Dashboard** — Volume trends, batch status distribution, and manufacturing metrics over time.
- **Quality Metrics Dashboard** — Quality scores, failure rates, and trends across CMOs and data domains.
- **SLA Compliance Dashboard** — Timeliness, availability, and quality compliance rates per CMO.

**Key features of QuickSight dashboards:**

- **Filters** — Filter by CMO, date range, and data domain to focus on specific data.
- **Drill-down** — Click on chart elements to drill into more detailed views.
- **Auto-refresh** — Dashboards refresh automatically based on your data contract delivery frequency (hourly, daily, weekly, or monthly).
- **Row-level security** — You only see data from CMOs you're authorized to access, enforced by AWS Lake Formation.

### Available Metrics

| Metric                  | Description                                              | Source Layer |
|-------------------------|----------------------------------------------------------|--------------|
| Pipeline Execution Time | How long each pipeline run takes                         | CloudWatch   |
| Records Processed       | Number of records ingested per run                       | CloudWatch   |
| Quality Score           | Percentage of records passing quality rules              | CloudWatch   |
| SLA Timeliness          | Whether data arrived within the agreed delay window      | Gold         |
| SLA Availability        | Pipeline uptime percentage                               | Gold         |
| Batch Volume            | Number of batches per time period                        | Gold         |
| Failure Rate            | Percentage of records that failed validation             | Silver       |

---

## 9. FAQ

### Registration & Onboarding

**Q: What is a CMO ID and where do I find it?**
A: Your CMO ID is assigned when you register (format: `cmo-{name}`). It appears in the green success banner after registration. You'll need it when creating data contracts.

**Q: Can I update my organization details after registration?**
A: Contact the Merck data platform team to update your CMO profile. Self-service profile editing is planned for a future release.

**Q: What does GxP certification mean for my account?**
A: Checking the GxP certification box indicates your organization follows Good Practice quality guidelines. This information is stored in your profile for compliance tracking.

### Data Contracts

**Q: What is the contract ID format?**
A: Contract IDs follow the pattern `CMO-{NAME}-{DOMAIN}-{NUMBER}` — for example, `CMO-ALPHA-BATCH-001`. They're generated automatically when you create a contract.

**Q: Can I edit a contract after creation?**
A: Yes. Click on a contract in the Data Contracts list to view its details, then make changes. Note that schema changes must be backward-compatible with previous versions.

**Q: What happens if my data fails quality rules?**
A: Records that fail validation are quarantined in a separate storage area. They are not promoted to the Silver layer. You'll receive a notification if quality thresholds are breached.

### Integration Patterns

**Q: Which pattern should I choose?**
A: Use Pattern 1 if you have a modern database (Snowflake, Oracle, etc.). Use Pattern 2 if you can export files but don't support direct connections. Use Pattern 3 if your data is in PDFs or images.

**Q: Can I change my integration pattern later?**
A: You can create a new contract with a different pattern. Existing pipelines continue to run until suspended.

**Q: Are my database credentials secure?**
A: Yes. All credentials are stored in AWS Secrets Manager and encrypted. They are never displayed in logs or error messages.

### Schemas

**Q: What file formats can I upload for schema inference?**
A: CSV, JSON, and Parquet files are supported.

**Q: What if the inferred schema is wrong?**
A: You can edit any field inline in the schema table — change names, types, or constraints. You can also remove fields or add new ones before approving.

### Pipelines

**Q: How long does pipeline activation take?**
A: Most pipelines deploy within a few minutes. The status indicator shows "Deploying" while setup is in progress and auto-refreshes every 10 seconds.

**Q: What should I do if my pipeline fails?**
A: Check the error details by clicking "View Details" on the Pipelines page. The error message includes actionable guidance. The system automatically retries up to 3 times before reporting a failure.

**Q: How is my data organized?**
A: Data flows through three layers:
- **Bronze** — Raw data as received (immutable, partitioned by date)
- **Silver** — Validated and cleansed data (schema-enforced, quality-checked)
- **Gold** — Business-ready aggregated data (optimized for analytics)

### Natural Language Queries

**Q: What data can I query?**
A: You can query any data from CMOs you're authorized to access. Access controls are enforced automatically by AWS Lake Formation.

**Q: Can I export query results?**
A: Query results are displayed in the portal. For exports and advanced analytics, use the QuickSight dashboards.

**Q: What if the query returns unexpected results?**
A: Expand the "Generated SQL" section to review the query logic. Try rephrasing your question to be more specific about the data domain, time range, or CMO.

### Security & Compliance

**Q: Is my data encrypted?**
A: Yes. All data is encrypted at rest using AWS KMS with CMO-specific customer-managed keys, and encrypted in transit using TLS.

**Q: Who can see my data?**
A: Access is controlled by AWS Lake Formation with row-level and column-level security. Only users explicitly listed in your contract's governance settings (allowed users and groups) can access your data.

**Q: Are there audit logs?**
A: Yes. Every action — portal interactions, data access, pipeline executions, and configuration changes — is logged by AWS CloudTrail. Audit logs are encrypted, stored immutably, and retained for 7 years per GxP requirements.

**Q: How is PII handled?**
A: Fields you mark as PII in your contract governance settings are automatically detected by Amazon Macie and masked (hashed or redacted) before being accessible to users.

---

*For additional support, contact the Merck Data Platform team or use the "Documentation" link in the top navigation bar.*
