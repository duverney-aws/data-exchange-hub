"""
Textract Result Processor Lambda — Stage 2.

Triggered by SNS notification when Textract async job completes.
Collects all pages of results, builds structured JSON, saves to Bronze layer.
"""
import json
import logging
import os
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

CONFIDENCE_THRESHOLD = float(os.environ.get('CONFIDENCE_THRESHOLD', '85'))
BATCHES_TABLE = os.environ.get('BATCH_TABLE_NAME', 'batches')

s3 = boto3.client('s3')
textract = boto3.client('textract')
dynamodb = boto3.resource('dynamodb')


def handler(event, context):
    for record in event.get('Records', []):
        message = json.loads(record['Sns']['Message'])
        status = message.get('Status')
        job_id = message.get('JobId')
        logger.info('Textract job %s status: %s', job_id, status)

        if status != 'SUCCEEDED':
            logger.error('Textract job %s failed: %s', job_id, message.get('StatusMessage', ''))
            continue

        try:
            _process_completed_job(job_id, message)
        except Exception:
            logger.exception('Failed to process Textract job %s', job_id)


def _process_completed_job(job_id, message):
    """Collect all pages of Textract results and save to S3."""
    # Look up original file metadata from S3 (stored by ai_processor)
    # Bucket comes from the SNS message DocumentLocation
    doc_location = message.get('DocumentLocation', {})
    bucket = doc_location.get('S3Bucket', os.environ.get('DATA_LAKE_BUCKET', ''))

    meta_key = f'pending-textract/{job_id}.json'
    try:
        meta_obj = s3.get_object(Bucket=bucket, Key=meta_key)
        meta = json.loads(meta_obj['Body'].read())
        original_key = meta['originalKey']
    except Exception:
        logger.exception('Cannot find metadata for job %s at %s', job_id, meta_key)
        return

    # Collect all blocks across all pages
    all_blocks = []
    next_token = None
    while True:
        kwargs = {'JobId': job_id}
        if next_token:
            kwargs['NextToken'] = next_token
        resp = textract.get_document_analysis(**kwargs)
        all_blocks.extend(resp.get('Blocks', []))
        next_token = resp.get('NextToken')
        if not next_token:
            break

    logger.info('Collected %d blocks for job %s', len(all_blocks), job_id)

    # Extract text lines
    lines = [b['Text'] for b in all_blocks if b['BlockType'] == 'LINE']

    # Extract key-value pairs from forms
    key_map, value_map, block_map = {}, {}, {}
    for b in all_blocks:
        block_map[b['Id']] = b
        if b['BlockType'] == 'KEY_VALUE_SET':
            if 'KEY' in b.get('EntityTypes', []):
                key_map[b['Id']] = b
            else:
                value_map[b['Id']] = b

    forms = {}
    for kid, kb in key_map.items():
        k_text = _get_text(kb, block_map)
        v_text = ''
        for rel in kb.get('Relationships', []):
            if rel['Type'] == 'VALUE':
                for vid in rel['Ids']:
                    if vid in value_map:
                        v_text = _get_text(value_map[vid], block_map)
        if k_text:
            forms[k_text] = v_text

    # Extract tables
    tables = []
    for b in all_blocks:
        if b['BlockType'] == 'TABLE':
            table = _extract_table(b, block_map)
            if table:
                tables.append(table)

    # Average confidence
    confidences = [b['Confidence'] for b in all_blocks if 'Confidence' in b]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0

    result = {
        'sourceFile': original_key.split('/')[-1],
        'fileType': 'pdf',
        'processor': 'textract-async',
        'jobId': job_id,
        'confidence': round(avg_confidence, 2),
        'extractedText': lines,
        'forms': forms,
        'tables': tables,
        'blockCount': len(all_blocks),
        'processedAt': datetime.now(timezone.utc).isoformat(),
    }

    lot_number = meta.get('lotNumber', '')
    _save_result(bucket, original_key, result, lot_number=lot_number)

    # Clean up pending-textract metadata file
    try:
        s3.delete_object(Bucket=bucket, Key=meta_key)
    except Exception:
        logger.warning('Could not clean up pending-textract metadata', exc_info=True)

    # Delete original incoming file
    try:
        s3.delete_object(Bucket=bucket, Key=original_key)
        logger.info('Deleted original file: %s', original_key)
    except Exception:
        logger.warning('Could not delete original file %s', original_key, exc_info=True)


def _save_result(bucket, original_key, result, lot_number=''):
    """Save extracted JSON to Bronze layer or manual-review based on confidence.

    Uses lot={lotNumber} partition when available (CMO's own identifier).
    Falls back to batchId= if lotNumber not provided.
    """
    parts = original_key.split('/')
    incoming_idx = parts.index('incoming')
    base_path = '/'.join(parts[:incoming_idx])
    filename = parts[-1].rsplit('.', 1)[0] + '.json'

    # Extract batchId and elementType if present in path
    batch_id = None
    element_type = None
    remaining = parts[incoming_idx + 1:]
    if len(remaining) >= 3:
        batch_id = remaining[0]
        element_type = remaining[1]

    now = datetime.now(timezone.utc)
    confidence = result.get('confidence', 0)

    lot_label = lot_number or batch_id  # prefer CMO lot number; fall back to internal batchId
    if confidence >= CONFIDENCE_THRESHOLD:
        if lot_label:
            dest_key = f'{base_path}/lot={lot_label}/year={now.year}/month={now.month:02d}/day={now.day:02d}/{filename}'
        else:
            dest_key = f'{base_path}/year={now.year}/month={now.month:02d}/day={now.day:02d}/{filename}'
    else:
        dest_key = f'{base_path}/manual-review/{filename}'

    result['destinationKey'] = dest_key
    result['confidenceThreshold'] = CONFIDENCE_THRESHOLD
    result['passedThreshold'] = confidence >= CONFIDENCE_THRESHOLD
    if lot_number:
        result['lotNumber'] = lot_number
    if batch_id:
        result['batchId'] = batch_id
    if element_type:
        result['elementType'] = element_type

    s3.put_object(
        Bucket=bucket,
        Key=dest_key,
        Body=json.dumps(result, indent=2, default=str),
        ContentType='application/json',
    )
    logger.info('Saved result to s3://%s/%s (confidence: %.1f%%)', bucket, dest_key, confidence)

    # Update batch element with final Bronze s3Path
    if batch_id and element_type and BATCHES_TABLE:
        _write_s3_path_to_batch(batch_id, element_type, f's3://{bucket}/{dest_key}')

    return dest_key


def _write_s3_path_to_batch(batch_id, element_type, s3_path):
    """Overwrite batch element s3Path with the final processed Bronze path."""
    try:
        table = dynamodb.Table(BATCHES_TABLE)
        result = table.get_item(Key={'batchId': batch_id})
        item = result.get('Item')
        if not item:
            logger.warning('Batch %s not found — skipping s3Path update', batch_id)
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        elements = item.get('dataElements', [])
        for el in elements:
            if el['elementType'] == element_type:
                el['s3Path'] = s3_path
                if not el.get('received'):
                    el['received'] = True
                    el['receivedAt'] = now_iso
                break
        missing = [e['elementType'] for e in elements if not e['received']]
        item['dataElements'] = elements
        item['missingElements'] = missing
        item['isComplete'] = len(missing) == 0
        item['updatedAt'] = now_iso
        table.put_item(Item=item)
        logger.info('Updated batch %s element %s final s3Path=%s', batch_id, element_type, s3_path)
    except Exception:
        logger.exception('Failed to update batch %s element %s', batch_id, element_type)


def _get_text(block, block_map):
    text = ''
    for rel in block.get('Relationships', []):
        if rel['Type'] == 'CHILD':
            for cid in rel['Ids']:
                child = block_map.get(cid, {})
                if child.get('BlockType') == 'WORD':
                    text += child.get('Text', '') + ' '
    return text.strip()


def _extract_table(table_block, block_map):
    rows = {}
    for rel in table_block.get('Relationships', []):
        if rel['Type'] == 'CHILD':
            for cid in rel['Ids']:
                cell = block_map.get(cid, {})
                if cell.get('BlockType') == 'CELL':
                    r = cell.get('RowIndex', 0)
                    c = cell.get('ColumnIndex', 0)
                    rows.setdefault(r, {})[c] = _get_text(cell, block_map)
    if not rows:
        return None
    return [[rows[r].get(c, '') for c in sorted(rows[r])] for r in sorted(rows)]
