"""
Contract Service

DynamoDB operations for data contract CRUD, querying by CMO, and status updates.
Uses the data-contracts table with GSI cmo-contracts-index.

Requirements: 2.4
"""
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

import boto3
from boto3.dynamodb.conditions import Key

from models.data_contract import DataContract
from services.contract_validation_service import ContractValidationService
from utils.contract_utils import generate_contract_id

logger = logging.getLogger(__name__)

VALID_STATUSES = {'draft', 'active', 'suspended'}


class ContractServiceError(Exception):
    """Base exception for contract service operations."""
    pass


class ContractNotFoundError(ContractServiceError):
    """Raised when a contract is not found in DynamoDB."""
    pass


class ContractService:
    """
    Service for managing data contracts in DynamoDB.

    Provides CRUD operations, CMO-based queries via GSI, and status management.
    """

    def __init__(self, table_name: str = 'data-contracts', dynamodb_resource=None):
        self.dynamodb = dynamodb_resource or boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        self.validation_service = ContractValidationService()

    def create_contract(self, data: dict) -> DataContract:
        """
        Validate, generate ID, persist, and return a new DataContract.

        Args:
            data: Dictionary with contract payload (cmoId, dataDomain, etc.).

        Returns:
            The persisted DataContract instance.

        Raises:
            ContractServiceError: If validation fails or DynamoDB write fails.
        """
        is_valid, errors = self.validation_service.validate_contract(data)
        if not is_valid:
            raise ContractServiceError(f"Validation failed: {'; '.join(errors)}")

        cmo_id = data['cmoId']
        data_domain = data['dataDomain']
        existing_count = self._count_contracts_for_cmo_domain(cmo_id, data_domain)
        contract_id = self.validation_service.generate_contract_id(
            cmo_id, data_domain, existing_count,
        )

        now = datetime.now(timezone.utc)
        contract = DataContract.from_dynamodb_item({
            'contractId': contract_id,
            'cmoId': cmo_id,
            'productId': data.get('productId', ''),
            'dataDomain': data_domain,
            'schemaId': data['schemaId'],
            'schemaVersion': data['schemaVersion'],
            'qualityRules': data['qualityRules'],
            'elementSlas': data.get('elementSlas', []),
            'sla': data['sla'],
            'deliverySchedule': data['deliverySchedule'],
            'governance': data['governance'],
            'connectionId': data.get('connectionId', ''),
            'integrationPattern': data.get('integrationPattern', ''),
            'integrationConfig': data.get('integrationConfig', {}),
            'status': 'draft',
            'createdAt': now.isoformat(),
            'updatedAt': now.isoformat(),
        })

        try:
            self.table.put_item(Item=self._convert_floats(contract.to_dynamodb_item()))
        except Exception as exc:
            raise ContractServiceError(f"Failed to save contract: {exc}") from exc

        return contract

    def get_contract(self, contract_id: str) -> DataContract:
        """
        Retrieve a contract by its primary key.

        Raises:
            ContractNotFoundError: If the contract does not exist.
        """
        try:
            response = self.table.get_item(Key={'contractId': contract_id})
        except Exception as exc:
            raise ContractServiceError(f"Failed to get contract: {exc}") from exc

        item = response.get('Item')
        if not item:
            raise ContractNotFoundError(f"Contract '{contract_id}' not found")

        return DataContract.from_dynamodb_item(self._convert_decimals(item))

    def update_contract(self, contract_id: str, data: dict) -> DataContract:
        """
        Update an existing contract's mutable fields.

        Fetches the current contract, merges provided fields, validates,
        and writes back.

        Raises:
            ContractNotFoundError: If the contract does not exist.
            ContractServiceError: If validation or write fails.
        """
        existing = self.get_contract(contract_id)
        merged = existing.to_dynamodb_item()

        updatable_fields = [
            'schemaId', 'schemaVersion', 'qualityRules',
            'sla', 'deliverySchedule', 'governance',
        ]
        for field in updatable_fields:
            if field in data:
                merged[field] = data[field]

        is_valid, errors = self.validation_service.validate_contract(merged)
        if not is_valid:
            raise ContractServiceError(f"Validation failed: {'; '.join(errors)}")

        merged['updatedAt'] = datetime.now(timezone.utc).isoformat()

        try:
            self.table.put_item(Item=self._convert_floats(merged))
        except Exception as exc:
            raise ContractServiceError(f"Failed to update contract: {exc}") from exc

        return DataContract.from_dynamodb_item(merged)

    def update_contract_status(self, contract_id: str, new_status: str) -> DataContract:
        """
        Update only the status and updatedAt timestamp.

        Args:
            contract_id: The contract to update.
            new_status: One of 'draft', 'active', 'suspended'.

        Raises:
            ContractServiceError: If the status value is invalid.
            ContractNotFoundError: If the contract does not exist.
        """
        if new_status not in VALID_STATUSES:
            raise ContractServiceError(
                f"Invalid status '{new_status}'. Must be one of {sorted(VALID_STATUSES)}"
            )

        existing = self.get_contract(contract_id)
        now = datetime.now(timezone.utc).isoformat()

        try:
            self.table.update_item(
                Key={'contractId': contract_id},
                UpdateExpression='SET #s = :status, updatedAt = :ts',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={':status': new_status, ':ts': now},
            )
        except Exception as exc:
            raise ContractServiceError(f"Failed to update status: {exc}") from exc

        existing.status = new_status
        existing.updated_at = datetime.fromisoformat(now)
        return existing

    def query_contracts_by_cmo(
        self, cmo_id: str, status: Optional[str] = None,
    ) -> List[DataContract]:
        """
        Query contracts using the cmo-contracts-index GSI.

        Args:
            cmo_id: Partition key value.
            status: Optional sort key condition to filter by status.

        Returns:
            List of matching DataContract instances.
        """
        key_condition = Key('cmoId').eq(cmo_id)
        if status:
            key_condition = key_condition & Key('status').eq(status)

        try:
            response = self.table.query(
                IndexName='cmo-contracts-index',
                KeyConditionExpression=key_condition,
            )
        except Exception as exc:
            raise ContractServiceError(f"Failed to query contracts: {exc}") from exc

        return [DataContract.from_dynamodb_item(self._convert_decimals(item)) for item in response.get('Items', [])]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_floats(obj):
        """Recursively convert float values to Decimal for DynamoDB compatibility."""
        if isinstance(obj, float):
            return Decimal(str(obj))
        if isinstance(obj, dict):
            return {k: ContractService._convert_floats(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [ContractService._convert_floats(v) for v in obj]
        return obj

    @staticmethod
    def _convert_decimals(obj):
        """Recursively convert Decimal values back to float/int for model compatibility."""
        if isinstance(obj, Decimal):
            if obj == int(obj):
                return int(obj)
            return float(obj)
        if isinstance(obj, dict):
            return {k: ContractService._convert_decimals(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [ContractService._convert_decimals(v) for v in obj]
        return obj

    def _count_contracts_for_cmo_domain(self, cmo_id: str, data_domain: str) -> int:
        """Count existing contracts for a CMO + data domain combination."""
        try:
            response = self.table.query(
                IndexName='cmo-contracts-index',
                KeyConditionExpression=Key('cmoId').eq(cmo_id),
                Select='COUNT',
            )
            # Filter by dataDomain client-side from the count isn't precise,
            # so we do a full query and filter.
            response = self.table.query(
                IndexName='cmo-contracts-index',
                KeyConditionExpression=Key('cmoId').eq(cmo_id),
            )
            items = response.get('Items', [])
            return sum(1 for item in items if item.get('dataDomain') == data_domain)
        except Exception:
            return 0
