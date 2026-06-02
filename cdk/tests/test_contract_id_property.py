"""
Property-Based Tests for Data Contract ID Format Compliance

Feature: pharma-data-exchange-hub, Property 7: Contract ID Format Compliance

This test validates that for any data contract saved to DynamoDB, the contract ID 
follows the format CMO-{NAME}-{DOMAIN}-{NUMBER} where NAME is uppercase, DOMAIN is 
the data domain, and NUMBER is a sequential integer.

Validates: Requirements 2.4
"""
import re
from datetime import datetime
from hypothesis import given, strategies as st, settings
import pytest

from models.data_contract import DataContract, QualityRule, SLA, DeliverySchedule, Governance
from utils.contract_utils import generate_contract_id, validate_contract_id_format, parse_contract_id


# Custom strategies for generating test data
@st.composite
def cmo_name_strategy(draw):
    """Generate valid CMO names (must contain at least one alphanumeric character)"""
    # Ensure at least one alphanumeric character
    alpha_chars = draw(st.lists(
        st.sampled_from('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'),
        min_size=1,
        max_size=10
    ))
    # Optionally add spaces and hyphens
    extra_chars = draw(st.lists(
        st.sampled_from('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- '),
        min_size=0,
        max_size=10
    ))
    name = ''.join(alpha_chars + extra_chars).strip()
    if not name:
        name = 'A'
    return name


@st.composite
def data_domain_strategy(draw):
    """Generate valid data domain names (lowercase alphanumeric with hyphens)"""
    # Common data domains in pharma
    common_domains = [
        'batch-records',
        'quality-data',
        'manufacturing-data',
        'test-results',
        'stability-data',
        'raw-materials',
        'finished-products',
        'equipment-logs',
        'environmental-monitoring',
        'deviation-reports'
    ]
    
    # 80% of the time use a common domain, 20% generate random
    use_common = draw(st.booleans())
    if use_common and draw(st.integers(0, 100)) < 80:
        return draw(st.sampled_from(common_domains))
    else:
        # Generate random domain name
        length = draw(st.integers(min_value=1, max_value=30))
        chars = draw(st.lists(
            st.sampled_from('abcdefghijklmnopqrstuvwxyz0123456789-'),
            min_size=length,
            max_size=length
        ))
        domain = ''.join(chars).strip('-')
        if not domain:
            domain = 'data'
        return domain


@st.composite
def quality_rule_strategy(draw):
    """Generate a valid quality rule"""
    rule_types = ['completeness', 'accuracy', 'uniqueness', 'consistency']
    severities = ['warning', 'error']
    
    return QualityRule(
        rule_id=f"rule-{draw(st.integers(min_value=1, max_value=999))}",
        rule_name=draw(st.text(min_size=5, max_size=50)),
        rule_type=draw(st.sampled_from(rule_types)),
        expression=f"ColumnExists \"{draw(st.text(min_size=1, max_size=20))}\"",
        threshold=draw(st.floats(min_value=0.0, max_value=100.0)),
        severity=draw(st.sampled_from(severities))
    )


@st.composite
def sla_strategy(draw):
    """Generate a valid SLA"""
    return SLA(
        timeliness={
            'maxDelayHours': draw(st.integers(min_value=1, max_value=168)),
            'measurementWindow': 'daily'
        },
        availability={
            'uptimePercentage': draw(st.floats(min_value=90.0, max_value=99.99)),
            'measurementWindow': 'monthly'
        },
        quality={
            'minQualityScore': draw(st.floats(min_value=80.0, max_value=100.0)),
            'measurementWindow': 'daily'
        }
    )


@st.composite
def delivery_schedule_strategy(draw):
    """Generate a valid delivery schedule"""
    frequencies = ['real-time', 'hourly', 'daily', 'weekly', 'monthly']
    return DeliverySchedule(
        frequency=draw(st.sampled_from(frequencies)),
        cron_expression=None,
        timezone='UTC'
    )


@st.composite
def governance_strategy(draw):
    """Generate valid governance settings"""
    classifications = ['public', 'internal', 'confidential', 'restricted']
    return Governance(
        data_classification=draw(st.sampled_from(classifications)),
        retention_years=draw(st.integers(min_value=1, max_value=10)),
        allowed_users=[],
        allowed_groups=[],
        pii_fields=[],
        encryption_required=True
    )


# Feature: pharma-data-exchange-hub, Property 7: Contract ID Format Compliance
@settings(max_examples=100)
@given(
    cmo_name=cmo_name_strategy(),
    data_domain=data_domain_strategy(),
    number=st.integers(min_value=1, max_value=999)
)
def test_contract_id_format_compliance(cmo_name, data_domain, number):
    """
    Property 7: Contract ID Format Compliance
    
    For any data contract saved to DynamoDB, the contract ID should follow 
    the format CMO-{NAME}-{DOMAIN}-{NUMBER} where NAME is uppercase, DOMAIN 
    is the data domain, and NUMBER is a sequential integer.
    
    Validates: Requirements 2.4
    """
    # Generate contract ID using the utility function
    contract_id = generate_contract_id(cmo_name, data_domain, number)
    
    # Property 1: Contract ID must start with "CMO-"
    assert contract_id.startswith('CMO-'), \
        f"Contract ID must start with 'CMO-', got: {contract_id}"
    
    # Property 2: Contract ID must have exactly 4 parts separated by hyphens
    # Note: data_domain can contain hyphens, so we need to be more flexible
    parts = contract_id.split('-')
    assert len(parts) >= 4, \
        f"Contract ID must have at least 4 parts, got {len(parts)}: {contract_id}"
    
    # Property 3: First part must be "CMO"
    assert parts[0] == 'CMO', \
        f"First part must be 'CMO', got: {parts[0]}"
    
    # Property 4: CMO name part (second part) must be uppercase
    cmo_name_part = parts[1]
    assert cmo_name_part.isupper() or cmo_name_part.isdigit() or '-' in cmo_name_part, \
        f"CMO name must be uppercase, got: {cmo_name_part}"
    
    # Property 5: Last part must be a 3-digit number
    number_part = parts[-1]
    assert len(number_part) == 3, \
        f"Number part must be 3 digits, got: {number_part}"
    assert number_part.isdigit(), \
        f"Number part must be numeric, got: {number_part}"
    assert int(number_part) == number, \
        f"Number part must match input number {number}, got: {int(number_part)}"
    
    # Property 6: Number must be zero-padded
    expected_number = str(number).zfill(3)
    assert number_part == expected_number, \
        f"Number must be zero-padded to 3 digits, expected {expected_number}, got: {number_part}"
    
    # Property 7: Data domain must be present (everything between CMO name and number)
    domain_parts = parts[2:-1]
    assert len(domain_parts) > 0, \
        f"Data domain must be present in contract ID: {contract_id}"
    
    # Property 8: Contract ID must match the expected format pattern
    assert validate_contract_id_format(contract_id), \
        f"Contract ID must match format pattern CMO-{{NAME}}-{{DOMAIN}}-{{NUMBER}}: {contract_id}"
    
    # Property 9: Contract ID must be parseable back to components
    parsed = parse_contract_id(contract_id)
    assert parsed is not None, \
        f"Contract ID must be parseable: {contract_id}"
    assert parsed['number'] == number, \
        f"Parsed number must match original: expected {number}, got {parsed['number']}"


@settings(max_examples=100)
@given(
    cmo_name=cmo_name_strategy(),
    data_domain=data_domain_strategy(),
    number=st.integers(min_value=1, max_value=999),
    quality_rules=st.lists(quality_rule_strategy(), min_size=1, max_size=5),
    sla=sla_strategy(),
    delivery_schedule=delivery_schedule_strategy(),
    governance=governance_strategy()
)
def test_data_contract_with_valid_contract_id(
    cmo_name, data_domain, number, quality_rules, sla, delivery_schedule, governance
):
    """
    Property 7 (Extended): Data Contract Creation with Valid Contract ID
    
    For any data contract created with valid components, the contract ID 
    should follow the required format and the contract should be serializable 
    to DynamoDB format.
    
    Validates: Requirements 2.4
    """
    # Generate contract ID
    contract_id = generate_contract_id(cmo_name, data_domain, number)
    
    # Create a data contract with the generated ID
    cmo_id = f"cmo-{cmo_name.lower().replace(' ', '-')}"
    now = datetime.now()
    
    contract = DataContract(
        contract_id=contract_id,
        cmo_id=cmo_id,
        data_domain=data_domain,
        schema_id=f"schema-{data_domain}",
        schema_version="1.0",
        quality_rules=quality_rules,
        sla=sla,
        delivery_schedule=delivery_schedule,
        governance=governance,
        status='draft',
        created_at=now,
        updated_at=now
    )
    
    # Property 1: Contract ID must follow the required format
    assert validate_contract_id_format(contract.contract_id), \
        f"Contract ID in DataContract must follow required format: {contract.contract_id}"
    
    # Property 2: Contract must be serializable to DynamoDB format
    dynamodb_item = contract.to_dynamodb_item()
    assert 'contractId' in dynamodb_item, \
        "DynamoDB item must contain contractId field"
    assert dynamodb_item['contractId'] == contract_id, \
        f"DynamoDB contractId must match: expected {contract_id}, got {dynamodb_item['contractId']}"
    
    # Property 3: Contract must be deserializable from DynamoDB format
    restored_contract = DataContract.from_dynamodb_item(dynamodb_item)
    assert restored_contract.contract_id == contract_id, \
        f"Restored contract ID must match: expected {contract_id}, got {restored_contract.contract_id}"
    
    # Property 4: Round-trip serialization must preserve contract ID format
    assert validate_contract_id_format(restored_contract.contract_id), \
        f"Restored contract ID must still follow required format: {restored_contract.contract_id}"


@settings(max_examples=50)
@given(
    cmo_name=cmo_name_strategy(),
    data_domain=data_domain_strategy(),
    number1=st.integers(min_value=1, max_value=999),
    number2=st.integers(min_value=1, max_value=999)
)
def test_contract_id_uniqueness_by_number(cmo_name, data_domain, number1, number2):
    """
    Property 7 (Uniqueness): Contract IDs with Different Numbers are Unique
    
    For any CMO and data domain, contracts with different numbers should 
    have different contract IDs.
    
    Validates: Requirements 2.4
    """
    contract_id1 = generate_contract_id(cmo_name, data_domain, number1)
    contract_id2 = generate_contract_id(cmo_name, data_domain, number2)
    
    if number1 != number2:
        # Property: Different numbers must produce different contract IDs
        assert contract_id1 != contract_id2, \
            f"Different numbers must produce different IDs: {contract_id1} vs {contract_id2}"
    else:
        # Property: Same numbers must produce identical contract IDs
        assert contract_id1 == contract_id2, \
            f"Same numbers must produce identical IDs: {contract_id1} vs {contract_id2}"


def test_contract_id_format_examples():
    """
    Unit test with specific examples to verify contract ID format.
    These are concrete examples that complement the property-based tests.
    """
    # Example 1: Simple case
    contract_id = generate_contract_id("Alpha", "batch-records", 1)
    assert contract_id == "CMO-ALPHA-BATCH-RECORDS-001"
    assert validate_contract_id_format(contract_id)
    
    # Example 2: Multi-word CMO name
    contract_id = generate_contract_id("Alpha Beta", "quality-data", 42)
    assert contract_id == "CMO-ALPHA-BETA-QUALITY-DATA-042"
    assert validate_contract_id_format(contract_id)
    
    # Example 3: Complex data domain
    contract_id = generate_contract_id("Gamma", "environmental-monitoring-data", 999)
    assert contract_id == "CMO-GAMMA-ENVIRONMENTAL-MONITORING-DATA-999"
    assert validate_contract_id_format(contract_id)
    
    # Example 4: Single character CMO name
    contract_id = generate_contract_id("X", "data", 5)
    assert contract_id == "CMO-X-DATA-005"
    assert validate_contract_id_format(contract_id)
    
    # Example 5: Numeric CMO name
    contract_id = generate_contract_id("123", "test-data", 100)
    assert contract_id == "CMO-123-TEST-DATA-100"
    assert validate_contract_id_format(contract_id)


def test_invalid_contract_id_formats():
    """
    Unit test to verify that invalid contract ID formats are rejected.
    """
    # Invalid formats that should fail validation
    invalid_ids = [
        "INVALID-FORMAT",
        "cmo-alpha-batch-001",  # lowercase 'cmo'
        "CMO-ALPHA-BATCH",  # missing number
        "CMO-ALPHA-BATCH-1",  # number not zero-padded
        "CMO-ALPHA-BATCH-1234",  # number too long
        "ALPHA-BATCH-001",  # missing CMO prefix
        "",  # empty string
        "CMO--BATCH-001",  # empty name
        "CMO-ALPHA--001",  # empty domain
    ]
    
    for invalid_id in invalid_ids:
        assert not validate_contract_id_format(invalid_id), \
            f"Should reject invalid format: {invalid_id}"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
