"""
Electronic Signature Service

Captures electronic signatures for critical actions, linking user
authentication and intent to electronic records per 21 CFR Part 11.

Requirements: 14.6
"""
import hashlib
import logging
import time
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)

CRITICAL_ACTIONS = frozenset({
    'activate_contract',
    'deactivate_contract',
    'modify_quality_rules',
    'approve_schema',
    'export_data',
    'delete_data',
})

SIGNATURES_TABLE = 'electronic-signatures'


class ElectronicSignatureError(Exception):
    """Base exception for electronic signature operations."""
    pass


class ElectronicSignatureService:
    """
    Service for capturing and verifying electronic signatures.

    Each signature records the signer's identity, the action performed,
    the target resource, the signer's stated intent, authentication
    method/details, a timestamp, and a SHA-256 integrity hash.

    Signatures are stored in DynamoDB and logged to the audit trail.
    """

    def __init__(self, dynamodb_resource=None, audit_logging_service=None,
                 table_name: str = SIGNATURES_TABLE):
        """
        Args:
            dynamodb_resource: boto3 DynamoDB resource (injected for testability).
            audit_logging_service: AuditLoggingService instance for audit trail.
            table_name: DynamoDB table name for signatures.
        """
        self.dynamodb_resource = dynamodb_resource
        self.audit_logging_service = audit_logging_service
        self.table_name = table_name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def capture_signature(
        self,
        user_id: str,
        action: str,
        resource: str,
        intent: str,
        auth_method: str,
        auth_details: Optional[dict] = None,
    ) -> dict:
        """
        Capture an electronic signature for a critical action.

        Args:
            user_id: Identity of the signer.
            action: The critical action being signed (must be in CRITICAL_ACTIONS).
            resource: The resource being acted upon.
            intent: Free-text description of the signer's intent.
            auth_method: Authentication method (e.g. 'sso', 'mfa', 'password').
            auth_details: Optional dict with IP address, session ID, etc.

        Returns:
            Signature record dict with signature_id, timestamp, and hash.

        Raises:
            ValueError: If required fields are missing or action is not critical.
            ElectronicSignatureError: If storage fails.
        """
        self._validate_capture_input(user_id, action, resource, intent, auth_method)

        timestamp = datetime.utcnow()
        timestamp_iso = timestamp.isoformat() + 'Z'
        timestamp_epoch = Decimal(str(timestamp.timestamp()))
        signature_id = f"SIG-{uuid.uuid4().hex[:16].upper()}"

        content_hash = self._compute_hash(
            user_id, action, resource, intent, timestamp_iso,
        )

        record = {
            'signature_id': signature_id,
            'user_id': user_id,
            'action': action,
            'resource': resource,
            'intent': intent,
            'auth_method': auth_method,
            'auth_details': auth_details or {},
            'timestamp': timestamp_epoch,
            'timestamp_iso': timestamp_iso,
            'content_hash': content_hash,
        }

        try:
            table = self.dynamodb_resource.Table(self.table_name)
            table.put_item(Item=record)
        except Exception as exc:
            raise ElectronicSignatureError(
                f"Failed to store signature: {exc}"
            ) from exc

        # Log to audit trail
        if self.audit_logging_service:
            try:
                self.audit_logging_service.log_audit_event(
                    event_type='ELECTRONIC_SIGNATURE',
                    user_id=user_id,
                    action=action,
                    resource=resource,
                    details={
                        'signature_id': signature_id,
                        'intent': intent,
                        'auth_method': auth_method,
                        'content_hash': content_hash,
                    },
                )
            except Exception:
                logger.warning(
                    "Failed to log signature %s to audit trail", signature_id,
                )

        logger.info(
            "Captured signature %s: user=%s action=%s resource=%s",
            signature_id, user_id, action, resource,
        )

        return record

    def verify_signature(self, signature_id: str) -> Optional[dict]:
        """
        Verify a previously captured signature exists and is valid.

        Args:
            signature_id: The unique signature identifier.

        Returns:
            The signature record if found and valid, else None.

        Raises:
            ValueError: If signature_id is empty.
            ElectronicSignatureError: If DynamoDB query fails.
        """
        if not signature_id:
            raise ValueError("signature_id is required")

        try:
            table = self.dynamodb_resource.Table(self.table_name)
            response = table.get_item(Key={'signature_id': signature_id})
            item = response.get('Item')
            if not item:
                return None

            # Verify integrity hash
            expected_hash = self._compute_hash(
                item['user_id'],
                item['action'],
                item['resource'],
                item['intent'],
                item['timestamp_iso'],
            )
            if expected_hash != item.get('content_hash'):
                logger.warning(
                    "Signature %s failed integrity check", signature_id,
                )
                return None

            return item
        except Exception as exc:
            raise ElectronicSignatureError(
                f"Failed to verify signature: {exc}"
            ) from exc

    def get_signatures_for_resource(
        self,
        resource_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list:
        """
        Query all signatures associated with a resource within a time range.

        Args:
            resource_id: The resource identifier.
            start_time: Start of the query window.
            end_time: End of the query window.

        Returns:
            List of signature record dicts.

        Raises:
            ValueError: If parameters are invalid.
            ElectronicSignatureError: If query fails.
        """
        if not resource_id:
            raise ValueError("resource_id is required")
        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")

        start_epoch = Decimal(str(start_time.timestamp()))
        end_epoch = Decimal(str(end_time.timestamp()))

        try:
            table = self.dynamodb_resource.Table(self.table_name)
            response = table.query(
                IndexName='resource-index',
                KeyConditionExpression='resource = :r AND #ts BETWEEN :s AND :e',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':r': resource_id,
                    ':s': start_epoch,
                    ':e': end_epoch,
                },
            )
            return response.get('Items', [])
        except Exception as exc:
            raise ElectronicSignatureError(
                f"Failed to query signatures for resource: {exc}"
            ) from exc

    def get_signatures_by_user(
        self,
        user_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list:
        """
        Query all signatures by a specific user within a time range.

        Args:
            user_id: The user identifier.
            start_time: Start of the query window.
            end_time: End of the query window.

        Returns:
            List of signature record dicts.

        Raises:
            ValueError: If parameters are invalid.
            ElectronicSignatureError: If query fails.
        """
        if not user_id:
            raise ValueError("user_id is required")
        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")

        start_epoch = Decimal(str(start_time.timestamp()))
        end_epoch = Decimal(str(end_time.timestamp()))

        try:
            table = self.dynamodb_resource.Table(self.table_name)
            response = table.query(
                IndexName='user-index',
                KeyConditionExpression='user_id = :u AND #ts BETWEEN :s AND :e',
                ExpressionAttributeNames={'#ts': 'timestamp'},
                ExpressionAttributeValues={
                    ':u': user_id,
                    ':s': start_epoch,
                    ':e': end_epoch,
                },
            )
            return response.get('Items', [])
        except Exception as exc:
            raise ElectronicSignatureError(
                f"Failed to query signatures by user: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_capture_input(user_id, action, resource, intent, auth_method):
        if not user_id:
            raise ValueError("user_id is required")
        if not action:
            raise ValueError("action is required")
        if not resource:
            raise ValueError("resource is required")
        if not intent:
            raise ValueError("intent is required")
        if not auth_method:
            raise ValueError("auth_method is required")
        if action not in CRITICAL_ACTIONS:
            raise ValueError(
                f"Action '{action}' is not a critical action. "
                f"Must be one of: {sorted(CRITICAL_ACTIONS)}"
            )

    @staticmethod
    def _compute_hash(user_id, action, resource, intent, timestamp_iso):
        """SHA-256 hash of signature content for integrity verification."""
        content = f"{user_id}{action}{resource}{intent}{timestamp_iso}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
