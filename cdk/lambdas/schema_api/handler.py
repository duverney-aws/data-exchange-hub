"""
Lambda handler for Schema API Gateway integration.

Routes:
    POST /api/schema/infer    - Infer schema from uploaded file (multipart or base64 JSON)
    POST /api/schema/register - Register a schema in Glue Schema Registry

Requirements: 2.2, 2.3
"""
import base64
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.schema_registry_service import (
    SchemaRegistryService,
    SchemaRegistryError,
    SchemaValidationError,
)

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

_registry_name = os.environ.get('REGISTRY_NAME', 'pharma-data-exchange')
_service = SchemaRegistryService(registry_name=_registry_name)


def handler(event, context):
    path = event.get('path', '')
    http_method = event.get('httpMethod', '')

    if http_method != 'POST':
        return _response(405, {'error': f'Method {http_method} not allowed'})

    try:
        if path.endswith('/infer'):
            return _handle_infer(event)
        elif path.endswith('/register'):
            return _handle_register(event)
        else:
            return _response(404, {'error': 'Not found'})
    except Exception:
        logger.exception("Unhandled error")
        return _response(500, {'error': 'Internal server error'})


def _handle_infer(event):
    """POST /api/schema/infer - infer schema from file bytes."""
    content_type = (event.get('headers') or {}).get('content-type', '')

    # API Gateway sends binary as base64-encoded body
    body = event.get('body', '')
    is_base64 = event.get('isBase64Encoded', False)

    if is_base64 and body:
        raw_bytes = base64.b64decode(body)
    elif isinstance(body, str):
        raw_bytes = body.encode('utf-8')
    else:
        raw_bytes = body or b''

    if not raw_bytes:
        return _response(400, {'error': 'No file data provided'})

    # Determine format from content-type or query param
    query_params = event.get('queryStringParameters') or {}
    file_format = query_params.get('format', '')
    if not file_format:
        if 'csv' in content_type:
            file_format = 'csv'
        elif 'parquet' in content_type:
            file_format = 'parquet'
        else:
            file_format = 'json'

    try:
        schema = _service.infer_schema_from_sample(raw_bytes, file_format)
        fields = _json_schema_to_fields(schema)
        return _response(200, {
            'schemaId': f"inferred-{uuid.uuid4().hex[:8]}",
            'fields': fields,
            'sourceFile': query_params.get('filename', 'uploaded-file'),
            'inferredAt': datetime.now(timezone.utc).isoformat(),
        })
    except SchemaValidationError as exc:
        return _response(400, {'error': str(exc)})
    except SchemaRegistryError as exc:
        return _response(500, {'error': str(exc)})


def _handle_register(event):
    """POST /api/schema/register - register schema in Glue Schema Registry."""
    body = _parse_body(event)
    if body is None:
        return _response(400, {'error': 'Request body must be valid JSON'})

    schema_name = body.get('schemaName')
    fields = body.get('fields')
    data_format = body.get('dataFormat', 'json').upper()

    if not schema_name or not fields:
        return _response(400, {'error': 'Missing required fields: schemaName, fields'})

    schema_definition = {'type': 'object', 'properties': {
        f['name']: {'type': f['type']} for f in fields
    }}

    try:
        version_id = _service.register_schema(
            schema_name=schema_name,
            schema_definition=schema_definition,
            data_format=data_format,
        )
        return _response(201, {
            'schemaId': schema_name,
            'schemaName': schema_name,
            'version': version_id,
            'registeredAt': datetime.now(timezone.utc).isoformat(),
        })
    except SchemaValidationError as exc:
        return _response(400, {'error': str(exc)})
    except SchemaRegistryError as exc:
        logger.error("Schema registration failed: %s", exc)
        return _response(500, {'error': 'Schema registration failed'})


def _json_schema_to_fields(schema: dict) -> list:
    """Convert a JSON Schema dict to the frontend SchemaField list format."""
    properties = schema.get('properties', {})
    required = set(schema.get('required', []))
    fields = []
    for name, defn in properties.items():
        fields.append({
            'name': name,
            'type': defn.get('type', 'string'),
            'nullable': name not in required,
        })
    return fields


def _parse_body(event):
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
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps(body, default=str),
    }
