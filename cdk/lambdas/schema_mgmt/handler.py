"""
Schema Management API Lambda handler (CMO-scoped).

Routes:
    POST  /api/schema                    - [merck-admins] Create schema
    GET   /api/schema                    - [both]         List schemas (?cmoId=)
    GET   /api/schema/{schemaId}         - [both]         Get schema
    PUT   /api/schema/{schemaId}         - [merck-admins] Update schema
    POST  /api/schema/infer              - [both]         Infer fields from uploaded file
    POST  /api/schema/{schemaId}/register - [merck-admins] Register in Glue
"""
import base64
import csv
import io
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

_TABLE = os.environ.get('SCHEMA_TABLE_NAME', 'schemas')
_REGISTRY = os.environ.get('REGISTRY_NAME', 'pharma-data-exchange')


def handler(event, context):
    method = event.get('httpMethod', '')
    path = event.get('resource', '')
    try:
        if method == 'POST' and '/infer' in path:
            return _handle_infer(event)
        if method == 'POST' and '/register' in path:
            return _require_role(event, 'merck-admins', _handle_register)
        if method == 'POST':
            return _require_role(event, 'merck-admins', _handle_create)
        if method == 'GET':
            params = event.get('pathParameters') or {}
            if params.get('schemaId'):
                return _handle_get(event)
            return _handle_list(event)
        if method == 'PUT':
            return _require_role(event, 'merck-admins', _handle_update)
        return _resp(405, {'error': 'Method not allowed'})
    except Exception:
        logger.exception('Unhandled error')
        return _resp(500, {'error': 'Internal server error'})


def _handle_create(event):
    body = _parse_body(event)
    if not body:
        return _resp(400, {'error': 'Request body required'})
    missing = [f for f in ('cmoId', 'name', 'fields') if not body.get(f)]
    if missing:
        return _resp(400, {'error': 'Missing: ' + ', '.join(missing)})
    now = _now()
    item = {
        'schemaId': 'schema-' + uuid.uuid4().hex[:12],
        'cmoId': body['cmoId'],
        'name': body['name'],
        'fields': body['fields'],
        'version': '1',
        'status': 'draft',
        'registrySchemaName': '',
        'createdAt': now,
        'updatedAt': now,
    }
    boto3.resource('dynamodb').Table(_TABLE).put_item(Item=item)
    return _resp(201, item)


def _handle_list(event):
    qs = event.get('queryStringParameters') or {}
    _, groups, jwt_cmo_id = _get_user_info(event)
    table = boto3.resource('dynamodb').Table(_TABLE)
    if 'cmo-users' in groups and 'merck-admins' not in groups:
        if not jwt_cmo_id:
            return _resp(403, {'error': 'No organization linked to your account.'})
        cmo_id = jwt_cmo_id
    else:
        cmo_id = qs.get('cmoId')
    if cmo_id:
        result = table.query(IndexName='cmo-schemas-index', KeyConditionExpression=Key('cmoId').eq(cmo_id))
    else:
        result = table.scan()
    return _resp(200, {'schemas': result.get('Items', [])})


def _handle_get(event):
    sid = (event.get('pathParameters') or {}).get('schemaId')
    item = boto3.resource('dynamodb').Table(_TABLE).get_item(Key={'schemaId': sid}).get('Item')
    if not item:
        return _resp(404, {'error': 'Schema not found'})
    return _resp(200, item)


def _handle_update(event):
    sid = (event.get('pathParameters') or {}).get('schemaId')
    body = _parse_body(event)
    if not body:
        return _resp(400, {'error': 'Request body required'})
    table = boto3.resource('dynamodb').Table(_TABLE)
    item = table.get_item(Key={'schemaId': sid}).get('Item')
    if not item:
        return _resp(404, {'error': 'Schema not found'})
    fields_changed = 'fields' in body and body['fields'] != item.get('fields')
    for f in ('name', 'fields'):
        if f in body:
            item[f] = body[f]
    # If fields changed on a registered schema, reset to draft so it can be re-registered
    if fields_changed and item.get('status') == 'registered':
        item['status'] = 'draft'
    item['updatedAt'] = _now()
    table.put_item(Item=item)
    return _resp(200, item)


def _handle_infer(event):
    """Infer schema fields from uploaded file bytes."""
    body_raw = event.get('body', '')
    is_base64 = event.get('isBase64Encoded', False)

    if is_base64 and body_raw:
        raw_bytes = base64.b64decode(body_raw)
    elif isinstance(body_raw, str):
        raw_bytes = body_raw.encode('utf-8')
    else:
        raw_bytes = body_raw or b''

    if not raw_bytes:
        return _resp(400, {'error': 'No file data provided'})

    # Extract file content from multipart/form-data envelope
    raw_bytes = _extract_multipart(raw_bytes)

    qs = event.get('queryStringParameters') or {}
    fmt = qs.get('format', 'csv')

    try:
        if fmt == 'json':
            fields = _infer_json(raw_bytes)
        else:
            fields = _infer_csv(raw_bytes)
        return _resp(200, {
            'fields': fields,
            'sourceFile': qs.get('filename', 'uploaded-file'),
            'inferredAt': _now(),
        })
    except Exception as e:
        logger.exception('Infer failed')
        return _resp(400, {'error': 'Failed to infer schema: ' + str(e)})


def _handle_register(event):
    """Register schema in Glue Schema Registry."""
    sid = (event.get('pathParameters') or {}).get('schemaId')
    table = boto3.resource('dynamodb').Table(_TABLE)
    item = table.get_item(Key={'schemaId': sid}).get('Item')
    if not item:
        return _resp(404, {'error': 'Schema not found'})
    fields = item.get('fields', [])
    schema_name = (item['cmoId'] + '-' + item['name']).lower().replace(' ', '-')
    # Map internal types to valid JSON Schema types
    type_map = {'integer': 'integer', 'double': 'number', 'boolean': 'boolean',
                'string': 'string', 'array': 'array', 'object': 'object',
                'timestamp': 'string', 'date': 'string'}
    schema_def = json.dumps({
        'type': 'object',
        'properties': {f['name']: {'type': type_map.get(f['type'], 'string')} for f in fields}
    })
    glue = boto3.client('glue')
    try:
        glue.get_schema(SchemaId={'RegistryName': _REGISTRY, 'SchemaName': schema_name})
        resp = glue.register_schema_version(
            SchemaId={'RegistryName': _REGISTRY, 'SchemaName': schema_name},
            SchemaDefinition=schema_def,
        )
        version = str(resp.get('VersionNumber', '1'))
    except glue.exceptions.EntityNotFoundException:
        resp = glue.create_schema(
            RegistryId={'RegistryName': _REGISTRY},
            SchemaName=schema_name,
            DataFormat='JSON',
            Compatibility='BACKWARD',
            SchemaDefinition=schema_def,
        )
        version = '1'
    item['registrySchemaName'] = schema_name
    item['version'] = version
    item['status'] = 'registered'
    item['updatedAt'] = _now()
    table.put_item(Item=item)
    return _resp(200, item)


def _extract_multipart(raw_bytes):
    """Extract file content from multipart/form-data envelope."""
    text = raw_bytes.decode('utf-8', errors='replace')
    # Check if this looks like multipart data
    if not text.lstrip().startswith('------'):
        return raw_bytes
    # Split headers from body on double newline
    sep = '\r\n\r\n' if '\r\n\r\n' in text else '\n\n'
    parts = text.split(sep, 1)
    if len(parts) < 2:
        return raw_bytes
    body = parts[1]
    # Remove trailing boundary
    result_lines = []
    for line in body.split('\n'):
        if line.strip().startswith('------'):
            break
        result_lines.append(line.rstrip('\r'))
    result = '\n'.join(result_lines).strip()
    return result.encode('utf-8') if result else raw_bytes


def _infer_csv(raw_bytes):
    text = raw_bytes.decode('utf-8', errors='replace')
    reader = csv.DictReader(io.StringIO(text))
    fields = []
    for col in (reader.fieldnames or []):
        fields.append({'name': col.strip(), 'type': 'string', 'nullable': True})
    try:
        row = next(reader)
        for f in fields:
            val = row.get(f['name'], '')
            if val.isdigit():
                f['type'] = 'integer'
            else:
                try:
                    float(val)
                    f['type'] = 'double'
                except ValueError:
                    pass
    except StopIteration:
        pass
    return fields


def _infer_json(raw_bytes):
    data = json.loads(raw_bytes)
    sample = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {}
    type_map = {str: 'string', int: 'integer', float: 'double', bool: 'boolean', list: 'array', dict: 'object'}
    return [{'name': k, 'type': type_map.get(type(v), 'string'), 'nullable': True} for k, v in sample.items()]


# --- helpers ---

def _get_user_info(event):
    claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
    user_id = claims.get('sub') or claims.get('cognito:username', 'unknown')
    groups_str = claims.get('cognito:groups', '')
    groups = groups_str.split(',') if isinstance(groups_str, str) and groups_str else []
    cmo_id = claims.get('custom:organization')
    return user_id, groups, cmo_id


def _require_role(event, required_group, fn):
    _, groups, _ = _get_user_info(event)
    if required_group not in groups:
        return _resp(403, {'error': 'Access denied. Required role: ' + required_group})
    return fn(event)


def _now():
    return datetime.now(timezone.utc).isoformat()


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


def _resp(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        },
        'body': json.dumps(body, default=str),
    }
