"""
AI Unstructured Data Processor Lambda — Stage 1.

Triggered by S3 events on incoming/ prefix for AI connections.
- PDF files → Textract async (StartDocumentAnalysis) — handles multi-page PDFs
- Image files → Rekognition sync (DetectLabels + DetectText)
- PDF jobs: saves job metadata to S3 and waits for SNS completion notification
- Image results: saved immediately as JSON to Bronze layer
"""
import json
import logging
import os
import urllib.parse
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

CONFIDENCE_THRESHOLD = float(os.environ.get('CONFIDENCE_THRESHOLD', '85'))
DATA_LAKE_BUCKET = os.environ.get('DATA_LAKE_BUCKET', '')
TEXTRACT_SNS_TOPIC_ARN = os.environ.get('TEXTRACT_SNS_TOPIC_ARN', '')
TEXTRACT_ROLE_ARN = os.environ.get('TEXTRACT_ROLE_ARN', '')

s3 = boto3.client('s3')
textract = boto3.client('textract')
rekognition = boto3.client('rekognition')

PDF_EXTS = {'.pdf'}
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.tiff'}


def handler(event, context):
    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'])
        logger.info('Processing s3://%s/%s', bucket, key)

        if '/incoming/' not in key:
            continue

        ext = '.' + key.rsplit('.', 1)[-1].lower() if '.' in key else ''
        if ext not in PDF_EXTS and ext not in IMAGE_EXTS:
            logger.info('Skipping unsupported extension: %s', ext)
            continue

        try:
            if ext in PDF_EXTS:
                _start_pdf_async(bucket, key)
            else:
                result = _process_image(bucket, key)
                _save_result(bucket, key, result)
                s3.delete_object(Bucket=bucket, Key=key)
                logger.info('Image processed and moved: %s', key)
        except Exception:
            logger.exception('Failed to process %s', key)


def _start_pdf_async(bucket, key):
    """Start async Textract job for PDF (supports multi-page)."""
    # Save job metadata first so result processor can look it up by job ID
    # (JobTag is limited to 64 chars — can't embed full S3 path)
    # We'll use a well-known prefix: pending-textract/{jobId}.json
    # But we don't have the job ID yet, so we use a temp key based on the file path
    temp_meta_key = key.replace('/incoming/', '/pending-textract/')

    # Read S3 object metadata to get lotNumber stored by the upload handler
    obj_meta = {}
    try:
        head = s3.head_object(Bucket=bucket, Key=key)
        obj_meta = head.get('Metadata', {})
    except Exception:
        logger.warning('Could not read S3 metadata for %s', key)

    resp = textract.start_document_analysis(
        DocumentLocation={'S3Object': {'Bucket': bucket, 'Name': key}},
        FeatureTypes=['TABLES', 'FORMS'],
        NotificationChannel={
            'SNSTopicArn': TEXTRACT_SNS_TOPIC_ARN,
            'RoleArn': TEXTRACT_ROLE_ARN,
        },
    )
    job_id = resp['JobId']
    logger.info('Started Textract job %s for %s', job_id, key)

    # Save metadata keyed by job ID so result processor can find the original file + lot number
    meta_key = f'pending-textract/{job_id}.json'
    s3.put_object(
        Bucket=bucket,
        Key=meta_key,
        Body=json.dumps({
            'jobId': job_id, 'bucket': bucket, 'originalKey': key,
            'lotNumber': obj_meta.get('lot-number', ''),
            'batchId': obj_meta.get('batch-id', ''),
            'elementType': obj_meta.get('element-type', ''),
            'startedAt': datetime.now(timezone.utc).isoformat(),
        }),
        ContentType='application/json',
    )


def _process_image(bucket, key):
    """Detect labels and text in images using Rekognition."""
    s3_obj = {'S3Object': {'Bucket': bucket, 'Name': key}}

    labels_resp = rekognition.detect_labels(Image=s3_obj, MaxLabels=20, MinConfidence=50)
    labels = [{'name': l['Name'], 'confidence': round(l['Confidence'], 2)}
              for l in labels_resp.get('Labels', [])]

    text_resp = rekognition.detect_text(Image=s3_obj)
    text_detections = [{'text': t['DetectedText'], 'confidence': round(t['Confidence'], 2), 'type': t['Type']}
                       for t in text_resp.get('TextDetections', []) if t['Type'] == 'LINE']

    all_conf = [l['confidence'] for l in labels] + [t['confidence'] for t in text_detections]
    avg_confidence = sum(all_conf) / len(all_conf) if all_conf else 0

    return {
        'sourceFile': key.split('/')[-1],
        'fileType': 'image',
        'processor': 'rekognition',
        'confidence': round(avg_confidence, 2),
        'labels': labels,
        'textDetections': text_detections,
        'processedAt': datetime.now(timezone.utc).isoformat(),
    }


def _save_result(bucket, key, result):
    """Save extracted JSON to Bronze layer or manual-review based on confidence."""
    parts = key.split('/')
    incoming_idx = parts.index('incoming')
    base_path = '/'.join(parts[:incoming_idx])
    filename = parts[-1].rsplit('.', 1)[0] + '.json'

    now = datetime.now(timezone.utc)
    confidence = result.get('confidence', 0)

    if confidence >= CONFIDENCE_THRESHOLD:
        dest_key = f'{base_path}/year={now.year}/month={now.month:02d}/day={now.day:02d}/{filename}'
    else:
        dest_key = f'{base_path}/manual-review/{filename}'

    result['destinationKey'] = dest_key
    result['confidenceThreshold'] = CONFIDENCE_THRESHOLD
    result['passedThreshold'] = confidence >= CONFIDENCE_THRESHOLD

    s3.put_object(
        Bucket=bucket,
        Key=dest_key,
        Body=json.dumps(result, indent=2, default=str),
        ContentType='application/json',
    )
    logger.info('Saved result to s3://%s/%s (confidence: %.1f%%)', bucket, dest_key, confidence)
