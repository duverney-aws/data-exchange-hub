# Pharma Data Exchange Hub

A self-service data integration platform that accelerates CMO (Contract Manufacturing Organization) onboarding from months to weeks. Built on AWS with three proven integration patterns.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Self-Service Portal (React)                    │
├─────────────────────────────────────────────────────────────────┤
│           API Gateway + Lambda (Python) + Cognito Auth            │
├───────────────────┬───────────────────┬─────────────────────────┤
│  Pattern 1:       │  Pattern 2:       │  Pattern 3:             │
│  Native Connectors│  Secure Transfer  │  AI Unstructured        │
│  (Glue JDBC)      │  (SFTP)           │  (Textract/Rekognition) │
├───────────────────┴───────────────────┴─────────────────────────┤
│              S3 Data Lake (Bronze / Silver / Gold)                │
└─────────────────────────────────────────────────────────────────┘
```

## Integration Patterns

| Pattern | Technology | Use Case |
|---------|-----------|----------|
| Native Connectors | AWS Glue JDBC | Cloud data warehouses, databases (Oracle, SQL Server, Snowflake, SAP) |
| Secure Transfer | AWS Transfer Family (SFTP) | Legacy systems, universal file-based integration |
| AI Unstructured | Amazon Textract + Rekognition | PDFs (CoA, BMR), images, scanned documents |

## Project Structure

```
cdk/                          # Backend (AWS CDK + Python)
├── stacks/                   # CloudFormation stacks (13 total)
├── lambdas/                  # Lambda function handlers
├── services/                 # Business logic layer
├── models/                   # Data models (contract, batch, product, connection, schema)
├── glue_scripts/             # PySpark ETL scripts
└── app.py                    # CDK app entry point

frontend/                     # Portal (React + TypeScript)
├── src/pages/                # UI pages (Dashboard, Contracts, Batches, Connections, etc.)
├── src/services/api.ts       # API client
├── src/context/AuthContext.tsx
└── public/docs/              # User Guide & API Guide (HTML)

docs/                         # Static documentation
```

## AWS Services Used

- **Cognito** — Authentication (two roles: admin, CMO user)
- **API Gateway + Lambda** — REST API
- **DynamoDB** — Contracts, CMOs, products, batches, connections, schemas
- **S3** — Data lake (medallion architecture)
- **Transfer Family** — Managed SFTP
- **Textract / Rekognition** — AI document processing
- **Glue** — Schema registry, JDBC connections, ETL jobs
- **EventBridge** — SLA monitoring (daily scheduled checks)
- **Secrets Manager** — Credential storage
- **KMS** — Encryption at rest
- **CloudTrail** — Audit logging

## Deployment

### Prerequisites

- AWS CLI configured
- Node.js 18+
- Python 3.12+
- AWS CDK CLI (`npm install -g aws-cdk`)

### Backend

```bash
cd cdk
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cdk deploy --all --require-approval never
```

### Frontend

```bash
cd frontend
npm install
npm run build
# Deploy to Amplify (or any static hosting)
```

## Key Features

- **Two-persona workflow** — Admin creates contracts, CMO reviews and accepts
- **CMO self-service** — CMOs configure their own database connections
- **Batch traceability** — Every file tagged with lot number in S3 path (`lot={lotNumber}/`)
- **SLA monitoring** — Automated daily checks flag overdue data elements
- **CoA viewer** — Textract-extracted documents rendered in the portal
- **Multi-table ETL** — Single database connection supports multiple table extractions
- **JWT-enforced isolation** — CMO users only see their own data

## License

TBD
