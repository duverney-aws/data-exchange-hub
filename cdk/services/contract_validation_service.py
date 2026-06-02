"""
Contract Validation Service

Validates data contract components including schema definitions, quality rules,
SLA thresholds, delivery schedules, and governance settings. Generates unique
contract IDs in the format CMO-{NAME}-{DOMAIN}-{NUMBER}.

Requirements: 2.1, 2.4, 2.5, 2.6
"""
import logging
import re
from typing import List, Tuple

from utils.contract_utils import generate_contract_id as _generate_contract_id

logger = logging.getLogger(__name__)

# Valid DQDL keywords recognised by AWS Glue Data Quality
VALID_DQDL_KEYWORDS = {
    'ColumnExists',
    'ColumnValues',
    'Completeness',
    'Uniqueness',
    'RowCount',
    'CustomSql',
    'IsComplete',
    'IsUnique',
    'IsPrimaryKey',
    'ColumnDataType',
    'ColumnNamesMatchPattern',
    'ColumnCorrelation',
    'StandardDeviation',
    'Mean',
    'Sum',
    'Entropy',
    'DistinctValuesCount',
    'UniqueValueRatio',
    'DataFreshness',
    'ReferentialIntegrity',
    'DatasetMatch',
    'SchemaMatch',
    'AggregateMatch',
    'RowCountMatch',
}

# Allowed delivery frequencies
ALLOWED_FREQUENCIES = {'real-time', 'hourly', 'daily', 'weekly', 'monthly'}

# Valid data classifications for governance
VALID_DATA_CLASSIFICATIONS = {'public', 'internal', 'confidential', 'restricted'}

# Valid quality-rule types
VALID_RULE_TYPES = {'completeness', 'accuracy', 'uniqueness', 'consistency'}

# Valid severity levels
VALID_SEVERITIES = {'warning', 'error'}


class ContractValidationError(Exception):
    """Raised when contract validation fails."""
    pass


class ContractValidationService:
    """
    Service for validating data contract components.

    Validates schema definitions, quality rules (DQDL), SLA thresholds,
    delivery schedules, and governance settings before a contract is persisted.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_contract(self, data: dict) -> Tuple[bool, List[str]]:
        """
        Validate that all required contract components are present and valid.

        Args:
            data: Dictionary representing the full data contract payload.

        Returns:
            Tuple of (is_valid, list_of_error_messages).
        """
        errors: List[str] = []

        # --- Required top-level fields ---
        required_fields = [
            'cmoId', 'dataDomain', 'schemaId', 'schemaVersion',
            'qualityRules', 'sla', 'deliverySchedule', 'governance',
        ]
        for field in required_fields:
            if field not in data or data[field] is None:
                errors.append(f"Missing required field: {field}")

        # If critical fields are missing, return early – deeper checks would fail.
        if errors:
            return False, errors

        # --- Validate each component ---
        valid, rule_errors = self.validate_quality_rules(data['qualityRules'])
        errors.extend(rule_errors)

        valid, sla_errors = self.validate_sla(data['sla'])
        errors.extend(sla_errors)

        valid, delivery_errors = self.validate_delivery_schedule(data['deliverySchedule'])
        errors.extend(delivery_errors)

        valid, gov_errors = self.validate_governance(data['governance'])
        errors.extend(gov_errors)

        # --- Lightweight field checks ---
        if not isinstance(data.get('cmoId'), str) or not data['cmoId'].strip():
            errors.append("cmoId must be a non-empty string")

        if not isinstance(data.get('dataDomain'), str) or not data['dataDomain'].strip():
            errors.append("dataDomain must be a non-empty string")

        if not isinstance(data.get('schemaId'), str) or not data['schemaId'].strip():
            errors.append("schemaId must be a non-empty string")

        if not isinstance(data.get('schemaVersion'), str) or not data['schemaVersion'].strip():
            errors.append("schemaVersion must be a non-empty string")

        is_valid = len(errors) == 0
        return is_valid, errors

    def validate_quality_rules(self, rules: list) -> Tuple[bool, List[str]]:
        """
        Validate that each quality rule has required fields and a valid DQDL expression.

        Args:
            rules: List of quality-rule dictionaries.

        Returns:
            Tuple of (is_valid, list_of_error_messages).
        """
        errors: List[str] = []

        if not isinstance(rules, list):
            return False, ["qualityRules must be a list"]

        if len(rules) == 0:
            return False, ["qualityRules must contain at least one rule"]

        for idx, rule in enumerate(rules):
            prefix = f"qualityRules[{idx}]"

            if not isinstance(rule, dict):
                errors.append(f"{prefix}: must be a dictionary")
                continue

            # Required fields
            for field in ('ruleId', 'ruleName', 'ruleType', 'expression', 'threshold', 'severity'):
                if field not in rule or rule[field] is None:
                    errors.append(f"{prefix}: missing required field '{field}'")

            # Rule type validation
            rule_type = rule.get('ruleType')
            if rule_type is not None and rule_type not in VALID_RULE_TYPES:
                errors.append(
                    f"{prefix}: invalid ruleType '{rule_type}'. "
                    f"Must be one of {sorted(VALID_RULE_TYPES)}"
                )

            # Threshold validation
            threshold = rule.get('threshold')
            if threshold is not None:
                if not isinstance(threshold, (int, float)):
                    errors.append(f"{prefix}: threshold must be a number")
                elif not (0 <= threshold <= 100):
                    errors.append(f"{prefix}: threshold must be between 0 and 100")

            # Severity validation
            severity = rule.get('severity')
            if severity is not None and severity not in VALID_SEVERITIES:
                errors.append(
                    f"{prefix}: invalid severity '{severity}'. "
                    f"Must be one of {sorted(VALID_SEVERITIES)}"
                )

            # DQDL expression validation
            expression = rule.get('expression')
            if expression is not None and isinstance(expression, str) and expression.strip():
                if not self._is_valid_dqdl(expression):
                    errors.append(
                        f"{prefix}: expression is not valid DQDL. "
                        f"Must start with a recognised DQDL keyword "
                        f"(e.g. Completeness, ColumnExists, Uniqueness, …)"
                    )

        is_valid = len(errors) == 0
        return is_valid, errors

    def validate_sla(self, sla: dict) -> Tuple[bool, List[str]]:
        """
        Validate SLA thresholds are measurable.

        Checks:
        - timeliness.maxDelayHours is a positive number
        - availability.uptimePercentage is between 0 and 100
        - quality.minQualityScore is between 0 and 100
        - Each section has a non-empty measurementWindow

        Args:
            sla: Dictionary representing the SLA component.

        Returns:
            Tuple of (is_valid, list_of_error_messages).
        """
        errors: List[str] = []

        if not isinstance(sla, dict):
            return False, ["sla must be a dictionary"]

        # --- timeliness ---
        timeliness = sla.get('timeliness')
        if timeliness is None:
            errors.append("sla: missing required section 'timeliness'")
        elif not isinstance(timeliness, dict):
            errors.append("sla.timeliness must be a dictionary")
        else:
            max_delay = timeliness.get('maxDelayHours')
            if max_delay is None:
                errors.append("sla.timeliness: missing 'maxDelayHours'")
            elif not isinstance(max_delay, (int, float)) or max_delay <= 0:
                errors.append("sla.timeliness.maxDelayHours must be a positive number")

            self._validate_measurement_window(timeliness, 'sla.timeliness', errors)

        # --- availability ---
        availability = sla.get('availability')
        if availability is None:
            errors.append("sla: missing required section 'availability'")
        elif not isinstance(availability, dict):
            errors.append("sla.availability must be a dictionary")
        else:
            uptime = availability.get('uptimePercentage')
            if uptime is None:
                errors.append("sla.availability: missing 'uptimePercentage'")
            elif not isinstance(uptime, (int, float)) or not (0 <= uptime <= 100):
                errors.append("sla.availability.uptimePercentage must be between 0 and 100")

            self._validate_measurement_window(availability, 'sla.availability', errors)

        # --- quality ---
        quality = sla.get('quality')
        if quality is None:
            errors.append("sla: missing required section 'quality'")
        elif not isinstance(quality, dict):
            errors.append("sla.quality must be a dictionary")
        else:
            min_score = quality.get('minQualityScore')
            if min_score is None:
                errors.append("sla.quality: missing 'minQualityScore'")
            elif not isinstance(min_score, (int, float)) or not (0 <= min_score <= 100):
                errors.append("sla.quality.minQualityScore must be between 0 and 100")

            self._validate_measurement_window(quality, 'sla.quality', errors)

        is_valid = len(errors) == 0
        return is_valid, errors

    def validate_delivery_schedule(self, schedule: dict) -> Tuple[bool, List[str]]:
        """
        Validate delivery schedule frequency and optional cron expression.

        Args:
            schedule: Dictionary representing the delivery schedule.

        Returns:
            Tuple of (is_valid, list_of_error_messages).
        """
        errors: List[str] = []

        if not isinstance(schedule, dict):
            return False, ["deliverySchedule must be a dictionary"]

        frequency = schedule.get('frequency')
        if frequency is None:
            errors.append("deliverySchedule: missing required field 'frequency'")
        elif frequency not in ALLOWED_FREQUENCIES:
            errors.append(
                f"deliverySchedule: invalid frequency '{frequency}'. "
                f"Must be one of {sorted(ALLOWED_FREQUENCIES)}"
            )

        # Validate cron expression if provided
        cron = schedule.get('cronExpression')
        if cron is not None:
            if not isinstance(cron, str) or not cron.strip():
                errors.append("deliverySchedule: cronExpression must be a non-empty string")
            elif not self._is_valid_cron(cron):
                errors.append(
                    "deliverySchedule: cronExpression is not a valid cron format. "
                    "Expected 5 or 6 space-separated fields"
                )

        is_valid = len(errors) == 0
        return is_valid, errors

    def validate_governance(self, governance: dict) -> Tuple[bool, List[str]]:
        """
        Validate governance settings have required fields with valid values.

        Args:
            governance: Dictionary representing governance settings.

        Returns:
            Tuple of (is_valid, list_of_error_messages).
        """
        errors: List[str] = []

        if not isinstance(governance, dict):
            return False, ["governance must be a dictionary"]

        # dataClassification
        classification = governance.get('dataClassification')
        if classification is None:
            errors.append("governance: missing required field 'dataClassification'")
        elif classification not in VALID_DATA_CLASSIFICATIONS:
            errors.append(
                f"governance: invalid dataClassification '{classification}'. "
                f"Must be one of {sorted(VALID_DATA_CLASSIFICATIONS)}"
            )

        # retentionYears
        retention = governance.get('retentionYears')
        if retention is None:
            errors.append("governance: missing required field 'retentionYears'")
        elif not isinstance(retention, int) or retention <= 0:
            errors.append("governance: retentionYears must be a positive integer")

        # allowedUsers
        allowed_users = governance.get('allowedUsers')
        if allowed_users is None:
            errors.append("governance: missing required field 'allowedUsers'")
        elif not isinstance(allowed_users, list):
            errors.append("governance: allowedUsers must be a list")

        # allowedGroups
        allowed_groups = governance.get('allowedGroups')
        if allowed_groups is None:
            errors.append("governance: missing required field 'allowedGroups'")
        elif not isinstance(allowed_groups, list):
            errors.append("governance: allowedGroups must be a list")

        # piiFields
        pii_fields = governance.get('piiFields')
        if pii_fields is None:
            errors.append("governance: missing required field 'piiFields'")
        elif not isinstance(pii_fields, list):
            errors.append("governance: piiFields must be a list")

        # encryptionRequired
        encryption = governance.get('encryptionRequired')
        if encryption is None:
            errors.append("governance: missing required field 'encryptionRequired'")
        elif not isinstance(encryption, bool):
            errors.append("governance: encryptionRequired must be a boolean")

        is_valid = len(errors) == 0
        return is_valid, errors

    def generate_contract_id(
        self, cmo_name: str, data_domain: str, existing_count: int
    ) -> str:
        """
        Generate a unique contract ID in format CMO-{NAME}-{DOMAIN}-{NUMBER}.

        Wraps the utility function with number = existing_count + 1.

        Args:
            cmo_name: CMO organisation name.
            data_domain: Data domain identifier (e.g. 'batch-records').
            existing_count: Number of existing contracts for this CMO/domain.

        Returns:
            Contract ID string.
        """
        return _generate_contract_id(cmo_name, data_domain, existing_count + 1)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_valid_dqdl(expression: str) -> bool:
        """Return True if *expression* starts with a recognised DQDL keyword."""
        expression = expression.strip()
        for keyword in VALID_DQDL_KEYWORDS:
            if expression.startswith(keyword):
                return True
        return False

    @staticmethod
    def _is_valid_cron(cron: str) -> bool:
        """Basic cron validation – expects 5 or 6 space-separated fields."""
        parts = cron.strip().split()
        return len(parts) in (5, 6)

    @staticmethod
    def _validate_measurement_window(
        section: dict, path: str, errors: List[str]
    ) -> None:
        """Ensure *measurementWindow* is a non-empty string."""
        window = section.get('measurementWindow')
        if window is None:
            errors.append(f"{path}: missing 'measurementWindow'")
        elif not isinstance(window, str) or not window.strip():
            errors.append(f"{path}: measurementWindow must be a non-empty string")
