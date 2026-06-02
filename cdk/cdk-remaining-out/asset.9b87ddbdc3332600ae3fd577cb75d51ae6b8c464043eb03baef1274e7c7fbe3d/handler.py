"""
Lambda handler for Contract API Gateway integration.

Routes:
    POST   /api/contract                      – Create a new data contract
    GET    /api/contract/{contractId}          – Get contract details
    PUT    /api/contract/{contractId}          – Update a data contract
    POST   /api/contract/{contractId}/activate – Activate pipeline

Requirements: 2.1, 4.1
"""
import json
import logging
import os
import sys

# Ensure the project root is on the path so we can import services/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.contract_service import (
    ContractService,
    ContractNotFoundError,
    ContractServiceError,
)

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialise service once per Lambda cold-start
_table_name = os.environ.get('TABLE_NAME', 'data-contracts')
_service = ContractService(table_name=_table_name)


def handler(event, context):
    """
    API Gateway proxy Lambda handler.

    Dispatches to create, get, update, or activate based on HTTP method and path.
    """
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')

    try:
        if http_method == 'POST' and path.endswith('/activate'):
            return _handle_activate(event)
        elif http_method == 'POST':
            return _handle_create(event)
        elif http_method == 'PUT':
            return _handle_update(event)
        elif http_method == 'GET':
            return _handle_get(event)
        else:
            return _response(405, {'error': f'Method {http_method} not allowed'})
    except Exception as exc:
        logger.exception("Unhandled error")
        return _response(500, {'error': 'Internal server error'})


# ------------------------------------------------------------------
# Route handlers
# ------------------------------------------------------------------

def _handle_create(event):
    """Handle POST /api/contract – create a new data contract."""
    body = _parse_body(event)
    if body is None:
        return _response(400, {'error': 'Request body must be valid JSON'})

    try:
        contract = _service.create_contract(body)
        return _response(201, contract.to_dynamodb_item())
    except ContractServiceError as exc:
        return _response(400, {'error': str(exc)})


def _handle_get(event):
    """Handle GET /api/contract/{contractId} – retrieve contract details."""
    path_params = event.get('pathParameters') or {}
    contract_id = path_params.get('contractId')
    if not contract_id:
        return _response(400, {'error': 'Missing path parameter: contractId'})

    try:
        contract = _service.get_contract(contract_id)
        return _response(200, contract.to_dynamodb_item())
    except ContractNotFoundError as exc:
        return _response(404, {'error': str(exc)})
    except ContractServiceError as exc:
        logger.error("Contract retrieval failed: %s", exc)
        return _response(500, {'error': 'Contract retrieval failed'})


def _handle_update(event):
    """Handle PUT /api/contract/{contractId} – update a data contract."""
    path_params = event.get('pathParameters') or {}
    contract_id = path_params.get('contractId')
    if not contract_id:
        return _response(400, {'error': 'Missing path parameter: contractId'})

    body = _parse_body(event)
    if body is None:
        return _response(400, {'error': 'Request body must be valid JSON'})

    try:
        contract = _service.update_contract(contract_id, body)
        return _response(200, contract.to_dynamodb_item())
    except ContractNotFoundError as exc:
        return _response(404, {'error': str(exc)})
    except ContractServiceError as exc:
        return _response(400, {'error': str(exc)})


def _handle_activate(event):
    """Handle POST /api/contract/{contractId}/activate – activate pipeline."""
    path_params = event.get('pathParameters') or {}
    contract_id = path_params.get('contractId')
    if not contract_id:
        return _response(400, {'error': 'Missing path parameter: contractId'})

    try:
        contract = _service.update_contract_status(contract_id, 'active')
        return _response(200, contract.to_dynamodb_item())
    except ContractNotFoundError as exc:
        return _response(404, {'error': str(exc)})
    except ContractServiceError as exc:
        return _response(400, {'error': str(exc)})


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_body(event):
    """Parse the JSON body from the API Gateway event."""
    body = event.get('body')
    if body is None:
        return None
    if isinstance(body, str):
        try:
            return json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return None
    return body


def _response(status_code: int, body: dict) -> dict:
    """Build an API Gateway proxy response."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps(body, default=str),
    }
