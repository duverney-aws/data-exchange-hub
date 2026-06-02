"""
Unit tests for ContractValidationService.

Covers: validate_contract, validate_quality_rules, validate_sla,
        validate_delivery_schedule, validate_governance, generate_contract_id.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.contract_validation_service import (
    ContractValidationService,
    ContractValidationError,
    VALID_DQDL_KEYWORDS,
    ALLOWED_FREQUENCIES,
    VALID_DATA_CLASSIFICATIONS,
)


@pytest.fixture
def service():
    return ContractValidationService()


def _valid_quality_rule():
    return {
        'ruleId': 'rule-001',
        'ruleName': 'Batch ID completeness',
        'ruleType': 'completeness',
        'expression': 'Completeness "batch_id" > 0.99',
        'threshold': 99.0,
        'severity': 'error',
    }


def _valid_sla():
    return {
        'timeliness': {'maxDelayHours': 24, 'measurementWindow': 'monthly'},
        'availability': {'uptimePercentage': 99.5, 'measurementWindow': 'monthly'},
        'quality': {'minQualityScore': 95.0, 'measurementWindow': 'monthly'},
    }


def _valid_delivery_schedule():
    return {'frequency': 'daily', 'cronExpression': '0 2 * * *', 'timezone': 'UTC'}


def _valid_governance():
    return {
        'dataClassification': 'confidential',
        'retentionYears': 7,
        'allowedUsers': ['user-a'],
        'allowedGroups': ['group-a'],
        'piiFields': ['email'],
        'encryptionRequired': True,
    }


def _valid_contract():
    return {
        'cmoId': 'cmo-alpha',
        'dataDomain': 'batch-records',
        'schemaId': 'schema-001',
        'schemaVersion': '1.0',
        'qualityRules': [_valid_quality_rule()],
        'sla': _valid_sla(),
        'deliverySchedule': _valid_delivery_schedule(),
        'governance': _valid_governance(),
    }


# ---------------------------------------------------------------
# validate_contract
# ---------------------------------------------------------------

class TestValidateContract:
    def test_valid_contract_passes(self, service):
        is_valid, errors = service.validate_contract(_valid_contract())
        assert is_valid is True
        assert errors == []

    def test_missing_required_fields(self, service):
        is_valid, errors = service.validate_contract({})
        assert is_valid is False
        assert len(errors) == 8  # all 8 required fields missing

    def test_missing_single_field(self, service):
        data = _valid_contract()
        del data['sla']
        is_valid, errors = service.validate_contract(data)
        assert is_valid is False
        assert any('sla' in e for e in errors)

    def test_empty_cmo_id_rejected(self, service):
        data = _valid_contract()
        data['cmoId'] = '   '
        is_valid, errors = service.validate_contract(data)
        assert is_valid is False
        assert any('cmoId' in e for e in errors)

    def test_none_field_treated_as_missing(self, service):
        data = _valid_contract()
        data['schemaId'] = None
        is_valid, errors = service.validate_contract(data)
        assert is_valid is False


# ---------------------------------------------------------------
# validate_quality_rules
# ---------------------------------------------------------------

class TestValidateQualityRules:
    def test_valid_rules(self, service):
        is_valid, errors = service.validate_quality_rules([_valid_quality_rule()])
        assert is_valid is True
        assert errors == []

    def test_empty_list_rejected(self, service):
        is_valid, errors = service.validate_quality_rules([])
        assert is_valid is False
        assert any('at least one' in e for e in errors)

    def test_not_a_list_rejected(self, service):
        is_valid, errors = service.validate_quality_rules("not-a-list")
        assert is_valid is False

    def test_missing_rule_fields(self, service):
        is_valid, errors = service.validate_quality_rules([{}])
        assert is_valid is False
        assert len(errors) >= 6  # all required fields missing

    def test_invalid_rule_type(self, service):
        rule = _valid_quality_rule()
        rule['ruleType'] = 'invalid-type'
        is_valid, errors = service.validate_quality_rules([rule])
        assert is_valid is False
        assert any('ruleType' in e for e in errors)

    def test_threshold_out_of_range(self, service):
        rule = _valid_quality_rule()
        rule['threshold'] = 150
        is_valid, errors = service.validate_quality_rules([rule])
        assert is_valid is False
        assert any('threshold' in e for e in errors)

    def test_invalid_dqdl_expression(self, service):
        rule = _valid_quality_rule()
        rule['expression'] = 'SELECT * FROM table'
        is_valid, errors = service.validate_quality_rules([rule])
        assert is_valid is False
        assert any('DQDL' in e for e in errors)

    def test_valid_dqdl_keywords(self, service):
        """Each recognised DQDL keyword should pass expression validation."""
        for keyword in ['Completeness', 'ColumnExists', 'Uniqueness', 'RowCount',
                        'CustomSql', 'IsComplete', 'IsUnique', 'ColumnValues']:
            rule = _valid_quality_rule()
            rule['expression'] = f'{keyword} "col" > 0.9'
            is_valid, errors = service.validate_quality_rules([rule])
            assert is_valid is True, f"Keyword {keyword} should be valid"

    def test_invalid_severity(self, service):
        rule = _valid_quality_rule()
        rule['severity'] = 'critical'
        is_valid, errors = service.validate_quality_rules([rule])
        assert is_valid is False
        assert any('severity' in e for e in errors)


# ---------------------------------------------------------------
# validate_sla
# ---------------------------------------------------------------

class TestValidateSLA:
    def test_valid_sla(self, service):
        is_valid, errors = service.validate_sla(_valid_sla())
        assert is_valid is True
        assert errors == []

    def test_not_a_dict_rejected(self, service):
        is_valid, errors = service.validate_sla("bad")
        assert is_valid is False

    def test_missing_timeliness(self, service):
        sla = _valid_sla()
        del sla['timeliness']
        is_valid, errors = service.validate_sla(sla)
        assert is_valid is False
        assert any('timeliness' in e for e in errors)

    def test_negative_max_delay(self, service):
        sla = _valid_sla()
        sla['timeliness']['maxDelayHours'] = -1
        is_valid, errors = service.validate_sla(sla)
        assert is_valid is False
        assert any('maxDelayHours' in e for e in errors)

    def test_zero_max_delay_rejected(self, service):
        sla = _valid_sla()
        sla['timeliness']['maxDelayHours'] = 0
        is_valid, errors = service.validate_sla(sla)
        assert is_valid is False

    def test_uptime_over_100_rejected(self, service):
        sla = _valid_sla()
        sla['availability']['uptimePercentage'] = 101
        is_valid, errors = service.validate_sla(sla)
        assert is_valid is False

    def test_quality_score_negative_rejected(self, service):
        sla = _valid_sla()
        sla['quality']['minQualityScore'] = -5
        is_valid, errors = service.validate_sla(sla)
        assert is_valid is False

    def test_missing_measurement_window(self, service):
        sla = _valid_sla()
        del sla['timeliness']['measurementWindow']
        is_valid, errors = service.validate_sla(sla)
        assert is_valid is False
        assert any('measurementWindow' in e for e in errors)

    def test_empty_measurement_window_rejected(self, service):
        sla = _valid_sla()
        sla['availability']['measurementWindow'] = '   '
        is_valid, errors = service.validate_sla(sla)
        assert is_valid is False

    def test_boundary_values_accepted(self, service):
        sla = _valid_sla()
        sla['availability']['uptimePercentage'] = 0
        sla['quality']['minQualityScore'] = 100
        is_valid, errors = service.validate_sla(sla)
        assert is_valid is True


# ---------------------------------------------------------------
# validate_delivery_schedule
# ---------------------------------------------------------------

class TestValidateDeliverySchedule:
    def test_valid_schedule(self, service):
        is_valid, errors = service.validate_delivery_schedule(_valid_delivery_schedule())
        assert is_valid is True
        assert errors == []

    def test_not_a_dict_rejected(self, service):
        is_valid, errors = service.validate_delivery_schedule([])
        assert is_valid is False

    def test_missing_frequency(self, service):
        is_valid, errors = service.validate_delivery_schedule({'timezone': 'UTC'})
        assert is_valid is False
        assert any('frequency' in e for e in errors)

    def test_invalid_frequency(self, service):
        is_valid, errors = service.validate_delivery_schedule({'frequency': 'biweekly'})
        assert is_valid is False
        assert any('frequency' in e for e in errors)

    def test_all_allowed_frequencies(self, service):
        for freq in ALLOWED_FREQUENCIES:
            is_valid, errors = service.validate_delivery_schedule({'frequency': freq})
            assert is_valid is True, f"Frequency '{freq}' should be valid"

    def test_invalid_cron_expression(self, service):
        schedule = {'frequency': 'daily', 'cronExpression': 'bad'}
        is_valid, errors = service.validate_delivery_schedule(schedule)
        assert is_valid is False
        assert any('cronExpression' in e for e in errors)

    def test_valid_5_field_cron(self, service):
        schedule = {'frequency': 'daily', 'cronExpression': '0 2 * * *'}
        is_valid, errors = service.validate_delivery_schedule(schedule)
        assert is_valid is True

    def test_valid_6_field_cron(self, service):
        schedule = {'frequency': 'daily', 'cronExpression': '0 2 * * * 2024'}
        is_valid, errors = service.validate_delivery_schedule(schedule)
        assert is_valid is True

    def test_no_cron_is_fine(self, service):
        schedule = {'frequency': 'real-time'}
        is_valid, errors = service.validate_delivery_schedule(schedule)
        assert is_valid is True


# ---------------------------------------------------------------
# validate_governance
# ---------------------------------------------------------------

class TestValidateGovernance:
    def test_valid_governance(self, service):
        is_valid, errors = service.validate_governance(_valid_governance())
        assert is_valid is True
        assert errors == []

    def test_not_a_dict_rejected(self, service):
        is_valid, errors = service.validate_governance("bad")
        assert is_valid is False

    def test_missing_all_fields(self, service):
        is_valid, errors = service.validate_governance({})
        assert is_valid is False
        assert len(errors) == 6  # all 6 required fields

    def test_invalid_classification(self, service):
        gov = _valid_governance()
        gov['dataClassification'] = 'top-secret'
        is_valid, errors = service.validate_governance(gov)
        assert is_valid is False

    def test_all_valid_classifications(self, service):
        for cls in VALID_DATA_CLASSIFICATIONS:
            gov = _valid_governance()
            gov['dataClassification'] = cls
            is_valid, errors = service.validate_governance(gov)
            assert is_valid is True, f"Classification '{cls}' should be valid"

    def test_zero_retention_rejected(self, service):
        gov = _valid_governance()
        gov['retentionYears'] = 0
        is_valid, errors = service.validate_governance(gov)
        assert is_valid is False

    def test_float_retention_rejected(self, service):
        gov = _valid_governance()
        gov['retentionYears'] = 7.5
        is_valid, errors = service.validate_governance(gov)
        assert is_valid is False

    def test_encryption_non_bool_rejected(self, service):
        gov = _valid_governance()
        gov['encryptionRequired'] = 'yes'
        is_valid, errors = service.validate_governance(gov)
        assert is_valid is False


# ---------------------------------------------------------------
# generate_contract_id
# ---------------------------------------------------------------

class TestGenerateContractId:
    def test_basic_generation(self, service):
        cid = service.generate_contract_id('alpha', 'batch-records', 0)
        assert cid == 'CMO-ALPHA-BATCH-RECORDS-001'

    def test_increments_count(self, service):
        cid = service.generate_contract_id('alpha', 'batch-records', 5)
        assert cid == 'CMO-ALPHA-BATCH-RECORDS-006'

    def test_uppercase_conversion(self, service):
        cid = service.generate_contract_id('beta pharma', 'quality-data', 0)
        assert 'BETA-PHARMA' in cid
        assert cid.startswith('CMO-')
