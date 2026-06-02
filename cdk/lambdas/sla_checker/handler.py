"""
SLA Checker Lambda — triggered daily by EventBridge.

For each in_progress batch:
  1. Look up the contract's elementSlas
  2. Compare each unreceived element's deadline (manufacturingDate + maxDaysAfterBatch)
  3. If overdue, set overdue=True on the element and persist
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta

import boto3
from boto3.dynamodb.conditions import Attr

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

BATCH_TABLE = os.environ.get('BATCH_TABLE_NAME', 'batches')
CONTRACT_TABLE = os.environ.get('CONTRACT_TABLE_NAME', 'data-contracts')


def handler(event, context):
    ddb = boto3.resource('dynamodb')
    batch_table = ddb.Table(BATCH_TABLE)
    contract_table = ddb.Table(CONTRACT_TABLE)

    # Scan for in-progress batches only
    result = batch_table.scan(FilterExpression=Attr('status').eq('in_progress'))
    batches = result.get('Items', [])
    logger.info('Found %d in-progress batches to check', len(batches))

    # Cache contracts
    contract_cache = {}
    now = datetime.now(timezone.utc)
    flagged = 0

    for batch in batches:
        contract_id = batch.get('contractId')
        if not contract_id:
            continue

        # Load contract (cached)
        if contract_id not in contract_cache:
            cr = contract_table.get_item(Key={'contractId': contract_id})
            contract_cache[contract_id] = cr.get('Item')
        contract = contract_cache[contract_id]
        if not contract:
            continue

        # Build SLA lookup: elementType -> maxDaysAfterBatch
        sla_map = {}
        for sla in contract.get('elementSlas', []):
            sla_map[sla['elementType']] = int(sla['maxDaysAfterBatch'])

        if not sla_map:
            continue

        mfg_date_str = batch.get('manufacturingDate', '')
        try:
            mfg_date = datetime.strptime(mfg_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        changed = False
        elements = batch.get('dataElements', [])
        for el in elements:
            if el.get('received'):
                continue
            max_days = sla_map.get(el['elementType'])
            if max_days is None:
                continue
            deadline = mfg_date + timedelta(days=max_days)
            if now > deadline and not el.get('overdue'):
                el['overdue'] = True
                changed = True
                flagged += 1

        if changed:
            batch['dataElements'] = elements
            batch['updatedAt'] = now.isoformat()
            batch_table.put_item(Item=batch)

    logger.info('Flagged %d overdue elements across %d batches', flagged, len(batches))
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        },
        'body': json.dumps({'checked': len(batches), 'flagged': flagged}),
    }
