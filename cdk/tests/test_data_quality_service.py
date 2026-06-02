"""
Unit Tests for Data Quality Service – DQDL ruleset building, rule evaluation,
quality metrics generation, and pass/fail determination.

Requirements: 8.2
"""
import sys
import os

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models.data_contract import QualityRule
from services.data_quality_service import (
    DataQualityError,
    DataQualityService,
    QualityReport,
    RuleEvaluationResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rule(
    rule_id='R1',
    rule_name='Test Rule',
    rule_type='completeness',
    expression='Completeness "batch_id" > 0.99',
    threshold=99.0,
    severity='error',
) -> QualityRule:
    return QualityRule(
        rule_id=rule_id,
        rule_name=rule_name,
        rule_type=rule_type,
        expression=expression,
        threshold=threshold,
        severity=severity,
    )


def _sample_df():
    return pd.DataFrame({
        'batch_id': ['B001', 'B002', 'B003'],
        'product_name': ['Aspirin', 'Ibuprofen', 'Paracetamol'],
        'quantity': [100.0, 200.0, 150.0],
        'quality_status': ['PASS', 'FAIL', 'PASS'],
    })


@pytest.fixture
def service():
    return DataQualityService()


# ---------------------------------------------------------------------------
# build_dqdl_ruleset
# ---------------------------------------------------------------------------

class TestBuildDQDLRuleset:
    def test_single_rule(self):
        rules = [_rule(expression='Completeness "batch_id" > 0.99')]
        result = DataQualityService.build_dqdl_ruleset(rules)

        assert 'Rules = [' in result
        assert 'Completeness "batch_id" > 0.99' in result
        assert result.endswith(']')

    def test_multiple_rules(self):
        rules = [
            _rule(rule_id='R1', expression='Completeness "batch_id" > 0.99'),
            _rule(rule_id='R2', expression='Uniqueness "batch_id" > 0.99'),
            _rule(rule_id='R3', expression='ColumnValues "quality_status" in ["PASS", "FAIL", "PENDING"]'),
        ]
        result = DataQualityService.build_dqdl_ruleset(rules)

        # Verify all three rules appear in the output
        assert 'Completeness' in result
        assert 'Uniqueness' in result
        assert 'ColumnValues' in result
        # Verify the ruleset structure
        assert result.startswith('Rules = [')
        assert result.endswith(']')

    def test_empty_rules_raises(self):
        with pytest.raises(DataQualityError, match="No quality rules"):
            DataQualityService.build_dqdl_ruleset([])

    def test_preserves_expression_content(self):
        rules = [
            _rule(expression='RowCount between 1 and 1000000'),
            _rule(expression='CustomSql "SELECT COUNT(*) FROM primary" > 0'),
        ]
        result = DataQualityService.build_dqdl_ruleset(rules)

        assert 'RowCount between 1 and 1000000' in result
        assert 'CustomSql' in result


# ---------------------------------------------------------------------------
# evaluate_rules – Completeness
# ---------------------------------------------------------------------------

class TestEvaluateCompleteness:
    def test_full_completeness(self, service):
        df = _sample_df()
        rules = [_rule(threshold=99.0)]
        report = service.evaluate_rules(df, rules)

        assert report.rule_results[0].passed is True
        assert report.rule_results[0].actual_value == 100.0

    def test_partial_completeness(self, service):
        df = pd.DataFrame({'batch_id': ['B001', None, 'B003']})
        rules = [_rule(threshold=99.0)]
        report = service.evaluate_rules(df, rules)

        result = report.rule_results[0]
        assert result.passed is False
        assert 60.0 < result.actual_value < 70.0  # ~66.67%

    def test_missing_column_zero_completeness(self, service):
        df = pd.DataFrame({'other_col': [1, 2, 3]})
        rules = [_rule(expression='Completeness "batch_id" > 0.99', threshold=99.0)]
        report = service.evaluate_rules(df, rules)

        assert report.rule_results[0].actual_value == 0.0
        assert report.rule_results[0].passed is False

    def test_empty_dataframe(self, service):
        df = pd.DataFrame(columns=['batch_id'])
        rules = [_rule(threshold=50.0)]
        report = service.evaluate_rules(df, rules)

        assert report.rule_results[0].actual_value == 0.0
        assert report.rule_results[0].passed is False


# ---------------------------------------------------------------------------
# evaluate_rules – Accuracy
# ---------------------------------------------------------------------------

class TestEvaluateAccuracy:
    def test_in_list_all_match(self, service):
        df = _sample_df()
        rules = [_rule(
            rule_type='accuracy',
            expression='ColumnValues "quality_status" in ["PASS", "FAIL"]',
            threshold=99.0,
        )]
        report = service.evaluate_rules(df, rules)

        assert report.rule_results[0].passed is True
        assert report.rule_results[0].actual_value == 100.0

    def test_in_list_partial_match(self, service):
        df = _sample_df()
        rules = [_rule(
            rule_type='accuracy',
            expression='ColumnValues "quality_status" in ["PASS"]',
            threshold=99.0,
        )]
        report = service.evaluate_rules(df, rules)

        result = report.rule_results[0]
        assert result.passed is False
        assert 60.0 < result.actual_value < 70.0  # 2/3 ≈ 66.67%

    def test_matches_regex(self, service):
        df = pd.DataFrame({'batch_id': ['B001', 'B002', 'X003']})
        rules = [_rule(
            rule_type='accuracy',
            expression='ColumnValues "batch_id" matches "B\\d{3}"',
            threshold=90.0,
        )]
        report = service.evaluate_rules(df, rules)

        result = report.rule_results[0]
        assert result.passed is False  # 2/3 ≈ 66.67% < 90%

    def test_between_range(self, service):
        df = pd.DataFrame({'quantity': [50.0, 100.0, 200.0, 500.0]})
        rules = [_rule(
            rule_type='accuracy',
            expression='ColumnValues "quantity" between 0 and 300',
            threshold=70.0,
        )]
        report = service.evaluate_rules(df, rules)

        result = report.rule_results[0]
        assert result.passed is True  # 3/4 = 75% >= 70%

    def test_missing_column(self, service):
        df = pd.DataFrame({'other': [1, 2]})
        rules = [_rule(
            rule_type='accuracy',
            expression='ColumnValues "batch_id" in ["B001"]',
            threshold=50.0,
        )]
        report = service.evaluate_rules(df, rules)

        assert report.rule_results[0].actual_value == 0.0


# ---------------------------------------------------------------------------
# evaluate_rules – Uniqueness
# ---------------------------------------------------------------------------

class TestEvaluateUniqueness:
    def test_all_unique(self, service):
        df = _sample_df()
        rules = [_rule(
            rule_type='uniqueness',
            expression='Uniqueness "batch_id" > 0.99',
            threshold=99.0,
        )]
        report = service.evaluate_rules(df, rules)

        assert report.rule_results[0].passed is True
        assert report.rule_results[0].actual_value == 100.0

    def test_duplicates_present(self, service):
        df = pd.DataFrame({'batch_id': ['B001', 'B001', 'B002', 'B003']})
        rules = [_rule(
            rule_type='uniqueness',
            expression='Uniqueness "batch_id" > 0.99',
            threshold=99.0,
        )]
        report = service.evaluate_rules(df, rules)

        result = report.rule_results[0]
        assert result.passed is False
        assert result.actual_value == 75.0  # 3 unique / 4 total

    def test_missing_column(self, service):
        df = pd.DataFrame({'other': [1, 2]})
        rules = [_rule(
            rule_type='uniqueness',
            expression='Uniqueness "batch_id" > 0.99',
            threshold=50.0,
        )]
        report = service.evaluate_rules(df, rules)

        assert report.rule_results[0].actual_value == 0.0

    def test_empty_dataframe(self, service):
        df = pd.DataFrame(columns=['batch_id'])
        rules = [_rule(
            rule_type='uniqueness',
            expression='Uniqueness "batch_id" > 0.99',
            threshold=50.0,
        )]
        report = service.evaluate_rules(df, rules)

        assert report.rule_results[0].actual_value == 0.0



# ---------------------------------------------------------------------------
# evaluate_rules – Consistency
# ---------------------------------------------------------------------------

class TestEvaluateConsistency:
    def test_row_count_within_range(self, service):
        df = _sample_df()
        rules = [_rule(
            rule_type='consistency',
            expression='RowCount between 1 and 1000000',
            threshold=0.0,
        )]
        report = service.evaluate_rules(df, rules)

        assert report.rule_results[0].passed is True
        assert report.rule_results[0].actual_value == 3.0

    def test_row_count_outside_range(self, service):
        df = _sample_df()
        rules = [_rule(
            rule_type='consistency',
            expression='RowCount between 100 and 1000',
            threshold=0.0,
        )]
        report = service.evaluate_rules(df, rules)

        assert report.rule_results[0].passed is False

    def test_cross_column_comparison(self, service):
        df = pd.DataFrame({
            'start_date': [1, 2, 3],
            'end_date': [2, 3, 4],
        })
        rules = [_rule(
            rule_type='consistency',
            expression='ColumnValues "end_date" > "start_date"',
            threshold=99.0,
        )]
        report = service.evaluate_rules(df, rules)

        assert report.rule_results[0].passed is True
        assert report.rule_results[0].actual_value == 100.0

    def test_cross_column_partial_pass(self, service):
        df = pd.DataFrame({
            'start_date': [1, 5, 3],
            'end_date': [2, 3, 4],
        })
        rules = [_rule(
            rule_type='consistency',
            expression='ColumnValues "end_date" > "start_date"',
            threshold=99.0,
        )]
        report = service.evaluate_rules(df, rules)

        result = report.rule_results[0]
        assert result.passed is False
        assert 60.0 < result.actual_value < 70.0  # 2/3 ≈ 66.67%

    def test_custom_sql_skipped(self, service):
        df = _sample_df()
        rules = [_rule(
            rule_type='consistency',
            expression='CustomSql "SELECT COUNT(*) FROM primary" > 0',
            threshold=0.0,
        )]
        report = service.evaluate_rules(df, rules)

        # CustomSql can't be evaluated locally, should be skipped (pass)
        assert report.rule_results[0].passed is True


# ---------------------------------------------------------------------------
# QualityReport – Overall Metrics
# ---------------------------------------------------------------------------

class TestQualityReport:
    def test_all_rules_pass(self, service):
        df = _sample_df()
        rules = [
            _rule(rule_id='R1', threshold=99.0),
            _rule(
                rule_id='R2',
                rule_type='uniqueness',
                expression='Uniqueness "batch_id" > 0.99',
                threshold=99.0,
            ),
        ]
        report = service.evaluate_rules(df, rules)

        assert report.overall_score == 100.0
        assert report.passed is True
        assert report.rules_passed == 2
        assert report.rules_failed == 0
        assert report.warnings == 0
        assert report.errors == 0

    def test_error_rule_fails_report(self, service):
        df = pd.DataFrame({'batch_id': ['B001', None, 'B003']})
        rules = [
            _rule(rule_id='R1', severity='error', threshold=99.0),
        ]
        report = service.evaluate_rules(df, rules)

        assert report.passed is False
        assert report.errors == 1

    def test_warning_only_still_passes(self, service):
        df = pd.DataFrame({'batch_id': ['B001', None, 'B003']})
        rules = [
            _rule(rule_id='R1', severity='warning', threshold=99.0),
        ]
        report = service.evaluate_rules(df, rules)

        # Warnings don't cause overall failure
        assert report.passed is True
        assert report.warnings == 1
        assert report.errors == 0

    def test_mixed_severity(self, service):
        df = pd.DataFrame({'batch_id': ['B001', None, 'B003']})
        rules = [
            _rule(rule_id='R1', severity='warning', threshold=99.0),
            _rule(rule_id='R2', severity='error', threshold=99.0),
        ]
        report = service.evaluate_rules(df, rules)

        assert report.passed is False
        assert report.warnings == 1
        assert report.errors == 1
        assert report.overall_score == 0.0

    def test_report_to_dict(self, service):
        df = _sample_df()
        rules = [_rule()]
        report = service.evaluate_rules(df, rules)
        d = report.to_dict()

        assert 'overall_score' in d
        assert 'passed' in d
        assert 'rules_passed' in d
        assert 'rules_failed' in d
        assert 'warnings' in d
        assert 'errors' in d
        assert 'total_rules' in d
        assert 'rule_results' in d
        assert 'evaluated_at' in d
        assert len(d['rule_results']) == 1

    def test_no_rules_gives_perfect_score(self):
        report = QualityReport([])
        assert report.overall_score == 100.0
        assert report.passed is True


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_none_dataframe_raises(self, service):
        with pytest.raises(DataQualityError, match="DataFrame cannot be None"):
            service.evaluate_rules(None, [_rule()])

    def test_unknown_rule_type(self, service):
        df = _sample_df()
        rules = [_rule(rule_type='unknown')]
        report = service.evaluate_rules(df, rules)

        result = report.rule_results[0]
        assert result.passed is False
        assert 'Unknown rule type' in result.message

    def test_rule_result_to_dict(self):
        result = RuleEvaluationResult(
            rule_id='R1',
            rule_name='Test',
            rule_type='completeness',
            severity='error',
            passed=True,
            actual_value=100.0,
            threshold=99.0,
            message='OK',
        )
        d = result.to_dict()
        assert d['rule_id'] == 'R1'
        assert d['passed'] is True
        assert d['actual_value'] == 100.0
