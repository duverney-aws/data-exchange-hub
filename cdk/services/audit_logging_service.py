"""
Audit Logging Service

Provides structured audit event logging to CloudWatch and querying of
CloudTrail events for compliance reporting.

Requirements: 10.5, 14.1, 14.2, 14.3, 14.5
"""
import json
import logging
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

AUDIT_LOG_GROUP = "/pharma-data-exchange/cloudtrail"
CLOUDTRAIL_NAMESPACE = "CMO/AuditCompliance"


class AuditLoggingError(Exception):
    """Base exception for audit logging operations."""
    pass


class AuditLoggingService:
    """
    Service for structured audit event logging and CloudTrail event querying.

    Logs structured audit events to CloudWatch Logs and queries CloudTrail
    for data access events filtered by time range, user, or CMO.
    """

    def __init__(
        self,
        cloudtrail_client=None,
        logs_client=None,
        region: str = "us-east-1",
        log_group_name: str = AUDIT_LOG_GROUP,
    ):
        """
        Args:
            cloudtrail_client: boto3 CloudTrail client (injected for testability).
            logs_client: boto3 CloudWatch Logs client (injected for testability).
            region: AWS region.
            log_group_name: CloudWatch log group for audit events.
        """
        self.cloudtrail_client = cloudtrail_client
        self.logs_client = logs_client
        self.region = region
        self.log_group_name = log_group_name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_audit_event(
        self,
        event_type: str,
        user_id: str,
        action: str,
        resource: str,
        details: Optional[dict] = None,
    ) -> dict:
        """
        Log a structured audit event to CloudWatch Logs.

        Args:
            event_type: Category of event (e.g. 'DATA_ACCESS', 'DATA_MODIFICATION').
            user_id: Identity of the user performing the action.
            action: Description of the action (e.g. 'ReadObject', 'UpdateContract').
            resource: ARN or identifier of the affected resource.
            details: Optional dict with before/after values or extra context.

        Returns:
            dict with event_id and timestamp.

        Raises:
            AuditLoggingError: If the log write fails.
        """
        if not event_type or not user_id or not action or not resource:
            raise ValueError("event_type, user_id, action, and resource are required")

        timestamp = datetime.utcnow()
        timestamp_ms = int(timestamp.timestamp() * 1000)

        event = {
            "event_type": event_type,
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "timestamp": timestamp.isoformat() + "Z",
            "details": details or {},
        }

        log_stream = f"audit-events/{timestamp.strftime('%Y/%m/%d')}"

        try:
            # Ensure log stream exists
            self._ensure_log_stream(log_stream)

            self.logs_client.put_log_events(
                logGroupName=self.log_group_name,
                logStreamName=log_stream,
                logEvents=[
                    {
                        "timestamp": timestamp_ms,
                        "message": json.dumps(event),
                    }
                ],
            )

            logger.info(
                "Logged audit event: type=%s user=%s action=%s resource=%s",
                event_type, user_id, action, resource,
            )

            return {
                "event_id": f"{event_type}-{timestamp_ms}",
                "timestamp": timestamp.isoformat() + "Z",
            }

        except Exception as exc:
            raise AuditLoggingError(
                f"Failed to log audit event: {exc}"
            ) from exc

    def query_audit_events(
        self,
        start_time: datetime,
        end_time: datetime,
        filters: Optional[dict] = None,
    ) -> list:
        """
        Query CloudTrail events via the Lookup API.

        Args:
            start_time: Start of the query window.
            end_time: End of the query window.
            filters: Optional dict with keys like 'EventName', 'Username',
                     'ResourceType', 'ResourceName'.

        Returns:
            List of CloudTrail event dicts.

        Raises:
            AuditLoggingError: If the lookup fails.
        """
        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")

        lookup_attrs = []
        if filters:
            attr_map = {
                "EventName": "EventName",
                "Username": "Username",
                "ResourceType": "ResourceType",
                "ResourceName": "ResourceName",
            }
            for key, ct_key in attr_map.items():
                if key in filters:
                    lookup_attrs.append({
                        "AttributeKey": ct_key,
                        "AttributeValue": filters[key],
                    })

        try:
            kwargs = {
                "StartTime": start_time,
                "EndTime": end_time,
                "MaxResults": 50,
            }
            if lookup_attrs:
                kwargs["LookupAttributes"] = lookup_attrs

            response = self.cloudtrail_client.lookup_events(**kwargs)

            events = []
            for event in response.get("Events", []):
                events.append({
                    "event_id": event.get("EventId", ""),
                    "event_name": event.get("EventName", ""),
                    "event_time": (
                        event["EventTime"].isoformat()
                        if hasattr(event.get("EventTime", ""), "isoformat")
                        else str(event.get("EventTime", ""))
                    ),
                    "username": event.get("Username", ""),
                    "resources": event.get("Resources", []),
                    "cloud_trail_event": event.get("CloudTrailEvent", ""),
                })

            logger.info(
                "Queried %d CloudTrail events between %s and %s",
                len(events), start_time.isoformat(), end_time.isoformat(),
            )
            return events

        except Exception as exc:
            raise AuditLoggingError(
                f"Failed to query CloudTrail events: {exc}"
            ) from exc

    def get_data_access_events(
        self,
        cmo_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list:
        """
        Get data access events filtered by CMO.

        Queries CloudTrail for S3 GetObject/PutObject events on the
        CMO's data lake prefix.

        Args:
            cmo_id: CMO identifier (e.g. 'cmo-alpha').
            start_time: Start of the query window.
            end_time: End of the query window.

        Returns:
            List of data access event dicts filtered to the given CMO.

        Raises:
            AuditLoggingError: If the lookup fails.
        """
        if not cmo_id:
            raise ValueError("cmo_id is required")
        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")

        # Query S3 data events from CloudTrail
        all_events = self.query_audit_events(
            start_time=start_time,
            end_time=end_time,
            filters={"ResourceType": "AWS::S3::Object"},
        )

        # Filter to events involving this CMO's prefix
        cmo_events = []
        for event in all_events:
            ct_event_str = event.get("cloud_trail_event", "")
            if cmo_id in ct_event_str:
                cmo_events.append(event)
            else:
                # Also check resources list
                for resource in event.get("resources", []):
                    resource_name = resource.get("ResourceName", "")
                    if cmo_id in resource_name:
                        cmo_events.append(event)
                        break

        logger.info(
            "Found %d data access events for CMO %s between %s and %s",
            len(cmo_events), cmo_id,
            start_time.isoformat(), end_time.isoformat(),
        )
        return cmo_events

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_log_stream(self, log_stream: str) -> None:
        """Create the log stream if it doesn't exist."""
        try:
            self.logs_client.create_log_stream(
                logGroupName=self.log_group_name,
                logStreamName=log_stream,
            )
        except self.logs_client.exceptions.ResourceAlreadyExistsException:
            pass  # Stream already exists
        except AttributeError:
            # Mock clients may not have exceptions attribute
            try:
                self.logs_client.create_log_stream(
                    logGroupName=self.log_group_name,
                    logStreamName=log_stream,
                )
            except Exception:
                pass
