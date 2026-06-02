"""
Unit Tests for Contract API Lambda handler.

Uses moto to mock DynamoDB. Tests all routes, error handling, and CORS headers.

Requirements: 2.1, 4.1
"""
import sys
import os
import json
import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_table(dynamodb):
    """Create the data-contracts table with the cmo-contracts-index GSI."""
    dynamodb.create_table(
        TableName='data-contracts',
        KeySchema=[{'AttributeName': 'contractId', 'KeyType': 'HASH'}],
        AttributeDefinitions=[
            {'AttributeName': 'contractId', 'AttributeType': 'S'},
            {'AttributeName': 'cmoId', 'AttributeType': 'S'},
            {'AttributeName': 'status', 'AttributeType': 'S'},
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'cmo-contracts-index',
                'KeySchema': [
                    {'AttributeName': 'cmoId', 'KeyType': 'HASH'},
                    {'AttributeName': 'status', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
            }
        ],
        BillingMode='PAY_PER_REQUEST',
    )


def _valid_contract_body():
    """Return a minimal valid contract payload as a JSON string."""
    return json.dumps({
        'cmoId': 'cmo-alpha',
        'dataDomain': 'batch-records',
        'schemaId': 'schema-001',
        'schemaVersion': '1.0',
        'qualityRules': [
            {
                'ruleId': 'rule-001',
                'ruleName': 'Batch ID completeness',
                'ruleType': 'completeness',
                'expression': 'Completeness "batch_id" > 0.99',
                'threshold': 99.0,
                'severity': 'error',
            }
        ],
        'sla': {
            'timeliness': {'maxDelayHours': 24, 'measurementWindow': 'monthly'},
            'availability': {'uptimePercentage': 99.5, 'measurementWindow': 'monthly'},
            'quality': {'minQualityScore': 95.0, 'measurementWindow': 'monthly'},
        },
        'deliverySchedule': {'frequency': 'daily'},
        'governance': {
            'dataClassification': 'confidential',
            'retentionYears': 7,
            'allowedUsers': ['user-a'],
            'allowedGroups': ['group-a'],
            'piiFields': ['email'],
            'encryptionRequired': True,
        },
    })


def _make_event(method, path, body=None, path_params=None):
    """Build a minimal API Gateway proxy event."""
    event = {
        'httpMethod': method,
        'path': path,
        'pathParameters': path_params,
        'body': body,
        'queryStringParameters': None,
    }
    return event


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def aws_env(monkeypatch):
    """Set dummy AWS credentials for moto."""
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'testing')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'testing')
    monkeypatch.setenv('AWS_SECURITY_TOKEN', 'testing')
    monkeypatch.setenv('AWS_SESSION_TOKEN', 'testing')
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')
    monkeypatch.setenv('TABLE_NAME', 'data-contracts')


@pytest.fixture
def setup_handler(aws_env):
    """Set up moto mock and re-import handler so it picks up the mock."""
    with mock_aws():
        ddb = boto3.resource('dynamodb', region_name='us-east-1')
        _create_table(ddb)

        # Re-import handler module so the module-level _service uses mocked DynamoDB
        import importlib
        from services.contract_service import ContractService
        import lambdas.contract_api.handler as handler_mod
        handler_mod._service = ContractService(
            table_name='data-contracts', dynamodb_resource=ddb,
        )
        importlib.reload(handler_mod)
        handler_mod._service = ContractService(
            table_name='data-contracts', dynamodb_resource=ddb,
        )

        yield handler_mod.handler


# ---------------------------------------------------------------------------
# POST /api/contract – Create
# ---------------------------------------------------------------------------

class TestCreateContract:
    def test_create_returns_201(self, setup_handler):
        handler = setup_handler
        event = _make_event('POST', '/api/contract', body=_valid_contract_body())
        result = handler(event, None)
        assert result['statusCode'] == 201
        body = json.loads(result['body'])
        assert body['contractId'].startswith('CMO-')
        assert body['status'] == 'draft'

    def test_create_invalid_body_returns_400(self, setup_handler):
        handler = setup_handler
        event = _make_event('POST', '/api/contract', body='not-json')
        result = handler(event, None)
        assert result['statusCode'] == 400

    def test_create_missing_fields_returns_400(self, setup_handler):
        handler = setup_handler
        event = _make_event('POST', '/api/contract', body=json.dumps({'cmoId': 'alpha'}))
        result = handler(event, None)
        assert result['statusCode'] == 400


# ---------------------------------------------------------------------------
# GET /api/contract/{contractId}
# ---------------------------------------------------------------------------

class TestGetContract:
    def test_get_returns_200(self, setup_handler):
        handler = setup_handler
        # Create first
        create_event = _make_event('POST', '/api/contract', body=_valid_contract_body())
        create_result = handler(create_event, None)
        contract_id = json.loads(create_result['body'])['contractId']

        # Get
        get_event = _make_event(
            'GET', f'/api/contract/{contract_id}',
            path_params={'contractId': contract_id},
        )
        result = handler(get_event, None)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['contractId'] == contract_id

    def test_get_nonexistent_returns_404(self, setup_handler):
        handler = setup_handler
        event = _make_event(
            'GET', '/api/contract/CMO-MISSING-001',
            path_params={'contractId': 'CMO-MISSING-001'},
        )
        result = handler(event, None)
        assert result['statusCode'] == 404

    def test_get_missing_path_param_returns_400(self, setup_handler):
        handler = setup_handler
        event = _make_event('GET', '/api/contract/', path_params={})
        result = handler(event, None)
        assert result['statusCode'] == 400


# ---------------------------------------------------------------------------
# PUT /api/contract/{contractId} – Update
# ---------------------------------------------------------------------------

class TestUpdateContract:
    def test_update_returns_200(self, setup_handler):
        handler = setup_handler
        # Create first
        create_result = handler(
            _make_event('POST', '/api/contract', body=_valid_contract_body()), None,
        )
        contract_id = json.loads(create_result['body'])['contractId']

        # Update
        update_body = json.dumps({'schemaVersion': '2.0'})
        event = _make_event(
            'PUT', f'/api/contract/{contract_id}',
            body=update_body,
            path_params={'contractId': contract_id},
        )
        result = handler(event, None)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['schemaVersion'] == '2.0'

    def test_update_nonexistent_returns_404(self, setup_handler):
        handler = setup_handler
        event = _make_event(
            'PUT', '/api/contract/CMO-MISSING-001',
            body=json.dumps({'schemaVersion': '2.0'}),
            path_params={'contractId': 'CMO-MISSING-001'},
        )
        result = handler(event, None)
        assert result['statusCode'] == 404


# ---------------------------------------------------------------------------
# POST /api/contract/{contractId}/activate
# ---------------------------------------------------------------------------

class TestActivateContract:
    def test_activate_returns_200(self, setup_handler):
        handler = setup_handler
        # Create first
        create_result = handler(
            _make_event('POST', '/api/contract', body=_valid_contract_body()), None,
        )
        contract_id = json.loads(create_result['body'])['contractId']

        # Activate
        event = _make_event(
            'POST', f'/api/contract/{contract_id}/activate',
            path_params={'contractId': contract_id},
        )
        result = handler(event, None)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['status'] == 'active'

    def test_activate_nonexistent_returns_404(self, setup_handler):
        handler = setup_handler
        event = _make_event(
            'POST', '/api/contract/CMO-MISSING-001/activate',
            path_params={'contractId': 'CMO-MISSING-001'},
        )
        result = handler(event, None)
        assert result['statusCode'] == 404


# ---------------------------------------------------------------------------
# Unsupported method & CORS
# ---------------------------------------------------------------------------

class TestMethodAndCors:
    def test_unsupported_method_returns_405(self, setup_handler):
        handler = setup_handler
        event = _make_event('DELETE', '/api/contract')
        result = handler(event, None)
        assert result['statusCode'] == 405

    def test_cors_headers_present(self, setup_handler):
        handler = setup_handler
        event = _make_event('GET', '/api/contract/test', path_params={'contractId': 'test'})
        result = handler(event, None)
        assert result['headers']['Access-Control-Allow-Origin'] == '*'
        assert result['headers']['Content-Type'] == 'application/json'
