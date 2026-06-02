"""
Contract utility functions for data contract management
"""
import re
from typing import Optional


def generate_contract_id(cmo_name: str, data_domain: str, number: int) -> str:
    """
    Generate a contract ID following the format CMO-{NAME}-{DOMAIN}-{NUMBER}
    
    Args:
        cmo_name: CMO organization name (will be converted to uppercase)
        data_domain: Data domain identifier (e.g., 'batch-records', 'quality-data')
        number: Sequential number for the contract
        
    Returns:
        Contract ID in format CMO-{NAME}-{DOMAIN}-{NUMBER}
        
    Example:
        >>> generate_contract_id("alpha", "batch-records", 1)
        'CMO-ALPHA-BATCH-RECORDS-001'
    """
    # Convert CMO name to uppercase and replace spaces with hyphens
    name_upper = cmo_name.upper().replace(' ', '-')
    
    # Strip leading/trailing hyphens and collapse consecutive hyphens
    name_upper = re.sub(r'-+', '-', name_upper).strip('-')
    
    # Ensure non-empty name after sanitization
    if not name_upper:
        name_upper = 'UNKNOWN'
    
    # Format number with leading zeros (3 digits)
    number_formatted = str(number).zfill(3)
    
    # Construct contract ID
    contract_id = f"CMO-{name_upper}-{data_domain.upper()}-{number_formatted}"
    
    return contract_id


def validate_contract_id_format(contract_id: str) -> bool:
    """
    Validate that a contract ID follows the required format CMO-{NAME}-{DOMAIN}-{NUMBER}
    
    Args:
        contract_id: Contract ID to validate
        
    Returns:
        True if format is valid, False otherwise
        
    Example:
        >>> validate_contract_id_format("CMO-ALPHA-BATCH-RECORDS-001")
        True
        >>> validate_contract_id_format("invalid-format")
        False
    """
    # Pattern: CMO-{UPPERCASE}-{DOMAIN}-{3-DIGIT-NUMBER}
    pattern = r'^CMO-[A-Z0-9\-]+-[A-Z0-9\-]+-\d{3}$'
    return bool(re.match(pattern, contract_id))


def parse_contract_id(contract_id: str) -> Optional[dict]:
    """
    Parse a contract ID into its components
    
    Args:
        contract_id: Contract ID to parse
        
    Returns:
        Dictionary with 'cmo_name', 'data_domain', and 'number' keys, or None if invalid
        
    Example:
        >>> parse_contract_id("CMO-ALPHA-BATCH-RECORDS-001")
        {'cmo_name': 'ALPHA', 'data_domain': 'BATCH-RECORDS', 'number': 1}
    """
    if not validate_contract_id_format(contract_id):
        return None
    
    parts = contract_id.split('-')
    
    # Find where the number starts (last part that's all digits)
    number_str = parts[-1]
    number = int(number_str)
    
    # Everything between CMO and the number is split between name and domain
    # We need to find the boundary - this is ambiguous without more context
    # For now, assume the second part is the CMO name and everything else up to the number is domain
    cmo_name = parts[1]
    data_domain = '-'.join(parts[2:-1])
    
    return {
        'cmo_name': cmo_name,
        'data_domain': data_domain,
        'number': number
    }
