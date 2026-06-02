"""
Lambda handler for Schema Registry API Gateway integration.

Routes:
    POST /api/schema   – Register a new schema (or new version)
    GET  /api/schema/{schemaId} – Retrieve a schema definition

Requirements: 2.2, 2.3
"""
import json
import logging
import os
import sys

# Ensure the project root is on the path so we can import services/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.schema_registry_service import (
    SchemaRegistryService,
    SchemaRegistryError,
    SchemaNotFoundError,
    SchemaValidationError,
)

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialise service once per Lambda cold-start
_registry_name = os.environ.get('REGISTRY_NAME', 'pharma-data-exchange')
_service = SchemaRegistryService(registry_name=_registry_name)


def handler(event, context):
    """
    API Gateway proxy Lambda handler.

    Dispatches to register or get based on HTTP method.
    """
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')

    try:
        if http_method == 'POST':
            return _handle_register(event)
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

def _handle_register(event):
    """Handle POST – register a schema."""
    body = _parse_body(event)
    if body is None:
        return _response(400, {'error': 'Request body must be valid JSON'})

    schema_name = body.get('schema_name')
    schema_definition = body.get('schema_definition')
    data_format = body.get('data_format')

    if not schema_name or schema_definition is None or not data_format:
        return _response(400, {
            'error': 'Missing required fields: schema_name, schema_definition, data_format'
        })

    try:
        version_id = _service.register_schema(
            schema_name=schema_name,
            schema_definition=schema_definition,
            data_format=data_format,
        )
        return _response(201, {
            'schema_name': schema_name,
            'schema_version_id': version_id,
        })
    except SchemaValidationError as exc:
        return _response(400, {'error': str(exc)})
    except SchemaRegistryError as exc:
        logger.error("Schema registration failed: %s", exc)
        return _response(500, {'error': 'Schema registration failed'})


def _handle_get(event):
    """Handle GET – retrieve a schema."""
    path_params = event.get('pathParameters') or {}
    query_params = event.get('queryStringParameters') or {}

    schema_id = path_params.get('schemaId')
    if not schema_id:
        return _response(400, {'error': 'Missing path parameter: schemaId'})

    version = query_params.get('version', 'latest')

    try:
        result = _service.get_schema(schema_id=schema_id, version=version)
        return _response(200, result)
    except SchemaNotFoundError as exc:
        return _response(404, {'error': str(exc)})
    except SchemaRegistryError as exc:
        logger.error("Schema retrieval failed: %s", exc)
        return _response(500, {'error': 'Schema retrieval failed'})


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
