"""
Batch API Lambda handler.

Routes:
    POST  /api/batch                          - [cmo-users]    Create a new batch record
    GET   /api/batch                          - [both]         List batches (filtered by cmoId for CMO users)
    GET   /api/batch/{batchId}                - [both]         Get batch details
    PUT   /api/batch/{batchId}                - [cmo-users]    Update batch (add data element receipt)
    POST  /api/batch/{batchId}/submit         - [cmo-users]    Mark batch as fully submitted
"""
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

_TABLE = os.environ.get('BATCH_TABLE_NAME', 'batches')
_CONN_TABLE = os.environ.get('CONNECTION_TABLE_NAME', 'connections')
_DATA_LAKE_BUCKET = os.environ.get('DATA_LAKE_BUCKET', '')


def handler(event, context):
    method = event.get('httpMethod', '')
    path = event.get('path', '')
    try:
        if method == 'POST' and path.endswith('/submit'):
            return _require_role(event, 'cmo-users', _handle_submit)
        elif method == 'POST':
            return _require_role(event, 'cmo-users', _handle_create)
        elif method == 'GET' and path.endswith('/view'):
            return _handle_element_view(event)
        elif method == 'GET' and path.endswith('/connections'):
            return _handle_get_connections(event)
        elif method == 'GET':
            path_params = event.get('pathParameters') or {}
            if path_params.get('batchId'):
                return _handle_get(event)
            return _handle_list(event)
        elif method == 'PUT':
            return _require_role(event, 'cmo-users', _handle_update)
        else:
            return _resp(405, {'error': 'Method not allowed'})
    except Exception:
        logger.exception('Unhandled error')
        return _resp(500, {'error': 'Internal server error'})


def _handle_create(event):
    body = _parse_body(event)
    if not body:
        return _resp(400, {'error': 'Request body required'})

    required = ['lotNumber', 'productId', 'manufacturingDate']
    missing = [f for f in required if not body.get(f)]
    if missing:
        return _resp(400, {'error': f'Missing required fields: {", ".join(missing)}'})

    _, _, _, cmo_id = _get_user_info(event)
    if not cmo_id:
        return _resp(403, {'error': 'CMO user must be linked to an organization'})

    now = _now()
    batch_id = f'batch-{uuid.uuid4().hex[:12]}'
    item = {
        'batchId': batch_id,
        'lotNumber': body['lotNumber'],
        'productId': body['productId'],
        'cmoId': cmo_id,
        'manufacturingDate': body['manufacturingDate'],
        'status': 'in_progress',
        'dataElements': [
            {'elementType': e, 'received': False, 'receivedAt': None, 's3Path': None, 'overdue': False}
            for e in ['bmr', 'coa', 'in_process', 'yield']
        ],
        'isComplete': False,
        'missingElements': ['bmr', 'coa', 'in_process', 'yield'],
        'createdAt': now,
        'updatedAt': now,
    }
    if body.get('contractId'):
        item['contractId'] = body['contractId']
    if body.get('notes'):
        item['notes'] = body['notes']

    boto3.resource('dynamodb').Table(_TABLE).put_item(Item=item)
    return _resp(201, item)


def _handle_list(event):
    _, groups, _, cmo_id = _get_user_info(event)
    query_params = event.get('queryStringParameters') or {}
    table = boto3.resource('dynamodb').Table(_TABLE)

    # CMO users only see their own batches
    if 'cmo-users' in groups and 'merck-admins' not in groups:
        if not cmo_id:
            return _resp(403, {'error': 'CMO user must be linked to an organization'})
        result = table.query(
            IndexName='cmo-batches-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('cmoId').eq(cmo_id),
        )
    elif query_params.get('cmoId'):
        result = table.query(
            IndexName='cmo-batches-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('cmoId').eq(query_params['cmoId']),
        )
    elif query_params.get('productId'):
        result = table.query(
            IndexName='product-batches-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('productId').eq(query_params['productId']),
        )
    else:
        result = table.scan()

    return _resp(200, {'batches': result.get('Items', [])})


def _handle_get(event):
    batch_id = (event.get('pathParameters') or {}).get('batchId')
    result = boto3.resource('dynamodb').Table(_TABLE).get_item(Key={'batchId': batch_id})
    item = result.get('Item')
    if not item:
        return _resp(404, {'error': f'Batch {batch_id} not found'})
    return _resp(200, item)


def _handle_update(event):
    """Update data element receipt status on a batch."""
    batch_id = (event.get('pathParameters') or {}).get('batchId')
    body = _parse_body(event)
    if not body:
        return _resp(400, {'error': 'Request body required'})

    table = boto3.resource('dynamodb').Table(_TABLE)
    result = table.get_item(Key={'batchId': batch_id})
    item = result.get('Item')
    if not item:
        return _resp(404, {'error': f'Batch {batch_id} not found'})

    # Update a specific data element as received
    element_type = body.get('elementType')
    s3_path = body.get('s3Path')
    if element_type:
        elements = item.get('dataElements', [])
        for el in elements:
            if el['elementType'] == element_type:
                el['received'] = True
                el['receivedAt'] = _now()
                if s3_path:
                    el['s3Path'] = s3_path
                break
        item['dataElements'] = elements
        missing = [e['elementType'] for e in elements if not e['received']]
        item['missingElements'] = missing
        item['isComplete'] = len(missing) == 0

    item['updatedAt'] = _now()
    table.put_item(Item=item)
    return _resp(200, item)


def _handle_submit(event):
    """CMO marks batch as fully submitted."""
    batch_id = (event.get('pathParameters') or {}).get('batchId')
    table = boto3.resource('dynamodb').Table(_TABLE)
    result = table.get_item(Key={'batchId': batch_id})
    item = result.get('Item')
    if not item:
        return _resp(404, {'error': f'Batch {batch_id} not found'})

    if item.get('status') != 'in_progress':
        return _resp(400, {'error': f'Batch already submitted (status: {item["status"]})'})

    now = _now()
    item['status'] = 'submitted'
    item['submittedAt'] = now
    item['updatedAt'] = now
    table.put_item(Item=item)
    return _resp(200, item)


def _handle_element_view(event):
    """Return a presigned S3 GET URL for a received batch element's processed result file."""
    path_params = event.get('pathParameters') or {}
    batch_id = path_params.get('batchId')
    element_type = path_params.get('elementType')

    table = boto3.resource('dynamodb').Table(_TABLE)
    result = table.get_item(Key={'batchId': batch_id})
    item = result.get('Item')
    if not item:
        return _resp(404, {'error': f'Batch {batch_id} not found'})

    s3_path = None
    for el in item.get('dataElements', []):
        if el['elementType'] == element_type:
            s3_path = el.get('s3Path')
            break

    if not s3_path:
        return _resp(404, {'error': f'No s3Path recorded for element {element_type}'})

    # s3_path format: s3://{bucket}/{key}
    if not s3_path.startswith('s3://'):
        return _resp(400, {'error': 'Invalid s3Path format'})
    without_prefix = s3_path[5:]
    bucket, _, key = without_prefix.partition('/')

    s3_client = boto3.client('s3')
    obj = s3_client.get_object(Bucket=bucket, Key=key)
    content = json.loads(obj['Body'].read())
    return _resp(200, content)


def _handle_get_connections(event):
    """Return all active connections for the CMO that owns this batch."""
    batch_id = (event.get('pathParameters') or {}).get('batchId')
    table = boto3.resource('dynamodb').Table(_TABLE)
    result = table.get_item(Key={'batchId': batch_id})
    item = result.get('Item')
    if not item:
        return _resp(404, {'error': f'Batch {batch_id} not found'})

    cmo_id = item.get('cmoId')
    conn_table = boto3.resource('dynamodb').Table(_CONN_TABLE)
    conn_result = conn_table.query(
        IndexName='cmo-connections-index',
        KeyConditionExpression=boto3.dynamodb.conditions.Key('cmoId').eq(cmo_id),
    )
    active = [c for c in conn_result.get('Items', []) if c.get('status') == 'active']
    return _resp(200, {'connections': active})


# --- helpers ---

def _get_user_info(event):
    claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
    user_id = claims.get('sub') or claims.get('cognito:username', 'unknown')
    groups_str = claims.get('cognito:groups', '')
    groups = groups_str.split(',') if isinstance(groups_str, str) and groups_str else []
    email = claims.get('email', user_id)
    cmo_id = claims.get('custom:organization')
    return user_id, groups, email, cmo_id


def _require_role(event, required_group, fn):
    _, groups, _, _ = _get_user_info(event)
    if required_group not in groups:
        return _resp(403, {'error': f'Access denied. Required role: {required_group}'})
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
