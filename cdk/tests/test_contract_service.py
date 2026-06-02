"""
Unit Tests for ContractService – DynamoDB operations for data contracts.

Uses moto to mock DynamoDB. Tests CRUD operations, CMO queries,
status updates, and error cases.

Requirements: 2.4
"""
import sys
import os
import boto3
import pytest
from moto import mock_aws
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.contract_service import (
    ContractService,
    ContractNotFoundError,
    ContractServiceError,
)


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


def _valid_contract_data():
    """Return a minimal valid contract payload."""
    return {
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
    }


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


@pytest.fixture
def dynamodb(aws_env):
    with mock_aws():
        ddb = boto3.resource('dynamodb', region_name='us-east-1')
        _create_table(ddb)
        yield ddb


@pytest.fixture
def service(dynamodb):
    return ContractService(table_name='data-contracts', dynamodb_resource=dynamodb)


# ---------------------------------------------------------------------------
# create_contract
# ---------------------------------------------------------------------------

class TestCreateContract:
    def test_creates_contract_with_draft_status(self, service):
        contract = service.create_contract(_valid_contract_data())
        assert contract.status == 'draft'
        assert contract.contract_id.startswith('CMO-')
        assert contract.cmo_id == 'cmo-alpha'

    def test_contract_id_format(self, service):
        contract = service.create_contract(_valid_contract_data())
        assert 'CMO-' in contract.contract_id
        assert 'ALPHA' in contract.contract_id.upper()
        assert contract.contract_id.endswith('-001')

    def test_sequential_ids_for_same_cmo_domain(self, service):
        c1 = service.create_contract(_valid_contract_data())
        c2 = service.create_contract(_valid_contract_data())
        assert c1.contract_id.endswith('-001')
        assert c2.contract_id.endswith('-002')

    def test_timestamps_are_set(self, service):
        contract = service.create_contract(_valid_contract_data())
        assert contract.created_at is not None
        assert contract.updated_at is not None

    def test_invalid_data_raises(self, service):
        with pytest.raises(ContractServiceError, match="Validation failed"):
            service.create_contract({'cmoId': 'alpha'})

    def test_persisted_to_dynamodb(self, service):
        contract = service.create_contract(_valid_contract_data())
        fetched = service.get_contract(contract.contract_id)
        assert fetched.contract_id == contract.contract_id
        assert fetched.cmo_id == contract.cmo_id


# ---------------------------------------------------------------------------
# get_contract
# ---------------------------------------------------------------------------

class TestGetContract:
    def test_get_existing_contract(self, service):
        created = service.create_contract(_valid_contract_data())
        fetched = service.get_contract(created.contract_id)
        assert fetched.contract_id == created.contract_id
        assert fetched.data_domain == 'batch-records'

    def test_get_nonexistent_raises(self, service):
        with pytest.raises(ContractNotFoundError, match="not found"):
            service.get_contract('CMO-NONEXISTENT-001')


# ---------------------------------------------------------------------------
# update_contract
# ---------------------------------------------------------------------------

class TestUpdateContract:
    def test_update_schema_version(self, service):
        created = service.create_contract(_valid_contract_data())
        updated = service.update_contract(created.contract_id, {'schemaVersion': '2.0'})
        assert updated.schema_version == '2.0'

    def test_update_preserves_unchanged_fields(self, service):
        created = service.create_contract(_valid_contract_data())
        updated = service.update_contract(created.contract_id, {'schemaVersion': '2.0'})
        assert updated.cmo_id == created.cmo_id
        assert updated.data_domain == created.data_domain

    def test_update_nonexistent_raises(self, service):
        with pytest.raises(ContractNotFoundError):
            service.update_contract('CMO-MISSING-001', {'schemaVersion': '2.0'})

    def test_update_with_invalid_data_raises(self, service):
        created = service.create_contract(_valid_contract_data())
        with pytest.raises(ContractServiceError, match="Validation failed"):
            service.update_contract(created.contract_id, {
                'sla': 'not-a-dict',
            })

    def test_updated_at_changes(self, service):
        created = service.create_contract(_valid_contract_data())
        original_updated = created.updated_at
        updated = service.update_contract(created.contract_id, {'schemaVersion': '2.0'})
        assert updated.updated_at >= original_updated


# ---------------------------------------------------------------------------
# update_contract_status
# ---------------------------------------------------------------------------

class TestUpdateContractStatus:
    def test_update_to_active(self, service):
        created = service.create_contract(_valid_contract_data())
        updated = service.update_contract_status(created.contract_id, 'active')
        assert updated.status == 'active'

    def test_update_to_suspended(self, service):
        created = service.create_contract(_valid_contract_data())
        updated = service.update_contract_status(created.contract_id, 'suspended')
        assert updated.status == 'suspended'

    def test_update_to_draft(self, service):
        created = service.create_contract(_valid_contract_data())
        service.update_contract_status(created.contract_id, 'active')
        updated = service.update_contract_status(created.contract_id, 'draft')
        assert updated.status == 'draft'

    def test_invalid_status_raises(self, service):
        created = service.create_contract(_valid_contract_data())
        with pytest.raises(ContractServiceError, match="Invalid status"):
            service.update_contract_status(created.contract_id, 'cancelled')

    def test_nonexistent_contract_raises(self, service):
        with pytest.raises(ContractNotFoundError):
            service.update_contract_status('CMO-MISSING-001', 'active')

    def test_status_persisted(self, service):
        created = service.create_contract(_valid_contract_data())
        service.update_contract_status(created.contract_id, 'active')
        fetched = service.get_contract(created.contract_id)
        assert fetched.status == 'active'


# ---------------------------------------------------------------------------
# query_contracts_by_cmo
# ---------------------------------------------------------------------------

class TestQueryContractsByCmo:
    def test_query_returns_all_for_cmo(self, service):
        service.create_contract(_valid_contract_data())
        data2 = _valid_contract_data()
        data2['dataDomain'] = 'quality-data'
        service.create_contract(data2)

        results = service.query_contracts_by_cmo('cmo-alpha')
        assert len(results) == 2

    def test_query_filters_by_status(self, service):
        c1 = service.create_contract(_valid_contract_data())
        service.create_contract(_valid_contract_data())
        service.update_contract_status(c1.contract_id, 'active')

        active = service.query_contracts_by_cmo('cmo-alpha', status='active')
        assert len(active) == 1
        assert active[0].status == 'active'

    def test_query_empty_for_unknown_cmo(self, service):
        results = service.query_contracts_by_cmo('cmo-unknown')
        assert results == []

    def test_query_returns_datacontract_instances(self, service):
        service.create_contract(_valid_contract_data())
        results = service.query_contracts_by_cmo('cmo-alpha')
        from models.data_contract import DataContract
        assert all(isinstance(r, DataContract) for r in results)


# ---------------------------------------------------------------------------
# _count_contracts_for_cmo_domain
# ---------------------------------------------------------------------------

class TestCountContractsForCmoDomain:
    def test_zero_when_none_exist(self, service):
        count = service._count_contracts_for_cmo_domain('cmo-alpha', 'batch-records')
        assert count == 0

    def test_counts_only_matching_domain(self, service):
        service.create_contract(_valid_contract_data())
        data2 = _valid_contract_data()
        data2['dataDomain'] = 'quality-data'
        service.create_contract(data2)

        count = service._count_contracts_for_cmo_domain('cmo-alpha', 'batch-records')
        assert count == 1
