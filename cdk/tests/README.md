# Pharma Data Exchange Hub - Tests

This directory contains property-based tests and unit tests for the Pharma Data Exchange Hub platform.

## Test Structure

- `test_contract_id_property.py` - Property-based tests for contract ID format compliance (Property 7)

## Running Tests

### Run all tests
```bash
cd cdk
python -m pytest tests/ -v
```

### Run specific test file
```bash
python -m pytest tests/test_contract_id_property.py -v
```

### Run with coverage
```bash
python -m pytest tests/ --cov=models --cov=utils --cov-report=html
```

## Property-Based Testing

We use [Hypothesis](https://hypothesis.readthedocs.io/) for property-based testing. Each property test:

- Runs 100+ iterations with randomized inputs
- References the design document property it validates
- Includes a tag: `# Feature: pharma-data-exchange-hub, Property {number}: {property_text}`

### Property 7: Contract ID Format Compliance

**Validates**: Requirements 2.4

**Property**: For any data contract saved to DynamoDB, the contract ID should follow the format `CMO-{NAME}-{DOMAIN}-{NUMBER}` where NAME is uppercase, DOMAIN is the data domain, and NUMBER is a sequential integer.

**Test Coverage**:
- Contract ID format validation
- Component parsing and verification
- Round-trip serialization to/from DynamoDB
- Uniqueness guarantees
- Edge cases (single character names, numeric names, complex domains)

## Test Results

✅ All property-based tests passing (100 examples per test)
✅ All unit tests passing
✅ Contract ID format compliance verified across randomized inputs

## Dependencies

- pytest >= 7.4.0
- hypothesis >= 6.92.0
- moto >= 4.2.0 (for AWS service mocking)

Install with:
```bash
pip install -r requirements.txt
```
