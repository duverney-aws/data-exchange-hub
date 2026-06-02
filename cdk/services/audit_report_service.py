"""
Audit Report Service

Generates compliance reports from CloudTrail audit logs, including
user action reports, data access reports, and data modification reports.
Supports export to PDF format.

Requirements: 14.4
"""
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

REPORT_TYPES = ("user_actions", "data_access", "data_modifications", "comprehensive")


class AuditReportError(Exception):
    """Base exception for audit report operations."""
    pass


class AuditReportService:
    """
    Service for generating compliance reports from CloudTrail audit logs.

    Uses an injected AuditLoggingService to query events, then formats
    results into structured report dicts or PDF output.
    """

    def __init__(self, audit_logging_service=None):
        """
        Args:
            audit_logging_service: AuditLoggingService instance for querying events.
        """
        self.audit_logging_service = audit_logging_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_compliance_report(
        self,
        report_type: str,
        cmo_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """
        Generate a compliance report by querying CloudTrail events.

        Args:
            report_type: One of 'user_actions', 'data_access',
                         'data_modifications', or 'comprehensive'.
            cmo_id: CMO identifier to scope the report.
            start_time: Start of the reporting window.
            end_time: End of the reporting window.

        Returns:
            Structured report dict with metadata, summary, and events.

        Raises:
            ValueError: If parameters are invalid.
            AuditReportError: If event querying fails.
        """
        self._validate_params(report_type, cmo_id, start_time, end_time)

        try:
            if report_type == "user_actions":
                events = self._query_user_action_events(cmo_id, start_time, end_time)
            elif report_type == "data_access":
                events = self._query_data_access_events(cmo_id, start_time, end_time)
            elif report_type == "data_modifications":
                events = self._query_data_modification_events(cmo_id, start_time, end_time)
            else:  # comprehensive
                events = self._query_all_events(cmo_id, start_time, end_time)
        except Exception as exc:
            raise AuditReportError(
                f"Failed to generate {report_type} report: {exc}"
            ) from exc

        return self._build_report(report_type, cmo_id, start_time, end_time, events)

    def get_user_action_report(
        self,
        user_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """
        Get all actions performed by a specific user.

        Args:
            user_id: The user identifier to filter on.
            start_time: Start of the reporting window.
            end_time: End of the reporting window.

        Returns:
            Structured report dict scoped to the given user.

        Raises:
            ValueError: If parameters are invalid.
            AuditReportError: If event querying fails.
        """
        if not user_id:
            raise ValueError("user_id is required")
        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")

        try:
            all_events = self.audit_logging_service.query_audit_events(
                start_time=start_time,
                end_time=end_time,
                filters={"Username": user_id},
            )
        except Exception as exc:
            raise AuditReportError(
                f"Failed to get user action report: {exc}"
            ) from exc

        return self._build_report(
            "user_actions", f"user:{user_id}", start_time, end_time, all_events,
        )

    def get_data_modification_report(
        self,
        cmo_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> dict:
        """
        Get all data modifications for a CMO.

        Args:
            cmo_id: CMO identifier.
            start_time: Start of the reporting window.
            end_time: End of the reporting window.

        Returns:
            Structured report dict with modification events.

        Raises:
            ValueError: If parameters are invalid.
            AuditReportError: If event querying fails.
        """
        if not cmo_id:
            raise ValueError("cmo_id is required")
        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")

        try:
            events = self._query_data_modification_events(cmo_id, start_time, end_time)
        except Exception as exc:
            raise AuditReportError(
                f"Failed to get data modification report: {exc}"
            ) from exc

        return self._build_report(
            "data_modifications", cmo_id, start_time, end_time, events,
        )

    def export_report_pdf(self, report: dict, output_path: str) -> str:
        """
        Export a report dict to PDF format using minimal raw PDF generation.

        Args:
            report: Structured report dict (from generate_compliance_report).
            output_path: File path to write the PDF to.

        Returns:
            The output_path written to.

        Raises:
            ValueError: If report is empty or output_path is missing.
            AuditReportError: If PDF generation fails.
        """
        if not report:
            raise ValueError("report is required")
        if not output_path:
            raise ValueError("output_path is required")

        try:
            pdf_bytes = self._render_pdf(report)
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)
            logger.info("Exported PDF report to %s (%d bytes)", output_path, len(pdf_bytes))
            return output_path
        except Exception as exc:
            raise AuditReportError(
                f"Failed to export PDF report: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_params(self, report_type, cmo_id, start_time, end_time):
        if report_type not in REPORT_TYPES:
            raise ValueError(
                f"Invalid report_type '{report_type}'. Must be one of {REPORT_TYPES}"
            )
        if not cmo_id:
            raise ValueError("cmo_id is required")
        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")

    def _query_user_action_events(self, cmo_id, start_time, end_time):
        events = self.audit_logging_service.query_audit_events(
            start_time=start_time, end_time=end_time,
        )
        return [e for e in events if cmo_id in json.dumps(e)]

    def _query_data_access_events(self, cmo_id, start_time, end_time):
        return self.audit_logging_service.get_data_access_events(
            cmo_id=cmo_id, start_time=start_time, end_time=end_time,
        )

    def _query_data_modification_events(self, cmo_id, start_time, end_time):
        events = self.audit_logging_service.query_audit_events(
            start_time=start_time, end_time=end_time,
            filters={"EventName": "PutObject"},
        )
        return [e for e in events if cmo_id in json.dumps(e)]

    def _query_all_events(self, cmo_id, start_time, end_time):
        all_events = self.audit_logging_service.query_audit_events(
            start_time=start_time, end_time=end_time,
        )
        access_events = self.audit_logging_service.get_data_access_events(
            cmo_id=cmo_id, start_time=start_time, end_time=end_time,
        )
        # Merge, dedup by event_id
        seen = set()
        merged = []
        for e in all_events + access_events:
            eid = e.get("event_id", "")
            if eid not in seen:
                seen.add(eid)
                if cmo_id in json.dumps(e):
                    merged.append(e)
        return merged

    def _build_report(self, report_type, scope, start_time, end_time, events):
        unique_users = set()
        event_names = {}
        for e in events:
            username = e.get("username", "unknown")
            unique_users.add(username)
            name = e.get("event_name", "unknown")
            event_names[name] = event_names.get(name, 0) + 1

        return {
            "report_id": f"RPT-{uuid.uuid4().hex[:12].upper()}",
            "report_type": report_type,
            "scope": scope,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "time_range": {
                "start": start_time.isoformat() + "Z",
                "end": end_time.isoformat() + "Z",
            },
            "summary": {
                "total_events": len(events),
                "unique_users": len(unique_users),
                "event_breakdown": event_names,
            },
            "events": events,
        }

    # ------------------------------------------------------------------
    # Minimal PDF renderer (no external dependencies)
    # ------------------------------------------------------------------

    def _render_pdf(self, report: dict) -> bytes:
        """
        Render a report dict as a minimal valid PDF.

        Uses raw PDF structure to avoid external dependencies.
        """
        text_lines = self._report_to_text_lines(report)
        return self._text_to_pdf_bytes(text_lines)

    def _report_to_text_lines(self, report: dict) -> list:
        lines = [
            f"Compliance Report: {report.get('report_type', 'N/A')}",
            f"Report ID: {report.get('report_id', 'N/A')}",
            f"Scope: {report.get('scope', 'N/A')}",
            f"Generated: {report.get('generated_at', 'N/A')}",
            "",
            f"Time Range: {report.get('time_range', {}).get('start', '')} to {report.get('time_range', {}).get('end', '')}",
            "",
            "--- Summary ---",
            f"Total Events: {report.get('summary', {}).get('total_events', 0)}",
            f"Unique Users: {report.get('summary', {}).get('unique_users', 0)}",
            "",
            "Event Breakdown:",
        ]
        for name, count in report.get("summary", {}).get("event_breakdown", {}).items():
            lines.append(f"  {name}: {count}")

        lines.append("")
        lines.append("--- Events ---")
        for i, event in enumerate(report.get("events", [])[:50], 1):
            lines.append(
                f"{i}. [{event.get('event_name', 'N/A')}] "
                f"user={event.get('username', 'N/A')} "
                f"time={event.get('event_time', 'N/A')}"
            )

        if len(report.get("events", [])) > 50:
            lines.append(f"... and {len(report['events']) - 50} more events")

        return lines

    @staticmethod
    def _text_to_pdf_bytes(lines: list) -> bytes:
        """
        Build a minimal valid PDF 1.4 document from text lines.
        """
        # Escape special PDF characters in text
        def _esc(s):
            return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

        # Build the stream content (simple text drawing)
        stream_lines = ["BT", "/F1 10 Tf"]
        y = 750
        for line in lines:
            if y < 50:
                break
            stream_lines.append(f"1 0 0 1 50 {y} Tm")
            stream_lines.append(f"({_esc(line)}) Tj")
            y -= 14
        stream_lines.append("ET")
        stream_content = "\n".join(stream_lines)
        stream_bytes = stream_content.encode("latin-1")

        # PDF objects
        objs = []

        # Object 1: Catalog
        objs.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

        # Object 2: Pages
        objs.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")

        # Object 3: Page
        objs.append(
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R "
            b"/MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        )

        # Object 4: Stream
        stream_obj = (
            f"4 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n"
        ).encode("latin-1") + stream_bytes + b"\nendstream\nendobj\n"
        objs.append(stream_obj)

        # Object 5: Font
        objs.append(
            b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        )

        # Build the file
        pdf = bytearray()
        pdf.extend(b"%PDF-1.4\n")

        offsets = []
        for obj in objs:
            offsets.append(len(pdf))
            pdf.extend(obj)

        # Cross-reference table
        xref_offset = len(pdf)
        pdf.extend(b"xref\n")
        pdf.extend(f"0 {len(objs) + 1}\n".encode())
        pdf.extend(b"0000000000 65535 f \n")
        for off in offsets:
            pdf.extend(f"{off:010d} 00000 n \n".encode())

        # Trailer
        pdf.extend(b"trailer\n")
        pdf.extend(f"<< /Size {len(objs) + 1} /Root 1 0 R >>\n".encode())
        pdf.extend(b"startxref\n")
        pdf.extend(f"{xref_offset}\n".encode())
        pdf.extend(b"%%EOF\n")

        return bytes(pdf)
