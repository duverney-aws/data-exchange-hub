"""
Unit Tests for Electronic Signature Service – signature capture,
verification, querying, input validation, and audit logging.

Requirements: 14.6
"""
import hashlib
import os
import sys
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.electronic_signature_service import (
    CRITICAL_ACTIONS,
    ElectronicSignatureError,
    ElectronicSignatureService,
    SIGNATURES_TABLE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_signatures_table(dynamodb_resource):
    """Create the electronic-signatures DynamoDB table with GSIs."""
    table = dynamodb_resource.create_table(
        TableName=SIGNATURES_TABLE,
        KeySchema=[
            {'AttributeName': 'signature_id', 'KeyType': 'HASH'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'signature_id', 'AttributeType': 'S'},
            {'AttributeName': 'resource', 'AttributeType': 'S'},
            {'AttributeName': 'timestamp', 'AttributeType': 'N'},
            {'AttributeName': 'user_id', 'AttributeType': 'S'},
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'resource-index',
                'KeySchema': [
                    {'AttributeName': 'resource', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
            },
            {
                'IndexName': 'user-index',
                'KeySchema': [
                    {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'},
                ],
                'Projection': {'ProjectionType': 'ALL'},
            },
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    table.meta.client.get_waiter('table_exists').wait(TableName=SIGNATURES_TABLE)
    return table


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def dynamodb_resource():
    with mock_aws():
        resource = boto3.resource('dynamodb', region_name='us-east-1')
        _create_signatures_table(resource)
        yield resource


@pytest.fixture
def mock_audit_logging():
    return MagicMock()


@pytest.fixture
def service(dynamodb_resource, mock_audit_logging):
    return ElectronicSignatureService(
        dynamodb_resource=dynamodb_resource,
        audit_logging_service=mock_audit_logging,
    )


# ---------------------------------------------------------------------------
# capture_signature – valid critical actions
# ---------------------------------------------------------------------------

class TestCaptureSignature:
    """Requirement 14.6: Capture user authentication and intent."""

    def test_capture_returns_signature_record(self, service):
        result = service.capture_signature(
            user_id='user-123',
            action='activate_contract',
            resource='CMO-ALPHA-BATCH-001',
            intent='Activating contract for production use',
            auth_method='mfa',
            auth_details={'ip': '10.0.0.1', 'session_id': 'sess-abc'},
        )

        assert result['signature_id'].startswith('SIG-')
        assert result['user_id'] == 'user-123'
        assert result['action'] == 'activate_contract'
        assert result['resource'] == 'CMO-ALPHA-BATCH-001'
        assert result['intent'] == 'Activating contract for production use'
        assert result['auth_method'] == 'mfa'
        assert result['auth_details'] == {'ip': '10.0.0.1', 'session_id': 'sess-abc'}
        assert 'timestamp' in result
        assert 'timestamp_iso' in result
        assert 'content_hash' in result

    def test_capture_all_critical_actions(self, service):
        for action in sorted(CRITICAL_ACTIONS):
            result = service.capture_signature(
                user_id='user-100',
                action=action,
                resource='resource-1',
                intent=f'Testing {action}',
                auth_method='sso',
            )
            assert result['action'] == action

    def test_capture_stores_in_dynamodb(self, service, dynamodb_resource):
        result = service.capture_signature(
            user_id='user-200',
            action='approve_schema',
            resource='schema-xyz',
            intent='Approving schema for CMO Alpha',
            auth_method='password',
        )

        table = dynamodb_resource.Table(SIGNATURES_TABLE)
        item = table.get_item(Key={'signature_id': result['signature_id']})['Item']
        assert item['user_id'] == 'user-200'
        assert item['action'] == 'approve_schema'

    def test_capture_defaults_auth_details_to_empty_dict(self, service):
        result = service.capture_signature(
            user_id='user-300',
            action='export_data',
            resource='dataset-1',
            intent='Exporting for review',
            auth_method='sso',
        )
        assert result['auth_details'] == {}


# ---------------------------------------------------------------------------
# capture_signature – rejects non-critical actions
# ---------------------------------------------------------------------------

class TestCaptureRejectsNonCritical:
    """Non-critical actions must be rejected."""

    def test_rejects_unknown_action(self, service):
        with pytest.raises(ValueError, match="not a critical action"):
            service.capture_signature(
                user_id='user-123',
                action='view_dashboard',
                resource='dashboard-1',
                intent='Viewing',
                auth_method='sso',
            )

    def test_rejects_empty_action(self, service):
        with pytest.raises(ValueError, match="action is required"):
            service.capture_signature(
                user_id='user-123',
                action='',
                resource='resource-1',
                intent='Intent',
                auth_method='sso',
            )


# ---------------------------------------------------------------------------
# verify_signature
# ---------------------------------------------------------------------------

class TestVerifySignature:
    """Verify previously captured signatures."""

    def test_verify_returns_valid_signature(self, service):
        captured = service.capture_signature(
            user_id='user-400',
            action='delete_data',
            resource='dataset-old',
            intent='Deleting obsolete data',
            auth_method='mfa',
        )

        verified = service.verify_signature(captured['signature_id'])
        assert verified is not None
        assert verified['signature_id'] == captured['signature_id']
        assert verified['user_id'] == 'user-400'

    def test_verify_returns_none_for_nonexistent(self, service):
        result = service.verify_signature('SIG-DOESNOTEXIST')
        assert result is None

    def test_verify_empty_id_raises(self, service):
        with pytest.raises(ValueError, match="signature_id is required"):
            service.verify_signature('')

    def test_verify_detects_tampered_hash(self, service, dynamodb_resource):
        captured = service.capture_signature(
            user_id='user-500',
            action='activate_contract',
            resource='contract-1',
            intent='Activating',
            auth_method='sso',
        )

        # Tamper with the hash in DynamoDB
        table = dynamodb_resource.Table(SIGNATURES_TABLE)
        table.update_item(
            Key={'signature_id': captured['signature_id']},
            UpdateExpression='SET content_hash = :h',
            ExpressionAttributeValues={':h': 'tampered-hash-value'},
        )

        result = service.verify_signature(captured['signature_id'])
        assert result is None


# ---------------------------------------------------------------------------
# get_signatures_for_resource
# ---------------------------------------------------------------------------

class TestGetSignaturesForResource:
    """Query signatures by resource within a time range."""

    def test_returns_signatures_for_resource(self, service):
        service.capture_signature(
            user_id='user-600',
            action='activate_contract',
            resource='CMO-ALPHA-BATCH-001',
            intent='Activating',
            auth_method='sso',
        )
        service.capture_signature(
            user_id='user-601',
            action='modify_quality_rules',
            resource='CMO-ALPHA-BATCH-001',
            intent='Updating rules',
            auth_method='mfa',
        )

        results = service.get_signatures_for_resource(
            resource_id='CMO-ALPHA-BATCH-001',
            start_time=datetime(2020, 1, 1),
            end_time=datetime(2030, 1, 1),
        )
        assert len(results) == 2

    def test_empty_resource_id_raises(self, service):
        with pytest.raises(ValueError, match="resource_id is required"):
            service.get_signatures_for_resource(
                '', datetime(2024, 1, 1), datetime(2024, 1, 2),
            )

    def test_invalid_time_range_raises(self, service):
        with pytest.raises(ValueError, match="start_time must be before end_time"):
            service.get_signatures_for_resource(
                'resource-1', datetime(2024, 1, 2), datetime(2024, 1, 1),
            )


# ---------------------------------------------------------------------------
# get_signatures_by_user
# ---------------------------------------------------------------------------

class TestGetSignaturesByUser:
    """Query signatures by user within a time range."""

    def test_returns_signatures_for_user(self, service):
        service.capture_signature(
            user_id='user-700',
            action='export_data',
            resource='dataset-a',
            intent='Exporting',
            auth_method='password',
        )
        service.capture_signature(
            user_id='user-700',
            action='delete_data',
            resource='dataset-b',
            intent='Deleting',
            auth_method='mfa',
        )

        results = service.get_signatures_by_user(
            user_id='user-700',
            start_time=datetime(2020, 1, 1),
            end_time=datetime(2030, 1, 1),
        )
        assert len(results) == 2

    def test_empty_user_id_raises(self, service):
        with pytest.raises(ValueError, match="user_id is required"):
            service.get_signatures_by_user(
                '', datetime(2024, 1, 1), datetime(2024, 1, 2),
            )

    def test_invalid_time_range_raises(self, service):
        with pytest.raises(ValueError, match="start_time must be before end_time"):
            service.get_signatures_by_user(
                'user-1', datetime(2024, 1, 2), datetime(2024, 1, 1),
            )


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    """Validate required fields for signature capture."""

    def test_missing_user_id_raises(self, service):
        with pytest.raises(ValueError, match="user_id is required"):
            service.capture_signature(
                user_id='',
                action='activate_contract',
                resource='r',
                intent='i',
                auth_method='sso',
            )

    def test_missing_resource_raises(self, service):
        with pytest.raises(ValueError, match="resource is required"):
            service.capture_signature(
                user_id='u',
                action='activate_contract',
                resource='',
                intent='i',
                auth_method='sso',
            )

    def test_missing_intent_raises(self, service):
        with pytest.raises(ValueError, match="intent is required"):
            service.capture_signature(
                user_id='u',
                action='activate_contract',
                resource='r',
                intent='',
                auth_method='sso',
            )

    def test_missing_auth_method_raises(self, service):
        with pytest.raises(ValueError, match="auth_method is required"):
            service.capture_signature(
                user_id='u',
                action='activate_contract',
                resource='r',
                intent='i',
                auth_method='',
            )


# ---------------------------------------------------------------------------
# DynamoDB error handling
# ---------------------------------------------------------------------------

class TestDynamoDBErrorHandling:
    """Handle DynamoDB failures gracefully."""

    def test_capture_raises_on_dynamodb_failure(self, mock_audit_logging):
        bad_resource = MagicMock()
        bad_table = MagicMock()
        bad_table.put_item.side_effect = Exception("ProvisionedThroughputExceeded")
        bad_resource.Table.return_value = bad_table

        svc = ElectronicSignatureService(
            dynamodb_resource=bad_resource,
            audit_logging_service=mock_audit_logging,
        )

        with pytest.raises(ElectronicSignatureError, match="Failed to store signature"):
            svc.capture_signature(
                user_id='user-x',
                action='activate_contract',
                resource='r',
                intent='i',
                auth_method='sso',
            )

    def test_verify_raises_on_dynamodb_failure(self, mock_audit_logging):
        bad_resource = MagicMock()
        bad_table = MagicMock()
        bad_table.get_item.side_effect = Exception("InternalServerError")
        bad_resource.Table.return_value = bad_table

        svc = ElectronicSignatureService(
            dynamodb_resource=bad_resource,
            audit_logging_service=mock_audit_logging,
        )

        with pytest.raises(ElectronicSignatureError, match="Failed to verify signature"):
            svc.verify_signature('SIG-ABC')


# ---------------------------------------------------------------------------
# Audit logging integration
# ---------------------------------------------------------------------------

class TestAuditLogging:
    """Audit logging is called on signature capture."""

    def test_audit_event_logged_on_capture(self, service, mock_audit_logging):
        service.capture_signature(
            user_id='user-800',
            action='activate_contract',
            resource='contract-1',
            intent='Activating for production',
            auth_method='mfa',
        )

        mock_audit_logging.log_audit_event.assert_called_once()
        call_kwargs = mock_audit_logging.log_audit_event.call_args[1]
        assert call_kwargs['event_type'] == 'ELECTRONIC_SIGNATURE'
        assert call_kwargs['user_id'] == 'user-800'
        assert call_kwargs['action'] == 'activate_contract'
        assert call_kwargs['resource'] == 'contract-1'
        assert 'signature_id' in call_kwargs['details']
        assert call_kwargs['details']['intent'] == 'Activating for production'

    def test_capture_succeeds_even_if_audit_fails(self, dynamodb_resource):
        failing_audit = MagicMock()
        failing_audit.log_audit_event.side_effect = Exception("Audit failure")

        svc = ElectronicSignatureService(
            dynamodb_resource=dynamodb_resource,
            audit_logging_service=failing_audit,
        )

        result = svc.capture_signature(
            user_id='user-900',
            action='export_data',
            resource='dataset-1',
            intent='Exporting',
            auth_method='sso',
        )
        assert result['signature_id'].startswith('SIG-')


# ---------------------------------------------------------------------------
# Signature hash integrity
# ---------------------------------------------------------------------------

class TestSignatureHashIntegrity:
    """Content hash provides integrity verification."""

    def test_hash_matches_expected_sha256(self, service):
        result = service.capture_signature(
            user_id='user-hash',
            action='activate_contract',
            resource='contract-hash',
            intent='Testing hash',
            auth_method='sso',
        )

        expected_content = (
            f"user-hash"
            f"activate_contract"
            f"contract-hash"
            f"Testing hash"
            f"{result['timestamp_iso']}"
        )
        expected_hash = hashlib.sha256(expected_content.encode('utf-8')).hexdigest()
        assert result['content_hash'] == expected_hash

    def test_different_inputs_produce_different_hashes(self, service):
        r1 = service.capture_signature(
            user_id='user-a',
            action='activate_contract',
            resource='resource-1',
            intent='Intent A',
            auth_method='sso',
        )
        r2 = service.capture_signature(
            user_id='user-b',
            action='activate_contract',
            resource='resource-1',
            intent='Intent B',
            auth_method='sso',
        )
        assert r1['content_hash'] != r2['content_hash']
