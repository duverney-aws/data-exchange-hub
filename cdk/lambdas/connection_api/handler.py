"""
Connection API Lambda handler.

Routes:
    POST  /api/connection                          - [merck-admins] Create connection
    GET   /api/connection                          - [both]         List connections (?cmoId=)
    GET   /api/connection/{connectionId}           - [both]         Get connection
    PUT   /api/connection/{connectionId}           - [merck-admins] Update connection
    POST  /api/connection/{connectionId}/activate  - [merck-admins] Activate (provision creds)
    DELETE /api/connection/{connectionId}          - [merck-admins] Deactivate
"""
import json
import logging
import os
import secrets
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

_TABLE = os.environ.get('CONNECTION_TABLE_NAME', 'connections')
_SFTP_SERVER_ID = os.environ.get('SFTP_SERVER_ID', '')
_DATA_LAKE_BUCKET = os.environ.get('DATA_LAKE_BUCKET', '')
_GLUE_SUBNET_ID = os.environ.get('GLUE_SUBNET_ID', '')
_GLUE_SECURITY_GROUP_ID = os.environ.get('GLUE_SECURITY_GROUP_ID', '')
_BATCH_TABLE = os.environ.get('BATCH_TABLE_NAME', 'batches')
_GLUE_ETL_ROLE_ARN = os.environ.get('GLUE_ETL_ROLE_ARN', '')
_GLUE_SCRIPT_S3_PATH = os.environ.get('GLUE_SCRIPT_S3_PATH', '')

VALID_TYPES = ('secure-transfer', 'native-connector', 'ai-unstructured')


def handler(event, context):
    method = event.get('httpMethod', '')
    path = event.get('resource', '')
    try:
        if method == 'POST' and '/upload' in path:
            return _handle_upload(event)
        if method == 'POST' and '/configure' in path:
            return _handle_configure(event)
        if method == 'POST' and '/activate' in path:
            return _require_role(event, 'merck-admins', _handle_activate)
        if method == 'POST':
            return _handle_create(event)  # CMO can create native-connector; Merck can create any type
        if method == 'GET':
            params = event.get('pathParameters') or {}
            if params.get('connectionId'):
                return _handle_get(event)
            return _handle_list(event)
        if method == 'PUT':
            return _require_role(event, 'merck-admins', _handle_update)
        if method == 'DELETE':
            return _require_role(event, 'merck-admins', _handle_deactivate)
        return _resp(405, {'error': 'Method not allowed'})
    except Exception:
        logger.exception('Unhandled error')
        return _resp(500, {'error': 'Internal server error'})


def _handle_create(event):
    body = _parse_body(event)
    if not body:
        return _resp(400, {'error': 'Request body required'})

    _, groups, jwt_cmo_id = _get_user_info(event)
    is_cmo = 'cmo-users' in groups and 'merck-admins' not in groups
    is_merck = 'merck-admins' in groups

    conn_type = body.get('connectionType', '')

    # CMO users can only create native-connector for their own org
    if is_cmo:
        if conn_type != 'native-connector':
            return _resp(403, {'error': 'CMO users can only create native-connector connections'})
        if not jwt_cmo_id:
            return _resp(403, {'error': 'No organization linked to your account'})
        body['cmoId'] = jwt_cmo_id  # always use JWT claim, ignore any client-supplied cmoId

    missing = [f for f in ('cmoId', 'connectionType', 'name') if not body.get(f)]
    if missing:
        return _resp(400, {'error': f'Missing: {", ".join(missing)}'})
    if conn_type not in VALID_TYPES:
        return _resp(400, {'error': f'Invalid type. Must be one of: {", ".join(VALID_TYPES)}'})

    now = _now()
    item = {
        'connectionId': f'conn-{uuid.uuid4().hex[:12]}',
        'cmoId': body['cmoId'],
        'connectionType': conn_type,
        'name': body['name'],
        'status': 'pending',
        'config': {},
        'createdAt': now,
        'updatedAt': now,
    }
    boto3.resource('dynamodb').Table(_TABLE).put_item(Item=item)

    # If CMO included JDBC details in the same request, auto-configure
    if is_cmo and all(body.get(f) for f in ('dbType', 'host', 'port', 'database', 'username', 'password', 'tableMappings')):
        fake_event = dict(event)
        fake_event['pathParameters'] = {'connectionId': item['connectionId']}
        result = _handle_configure(fake_event)
        if result['statusCode'] == 200:
            import json as _json
            return _resp(201, _json.loads(result['body']))

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
        result = table.query(IndexName='cmo-connections-index', KeyConditionExpression=Key('cmoId').eq(cmo_id))
    else:
        result = table.scan()
    return _resp(200, {'connections': result.get('Items', [])})


def _handle_get(event):
    cid = (event.get('pathParameters') or {}).get('connectionId')
    item = boto3.resource('dynamodb').Table(_TABLE).get_item(Key={'connectionId': cid}).get('Item')
    if not item:
        return _resp(404, {'error': 'Connection not found'})
    return _resp(200, item)


def _handle_update(event):
    cid = (event.get('pathParameters') or {}).get('connectionId')
    body = _parse_body(event)
    if not body:
        return _resp(400, {'error': 'Request body required'})
    table = boto3.resource('dynamodb').Table(_TABLE)
    item = table.get_item(Key={'connectionId': cid}).get('Item')
    if not item:
        return _resp(404, {'error': 'Connection not found'})
    for f in ('name', 'connectionType'):
        if f in body:
            item[f] = body[f]
    item['updatedAt'] = _now()
    table.put_item(Item=item)
    return _resp(200, item)


def _handle_configure(event):
    """CMO submits their JDBC connection details. Stores creds in Secrets Manager,
    sets status to pending_merck_review. Merck admin then one-click activates."""
    _, groups, jwt_cmo_id = _get_user_info(event)
    # Both CMO users and Merck admins can configure (Merck may do it on behalf of CMO)
    cid = (event.get('pathParameters') or {}).get('connectionId')
    table = boto3.resource('dynamodb').Table(_TABLE)
    item = table.get_item(Key={'connectionId': cid}).get('Item')
    if not item:
        return _resp(404, {'error': 'Connection not found'})
    if item['connectionType'] != 'native-connector':
        return _resp(400, {'error': 'configure only applies to native-connector type'})
    if item['status'] == 'active':
        return _resp(400, {'error': 'Connection is already active'})

    # CMO users can only configure their own org's connections
    if 'cmo-users' in groups and 'merck-admins' not in groups:
        if jwt_cmo_id and item['cmoId'] != jwt_cmo_id:
            return _resp(403, {'error': 'Access denied'})

    body = _parse_body(event) or {}
    required = ['dbType', 'host', 'port', 'database', 'username', 'password', 'tableMappings']
    missing = [f for f in required if not body.get(f)]
    if missing:
        return _resp(400, {'error': f'Missing: {", ".join(missing)}'})

    db_type = body['dbType']
    host = body['host']
    port = str(body['port'])
    database = body['database']
    username = body['username']
    password = body['password']
    # tableMappings: list of {sourceTable, dataDomain}
    table_mappings = body['tableMappings']
    if not isinstance(table_mappings, list) or not table_mappings:
        return _resp(400, {'error': 'tableMappings must be a non-empty list of {sourceTable, dataDomain}'})

    jdbc_urls = {
        'oracle':     f'jdbc:oracle:thin:@{host}:{port}:{database}',
        'sqlserver':  f'jdbc:sqlserver://{host}:{port};databaseName={database}',
        'postgresql': f'jdbc:postgresql://{host}:{port}/{database}',
        'mysql':      f'jdbc:mysql://{host}:{port}/{database}',
        'snowflake':  f'jdbc:snowflake://{host}/?db={database}',
        'sap':        f'jdbc:sap://{host}:{port}/?databaseName={database}',
    }
    jdbc_url = jdbc_urls.get(db_type, f'jdbc:{db_type}://{host}:{port}/{database}')

    safe_name = item['name'].lower().replace(' ', '-')
    secret_name = f'cmo/{item["cmoId"]}/jdbc-{safe_name}'

    sm = boto3.client('secretsmanager')
    secret_value = json.dumps({
        'username': username, 'password': password,
        'jdbcUrl': jdbc_url, 'dbType': db_type,
    })
    try:
        sm.create_secret(Name=secret_name, SecretString=secret_value)
    except sm.exceptions.ResourceExistsException:
        sm.put_secret_value(SecretId=secret_name, SecretString=secret_value)

    now = _now()
    connection_method = body.get('connectionMethod', 'direct')  # direct | nlb | privatelink
    private_link_service_name = body.get('privateLinkServiceName', '')

    # Store non-sensitive config on the item (no password)
    item['config'] = {
        'dbType': db_type,
        'host': host,
        'port': port,
        'database': database,
        'username': username,
        'jdbcUrl': jdbc_url,
        'secretName': secret_name,
        'connectionMethod': connection_method,
        'tableMappings': table_mappings,
    }
    if private_link_service_name:
        item['config']['privateLinkServiceName'] = private_link_service_name
    item['status'] = 'pending_merck_review'
    item['configuredAt'] = now
    item['updatedAt'] = now
    table.put_item(Item=item)

    # Return item without password (already excluded from config)
    return _resp(200, item)


def _handle_activate(event):
    cid = (event.get('pathParameters') or {}).get('connectionId')
    table = boto3.resource('dynamodb').Table(_TABLE)
    item = table.get_item(Key={'connectionId': cid}).get('Item')
    if not item:
        return _resp(404, {'error': 'Connection not found'})
    if item['status'] == 'active':
        return _resp(200, item)

    user_id, _, _ = _get_user_info(event)
    conn_type = item['connectionType']
    now = _now()

    if conn_type == 'secure-transfer':
        config = _provision_sftp(item['cmoId'], item['name'])
    elif conn_type == 'native-connector':
        if item['status'] != 'pending_merck_review':
            return _resp(400, {'error': 'Connection must be configured by CMO before activation. Status must be pending_merck_review.'})
        config = _provision_native_connector(item['cmoId'], item['name'], item.get('config', {}))
    elif conn_type == 'ai-unstructured':
        config = _provision_ai_unstructured(item['cmoId'], item['name'])
    else:
        return _resp(400, {'error': f'Unknown type: {conn_type}'})

    item['config'] = config
    item['status'] = 'active'
    item['activatedBy'] = user_id
    item['activatedAt'] = now
    item['updatedAt'] = now
    table.put_item(Item=item)
    return _resp(200, item)


def _handle_deactivate(event):
    cid = (event.get('pathParameters') or {}).get('connectionId')
    table = boto3.resource('dynamodb').Table(_TABLE)
    item = table.get_item(Key={'connectionId': cid}).get('Item')
    if not item:
        return _resp(404, {'error': 'Connection not found'})
    item['status'] = 'inactive'
    item['updatedAt'] = _now()
    table.put_item(Item=item)
    return _resp(200, item)


def _provision_sftp(cmo_id, name):
    """Provision SFTP credentials in Secrets Manager for Transfer Family auth."""
    safe_name = name.lower().replace(' ', '-')
    username = f'{cmo_id}-{safe_name}'
    password = secrets.token_urlsafe(24)
    secret_name = f'cmo/{cmo_id}/sftp-{safe_name}'

    sm = boto3.client('secretsmanager')
    secret_value = json.dumps({'username': username, 'password': password, 'cmoId': cmo_id})
    try:
        sm.create_secret(Name=secret_name, SecretString=secret_value)
    except sm.exceptions.ResourceExistsException:
        sm.put_secret_value(SecretId=secret_name, SecretString=secret_value)

    hostname = f'{_SFTP_SERVER_ID}.server.transfer.us-east-1.amazonaws.com' if _SFTP_SERVER_ID else 'sftp-not-configured'
    return {
        'hostname': hostname,
        'username': username,
        'password': password,
        'port': 22,
        'supportedFormats': ['csv', 'json', 'parquet'],
    }



def _provision_native_connector(cmo_id, name, existing_config):
    """Read JDBC credentials from Secrets Manager (stored by CMO via /configure),
    create the AWS Glue Connection, Glue ETL Job, and a daily Trigger."""
    secret_name = existing_config.get('secretName')
    if not secret_name:
        raise ValueError('No credentials found. CMO must configure the connection first.')

    sm = boto3.client('secretsmanager')
    secret = json.loads(sm.get_secret_value(SecretId=secret_name)['SecretString'])
    username = secret['username']
    password = secret['password']
    jdbc_url = secret['jdbcUrl']

    safe_name = name.lower().replace(' ', '-')
    glue_conn_name = f'{cmo_id}-{safe_name}'
    # data_domain derived from connection name (same slug used in S3 paths)
    data_domain = safe_name

    glue = boto3.client('glue')

    # 1. Glue Connection
    conn_input = {
        'Name': glue_conn_name,
        'Description': f'JDBC connection for CMO {cmo_id} — {name}',
        'ConnectionType': 'JDBC',
        'ConnectionProperties': {
            'JDBC_CONNECTION_URL': jdbc_url,
            'USERNAME': username,
            'PASSWORD': password,
        },
    }
    if _GLUE_SUBNET_ID and _GLUE_SECURITY_GROUP_ID:
        conn_input['PhysicalConnectionRequirements'] = {
            'SubnetId': _GLUE_SUBNET_ID,
            'SecurityGroupIdList': [_GLUE_SECURITY_GROUP_ID],
            'AvailabilityZone': 'us-east-1a',
        }
    try:
        glue.create_connection(ConnectionInput=conn_input)
    except glue.exceptions.AlreadyExistsException:
        glue.update_connection(Name=glue_conn_name, ConnectionInput=conn_input)

    # 2. Glue ETL Job (only if script path and role are configured)
    glue_job_name = None
    glue_trigger_name = None
    if _GLUE_SCRIPT_S3_PATH and _GLUE_ETL_ROLE_ARN:
        table_mappings = existing_config.get('tableMappings') or []
        # Fall back to single-table legacy config if no mappings stored
        if not table_mappings:
            db_table = existing_config.get('database', 'public')
            table_mappings = [{'sourceTable': db_table, 'dataDomain': data_domain}]

        created_jobs = []
        for mapping in table_mappings:
            source_table = mapping.get('sourceTable', '')
            domain = mapping.get('dataDomain', data_domain).lower().replace(' ', '-')
            t_job_name = f'{cmo_id}-{domain}-etl'
            t_trigger_name = f'{t_job_name}-trigger'
            job_args = {
                '--cmo_id': cmo_id,
                '--data_domain': domain,
                '--glue_conn_name': glue_conn_name,
                '--target_bucket': _DATA_LAKE_BUCKET,
                '--db_table': source_table,
                '--job-bookmark-option': 'job-bookmark-disable',
            }
            job_def = {
                'Name': t_job_name,
                'Description': f'JDBC → Bronze ETL for {cmo_id}/{domain} (table: {source_table})',
                'Role': _GLUE_ETL_ROLE_ARN,
                'Command': {
                    'Name': 'glueetl',
                    'ScriptLocation': _GLUE_SCRIPT_S3_PATH,
                    'PythonVersion': '3',
                },
                'DefaultArguments': job_args,
                'Connections': {'Connections': [glue_conn_name]},
                'GlueVersion': '4.0',
                'NumberOfWorkers': 2,
                'WorkerType': 'G.1X',
                'Timeout': 60,
            }
            try:
                glue.create_job(**job_def)
            except Exception:
                try:
                    update_def = {k: v for k, v in job_def.items() if k != 'Name'}
                    glue.update_job(JobName=t_job_name, JobUpdate=update_def)
                except Exception:
                    logger.exception('Failed to create/update Glue job %s', t_job_name)
                    continue

            try:
                glue.create_trigger(
                    Name=t_trigger_name,
                    Type='SCHEDULED',
                    Schedule='cron(0 2 * * ? *)',
                    Actions=[{'JobName': t_job_name, 'Arguments': job_args}],
                    StartOnCreation=True,
                )
            except Exception:
                logger.exception('Failed to create trigger %s', t_trigger_name)

            created_jobs.append({'jobName': t_job_name, 'triggerName': t_trigger_name, 'dataDomain': domain, 'sourceTable': source_table})

        glue_job_name = created_jobs[0]['jobName'] if created_jobs else None

    return {
        **existing_config,
        'glueConnectionName': glue_conn_name,
        **(({'glueJobs': created_jobs}) if glue_job_name else {}),
    }

def _provision_ai_unstructured(cmo_id, name):
    """Configure S3 prefix for AI unstructured uploads."""
    safe_name = name.lower().replace(' ', '-')
    prefix = f'bronze/{cmo_id}/{safe_name}/incoming/'
    return {
        'bucket': _DATA_LAKE_BUCKET,
        'uploadPrefix': prefix,
        'supportedFormats': ['pdf', 'png', 'jpg', 'jpeg', 'tiff'],
        'confidenceThreshold': 85,
    }


def _handle_upload(event):
    """Proxy file upload: receive file body and write directly to S3 with SSE-KMS.

    Query params:
      filename     - original filename
      batchId      - (required) batch this file belongs to
      elementType  - (required) data element type (coa, bmr, in_process, yield)
    """
    cid = (event.get('pathParameters') or {}).get('connectionId')
    table = boto3.resource('dynamodb').Table(_TABLE)
    item = table.get_item(Key={'connectionId': cid}).get('Item')
    if not item:
        return _resp(404, {'error': 'Connection not found'})
    if item['status'] != 'active' or item['connectionType'] != 'ai-unstructured':
        return _resp(400, {'error': 'Connection must be active ai-unstructured type'})

    qs = event.get('queryStringParameters') or {}
    filename = qs.get('filename', f'upload-{uuid.uuid4().hex[:8]}')
    batch_id = qs.get('batchId', '')
    lot_number = qs.get('lotNumber', '')
    element_type = qs.get('elementType', '')
    if not batch_id or not element_type or not lot_number:
        return _resp(400, {'error': 'batchId, lotNumber, and elementType query params are required'})

    config = item.get('config', {})
    bucket = config.get('bucket', _DATA_LAKE_BUCKET)
    cmo_id = item['cmoId']
    conn_name = item.get('name', cid).lower().replace(' ', '-')
    # incoming path carries batchId + elementType so processors can write back to DynamoDB
    # lotNumber is passed separately and used in the final dest path
    prefix = f'bronze/{cmo_id}/{conn_name}/incoming/{batch_id}/{element_type}/'
    key = f'{prefix}{filename}'

    body = event.get('body', '')
    if event.get('isBase64Encoded'):
        import base64
        file_bytes = base64.b64decode(body)
    else:
        file_bytes = body.encode('utf-8') if isinstance(body, str) else body
    file_bytes = _extract_multipart(file_bytes)

    s3_client = boto3.client('s3')
    s3_client.put_object(
        Bucket=bucket, Key=key, Body=file_bytes,
        Metadata={'lot-number': lot_number, 'batch-id': batch_id, 'element-type': element_type},
    )
    logger.info('Uploaded %s to s3://%s/%s', filename, bucket, key)

    # Write incoming s3Path to batch element immediately (Textract result processor will overwrite
    # with the final Bronze path once processing completes)
    _write_s3_path_to_batch(batch_id, element_type, f's3://{bucket}/{key}')

    return _resp(200, {'bucket': bucket, 'key': key, 'filename': filename, 'size': len(file_bytes)})


def _write_s3_path_to_batch(batch_id, element_type, s3_path):
    """Mark batch element received and record its S3 path."""
    try:
        table = boto3.resource('dynamodb').Table(_BATCH_TABLE)
        result = table.get_item(Key={'batchId': batch_id})
        item = result.get('Item')
        if not item:
            logger.warning('Batch %s not found — skipping s3Path update', batch_id)
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        elements = item.get('dataElements', [])
        for el in elements:
            if el['elementType'] == element_type:
                el['received'] = True
                el['receivedAt'] = el.get('receivedAt') or now_iso
                el['s3Path'] = s3_path
                break
        missing = [e['elementType'] for e in elements if not e['received']]
        item['dataElements'] = elements
        item['missingElements'] = missing
        item['isComplete'] = len(missing) == 0
        item['updatedAt'] = now_iso
        table.put_item(Item=item)
        logger.info('Updated batch %s element %s s3Path=%s', batch_id, element_type, s3_path)
    except Exception:
        logger.exception('Failed to update batch %s element %s', batch_id, element_type)



def _extract_multipart(raw_bytes):
    """Extract file content from multipart/form-data envelope."""
    try:
        text = raw_bytes.decode('utf-8', errors='replace')
    except Exception:
        return raw_bytes
    if not text.lstrip().startswith('------'):
        return raw_bytes
    sep = '\r\n\r\n' if '\r\n\r\n' in text else '\n\n'
    parts = text.split(sep, 1)
    if len(parts) < 2:
        return raw_bytes
    body = parts[1]
    result_lines = []
    for line in body.split('\n'):
        if line.strip().startswith('------'):
            break
        result_lines.append(line.rstrip('\r'))
    result = '\n'.join(result_lines).strip()
    return result.encode('utf-8') if result else raw_bytes

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
