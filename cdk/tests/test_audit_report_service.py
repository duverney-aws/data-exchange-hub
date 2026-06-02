"""
Unit Tests for Audit Report Service – compliance report generation,
PDF export, user action reports, and data modification reports.

Requirements: 14.4
"""
import json
import os
import sys
import tempfile
from datetime import datetime

import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.audit_report_service import (
    AuditReportError,
    AuditReportService,
    REPORT_TYPES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_event(event_id="evt-001", event_name="GetObject", username="user-123",
                event_time="2024-01-01T12:00:00", cmo_id="cmo-alpha"):
    return {
        "event_id": event_id,
        "event_name": event_name,
        "event_time": event_time,
        "username": username,
        "resources": [{"ResourceName": f"bronze/{cmo_id}/batch-records/data.parquet"}],
        "cloud_trail_event": json.dumps({"key": f"bronze/{cmo_id}/data.parquet"}),
    }


@pytest.fixture
def mock_audit_logging():
    service = MagicMock()
    service.query_audit_events.return_value = [
        _make_event("evt-001", "GetObject", "user-123"),
        _make_event("evt-002", "PutObject", "user-456"),
    ]
    service.get_data_access_events.return_value = [
        _make_event("evt-001", "GetObject", "user-123"),
    ]
    return service


@pytest.fixture
def service(mock_audit_logging):
    return AuditReportService(audit_logging_service=mock_audit_logging)


# ---------------------------------------------------------------------------
# generate_compliance_report
# ---------------------------------------------------------------------------

class TestGenerateComplianceReport:
    """Requirement 14.4: Generate audit reports from CloudTrail logs."""

    def test_user_actions_report(self, service):
        report = service.generate_compliance_report(
            "user_actions", "cmo-alpha",
            datetime(2024, 1, 1), datetime(2024, 1, 2),
        )
        assert report["report_type"] == "user_actions"
        assert report["report_id"].startswith("RPT-")
        assert "generated_at" in report
        assert report["time_range"]["start"] == "2024-01-01T00:00:00Z"
        assert report["summary"]["total_events"] >= 0

    def test_data_access_report(self, service):
        report = service.generate_compliance_report(
            "data_access", "cmo-alpha",
            datetime(2024, 1, 1), datetime(2024, 1, 2),
        )
        assert report["report_type"] == "data_access"
        assert isinstance(report["events"], list)

    def test_data_modifications_report(self, service):
        report = service.generate_compliance_report(
            "data_modifications", "cmo-alpha",
            datetime(2024, 1, 1), datetime(2024, 1, 2),
        )
        assert report["report_type"] == "data_modifications"

    def test_comprehensive_report(self, service):
        report = service.generate_compliance_report(
            "comprehensive", "cmo-alpha",
            datetime(2024, 1, 1), datetime(2024, 1, 2),
        )
        assert report["report_type"] == "comprehensive"
        assert "summary" in report
        assert "unique_users" in report["summary"]
        assert "event_breakdown" in report["summary"]

    def test_report_contains_required_fields(self, service):
        report = service.generate_compliance_report(
            "user_actions", "cmo-alpha",
            datetime(2024, 1, 1), datetime(2024, 1, 2),
        )
        assert "report_id" in report
        assert "report_type" in report
        assert "generated_at" in report
        assert "time_range" in report
        assert "summary" in report
        assert "events" in report

    def test_invalid_report_type_raises(self, service):
        with pytest.raises(ValueError, match="Invalid report_type"):
            service.generate_compliance_report(
                "invalid_type", "cmo-alpha",
                datetime(2024, 1, 1), datetime(2024, 1, 2),
            )

    def test_empty_cmo_id_raises(self, service):
        with pytest.raises(ValueError, match="cmo_id is required"):
            service.generate_compliance_report(
                "user_actions", "",
                datetime(2024, 1, 1), datetime(2024, 1, 2),
            )

    def test_start_after_end_raises(self, service):
        with pytest.raises(ValueError, match="start_time must be before end_time"):
            service.generate_compliance_report(
                "user_actions", "cmo-alpha",
                datetime(2024, 1, 2), datetime(2024, 1, 1),
            )

    def test_equal_times_raises(self, service):
        t = datetime(2024, 1, 1)
        with pytest.raises(ValueError, match="start_time must be before end_time"):
            service.generate_compliance_report("user_actions", "cmo-alpha", t, t)

    def test_audit_logging_failure_raises_report_error(self, service, mock_audit_logging):
        mock_audit_logging.query_audit_events.side_effect = Exception("AccessDenied")
        with pytest.raises(AuditReportError, match="Failed to generate"):
            service.generate_compliance_report(
                "user_actions", "cmo-alpha",
                datetime(2024, 1, 1), datetime(2024, 1, 2),
            )


# ---------------------------------------------------------------------------
# export_report_pdf
# ---------------------------------------------------------------------------

class TestExportReportPdf:
    """Requirement 14.4: Export reports in PDF format."""

    def test_exports_valid_pdf_file(self, service):
        report = service.generate_compliance_report(
            "user_actions", "cmo-alpha",
            datetime(2024, 1, 1), datetime(2024, 1, 2),
        )
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = service.export_report_pdf(report, tmp_path)
            assert result == tmp_path
            with open(tmp_path, "rb") as f:
                content = f.read()
            assert content.startswith(b"%PDF-1.4")
            assert b"%%EOF" in content
        finally:
            os.unlink(tmp_path)

    def test_pdf_contains_report_text(self, service):
        report = service.generate_compliance_report(
            "data_access", "cmo-alpha",
            datetime(2024, 1, 1), datetime(2024, 1, 2),
        )
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            service.export_report_pdf(report, tmp_path)
            with open(tmp_path, "rb") as f:
                content = f.read()
            # The report type text should appear in the PDF stream
            assert b"data_access" in content
            assert b"Report ID" in content
        finally:
            os.unlink(tmp_path)

    def test_empty_report_raises(self, service):
        with pytest.raises(ValueError, match="report is required"):
            service.export_report_pdf({}, "/tmp/test.pdf")

    def test_empty_output_path_raises(self, service):
        with pytest.raises(ValueError, match="output_path is required"):
            service.export_report_pdf({"report_id": "RPT-123"}, "")

    def test_none_report_raises(self, service):
        with pytest.raises(ValueError, match="report is required"):
            service.export_report_pdf(None, "/tmp/test.pdf")


# ---------------------------------------------------------------------------
# get_user_action_report
# ---------------------------------------------------------------------------

class TestGetUserActionReport:
    """Requirement 14.4: Get all actions performed by a specific user."""

    def test_returns_report_for_user(self, service, mock_audit_logging):
        mock_audit_logging.query_audit_events.return_value = [
            _make_event("evt-010", "GetObject", "admin-user"),
            _make_event("evt-011", "PutObject", "admin-user"),
        ]
        report = service.get_user_action_report(
            "admin-user", datetime(2024, 1, 1), datetime(2024, 1, 2),
        )
        assert report["report_type"] == "user_actions"
        assert report["scope"] == "user:admin-user"
        assert report["summary"]["total_events"] == 2

    def test_passes_username_filter(self, service, mock_audit_logging):
        mock_audit_logging.query_audit_events.return_value = []
        service.get_user_action_report(
            "admin-user", datetime(2024, 1, 1), datetime(2024, 1, 2),
        )
        call_kwargs = mock_audit_logging.query_audit_events.call_args[1]
        assert call_kwargs["filters"] == {"Username": "admin-user"}

    def test_empty_user_id_raises(self, service):
        with pytest.raises(ValueError, match="user_id is required"):
            service.get_user_action_report(
                "", datetime(2024, 1, 1), datetime(2024, 1, 2),
            )

    def test_invalid_time_range_raises(self, service):
        with pytest.raises(ValueError, match="start_time must be before end_time"):
            service.get_user_action_report(
                "admin-user", datetime(2024, 1, 2), datetime(2024, 1, 1),
            )

    def test_audit_logging_failure_raises(self, service, mock_audit_logging):
        mock_audit_logging.query_audit_events.side_effect = Exception("Timeout")
        with pytest.raises(AuditReportError, match="Failed to get user action report"):
            service.get_user_action_report(
                "admin-user", datetime(2024, 1, 1), datetime(2024, 1, 2),
            )


# ---------------------------------------------------------------------------
# get_data_modification_report
# ---------------------------------------------------------------------------

class TestGetDataModificationReport:
    """Requirement 14.4: Get all data modifications for a CMO."""

    def test_returns_modification_report(self, service, mock_audit_logging):
        mock_audit_logging.query_audit_events.return_value = [
            _make_event("evt-020", "PutObject", "glue-job", cmo_id="cmo-alpha"),
        ]
        report = service.get_data_modification_report(
            "cmo-alpha", datetime(2024, 1, 1), datetime(2024, 1, 2),
        )
        assert report["report_type"] == "data_modifications"
        assert report["scope"] == "cmo-alpha"
        assert report["summary"]["total_events"] == 1

    def test_filters_by_put_object(self, service, mock_audit_logging):
        mock_audit_logging.query_audit_events.return_value = []
        service.get_data_modification_report(
            "cmo-alpha", datetime(2024, 1, 1), datetime(2024, 1, 2),
        )
        call_kwargs = mock_audit_logging.query_audit_events.call_args[1]
        assert call_kwargs["filters"] == {"EventName": "PutObject"}

    def test_empty_cmo_id_raises(self, service):
        with pytest.raises(ValueError, match="cmo_id is required"):
            service.get_data_modification_report(
                "", datetime(2024, 1, 1), datetime(2024, 1, 2),
            )

    def test_invalid_time_range_raises(self, service):
        with pytest.raises(ValueError, match="start_time must be before end_time"):
            service.get_data_modification_report(
                "cmo-alpha", datetime(2024, 1, 2), datetime(2024, 1, 1),
            )

    def test_audit_logging_failure_raises(self, service, mock_audit_logging):
        mock_audit_logging.query_audit_events.side_effect = Exception("Throttled")
        with pytest.raises(AuditReportError, match="Failed to get data modification report"):
            service.get_data_modification_report(
                "cmo-alpha", datetime(2024, 1, 1), datetime(2024, 1, 2),
            )
