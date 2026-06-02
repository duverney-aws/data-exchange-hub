"""
Lambda handler for Natural Language Query API Gateway integration.

Routes:
    POST /api/query - Submit a natural language query

Requirements: 12.1, 12.2, 12.3, 12.4, 12.6
"""
import json
import logging
import os
import sys

import boto3

# Ensure the project root is on the path so we can import services/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.nl_query_service import (
    NLQueryService,
    NLQueryError,
    SQLValidationError,
    QueryTimeoutError,
)

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialise clients and service once per Lambda cold-start
_bedrock = boto3.client('bedrock-runtime')
_athena = boto3.client('athena')
_glue = boto3.client('glue')
_lakeformation = boto3.client('lakeformation')

_service = NLQueryService(
    bedrock_client=_bedrock,
    athena_client=_athena,
    glue_client=_glue,
    lakeformation_client=_lakeformation,
    database=os.environ.get('DATABASE_NAME', 'cmo_data_lake'),
    workgroup=os.environ.get('ATHENA_WORKGROUP', 'cmo-workgroup'),
    results_location=os.environ.get('RESULTS_LOCATION', 's3://athena-results/'),
    model_id=os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-sonnet-20240229-v1:0'),
)


def handler(event, context):
    """
    API Gateway proxy Lambda handler for natural language queries.

    Expects POST with JSON body: {"query": "...", "user_id": "..."}
    """
    http_method = event.get('httpMethod', '')
    if http_method != 'POST':
        return _response(405, {'error': f'Method {http_method} not allowed'})

    body = _parse_body(event)
    if body is None:
        return _response(400, {'error': 'Request body must be valid JSON'})

    user_query = body.get('query', '').strip()
    if not user_query:
        return _response(400, {'error': 'Missing required field: query'})

    # Extract user identity from API Gateway authorizer or body
    user_id = (
        body.get('user_id')
        or _extract_user_from_context(event)
    )
    if not user_id:
        return _response(400, {'error': 'Missing required field: user_id'})

    try:
        result = _service.process_query(user_query, user_id)
        return _response(200, result)
    except SQLValidationError as exc:
        return _response(400, {'error': str(exc)})
    except QueryTimeoutError as exc:
        return _response(504, {'error': str(exc)})
    except NLQueryError as exc:
        logger.error("NL query processing failed: %s", exc)
        return _response(500, {'error': 'Query processing failed. Please try again.'})
    except Exception as exc:
        logger.exception("Unhandled error in NL query handler")
        return _response(500, {'error': 'Internal server error'})


def _extract_user_from_context(event):
    """Extract user identity from API Gateway request context."""
    request_context = event.get('requestContext', {})
    authorizer = request_context.get('authorizer', {})
    return (
        authorizer.get('principalId')
        or authorizer.get('claims', {}).get('sub')
    )


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
