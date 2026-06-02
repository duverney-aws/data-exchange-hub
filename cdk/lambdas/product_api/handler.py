"""
Product API Lambda handler.

Routes:
    POST  /api/product                        - [merck-admins] Create a product
    GET   /api/product                        - [both]         List products (filter by ?cmoId=)
    GET   /api/product/{productId}            - [both]         Get product details
    PUT   /api/product/{productId}            - [merck-admins] Update product
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

_TABLE = os.environ.get('PRODUCT_TABLE_NAME', 'products')


def handler(event, context):
    method = event.get('httpMethod', '')
    path_params = event.get('pathParameters') or {}
    try:
        if method == 'POST':
            return _require_role(event, 'merck-admins', _handle_create)
        elif method == 'GET':
            if path_params.get('productId'):
                return _handle_get(event)
            return _handle_list(event)
        elif method == 'PUT':
            return _require_role(event, 'merck-admins', _handle_update)
        else:
            return _resp(405, {'error': 'Method not allowed'})
    except Exception:
        logger.exception('Unhandled error')
        return _resp(500, {'error': 'Internal server error'})


def _handle_create(event):
    body = _parse_body(event)
    if not body:
        return _resp(400, {'error': 'Request body required'})

    required = ['productName', 'strength', 'dosageForm', 'cmoId']
    missing = [f for f in required if not body.get(f)]
    if missing:
        return _resp(400, {'error': f'Missing required fields: {", ".join(missing)}'})

    now = _now()
    product_id = f'prod-{uuid.uuid4().hex[:12]}'
    item = {
        'productId': product_id,
        'productName': body['productName'],
        'strength': body['strength'],
        'dosageForm': body['dosageForm'],
        'cmoId': body['cmoId'],
        'isActive': body.get('isActive', True),
        'createdAt': now,
        'updatedAt': now,
    }
    if body.get('description'):
        item['description'] = body['description']

    boto3.resource('dynamodb').Table(_TABLE).put_item(Item=item)
    return _resp(201, item)


def _handle_list(event):
    query_params = event.get('queryStringParameters') or {}
    _, groups, jwt_cmo_id = _get_user_info(event)
    table = boto3.resource('dynamodb').Table(_TABLE)

    # CMO users: always filter by their JWT org claim
    if 'cmo-users' in groups and 'merck-admins' not in groups:
        if not jwt_cmo_id:
            return _resp(403, {'error': 'No organization linked to your account.'})
        cmo_id = jwt_cmo_id
    else:
        cmo_id = query_params.get('cmoId')

    if cmo_id:
        result = table.query(
            IndexName='cmo-products-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('cmoId').eq(cmo_id),
        )
    else:
        result = table.scan()

    return _resp(200, {'products': result.get('Items', [])})


def _handle_get(event):
    product_id = (event.get('pathParameters') or {}).get('productId')
    result = boto3.resource('dynamodb').Table(_TABLE).get_item(Key={'productId': product_id})
    item = result.get('Item')
    if not item:
        return _resp(404, {'error': f'Product {product_id} not found'})
    return _resp(200, item)


def _handle_update(event):
    product_id = (event.get('pathParameters') or {}).get('productId')
    body = _parse_body(event)
    if not body:
        return _resp(400, {'error': 'Request body required'})

    table = boto3.resource('dynamodb').Table(_TABLE)
    result = table.get_item(Key={'productId': product_id})
    item = result.get('Item')
    if not item:
        return _resp(404, {'error': f'Product {product_id} not found'})

    updatable = ['productName', 'strength', 'dosageForm', 'isActive', 'description']
    for field in updatable:
        if field in body:
            item[field] = body[field]
    item['updatedAt'] = _now()
    table.put_item(Item=item)
    return _resp(200, item)


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
