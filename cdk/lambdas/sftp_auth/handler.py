"""
SFTP Custom Identity Provider Lambda

Called by AWS Transfer Family on each login attempt.
Looks up username/password in Secrets Manager and returns
the IAM role + home directory mapping if credentials match.
"""
import json
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

sm = boto3.client("secretsmanager")
ROLE_ARN = os.environ.get("TRANSFER_ROLE_ARN", "")
BUCKET = os.environ.get("DATA_LAKE_BUCKET", "")


def handler(event, context):
    username = event.get("username", "")
    password = event.get("password", "")
    server_id = event.get("serverId", "")

    logger.info("Auth request: user=%s server=%s", username, server_id)

    if not username or not password:
        return {}

    # Find the matching secret by listing cmo/*/sftp-* secrets
    creds, cmo_id, domain = _find_credentials(username)
    if not creds:
        logger.warning("No credentials found for user: %s", username)
        return {}

    if creds.get("username") != username or creds.get("password") != password:
        logger.warning("Invalid credentials for %s", username)
        return {}

    home_dir = f"/{BUCKET}/bronze/{cmo_id}/{domain}/incoming"
    logger.info("Auth success: user=%s home=%s", username, home_dir)

    return {
        "Role": ROLE_ARN,
        "HomeDirectoryType": "LOGICAL",
        "HomeDirectoryDetails": json.dumps([
            {"Entry": "/", "Target": home_dir}
        ]),
    }


def _find_credentials(username):
    """Find credentials by trying all possible cmoId/domain splits against Secrets Manager."""
    parts = username.split("-")
    # Try splits: cmo_id gets 2..N-1 parts, domain gets the rest
    for i in range(2, len(parts)):
        cmo_id = "-".join(parts[:i])
        domain = "-".join(parts[i:])
        secret_name = f"cmo/{cmo_id}/sftp-{domain}"
        try:
            resp = sm.get_secret_value(SecretId=secret_name)
            creds = json.loads(resp["SecretString"])
            if creds.get("username") == username:
                return creds, cmo_id, domain
        except Exception:
            continue
    return None, None, None
