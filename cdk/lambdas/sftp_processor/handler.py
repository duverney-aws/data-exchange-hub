"""
SFTP File Processor Lambda

Triggered by S3 ObjectCreated events on bronze/{cmoId}/{dataDomain}/incoming/.
Expected upload path: incoming/{batchId}/{elementType}/{filename}
Copies file to bronze/{cmoId}/{dataDomain}/batchId={batchId}/year=YYYY/month=MM/day=DD/{filename}
Writes s3Path back to the batch element in DynamoDB.
"""
import json
import logging
import os
import urllib.parse
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

s3 = boto3.client("s3")
BUCKET = os.environ.get("DATA_LAKE_BUCKET", "")
BATCHES_TABLE = os.environ.get("BATCHES_TABLE", "")
ALLOWED_EXTENSIONS = {".csv", ".json", ".parquet", ".pdf", ".png", ".jpg", ".jpeg", ".tiff"}


def handler(event, context):
    for record in event.get("Records", []):
        _process_record(record)
    return {"status": "ok", "processed": len(event.get("Records", []))}


def _process_record(record):
    bucket = record["s3"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

    logger.info("Processing %s/%s", bucket, key)

    ext = _extension(key)
    if ext not in ALLOWED_EXTENSIONS:
        logger.warning("Skipping unsupported extension: %s", key)
        return

    if "/incoming/" not in key:
        logger.info("Not in incoming/ path, skipping: %s", key)
        return

    # Parse path: bronze/{cmoId}/{dataDomain}/incoming/{batchId}/{elementType}/{filename}
    parts = key.split("/")
    try:
        incoming_idx = parts.index("incoming")
        cmo_id = parts[1]
        data_domain = parts[2]
        batch_id = parts[incoming_idx + 1]
        element_type = parts[incoming_idx + 2]
        filename = "/".join(parts[incoming_idx + 3:])
    except (ValueError, IndexError):
        logger.error("Cannot parse batchId/elementType from key: %s — expected incoming/{batchId}/{elementType}/{filename}", key)
        return

    # Look up lot number — use it in S3 path so the data lake partition matches the CMO's identifier
    lot_number = _get_lot_number(batch_id) or batch_id

    now = datetime.now(timezone.utc)
    dest_key = (
        f"bronze/{cmo_id}/{data_domain}/lot={lot_number}/"
        f"year={now:%Y}/month={now:%m}/day={now:%d}/{filename}"
    )

    s3.copy_object(
        Bucket=bucket,
        CopySource={"Bucket": bucket, "Key": key},
        Key=dest_key,
    )
    s3.delete_object(Bucket=bucket, Key=key)
    logger.info("Processed: %s → %s", key, dest_key)

    s3_path = f"s3://{bucket}/{dest_key}"
    _write_s3_path_to_batch(batch_id, element_type, s3_path)


def _get_lot_number(batch_id):
    """Look up the CMO lot number for a batch. Falls back to batchId if not found."""
    if not BATCHES_TABLE:
        return None
    try:
        result = boto3.resource("dynamodb").Table(BATCHES_TABLE).get_item(Key={"batchId": batch_id})
        return result.get("Item", {}).get("lotNumber")
    except Exception:
        logger.warning("Could not look up lotNumber for batch %s", batch_id)
        return None


def _write_s3_path_to_batch(batch_id, element_type, s3_path):
    if not BATCHES_TABLE:
        logger.warning("BATCHES_TABLE not set — skipping DynamoDB update")
        return
    try:
        table = boto3.resource("dynamodb").Table(BATCHES_TABLE)
        result = table.get_item(Key={"batchId": batch_id})
        item = result.get("Item")
        if not item:
            logger.warning("Batch %s not found in DynamoDB", batch_id)
            return

        now_iso = datetime.now(timezone.utc).isoformat()
        elements = item.get("dataElements", [])
        for el in elements:
            if el["elementType"] == element_type:
                el["received"] = True
                el["receivedAt"] = el.get("receivedAt") or now_iso
                el["s3Path"] = s3_path
                break

        missing = [e["elementType"] for e in elements if not e["received"]]
        item["dataElements"] = elements
        item["missingElements"] = missing
        item["isComplete"] = len(missing) == 0
        item["updatedAt"] = now_iso
        table.put_item(Item=item)
        logger.info("Updated batch %s element %s with s3Path %s", batch_id, element_type, s3_path)
    except Exception:
        logger.exception("Failed to update batch %s element %s", batch_id, element_type)


def _extension(key):
    dot = key.rfind(".")
    return key[dot:].lower() if dot != -1 else ""
