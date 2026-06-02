"""
Unit Tests for Audit Logging Service – structured audit event logging,
CloudTrail event querying, and CMO-filtered data access events.

Requirements: 10.5, 14.1, 14.2, 14.3, 14.5
"""
import json
import sys
import os
from datetime import datetime, timedelta

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.audit_logging_service import (
    AuditLoggingError,
    AuditLoggingService,
    AUDIT_LOG_GROUP,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_cloudtrail():
    return MagicMock()


@pytest.fixture
def mock_logs():
    client = MagicMock()
    # Simulate exceptions attribute for create_log_stream
    client.exceptions = MagicMock()
    client.exceptions.ResourceAlreadyExistsException = type(
        "ResourceAlreadyExistsException", (Exception,), {}
    )
    return client


@pytest.fixture
def service(mock_cloudtrail, mock_logs):
    return AuditLoggingService(
        cloudtrail_client=mock_cloudtrail,
        logs_client=mock_logs,
        region="us-east-1",
        log_group_name=AUDIT_LOG_GROUP,
    )


# ---------------------------------------------------------------------------
# log_audit_event
# ---------------------------------------------------------------------------

class TestLogAuditEvent:
    """Requirement 14.1: Log events with timestamp, user identity, and action details."""

    def test_logs_event_to_cloudwatch(self, service, mock_logs):
        result = service.log_audit_event(
            event_type="DATA_ACCESS",
            user_id="user-123",
            action="ReadObject",
            resource="arn:aws:s3:::bucket/bronze/cmo-alpha/data.parquet",
        )

        mock_logs.put_log_events.assert_called_once()
        call_kwargs = mock_logs.put_log_events.call_args[1]
        assert call_kwargs["logGroupName"] == AUDIT_LOG_GROUP
        assert len(call_kwargs["logEvents"]) == 1

        message = json.loads(call_kwargs["logEvents"][0]["message"])
        assert message["event_type"] == "DATA_ACCESS"
        assert message["user_id"] == "user-123"
        assert message["action"] == "ReadObject"
        assert "timestamp" in message

    def test_returns_event_id_and_timestamp(self, service):
        result = service.log_audit_event(
            event_type="DATA_MODIFICATION",
            user_id="user-456",
            action="UpdateContract",
            resource="CMO-ALPHA-BATCH-001",
        )

        assert "event_id" in result
        assert "timestamp" in result
        assert result["event_id"].startswith("DATA_MODIFICATION-")

    def test_includes_details_when_provided(self, service, mock_logs):
        details = {"before": {"status": "draft"}, "after": {"status": "active"}}
        service.log_audit_event(
            event_type="DATA_MODIFICATION",
            user_id="user-789",
            action="ActivateContract",
            resource="CMO-ALPHA-BATCH-001",
            details=details,
        )

        call_kwargs = mock_logs.put_log_events.call_args[1]
        message = json.loads(call_kwargs["logEvents"][0]["message"])
        assert message["details"]["before"]["status"] == "draft"
        assert message["details"]["after"]["status"] == "active"

    def test_empty_details_defaults_to_empty_dict(self, service, mock_logs):
        service.log_audit_event(
            event_type="DATA_ACCESS",
            user_id="user-123",
            action="ReadObject",
            resource="some-resource",
        )

        call_kwargs = mock_logs.put_log_events.call_args[1]
        message = json.loads(call_kwargs["logEvents"][0]["message"])
        assert message["details"] == {}

    def test_missing_event_type_raises(self, service):
        with pytest.raises(ValueError, match="event_type.*required"):
            service.log_audit_event(
                event_type="",
                user_id="user-123",
                action="ReadObject",
                resource="some-resource",
            )

    def test_missing_user_id_raises(self, service):
        with pytest.raises(ValueError, match="user_id.*required"):
            service.log_audit_event(
                event_type="DATA_ACCESS",
                user_id="",
                action="ReadObject",
                resource="some-resource",
            )

    def test_missing_action_raises(self, service):
        with pytest.raises(ValueError, match="action.*required"):
            service.log_audit_event(
                event_type="DATA_ACCESS",
                user_id="user-123",
                action="",
                resource="some-resource",
            )

    def test_missing_resource_raises(self, service):
        with pytest.raises(ValueError, match="resource.*required"):
            service.log_audit_event(
                event_type="DATA_ACCESS",
                user_id="user-123",
                action="ReadObject",
                resource="",
            )

    def test_cloudwatch_failure_raises_audit_error(self, service, mock_logs):
        mock_logs.put_log_events.side_effect = Exception("Throttled")

        with pytest.raises(AuditLoggingError, match="Failed to log audit event"):
            service.log_audit_event(
                event_type="DATA_ACCESS",
                user_id="user-123",
                action="ReadObject",
                resource="some-resource",
            )

    def test_creates_log_stream_before_writing(self, service, mock_logs):
        service.log_audit_event(
            event_type="DATA_ACCESS",
            user_id="user-123",
            action="ReadObject",
            resource="some-resource",
        )

        mock_logs.create_log_stream.assert_called_once()
        call_kwargs = mock_logs.create_log_stream.call_args[1]
        assert call_kwargs["logGroupName"] == AUDIT_LOG_GROUP
        assert call_kwargs["logStreamName"].startswith("audit-events/")


# ---------------------------------------------------------------------------
# query_audit_events
# ---------------------------------------------------------------------------

class TestQueryAuditEvents:
    """Requirement 10.5, 14.1: Query CloudTrail events for audit compliance."""

    def test_queries_cloudtrail_with_time_range(self, service, mock_cloudtrail):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)
        mock_cloudtrail.lookup_events.return_value = {"Events": []}

        service.query_audit_events(start_time=start, end_time=end)

        mock_cloudtrail.lookup_events.assert_called_once()
        call_kwargs = mock_cloudtrail.lookup_events.call_args[1]
        assert call_kwargs["StartTime"] == start
        assert call_kwargs["EndTime"] == end

    def test_returns_parsed_events(self, service, mock_cloudtrail):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)
        mock_cloudtrail.lookup_events.return_value = {
            "Events": [
                {
                    "EventId": "evt-001",
                    "EventName": "GetObject",
                    "EventTime": datetime(2024, 1, 1, 12, 0),
                    "Username": "user-123",
                    "Resources": [{"ResourceName": "bucket/key"}],
                    "CloudTrailEvent": '{"key": "value"}',
                }
            ]
        }

        events = service.query_audit_events(start_time=start, end_time=end)

        assert len(events) == 1
        assert events[0]["event_id"] == "evt-001"
        assert events[0]["event_name"] == "GetObject"
        assert events[0]["username"] == "user-123"

    def test_applies_event_name_filter(self, service, mock_cloudtrail):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)
        mock_cloudtrail.lookup_events.return_value = {"Events": []}

        service.query_audit_events(
            start_time=start,
            end_time=end,
            filters={"EventName": "PutObject"},
        )

        call_kwargs = mock_cloudtrail.lookup_events.call_args[1]
        attrs = call_kwargs["LookupAttributes"]
        assert any(a["AttributeKey"] == "EventName" and a["AttributeValue"] == "PutObject" for a in attrs)

    def test_applies_username_filter(self, service, mock_cloudtrail):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)
        mock_cloudtrail.lookup_events.return_value = {"Events": []}

        service.query_audit_events(
            start_time=start,
            end_time=end,
            filters={"Username": "admin-user"},
        )

        call_kwargs = mock_cloudtrail.lookup_events.call_args[1]
        attrs = call_kwargs["LookupAttributes"]
        assert any(a["AttributeKey"] == "Username" for a in attrs)

    def test_no_filters_omits_lookup_attributes(self, service, mock_cloudtrail):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)
        mock_cloudtrail.lookup_events.return_value = {"Events": []}

        service.query_audit_events(start_time=start, end_time=end)

        call_kwargs = mock_cloudtrail.lookup_events.call_args[1]
        assert "LookupAttributes" not in call_kwargs

    def test_start_after_end_raises(self, service):
        with pytest.raises(ValueError, match="start_time must be before end_time"):
            service.query_audit_events(
                start_time=datetime(2024, 1, 2),
                end_time=datetime(2024, 1, 1),
            )

    def test_equal_times_raises(self, service):
        t = datetime(2024, 1, 1)
        with pytest.raises(ValueError, match="start_time must be before end_time"):
            service.query_audit_events(start_time=t, end_time=t)

    def test_cloudtrail_failure_raises_audit_error(self, service, mock_cloudtrail):
        mock_cloudtrail.lookup_events.side_effect = Exception("AccessDenied")

        with pytest.raises(AuditLoggingError, match="Failed to query CloudTrail"):
            service.query_audit_events(
                start_time=datetime(2024, 1, 1),
                end_time=datetime(2024, 1, 2),
            )


# ---------------------------------------------------------------------------
# get_data_access_events
# ---------------------------------------------------------------------------

class TestGetDataAccessEvents:
    """Requirement 10.5: Get data access events filtered by CMO."""

    def test_filters_events_by_cmo_id_in_cloud_trail_event(self, service, mock_cloudtrail):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)
        mock_cloudtrail.lookup_events.return_value = {
            "Events": [
                {
                    "EventId": "evt-001",
                    "EventName": "GetObject",
                    "EventTime": datetime(2024, 1, 1, 12, 0),
                    "Username": "user-123",
                    "Resources": [],
                    "CloudTrailEvent": '{"key": "bronze/cmo-alpha/batch-records/data.parquet"}',
                },
                {
                    "EventId": "evt-002",
                    "EventName": "GetObject",
                    "EventTime": datetime(2024, 1, 1, 13, 0),
                    "Username": "user-456",
                    "Resources": [],
                    "CloudTrailEvent": '{"key": "bronze/cmo-beta/batch-records/data.parquet"}',
                },
            ]
        }

        events = service.get_data_access_events("cmo-alpha", start, end)

        assert len(events) == 1
        assert events[0]["event_id"] == "evt-001"

    def test_filters_events_by_cmo_id_in_resources(self, service, mock_cloudtrail):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)
        mock_cloudtrail.lookup_events.return_value = {
            "Events": [
                {
                    "EventId": "evt-003",
                    "EventName": "PutObject",
                    "EventTime": datetime(2024, 1, 1, 14, 0),
                    "Username": "glue-job",
                    "Resources": [{"ResourceName": "bronze/cmo-alpha/quality/data.parquet"}],
                    "CloudTrailEvent": "{}",
                },
            ]
        }

        events = service.get_data_access_events("cmo-alpha", start, end)

        assert len(events) == 1
        assert events[0]["event_id"] == "evt-003"

    def test_returns_empty_when_no_cmo_match(self, service, mock_cloudtrail):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)
        mock_cloudtrail.lookup_events.return_value = {
            "Events": [
                {
                    "EventId": "evt-004",
                    "EventName": "GetObject",
                    "EventTime": datetime(2024, 1, 1, 15, 0),
                    "Username": "user-789",
                    "Resources": [{"ResourceName": "bronze/cmo-beta/data.parquet"}],
                    "CloudTrailEvent": '{"key": "cmo-beta"}',
                },
            ]
        }

        events = service.get_data_access_events("cmo-alpha", start, end)

        assert len(events) == 0

    def test_empty_cmo_id_raises(self, service):
        with pytest.raises(ValueError, match="cmo_id is required"):
            service.get_data_access_events(
                "", datetime(2024, 1, 1), datetime(2024, 1, 2),
            )

    def test_invalid_time_range_raises(self, service):
        with pytest.raises(ValueError, match="start_time must be before end_time"):
            service.get_data_access_events(
                "cmo-alpha", datetime(2024, 1, 2), datetime(2024, 1, 1),
            )

    def test_passes_resource_type_filter_to_cloudtrail(self, service, mock_cloudtrail):
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)
        mock_cloudtrail.lookup_events.return_value = {"Events": []}

        service.get_data_access_events("cmo-alpha", start, end)

        call_kwargs = mock_cloudtrail.lookup_events.call_args[1]
        attrs = call_kwargs["LookupAttributes"]
        assert any(
            a["AttributeKey"] == "ResourceType" and a["AttributeValue"] == "AWS::S3::Object"
            for a in attrs
        )
