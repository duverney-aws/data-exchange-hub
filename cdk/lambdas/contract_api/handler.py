"""
Lambda handler for Contract API Gateway integration.

Routes:
    POST   /api/cmo/register                   - [merck-admin] Register a new CMO
    POST   /api/contract                       - [merck-admin] Create a new data contract
    GET    /api/contract                       - [both] List contracts
    GET    /api/contract/{contractId}           - [both] Get contract details
    PUT    /api/contract/{contractId}           - [merck-admin] Update a data contract
    POST   /api/contract/{contractId}/submit    - [merck-admin] Submit contract to CMO for review
    POST   /api/contract/{contractId}/accept    - [cmo-user]    CMO accepts contract
    POST   /api/contract/{contractId}/approve   - [merck-admin] Merck final approval -> active
    POST   /api/contract/{contractId}/reject    - [both]        Reject contract
    POST   /api/contract/{contractId}/activate  - [merck-admin] Legacy direct activate
    GET    /api/contract/{contractId}/status    - [both] Get pipeline status
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.contract_service import (
    ContractService,
    ContractNotFoundError,
    ContractServiceError,
)

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

_service = ContractService(table_name=os.environ.get('TABLE_NAME', 'data-contracts'))
_cmo_table_name = os.environ.get('CMO_TABLE_NAME', 'cmo-profiles')


def handler(event, context):
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')

    try:
        if http_method == 'POST' and path.endswith('/submit'):
            return _require_role(event, 'merck-admins', _handle_submit)
        elif http_method == 'POST' and path.endswith('/accept'):
            return _require_role(event, 'cmo-users', _handle_accept)
        elif http_method == 'POST' and path.endswith('/approve'):
            return _require_role(event, 'merck-admins', _handle_approve)
        elif http_method == 'POST' and path.endswith('/reject'):
            return _handle_reject(event)  # both roles
        elif http_method == 'POST' and path.endswith('/activate'):
            return _require_role(event, 'merck-admins', _handle_activate)
        elif http_method == 'GET' and path.endswith('/status'):
            return _handle_pipeline_status(event)
        elif http_method == 'POST' and '/cmo/register' in path:
            return _require_role(event, 'merck-admins', _handle_cmo_register)
        elif http_method == 'POST' and '/cmo/' in path and '/invite' in path:
            return _require_role(event, 'merck-admins', _handle_cmo_invite)
        elif http_method == 'PUT' and '/cmo/' in path and 'contract' not in path:
            return _require_role(event, 'merck-admins', _handle_cmo_update)
        elif http_method == 'DELETE' and '/cmo/' in path and 'contract' not in path:
            return _require_role(event, 'merck-admins', _handle_cmo_deactivate)
        elif http_method == 'GET' and '/cmo' in path and 'contract' not in path:
            return _handle_list_cmos(event)
        elif http_method == 'POST':
            return _require_role(event, 'merck-admins', _handle_create)
        elif http_method == 'PUT':
            return _require_role(event, 'merck-admins', _handle_update)
        elif http_method == 'GET':
            path_params = event.get('pathParameters') or {}
            if path_params.get('contractId'):
                return _handle_get(event)
            return _handle_list(event)
        else:
            return _response(405, {'error': f'Method {http_method} not allowed'})
    except Exception:
        logger.exception("Unhandled error")
        return _response(500, {'error': 'Internal server error'})


# ------------------------------------------------------------------
# Role enforcement
# ------------------------------------------------------------------

def _get_user_info(event):
    """Extract user identity and groups from Cognito JWT claims."""
    ctx = event.get('requestContext', {})
    claims = ctx.get('authorizer', {}).get('claims', {})
    user_id = claims.get('sub') or claims.get('cognito:username', 'unknown')
    groups_str = claims.get('cognito:groups', '')
    groups = groups_str.split(',') if isinstance(groups_str, str) and groups_str else []
    email = claims.get('email', user_id)
    cmo_id = claims.get('custom:organization')  # set when CMO user is linked to a CMO org
    return user_id, groups, email, cmo_id


def _require_role(event, required_group, fn):
    """Call fn(event) only if the caller belongs to required_group."""
    user_id, groups, email, cmo_id = _get_user_info(event)
    if required_group not in groups:
        return _response(403, {'error': f'Access denied. Required role: {required_group}'})
    return fn(event)


# ------------------------------------------------------------------
# Route handlers
# ------------------------------------------------------------------

def _handle_cmo_register(event):
    import uuid
    import boto3

    body = _parse_body(event)
    if body is None:
        return _response(400, {'error': 'Request body must be valid JSON'})

    required = ['organizationName', 'contactEmail', 'contactPhone', 'address']
    missing = [f for f in required if not body.get(f)]
    if missing:
        return _response(400, {'error': f'Missing required fields: {", ".join(missing)}'})

    _, _, creator_email, _ = _get_user_info(event)
    cmo_id = f"cmo-{uuid.uuid4().hex[:8]}"
    now = _now()
    item = {
        'cmoId': cmo_id,
        'organizationName': body['organizationName'],
        'contactEmail': body['contactEmail'],
        'contactPhone': body['contactPhone'],
        'address': body['address'],
        'gxpCertified': body.get('gxpCertified', False),
        'createdAt': now,
        'createdBy': creator_email,
        'status': 'active',
        'inviteToken': uuid.uuid4().hex,
    }

    try:
        boto3.resource('dynamodb').Table(_cmo_table_name).put_item(Item=item)


        return _response(201, item)
    except Exception:
        logger.exception('CMO registration failed')
        return _response(500, {'error': 'CMO registration failed'})


def _link_cognito_user_to_cmo(email: str, cmo_id: str):
    """Set custom:organization on the Cognito user matching the given email."""
    import boto3
    user_pool_id = os.environ.get('USER_POOL_ID', '')
    if not user_pool_id:
        return
    try:
        client = boto3.client('cognito-idp')
        # Find user by email
        resp = client.list_users(
            UserPoolId=user_pool_id,
            Filter=f'email = "{email}"',
            Limit=1,
        )
        users = resp.get('Users', [])
        if not users:
            logger.info('No Cognito user found for email %s — skipping org link', email)
            return
        username = users[0]['Username']
        client.admin_update_user_attributes(
            UserPoolId=user_pool_id,
            Username=username,
            UserAttributes=[{'Name': 'custom:organization', 'Value': cmo_id}],
        )
        logger.info('Linked Cognito user %s to cmoId %s', username, cmo_id)
    except Exception as exc:
        logger.warning('Could not link Cognito user to CMO: %s', exc)


def _handle_cmo_invite(event):
    """POST /api/cmo/{cmoId}/invite - create Cognito user and link to CMO org."""
    import boto3
    path_params = event.get('pathParameters') or {}
    cmo_id = path_params.get('cmoId')
    if not cmo_id:
        return _response(400, {'error': 'Missing cmoId'})

    body = _parse_body(event) or {}
    email = body.get('email', '').strip()
    first_name = body.get('firstName', 'CMO').strip()
    last_name = body.get('lastName', 'User').strip()

    if not email:
        return _response(400, {'error': 'email is required'})

    user_pool_id = os.environ.get('USER_POOL_ID', '')
    if not user_pool_id:
        return _response(500, {'error': 'USER_POOL_ID not configured'})

    try:
        client = boto3.client('cognito-idp')

        # Check if user already exists
        existing = client.list_users(
            UserPoolId=user_pool_id,
            Filter=f'email = "{email}"',
            Limit=1,
        ).get('Users', [])

        if existing:
            username = existing[0]['Username']
            # Update org attribute if already exists
            client.admin_update_user_attributes(
                UserPoolId=user_pool_id,
                Username=username,
                UserAttributes=[{'Name': 'custom:organization', 'Value': cmo_id}],
            )
        else:
            # Create new Cognito user (Cognito sends temp password email)
            resp = client.admin_create_user(
                UserPoolId=user_pool_id,
                Username=email,
                UserAttributes=[
                    {'Name': 'email', 'Value': email},
                    {'Name': 'email_verified', 'Value': 'true'},
                    {'Name': 'given_name', 'Value': first_name},
                    {'Name': 'family_name', 'Value': last_name},
                    {'Name': 'custom:organization', 'Value': cmo_id},
                ],
                DesiredDeliveryMediums=['EMAIL'],
            )
            username = resp['User']['Username']

        # Add to cmo-users group
        client.admin_add_user_to_group(
            UserPoolId=user_pool_id,
            Username=username,
            GroupName='cmo-users',
        )

        return _response(200, {
            'message': f'Invitation sent to {email}',
            'cmoId': cmo_id,
            'email': email,
        })
    except client.exceptions.UsernameExistsException:
        return _response(409, {'error': f'User {email} already exists'})
    except Exception as exc:
        logger.exception('CMO invite failed')
        return _response(500, {'error': f'Invite failed: {exc}'})


def _handle_list_cmos(event):
    """Handle GET /api/cmo - list all registered CMOs."""
    import boto3
    try:
        result = boto3.resource('dynamodb').Table(_cmo_table_name).scan()
        cmos = result.get('Items', [])
        return _response(200, {'cmos': cmos})
    except Exception:
        logger.exception('CMO list failed')
        return _response(500, {'error': 'Failed to list CMOs'})


def _handle_cmo_update(event):
    """PUT /api/cmo/{cmoId} - update CMO profile fields."""
    path_params = event.get('pathParameters') or {}
    cmo_id = path_params.get('cmoId')
    if not cmo_id:
        return _response(400, {'error': 'Missing cmoId'})
    body = json.loads(event.get('body') or '{}')
    allowed = {'organizationName', 'contactEmail', 'contactPhone', 'address', 'gxpCertified'}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        return _response(400, {'error': 'No updatable fields provided'})
    updates['updatedAt'] = datetime.utcnow().isoformat()
    expr = 'SET ' + ', '.join(f'#{k} = :{k}' for k in updates)
    names = {f'#{k}': k for k in updates}
    values = {f':{k}': v for k, v in updates.items()}
    try:
        boto3.resource('dynamodb').Table(_cmo_table_name).update_item(
            Key={'cmoId': cmo_id},
            UpdateExpression=expr,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )
        return _response(200, {'cmoId': cmo_id, 'updated': list(updates.keys())})
    except Exception:
        logger.exception('CMO update failed')
        return _response(500, {'error': 'CMO update failed'})


def _handle_cmo_deactivate(event):
    """DELETE /api/cmo/{cmoId} - soft delete (set status=inactive)."""
    path_params = event.get('pathParameters') or {}
    cmo_id = path_params.get('cmoId')
    if not cmo_id:
        return _response(400, {'error': 'Missing cmoId'})
    try:
        boto3.resource('dynamodb').Table(_cmo_table_name).update_item(
            Key={'cmoId': cmo_id},
            UpdateExpression='SET #s = :s, updatedAt = :u',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={':s': 'inactive', ':u': datetime.utcnow().isoformat()},
        )
        return _response(200, {'cmoId': cmo_id, 'status': 'inactive'})
    except Exception:
        logger.exception('CMO deactivate failed')
        return _response(500, {'error': 'CMO deactivate failed'})


def _handle_list(event):
    query_params = event.get('queryStringParameters') or {}
    _, groups, _, jwt_cmo_id = _get_user_info(event)

    # CMO users: always filter by their JWT org claim — ignore client-supplied ?cmoId=
    if 'cmo-users' in groups and 'merck-admins' not in groups:
        if not jwt_cmo_id:
            return _response(403, {'error': 'No organization linked to your account. Contact your Merck administrator.'})
        cmo_id = jwt_cmo_id
    else:
        cmo_id = query_params.get('cmoId')

    try:
        if cmo_id:
            contract_objs = _service.query_contracts_by_cmo(cmo_id)
            contracts = [c.to_dynamodb_item() if hasattr(c, 'to_dynamodb_item') else c for c in contract_objs]
        else:
            import boto3
            result = boto3.resource('dynamodb').Table(
                os.environ.get('TABLE_NAME', 'data-contracts')
            ).scan()
            contracts = result.get('Items', [])

        return _response(200, {'contracts': contracts})
    except ContractServiceError as exc:
        return _response(500, {'error': str(exc)})


def _handle_create(event):
    body = _parse_body(event)
    if body is None:
        return _response(400, {'error': 'Request body must be valid JSON'})
    try:
        contract = _service.create_contract(body)
        return _response(201, contract.to_dynamodb_item())
    except ContractServiceError as exc:
        return _response(400, {'error': str(exc)})


def _handle_get(event):
    contract_id = (event.get('pathParameters') or {}).get('contractId')
    if not contract_id:
        return _response(400, {'error': 'Missing contractId'})
    try:
        contract = _service.get_contract(contract_id)
        return _response(200, contract.to_dynamodb_item())
    except ContractNotFoundError as exc:
        return _response(404, {'error': str(exc)})
    except ContractServiceError:
        return _response(500, {'error': 'Contract retrieval failed'})


def _handle_update(event):
    contract_id = (event.get('pathParameters') or {}).get('contractId')
    if not contract_id:
        return _response(400, {'error': 'Missing contractId'})
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


def _handle_submit(event):
    """Merck submits draft contract to CMO for review."""
    contract_id = (event.get('pathParameters') or {}).get('contractId')
    if not contract_id:
        return _response(400, {'error': 'Missing contractId'})
    _, _, email, _ = _get_user_info(event)
    try:
        contract = _service.get_contract(contract_id)
        if contract.status != 'draft':
            return _response(400, {'error': f'Contract must be in draft status to submit (current: {contract.status})'})
        return _update_contract_fields(contract_id, {
            '#s': 'pending_cmo_review', 'submitted_by': email, 'submitted_at': _now(),
        })
    except ContractNotFoundError as exc:
        return _response(404, {'error': str(exc)})
    except ContractServiceError as exc:
        return _response(400, {'error': str(exc)})


def _handle_accept(event):
    """CMO accepts contract, sends back to Merck for final approval."""
    contract_id = (event.get('pathParameters') or {}).get('contractId')
    if not contract_id:
        return _response(400, {'error': 'Missing contractId'})
    _, _, email, _ = _get_user_info(event)
    try:
        contract = _service.get_contract(contract_id)
        if contract.status != 'pending_cmo_review':
            return _response(400, {'error': f'Contract must be pending CMO review (current: {contract.status})'})
        return _update_contract_fields(contract_id, {
            '#s': 'pending_merck_approval', 'accepted_by': email, 'accepted_at': _now(),
        })
    except ContractNotFoundError as exc:
        return _response(404, {'error': str(exc)})
    except ContractServiceError as exc:
        return _response(400, {'error': str(exc)})


def _handle_approve(event):
    """Merck final approval — activates the contract."""
    contract_id = (event.get('pathParameters') or {}).get('contractId')
    if not contract_id:
        return _response(400, {'error': 'Missing contractId'})
    _, _, email, _ = _get_user_info(event)
    try:
        contract = _service.get_contract(contract_id)
        if contract.status != 'pending_merck_approval':
            return _response(400, {'error': f'Contract must be pending Merck approval (current: {contract.status})'})
        return _update_contract_fields(contract_id, {
            '#s': 'active', 'approved_by': email, 'approved_at': _now(),
        })
    except ContractNotFoundError as exc:
        return _response(404, {'error': str(exc)})
    except ContractServiceError as exc:
        return _response(400, {'error': str(exc)})


def _handle_reject(event):
    """Either party rejects the contract."""
    contract_id = (event.get('pathParameters') or {}).get('contractId')
    if not contract_id:
        return _response(400, {'error': 'Missing contractId'})
    _, _, email, _ = _get_user_info(event)
    body = _parse_body(event) or {}
    reason = body.get('reason', '')
    try:
        contract = _service.get_contract(contract_id)
        if contract.status not in ('pending_cmo_review', 'pending_merck_approval'):
            return _response(400, {'error': f'Cannot reject contract in status: {contract.status}'})
        return _update_contract_fields(contract_id, {
            '#s': 'rejected', 'rejected_by': email, 'rejected_at': _now(), 'rejection_reason': reason,
        })
    except ContractNotFoundError as exc:
        return _response(404, {'error': str(exc)})
    except ContractServiceError as exc:
        return _response(400, {'error': str(exc)})


def _handle_activate(event):
    """Activate contract pipeline — provisions integration resources."""
    contract_id = (event.get('pathParameters') or {}).get('contractId')
    if not contract_id:
        return _response(400, {'error': 'Missing contractId'})
    body = _parse_body(event) or {}
    pattern = body.get('integrationPattern', '')
    config = body.get('config', {})
    try:
        contract = _service.get_contract(contract_id)
        result = {'contractId': contract_id, 'status': 'active'}

        if pattern == 'secure-transfer':
            sftp_result = _provision_sftp_user(contract, contract_id)
            result['sftpCredentials'] = sftp_result
            config = sftp_result

        # Save pattern + config and set status to active
        _update_contract_fields(contract_id, {
            '#s': 'active',
            'integrationPattern': pattern or contract.integration_pattern or '',
            'integrationConfig': config,
        })
        return _response(200, result)
    except ContractNotFoundError as exc:
        return _response(404, {'error': str(exc)})
    except Exception as exc:
        logger.exception('Activate failed')
        return _response(500, {'error': str(exc)})


def _provision_sftp_user(contract, contract_id):
    """Store SFTP credentials in Secrets Manager for the custom identity provider."""
    import boto3, secrets, string
    sm_client = boto3.client('secretsmanager')

    server_id = os.environ.get('SFTP_SERVER_ID', '')
    cmo_id = contract.cmo_id
    domain = contract.data_domain

    username = f"{cmo_id}-{domain}"[:100]
    alphabet = string.ascii_letters + string.digits
    password = ''.join(secrets.choice(alphabet) for _ in range(24))
    hostname = f"{server_id}.server.transfer.us-east-1.amazonaws.com"

    # Store in Secrets Manager — the auth Lambda reads this on each SFTP login
    secret_name = f"cmo/{cmo_id}/sftp-{domain}"
    creds = {'username': username, 'password': password, 'hostname': hostname}
    try:
        sm_client.create_secret(Name=secret_name, SecretString=json.dumps(creds))
    except sm_client.exceptions.ResourceExistsException:
        sm_client.put_secret_value(SecretId=secret_name, SecretString=json.dumps(creds))

    return {'hostname': hostname, 'username': username, 'password': password}


def _handle_pipeline_status(event):
    import boto3
    contract_id = (event.get('pathParameters') or {}).get('contractId')
    if not contract_id:
        return _response(400, {'error': 'Missing contractId'})
    try:
        contract = _service.get_contract(contract_id)
        item = contract.to_dynamodb_item()

        # Resolve connection
        connection = None
        connection_type = None
        conn_id = item.get('connectionId')
        if conn_id:
            conn_table = os.environ.get('CONNECTION_TABLE_NAME', 'connections')
            conn_item = boto3.resource('dynamodb').Table(conn_table).get_item(
                Key={'connectionId': conn_id}
            ).get('Item')
            if conn_item:
                connection = conn_item
                connection_type = conn_item.get('connectionType')

        execution_details = {}

        bucket = os.environ.get('DATA_LAKE_BUCKET', '')
        cmo_id = item.get('cmoId', '')
        data_domain = item.get('dataDomain', '')

        if connection_type == 'secure-transfer' and bucket:
            # Find most recent file in bronze/{cmoId}/{dataDomain}/year=*/month=*/day=*/
            s3 = boto3.client('s3')
            prefix = f'bronze/{cmo_id}/{data_domain}/'
            paginator = s3.get_paginator('list_objects_v2')
            latest_obj = None
            total_files = 0
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    # Skip incoming/ and non-data files
                    if '/incoming/' in key:
                        continue
                    total_files += 1
                    if latest_obj is None or obj['LastModified'] > latest_obj['LastModified']:
                        latest_obj = obj
            if latest_obj:
                execution_details = {
                    'lastFileReceived': latest_obj['Key'].split('/')[-1],
                    'lastFileSize': latest_obj['Size'],
                    'lastReceivedAt': latest_obj['LastModified'].isoformat(),
                    'totalFilesReceived': total_files,
                    'bronzePath': f's3://{bucket}/{prefix}',
                }
            else:
                execution_details = {
                    'bronzePath': f's3://{bucket}/{prefix}',
                    'totalFilesReceived': 0,
                    'message': 'No files received yet',
                }

        elif connection_type == 'ai-unstructured' and bucket:
            s3 = boto3.client('s3')
            conn_name = (connection.get('config') or {}).get('uploadPrefix', '').strip('/').split('/')[-1] if connection else data_domain
            prefix = f'bronze/{cmo_id}/{conn_name}/'
            paginator = s3.get_paginator('list_objects_v2')
            latest_obj = None
            total_processed = 0
            manual_review_count = 0
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    if not key.endswith('.json'):
                        continue
                    if '/manual-review/' in key:
                        manual_review_count += 1
                    elif '/year=' in key:
                        total_processed += 1
                        if latest_obj is None or obj['LastModified'] > latest_obj['LastModified']:
                            latest_obj = obj
            execution_details = {
                'totalDocumentsProcessed': total_processed,
                'manualReviewPending': manual_review_count,
                'bronzePath': f's3://{bucket}/{prefix}',
            }
            if latest_obj:
                execution_details['lastProcessedAt'] = latest_obj['LastModified'].isoformat()
                execution_details['lastDocument'] = latest_obj['Key'].split('/')[-1]

        elif connection_type == 'native-connector' and connection:
            glue_conn_name = (connection.get('config') or {}).get('glueConnectionName')
            if glue_conn_name:
                glue = boto3.client('glue')
                # Look for a Glue job associated with this connection
                job_name = f'{cmo_id}-{data_domain}-etl'
                try:
                    runs_resp = glue.get_job_runs(JobName=job_name, MaxResults=1)
                    runs = runs_resp.get('JobRuns', [])
                    if runs:
                        run = runs[0]
                        execution_details = {
                            'glueJobName': job_name,
                            'glueConnectionName': glue_conn_name,
                            'lastRunStatus': run.get('JobRunState'),
                            'lastRunStartedAt': run.get('StartedOn', '').isoformat() if hasattr(run.get('StartedOn', ''), 'isoformat') else str(run.get('StartedOn', '')),
                            'lastRunDuration': run.get('ExecutionTime'),
                            'rowsExtracted': run.get('Statistics', {}).get('RowsInserted'),
                        }
                    else:
                        execution_details = {
                            'glueConnectionName': glue_conn_name,
                            'glueJobName': job_name,
                            'message': 'Glue connection active. No ETL job runs yet.',
                        }
                except glue.exceptions.EntityNotFoundException:
                    execution_details = {
                        'glueConnectionName': glue_conn_name,
                        'message': 'Glue connection active. ETL job not yet configured.',
                    }
            else:
                execution_details = {'message': 'Connection pending activation.'}

        return _response(200, {
            'contractId': contract_id,
            'status': item.get('status', 'draft'),
            'connectionType': connection_type,
            'connectionName': connection.get('name') if connection else None,
            'lastExecution': item.get('updatedAt'),
            'executionDetails': execution_details,
        })
    except ContractNotFoundError as exc:
        return _response(404, {'error': str(exc)})
    except Exception as exc:
        logger.exception('Pipeline status error')
        return _response(500, {'error': str(exc)})


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _now():
    return datetime.now(timezone.utc).isoformat()


def _update_contract_fields(contract_id, fields):
    """Direct DynamoDB update for workflow fields (status, submitted_by, etc.)."""
    import boto3
    table = boto3.resource('dynamodb').Table(os.environ.get('TABLE_NAME', 'data-contracts'))
    # '#s' key means status value; other keys are attribute names
    expr_parts = ['#s = :status', 'updatedAt = :ts']
    attr_names = {'#s': 'status'}
    attr_values = {':status': fields.pop('#s'), ':ts': _now()}
    for i, (k, v) in enumerate(fields.items()):
        placeholder = f':v{i}'
        expr_parts.append(f'{k} = {placeholder}')
        attr_values[placeholder] = v
    table.update_item(
        Key={'contractId': contract_id},
        UpdateExpression='SET ' + ', '.join(expr_parts),
        ExpressionAttributeNames=attr_names,
        ExpressionAttributeValues=attr_values,
    )
    # Return the full updated item
    item = table.get_item(Key={'contractId': contract_id}).get('Item', {})
    return _response(200, item)


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
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        },
        'body': json.dumps(body, default=str),
    }
