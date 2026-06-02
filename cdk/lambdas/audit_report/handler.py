"""
Lambda handler for Audit Report generation via API Gateway.

Accepts report parameters, generates compliance reports using
AuditReportService, and returns JSON or uploads PDF to S3.

Requirements: 14.4
"""
import json
import logging
import os
import sys
import tempfile
from datetime import datetime

import boto3

# Ensure the project root is on the path so we can import services/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from services.audit_logging_service import AuditLoggingService
from services.audit_report_service import AuditReportService, AuditReportError

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# Initialise clients once per Lambda cold-start
_region = os.environ.get('AWS_REGION', 'us-east-1')
_report_bucket = os.environ.get('REPORT_BUCKET', 'pharma-audit-reports')

_cloudtrail_client = boto3.client('cloudtrail', region_name=_region)
_logs_client = boto3.client('logs', region_name=_region)
_s3_client = boto3.client('s3', region_name=_region)

_audit_logging = AuditLoggingService(
    cloudtrail_client=_cloudtrail_client,
    logs_client=_logs_client,
    region=_region,
)
_report_service = AuditReportService(audit_logging_service=_audit_logging)


def handler(event, context):
    """
    API Gateway proxy Lambda handler for audit report generation.

    Expected body parameters:
        report_type: str  - 'user_actions', 'data_access', 'data_modifications', 'comprehensive'
        cmo_id: str       - CMO identifier
        start_time: str   - ISO 8601 datetime
        end_time: str     - ISO 8601 datetime
        output_format: str - 'json' (default) or 'pdf'
        user_id: str      - (optional) for user-specific reports
    """
    http_method = event.get('httpMethod', '')
    if http_method != 'POST':
        return _response(405, {'error': f'Method {http_method} not allowed'})

    try:
        body = _parse_body(event)
        if body is None:
            return _response(400, {'error': 'Request body must be valid JSON'})

        # Extract and validate parameters
        report_type = body.get('report_type', '')
        cmo_id = body.get('cmo_id', '')
        start_time_str = body.get('start_time', '')
        end_time_str = body.get('end_time', '')
        output_format = body.get('output_format', 'json')
        user_id = body.get('user_id')

        if not report_type:
            return _response(400, {'error': 'report_type is required'})
        if not cmo_id:
            return _response(400, {'error': 'cmo_id is required'})
        if not start_time_str or not end_time_str:
            return _response(400, {'error': 'start_time and end_time are required'})

        try:
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00')).replace(tzinfo=None)
            end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00')).replace(tzinfo=None)
        except (ValueError, TypeError):
            return _response(400, {'error': 'start_time and end_time must be valid ISO 8601 datetimes'})

        # Generate the report
        if user_id:
            report = _report_service.get_user_action_report(user_id, start_time, end_time)
        else:
            report = _report_service.generate_compliance_report(
                report_type, cmo_id, start_time, end_time,
            )

        # Return based on output format
        if output_format == 'pdf':
            return _handle_pdf_export(report)
        else:
            return _response(200, report)

    except ValueError as exc:
        return _response(400, {'error': str(exc)})
    except AuditReportError as exc:
        logger.error("Report generation failed: %s", exc)
        return _response(500, {'error': 'Report generation failed'})
    except Exception as exc:
        logger.exception("Unhandled error")
        return _response(500, {'error': 'Internal server error'})


def _handle_pdf_export(report):
    """Export report as PDF, upload to S3, and return a presigned URL."""
    try:
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp_path = tmp.name

        _report_service.export_report_pdf(report, tmp_path)

        s3_key = f"reports/{report['report_id']}.pdf"
        _s3_client.upload_file(tmp_path, _report_bucket, s3_key)

        presigned_url = _s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': _report_bucket, 'Key': s3_key},
            ExpiresIn=3600,
        )

        return _response(200, {
            'report_id': report['report_id'],
            'format': 'pdf',
            's3_key': s3_key,
            'download_url': presigned_url,
        })
    except Exception as exc:
        logger.error("PDF export failed: %s", exc)
        return _response(500, {'error': 'PDF export failed'})
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

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
