# Data Models

This directory contains Python data model classes that define the structure for data stored in DynamoDB tables.

## Overview

The data models provide type-safe representations of:
- CMO profiles
- Data contracts
- Pipeline execution history

Each model includes methods for converting to/from DynamoDB item format.

## Models

### CMOProfile

Represents a Contract Manufacturing Organization profile.

**DynamoDB Table**: `cmo-profiles`

**Attributes**:
- `cmo_id` (str): Unique identifier in format `cmo-{name}`
- `organization_name` (str): Legal name of the CMO
- `contact_email` (str): Primary contact email
- `contact_phone` (str): Primary contact phone
- `address` (str): Physical address
- `gxp_certified` (bool): GxP certification status
- `created_at` (datetime): Profile creation timestamp
- `status` (str): One of 'active', 'inactive', 'suspended'

**Example**:
```python
from models.cmo_profile import CMOProfile
from datetime import datetime

profile = CMOProfile(
    cmo_id="cmo-alpha",
    organization_name="Alpha Pharmaceuticals Inc.",
    contact_email="contact@alphapharma.com",
    contact_phone="+1-555-0100",
    address="123 Pharma Street, Boston, MA 02101",
    gxp_certified=True,
    created_at=datetime.now(),
    status="active"
)

# Convert to DynamoDB format
item = profile.to_dynamodb_item()

# Create from DynamoDB item
profile = CMOProfile.from_dynamodb_item(item)
```

### DataContract

Represents a data exchange contract between Merck and a CMO.

**DynamoDB Table**: `data-contracts`

**Attributes**:
- `contract_id` (str): Unique ID in format `CMO-{NAME}-{DOMAIN}-{NUMBER}`
- `cmo_id` (str): Reference to CMO profile
- `data_domain` (str): Data domain (e.g., 'batch-records')
- `schema_id` (str): Reference to Glue Schema Registry
- `schema_version` (str): Schema version
- `quality_rules` (List[QualityRule]): Data quality validation rules
- `sla` (SLA): Service level agreement thresholds
- `delivery_schedule` (DeliverySchedule): Delivery frequency
- `governance` (Governance): Access control settings
- `status` (str): One of 'draft', 'active', 'suspended'
- `created_at` (datetime): Contract creation timestamp
- `updated_at` (datetime): Last update timestamp

**Nested Types**:

#### QualityRule
- `rule_id` (str): Unique rule identifier
- `rule_name` (str): Human-readable rule name
- `rule_type` (str): One of 'completeness', 'accuracy', 'uniqueness', 'consistency'
- `expression` (str): Glue Data Quality DQDL expression
- `threshold` (float): Pass threshold (0-100)
- `severity` (str): One of 'warning', 'error'

#### SLA
- `timeliness` (dict): Max delay and measurement window
- `availability` (dict): Uptime percentage and measurement window
- `quality` (dict): Min quality score and measurement window

#### DeliverySchedule
- `frequency` (str): One of 'real-time', 'hourly', 'daily', 'weekly', 'monthly'
- `cron_expression` (str, optional): Custom cron schedule
- `timezone` (str): Timezone for scheduling (default: 'UTC')

#### Governance
- `data_classification` (str): One of 'public', 'internal', 'confidential', 'restricted'
- `retention_years` (int): Data retention period
- `allowed_users` (List[str]): Authorized user ARNs
- `allowed_groups` (List[str]): Authorized group ARNs
- `pii_fields` (List[str]): Fields containing PII
- `encryption_required` (bool): Whether encryption is mandatory

**Example**:
```python
from models.data_contract import (
    DataContract, QualityRule, SLA, DeliverySchedule, Governance
)
from datetime import datetime

contract = DataContract(
    contract_id="CMO-ALPHA-BATCH-001",
    cmo_id="cmo-alpha",
    data_domain="batch-records",
    schema_id="batch-records-schema",
    schema_version="1.0",
    quality_rules=[
        QualityRule(
            rule_id="rule-001",
            rule_name="Batch ID Completeness",
            rule_type="completeness",
            expression="Completeness \"batch_id\" > 0.99",
            threshold=99.0,
            severity="error"
        )
    ],
    sla=SLA(
        timeliness={'maxDelayHours': 24, 'measurementWindow': 'daily'},
        availability={'uptimePercentage': 99.5, 'measurementWindow': 'monthly'},
        quality={'minQualityScore': 95.0, 'measurementWindow': 'daily'}
    ),
    delivery_schedule=DeliverySchedule(
        frequency="daily",
        timezone="America/New_York"
    ),
    governance=Governance(
        data_classification="confidential",
        retention_years=7,
        allowed_users=["arn:aws:iam::123456789012:user/analyst"],
        allowed_groups=["arn:aws:iam::123456789012:group/quality-team"],
        pii_fields=["operator_name", "batch_operator_id"],
        encryption_required=True
    ),
    status="active",
    created_at=datetime.now(),
    updated_at=datetime.now()
)

# Convert to DynamoDB format
item = contract.to_dynamodb_item()

# Create from DynamoDB item
contract = DataContract.from_dynamodb_item(item)
```

### PipelineExecution

Represents a single pipeline execution record.

**DynamoDB Table**: `pipeline-executions`

**Attributes**:
- `contract_id` (str): Reference to data contract
- `execution_timestamp` (int): Unix timestamp in milliseconds
- `execution_id` (str): Unique execution identifier
- `status` (str): One of 'running', 'succeeded', 'failed', 'timeout'
- `records_processed` (int): Number of records processed
- `records_failed` (int): Number of records that failed validation
- `execution_time_seconds` (float): Total execution time
- `quality_score` (float): Overall quality score (0-100)
- `error_message` (str, optional): Error message if failed
- `metadata` (dict): Additional execution metadata
- `ttl` (int): Time-to-live timestamp (auto-set to 90 days)

**Example**:
```python
from models.pipeline_execution import PipelineExecution
import time

execution = PipelineExecution(
    contract_id="CMO-ALPHA-BATCH-001",
    execution_timestamp=int(time.time() * 1000),
    execution_id="exec-20240115-001",
    status="succeeded",
    records_processed=1000,
    records_failed=5,
    execution_time_seconds=45.2,
    quality_score=99.5,
    metadata={
        'source': 'snowflake',
        'layer': 'bronze',
        'partition': 'year=2024/month=01/day=15'
    }
)

# Convert to DynamoDB format
item = execution.to_dynamodb_item()

# Create from DynamoDB item
execution = PipelineExecution.from_dynamodb_item(item)
```

## Contract ID Format

Contract IDs follow a strict format: `CMO-{NAME}-{DOMAIN}-{NUMBER}`

- **CMO**: Literal prefix
- **NAME**: CMO name in uppercase (e.g., 'ALPHA', 'BETA')
- **DOMAIN**: Data domain in lowercase-with-hyphens (e.g., 'batch-records', 'quality-data')
- **NUMBER**: Sequential 3-digit number (e.g., '001', '002')

**Examples**:
- `CMO-ALPHA-BATCH-001`
- `CMO-BETA-QUALITY-002`
- `CMO-GAMMA-STABILITY-001`

## Usage in Lambda Functions

```python
import boto3
from models.cmo_profile import CMOProfile
from models.data_contract import DataContract

dynamodb = boto3.resource('dynamodb')
profiles_table = dynamodb.Table('cmo-profiles')
contracts_table = dynamodb.Table('data-contracts')

# Save CMO profile
profile = CMOProfile(...)
profiles_table.put_item(Item=profile.to_dynamodb_item())

# Query CMO profile
response = profiles_table.get_item(Key={'cmoId': 'cmo-alpha'})
profile = CMOProfile.from_dynamodb_item(response['Item'])

# Save data contract
contract = DataContract(...)
contracts_table.put_item(Item=contract.to_dynamodb_item())

# Query contracts by CMO
response = contracts_table.query(
    IndexName='cmo-contracts-index',
    KeyConditionExpression='cmoId = :cmo_id',
    ExpressionAttributeValues={':cmo_id': 'cmo-alpha'}
)
contracts = [DataContract.from_dynamodb_item(item) for item in response['Items']]
```

## Validation

All models include basic type validation through Python dataclasses. For additional validation:

1. **Contract ID Format**: Validate using regex `^CMO-[A-Z]+-[a-z-]+-\d{3}$`
2. **Email Format**: Validate using standard email regex
3. **Phone Format**: Validate using E.164 format
4. **DQDL Expressions**: Validate against Glue Data Quality syntax
5. **Cron Expressions**: Validate using cron parser

## Testing

See `tests/test_models.py` for comprehensive unit tests of all data models.

```bash
# Run model tests
pytest tests/test_models.py -v
```
