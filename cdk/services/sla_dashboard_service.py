"""
SLA Dashboard Service

Generates CloudWatch dashboard widget definitions for SLA compliance
monitoring.  Produces dashboard body JSON with per-CMO widgets for
execution time, quality scores, availability, and SLA breach counts.

Requirements: 11.4
"""
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

CLOUDWATCH_NAMESPACE = 'CMO/DataPipeline'
DEFAULT_PERIOD = 300  # 5 minutes
DEFAULT_REGION = 'us-east-1'


class SLADashboardService:
    """
    Builds CloudWatch dashboard body JSON for SLA compliance visualisation.

    Accepts lists of CMO IDs and contract IDs and returns a dict suitable
    for the CloudWatch ``put_dashboard`` API.
    """

    def __init__(self, region: str = DEFAULT_REGION):
        self.region = region

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_dashboard_body(
        self,
        cmo_contracts: Dict[str, List[str]],
        period: int = DEFAULT_PERIOD,
    ) -> dict:
        """
        Build a complete dashboard body with SLA compliance widgets.

        Args:
            cmo_contracts: Mapping of CMO ID → list of contract IDs.
                           Example: ``{'cmo-alpha': ['CMO-ALPHA-BATCH-001']}``
            period: CloudWatch metric period in seconds.

        Returns:
            dict with a ``widgets`` key ready for ``put_dashboard``.
        """
        widgets: List[dict] = []
        y_offset = 0

        # Section header
        header = self._text_widget(
            markdown='## SLA Compliance Dashboard\nPer-CMO execution time, '
                     'quality scores, availability, and breach counts.',
            x=0, y=y_offset, width=24, height=2,
        )
        widgets.append(header)
        y_offset += 2

        # Per-CMO widgets
        for cmo_id, contract_ids in cmo_contracts.items():
            cmo_widgets, rows_used = self._build_cmo_widgets(
                cmo_id, contract_ids, y_offset, period,
            )
            widgets.extend(cmo_widgets)
            y_offset += rows_used

        return {'widgets': widgets}

    # ------------------------------------------------------------------
    # Widget builders
    # ------------------------------------------------------------------

    def build_execution_time_widget(
        self, cmo_id: str, contract_ids: List[str],
        x: int = 0, y: int = 0, width: int = 12, height: int = 6,
        period: int = DEFAULT_PERIOD,
    ) -> dict:
        """Line graph widget for ExecutionTime metric per CMO."""
        metrics = []
        for cid in contract_ids:
            metrics.append(self._metric_entry(
                'ExecutionTime', cmo_id, cid, label=f'{cid}',
            ))
        return self._graph_widget(
            title=f'Execution Time – {cmo_id}',
            metrics=metrics,
            x=x, y=y, width=width, height=height,
            period=period, y_axis_label='Seconds',
        )

    def build_quality_score_widget(
        self, cmo_id: str, contract_ids: List[str],
        x: int = 0, y: int = 0, width: int = 12, height: int = 6,
        period: int = DEFAULT_PERIOD,
    ) -> dict:
        """Line graph widget for QualityScore metric per CMO."""
        metrics = []
        for cid in contract_ids:
            metrics.append(self._metric_entry(
                'QualityScore', cmo_id, cid, label=f'{cid}',
            ))
        return self._graph_widget(
            title=f'Quality Score – {cmo_id}',
            metrics=metrics,
            x=x, y=y, width=width, height=height,
            period=period, y_axis_label='Percent',
        )

    def build_availability_widget(
        self, cmo_id: str, contract_ids: List[str],
        x: int = 0, y: int = 0, width: int = 12, height: int = 6,
        period: int = DEFAULT_PERIOD,
    ) -> dict:
        """Line graph widget for AvailabilityPercent metric per CMO."""
        metrics = []
        for cid in contract_ids:
            metrics.append(self._metric_entry(
                'AvailabilityPercent', cmo_id, cid, label=f'{cid}',
            ))
        return self._graph_widget(
            title=f'Availability – {cmo_id}',
            metrics=metrics,
            x=x, y=y, width=width, height=height,
            period=period, y_axis_label='Percent',
        )

    def build_success_rate_widget(
        self, cmo_id: str, contract_ids: List[str],
        x: int = 0, y: int = 0, width: int = 6, height: int = 6,
        period: int = DEFAULT_PERIOD,
    ) -> dict:
        """Single-value widget for SuccessRate metric per CMO."""
        metrics = []
        for cid in contract_ids:
            metrics.append(self._metric_entry(
                'SuccessRate', cmo_id, cid, label=f'{cid}',
            ))
        return self._single_value_widget(
            title=f'Success Rate – {cmo_id}',
            metrics=metrics,
            x=x, y=y, width=width, height=height,
            period=period,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_cmo_widgets(
        self, cmo_id: str, contract_ids: List[str],
        y_start: int, period: int,
    ) -> tuple:
        """Return (widgets_list, rows_consumed) for one CMO."""
        widgets = []

        # Row 1: execution time (left) + quality score (right)
        widgets.append(self.build_execution_time_widget(
            cmo_id, contract_ids, x=0, y=y_start, width=12, height=6,
            period=period,
        ))
        widgets.append(self.build_quality_score_widget(
            cmo_id, contract_ids, x=12, y=y_start, width=12, height=6,
            period=period,
        ))

        # Row 2: availability (left) + success rate (right)
        widgets.append(self.build_availability_widget(
            cmo_id, contract_ids, x=0, y=y_start + 6, width=12, height=6,
            period=period,
        ))
        widgets.append(self.build_success_rate_widget(
            cmo_id, contract_ids, x=12, y=y_start + 6, width=6, height=6,
            period=period,
        ))

        return widgets, 12  # 2 rows × 6 height each

    def _metric_entry(
        self, metric_name: str, cmo_id: str, contract_id: str,
        label: str = '',
    ) -> list:
        """CloudWatch metric array entry."""
        entry = [
            CLOUDWATCH_NAMESPACE,
            metric_name,
            'CMOId', cmo_id,
            'ContractId', contract_id,
        ]
        props: dict = {}
        if label:
            props['label'] = label
        if props:
            entry.append(props)
        return entry

    @staticmethod
    def _text_widget(
        markdown: str, x: int, y: int, width: int, height: int,
    ) -> dict:
        return {
            'type': 'text',
            'x': x, 'y': y,
            'width': width, 'height': height,
            'properties': {'markdown': markdown},
        }

    @staticmethod
    def _graph_widget(
        title: str, metrics: list,
        x: int, y: int, width: int, height: int,
        period: int, y_axis_label: str = '',
    ) -> dict:
        props: dict = {
            'title': title,
            'metrics': metrics,
            'period': period,
            'stat': 'Average',
            'view': 'timeSeries',
            'region': DEFAULT_REGION,
        }
        if y_axis_label:
            props['yAxis'] = {'left': {'label': y_axis_label}}
        return {
            'type': 'metric',
            'x': x, 'y': y,
            'width': width, 'height': height,
            'properties': props,
        }

    @staticmethod
    def _single_value_widget(
        title: str, metrics: list,
        x: int, y: int, width: int, height: int,
        period: int,
    ) -> dict:
        return {
            'type': 'metric',
            'x': x, 'y': y,
            'width': width, 'height': height,
            'properties': {
                'title': title,
                'metrics': metrics,
                'period': period,
                'stat': 'Average',
                'view': 'singleValue',
                'region': DEFAULT_REGION,
            },
        }
