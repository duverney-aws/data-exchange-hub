"""
Data Quality Service

AWS Glue Data Quality validation logic: builds DQDL rulesets from contract
quality rules, evaluates completeness/accuracy/uniqueness/consistency locally,
and generates quality metrics and reports.

Requirements: 8.2
"""
import logging
import re
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd

from models.data_contract import QualityRule

logger = logging.getLogger(__name__)


class DataQualityError(Exception):
    """Base exception for data quality operations."""
    pass


class RuleEvaluationResult:
    """Result of evaluating a single quality rule."""

    def __init__(
        self,
        rule_id: str,
        rule_name: str,
        rule_type: str,
        severity: str,
        passed: bool,
        actual_value: float,
        threshold: float,
        message: str,
    ):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.rule_type = rule_type
        self.severity = severity
        self.passed = passed
        self.actual_value = actual_value
        self.threshold = threshold
        self.message = message

    def to_dict(self) -> dict:
        return {
            'rule_id': self.rule_id,
            'rule_name': self.rule_name,
            'rule_type': self.rule_type,
            'severity': self.severity,
            'passed': self.passed,
            'actual_value': self.actual_value,
            'threshold': self.threshold,
            'message': self.message,
        }


class QualityReport:
    """Aggregated quality report from all rule evaluations."""

    def __init__(self, rule_results: List[RuleEvaluationResult]):
        self.rule_results = rule_results
        self.rules_passed = sum(1 for r in rule_results if r.passed)
        self.rules_failed = sum(1 for r in rule_results if not r.passed)
        self.warnings = sum(
            1 for r in rule_results if not r.passed and r.severity == 'warning'
        )
        self.errors = sum(
            1 for r in rule_results if not r.passed and r.severity == 'error'
        )
        self.overall_score = self._calculate_score()
        self.passed = self.errors == 0

    def _calculate_score(self) -> float:
        """Calculate overall quality score (0-100)."""
        if not self.rule_results:
            return 100.0
        total = len(self.rule_results)
        return round((self.rules_passed / total) * 100, 2)

    def to_dict(self) -> dict:
        return {
            'overall_score': self.overall_score,
            'passed': self.passed,
            'rules_passed': self.rules_passed,
            'rules_failed': self.rules_failed,
            'warnings': self.warnings,
            'errors': self.errors,
            'total_rules': len(self.rule_results),
            'rule_results': [r.to_dict() for r in self.rule_results],
            'evaluated_at': datetime.now(timezone.utc).isoformat(),
        }



class DataQualityService:
    """
    Service for evaluating data quality rules against DataFrames.

    Builds DQDL rulesets from QualityRule objects, evaluates rules locally
    (completeness, accuracy, uniqueness, consistency), and generates
    quality metrics reports.
    """

    # ------------------------------------------------------------------
    # DQDL Ruleset Building
    # ------------------------------------------------------------------

    @staticmethod
    def build_dqdl_ruleset(quality_rules: List[QualityRule]) -> str:
        """
        Build a DQDL ruleset string from a list of QualityRule objects.

        The output follows the AWS Glue Data Quality DQDL format::

            Rules = [
                Completeness "column_name" > 0.99,
                Uniqueness "column_name" > 0.99
            ]

        Args:
            quality_rules: List of QualityRule objects from a DataContract.

        Returns:
            DQDL ruleset string.

        Raises:
            DataQualityError: If no rules are provided.
        """
        if not quality_rules:
            raise DataQualityError("No quality rules provided")

        lines = []
        for rule in quality_rules:
            expression = rule.expression.strip()
            lines.append(f"    {expression}")

        body = ",\n".join(lines)
        return f"Rules = [\n{body}\n]"

    # ------------------------------------------------------------------
    # Rule Evaluation
    # ------------------------------------------------------------------

    def evaluate_rules(
        self,
        df: pd.DataFrame,
        quality_rules: List[QualityRule],
    ) -> QualityReport:
        """
        Evaluate all quality rules against a DataFrame.

        Args:
            df: DataFrame to validate.
            quality_rules: List of QualityRule objects.

        Returns:
            QualityReport with per-rule results and overall metrics.

        Raises:
            DataQualityError: If the DataFrame is None.
        """
        if df is None:
            raise DataQualityError("DataFrame cannot be None")

        results: List[RuleEvaluationResult] = []

        for rule in quality_rules:
            result = self._evaluate_single_rule(df, rule)
            results.append(result)

        report = QualityReport(results)
        logger.info(
            "Quality evaluation complete: score=%.1f, passed=%d, failed=%d",
            report.overall_score,
            report.rules_passed,
            report.rules_failed,
        )
        return report

    # ------------------------------------------------------------------
    # Individual Rule Evaluators
    # ------------------------------------------------------------------

    def _evaluate_single_rule(
        self,
        df: pd.DataFrame,
        rule: QualityRule,
    ) -> RuleEvaluationResult:
        """Dispatch to the appropriate evaluator based on rule_type."""
        evaluators = {
            'completeness': self._evaluate_completeness,
            'accuracy': self._evaluate_accuracy,
            'uniqueness': self._evaluate_uniqueness,
            'consistency': self._evaluate_consistency,
        }

        evaluator = evaluators.get(rule.rule_type)
        if evaluator is None:
            return RuleEvaluationResult(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                rule_type=rule.rule_type,
                severity=rule.severity,
                passed=False,
                actual_value=0.0,
                threshold=rule.threshold,
                message=f"Unknown rule type: {rule.rule_type}",
            )

        return evaluator(df, rule)

    def _evaluate_completeness(
        self, df: pd.DataFrame, rule: QualityRule,
    ) -> RuleEvaluationResult:
        """
        Evaluate completeness: percentage of non-null values in a column.

        Expects expression like: Completeness "column_name" > 0.99
        """
        column = self._extract_column_from_expression(rule.expression)

        if df.empty:
            actual = 0.0
        elif column and column in df.columns:
            non_null = df[column].notna().sum()
            actual = (non_null / len(df)) * 100
        elif column and column not in df.columns:
            actual = 0.0
        else:
            # No column specified — overall completeness across all columns
            if df.empty:
                actual = 0.0
            else:
                total_cells = df.shape[0] * df.shape[1]
                non_null_cells = df.notna().sum().sum()
                actual = (non_null_cells / total_cells) * 100 if total_cells > 0 else 0.0

        passed = bool(actual >= rule.threshold)
        return RuleEvaluationResult(
            rule_id=rule.rule_id,
            rule_name=rule.rule_name,
            rule_type=rule.rule_type,
            severity=rule.severity,
            passed=passed,
            actual_value=round(float(actual), 2),
            threshold=rule.threshold,
            message=f"Completeness of '{column}': {actual:.2f}% (threshold: {rule.threshold}%)",
        )

    def _evaluate_accuracy(
        self, df: pd.DataFrame, rule: QualityRule,
    ) -> RuleEvaluationResult:
        """
        Evaluate accuracy: values match expected patterns/ranges.

        Supports expressions like:
          - ColumnValues "col" in ["VAL1", "VAL2"]
          - ColumnValues "col" matches "regex_pattern"
          - ColumnValues "col" between 0 and 100
        """
        column = self._extract_column_from_expression(rule.expression)

        if df.empty or not column or column not in df.columns:
            actual = 0.0 if not df.empty else 100.0
            passed = bool(actual >= rule.threshold)
            return RuleEvaluationResult(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                rule_type=rule.rule_type,
                severity=rule.severity,
                passed=passed,
                actual_value=round(actual, 2),
                threshold=rule.threshold,
                message=f"Accuracy of '{column}': {actual:.2f}% (threshold: {rule.threshold}%)",
            )

        series = df[column].dropna()
        if len(series) == 0:
            actual = 100.0
        else:
            matching = self._count_matching_values(series, rule.expression)
            actual = (matching / len(series)) * 100

        passed = bool(actual >= rule.threshold)
        return RuleEvaluationResult(
            rule_id=rule.rule_id,
            rule_name=rule.rule_name,
            rule_type=rule.rule_type,
            severity=rule.severity,
            passed=passed,
            actual_value=round(float(actual), 2),
            threshold=rule.threshold,
            message=f"Accuracy of '{column}': {actual:.2f}% (threshold: {rule.threshold}%)",
        )

    def _evaluate_uniqueness(
        self, df: pd.DataFrame, rule: QualityRule,
    ) -> RuleEvaluationResult:
        """
        Evaluate uniqueness: percentage of unique values in a column.
        """
        column = self._extract_column_from_expression(rule.expression)

        if df.empty:
            actual = 0.0
        elif column and column in df.columns:
            non_null = df[column].dropna()
            if len(non_null) == 0:
                actual = 100.0
            else:
                unique_count = non_null.nunique()
                actual = (unique_count / len(non_null)) * 100
        elif column and column not in df.columns:
            actual = 0.0
        else:
            actual = 0.0

        passed = bool(actual >= rule.threshold)
        return RuleEvaluationResult(
            rule_id=rule.rule_id,
            rule_name=rule.rule_name,
            rule_type=rule.rule_type,
            severity=rule.severity,
            passed=passed,
            actual_value=round(float(actual), 2),
            threshold=rule.threshold,
            message=f"Uniqueness of '{column}': {actual:.2f}% (threshold: {rule.threshold}%)",
        )

    def _evaluate_consistency(
        self, df: pd.DataFrame, rule: QualityRule,
    ) -> RuleEvaluationResult:
        """
        Evaluate consistency: cross-column validation rules.

        Supports expressions like:
          - ColumnValues "col_a" > "col_b"  (column comparison)
          - RowCount between N and M
          - CustomSql "SELECT ..." > 0  (treated as pass if we can't execute)
        """
        expression = rule.expression.strip()

        # RowCount between N and M
        row_count_match = re.match(
            r'RowCount\s+between\s+(\d+)\s+and\s+(\d+)',
            expression,
            re.IGNORECASE,
        )
        if row_count_match:
            low = int(row_count_match.group(1))
            high = int(row_count_match.group(2))
            count = len(df)
            passed = bool(low <= count <= high)
            actual = float(count)
            return RuleEvaluationResult(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                rule_type=rule.rule_type,
                severity=rule.severity,
                passed=passed,
                actual_value=actual,
                threshold=rule.threshold,
                message=f"RowCount {count} {'within' if passed else 'outside'} [{low}, {high}]",
            )

        # Cross-column comparison: ColumnValues "col_a" > "col_b"
        cross_col_match = re.match(
            r'ColumnValues\s+"([^"]+)"\s*(>|>=|<|<=|=)\s*"([^"]+)"',
            expression,
        )
        if cross_col_match:
            col_a = cross_col_match.group(1)
            op = cross_col_match.group(2)
            col_b = cross_col_match.group(3)
            return self._evaluate_cross_column(df, rule, col_a, op, col_b)

        # Fallback: try to evaluate as a generic expression
        # For CustomSql or unrecognized patterns, we can't evaluate locally
        return RuleEvaluationResult(
            rule_id=rule.rule_id,
            rule_name=rule.rule_name,
            rule_type=rule.rule_type,
            severity=rule.severity,
            passed=True,
            actual_value=100.0,
            threshold=rule.threshold,
            message=f"Rule '{rule.rule_name}' cannot be evaluated locally (skipped)",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_column_from_expression(expression: str) -> Optional[str]:
        """Extract column name from a DQDL expression like: Completeness "col" > 0.99"""
        match = re.search(r'"([^"]+)"', expression)
        return match.group(1) if match else None

    @staticmethod
    def _count_matching_values(series: pd.Series, expression: str) -> int:
        """Count values matching the accuracy expression pattern."""
        # ColumnValues "col" in ["VAL1", "VAL2", ...]
        in_match = re.search(
            r'\bin\s*\[([^\]]+)\]', expression, re.IGNORECASE,
        )
        if in_match:
            raw_values = in_match.group(1)
            allowed = [
                v.strip().strip('"').strip("'")
                for v in raw_values.split(',')
            ]
            return int(series.isin(allowed).sum())

        # ColumnValues "col" matches "pattern"
        matches_match = re.search(
            r'\bmatches\s+"([^"]+)"', expression, re.IGNORECASE,
        )
        if matches_match:
            pattern = matches_match.group(1)
            try:
                return int(series.astype(str).str.fullmatch(pattern).sum())
            except re.error:
                return 0

        # ColumnValues "col" between N and M
        between_match = re.search(
            r'\bbetween\s+([\d.]+)\s+and\s+([\d.]+)', expression, re.IGNORECASE,
        )
        if between_match:
            low = float(between_match.group(1))
            high = float(between_match.group(2))
            numeric = pd.to_numeric(series, errors='coerce')
            return int(((numeric >= low) & (numeric <= high)).sum())

        # Fallback: all values pass
        return len(series)

    def _evaluate_cross_column(
        self,
        df: pd.DataFrame,
        rule: QualityRule,
        col_a: str,
        op: str,
        col_b: str,
    ) -> RuleEvaluationResult:
        """Evaluate a cross-column comparison rule."""
        if df.empty or col_a not in df.columns or col_b not in df.columns:
            actual = 0.0 if not df.empty else 100.0
            return RuleEvaluationResult(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                rule_type=rule.rule_type,
                severity=rule.severity,
                passed=bool(actual >= rule.threshold),
                actual_value=round(float(actual), 2),
                threshold=rule.threshold,
                message=f"Cross-column check '{col_a}' {op} '{col_b}': {actual:.2f}%",
            )

        ops = {
            '>': lambda a, b: a > b,
            '>=': lambda a, b: a >= b,
            '<': lambda a, b: a < b,
            '<=': lambda a, b: a <= b,
            '=': lambda a, b: a == b,
        }
        comparator = ops.get(op, lambda a, b: a == b)

        mask = df[[col_a, col_b]].notna().all(axis=1)
        valid_rows = df[mask]
        if len(valid_rows) == 0:
            actual = 100.0
        else:
            matching = comparator(valid_rows[col_a], valid_rows[col_b]).sum()
            actual = (matching / len(valid_rows)) * 100

        passed = bool(actual >= rule.threshold)
        return RuleEvaluationResult(
            rule_id=rule.rule_id,
            rule_name=rule.rule_name,
            rule_type=rule.rule_type,
            severity=rule.severity,
            passed=passed,
            actual_value=round(float(actual), 2),
            threshold=rule.threshold,
            message=f"Cross-column check '{col_a}' {op} '{col_b}': {actual:.2f}% (threshold: {rule.threshold}%)",
        )
