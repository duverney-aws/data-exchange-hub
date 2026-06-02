"""
S3 path generation utilities for Pharma Data Exchange Hub
Implements path patterns for Bronze/Silver/Gold medallion architecture
"""
from datetime import datetime
from typing import Optional


def generate_s3_path(
    bucket_name: str,
    layer: str,
    cmo_id: str,
    data_domain: str,
    date: Optional[datetime] = None,
    include_partition: bool = True
) -> str:
    """
    Generate S3 path following the pattern:
    s3://bucket/{layer}/{cmo-id}/{data-domain}/year=YYYY/month=MM/day=DD/
    
    Args:
        bucket_name: S3 bucket name
        layer: Data lake layer ('bronze', 'silver', or 'gold')
        cmo_id: CMO identifier (e.g., 'cmo-alpha')
        data_domain: Data domain (e.g., 'batch-records', 'quality-data')
        date: Date for partitioning (defaults to current date if None)
        include_partition: Whether to include date partitioning
        
    Returns:
        S3 path string
        
    Example:
        >>> generate_s3_path('data-lake', 'bronze', 'cmo-alpha', 'batch-records')
        's3://data-lake/bronze/cmo-alpha/batch-records/year=2024/month=01/day=15/'
    """
    # Validate layer
    valid_layers = ['bronze', 'silver', 'gold']
    if layer not in valid_layers:
        raise ValueError(f"Layer must be one of {valid_layers}, got: {layer}")
    
    # Validate CMO ID format
    if not cmo_id.startswith('cmo-'):
        raise ValueError(f"CMO ID must start with 'cmo-', got: {cmo_id}")
    
    # Build base path
    base_path = f"s3://{bucket_name}/{layer}/{cmo_id}/{data_domain}"
    
    # Add date partitioning if requested
    if include_partition:
        if date is None:
            date = datetime.now()
        
        year = date.strftime('%Y')
        month = date.strftime('%m')
        day = date.strftime('%d')
        
        partition_path = f"/year={year}/month={month}/day={day}/"
        return base_path + partition_path
    else:
        return base_path + "/"


def generate_batch_path(
    bucket_name: str,
    layer: str,
    cmo_id: str,
    product_id: str,
    batch_id: str,
    element_type: str,
) -> str:
    """
    Generate S3 path for a specific batch data element.
    Pattern: s3://bucket/{layer}/{cmo-id}/{product-id}/{batch-id}/{element-type}/

    Args:
        bucket_name: S3 bucket name
        layer: Data lake layer ('bronze', 'silver', or 'gold')
        cmo_id: CMO identifier (e.g., 'cmo-alpha')
        product_id: Product identifier (e.g., 'prod-keytruda-50mg')
        batch_id: Batch identifier (e.g., 'batch-abc123')
        element_type: Data element type ('bmr', 'coa', 'in_process', 'yield', etc.)

    Returns:
        S3 path string

    Example:
        >>> generate_batch_path('data-lake', 'bronze', 'cmo-alpha', 'prod-abc', 'batch-001', 'coa')
        's3://data-lake/bronze/cmo-alpha/prod-abc/batch-001/coa/'
    """
    valid_layers = ['bronze', 'silver', 'gold']
    if layer not in valid_layers:
        raise ValueError(f"Layer must be one of {valid_layers}, got: {layer}")
    if not cmo_id.startswith('cmo-'):
        raise ValueError(f"CMO ID must start with 'cmo-', got: {cmo_id}")

    return f"s3://{bucket_name}/{layer}/{cmo_id}/{product_id}/{batch_id}/{element_type}/"


def generate_bronze_batch_path(
    bucket_name: str,
    cmo_id: str,
    product_id: str,
    batch_id: str,
    element_type: str,
) -> str:
    """Generate Bronze layer path for a batch data element."""
    return generate_batch_path(bucket_name, 'bronze', cmo_id, product_id, batch_id, element_type)


def generate_silver_batch_path(
    bucket_name: str,
    cmo_id: str,
    product_id: str,
    batch_id: str,
    element_type: str,
) -> str:
    """Generate Silver layer path for a batch data element."""
    return generate_batch_path(bucket_name, 'silver', cmo_id, product_id, batch_id, element_type)


def generate_bronze_path(
    bucket_name: str,
    cmo_id: str,
    data_domain: str,
    date: Optional[datetime] = None
) -> str:
    """
    Generate Bronze layer S3 path for raw ingested data.
    
    Args:
        bucket_name: S3 bucket name
        cmo_id: CMO identifier
        data_domain: Data domain
        date: Date for partitioning (defaults to current date)
        
    Returns:
        S3 path for Bronze layer
        
    Example:
        >>> generate_bronze_path('data-lake', 'cmo-alpha', 'batch-records')
        's3://data-lake/bronze/cmo-alpha/batch-records/year=2024/month=01/day=15/'
    """
    return generate_s3_path(bucket_name, 'bronze', cmo_id, data_domain, date)


def generate_silver_path(
    bucket_name: str,
    cmo_id: str,
    data_domain: str,
    date: Optional[datetime] = None
) -> str:
    """
    Generate Silver layer S3 path for validated and cleansed data.
    
    Args:
        bucket_name: S3 bucket name
        cmo_id: CMO identifier
        data_domain: Data domain
        date: Date for partitioning (defaults to current date)
        
    Returns:
        S3 path for Silver layer
        
    Example:
        >>> generate_silver_path('data-lake', 'cmo-alpha', 'batch-records')
        's3://data-lake/silver/cmo-alpha/batch-records/year=2024/month=01/day=15/'
    """
    return generate_s3_path(bucket_name, 'silver', cmo_id, data_domain, date)


def generate_gold_path(
    bucket_name: str,
    aggregation_type: str,
    date: Optional[datetime] = None
) -> str:
    """
    Generate Gold layer S3 path for business-ready aggregated data.
    Note: Gold layer uses aggregation type instead of CMO-specific paths.
    
    Args:
        bucket_name: S3 bucket name
        aggregation_type: Type of aggregation (e.g., 'batch-summary-daily', 'quality-metrics-monthly')
        date: Date for partitioning (defaults to current date)
        
    Returns:
        S3 path for Gold layer
        
    Example:
        >>> generate_gold_path('data-lake', 'batch-summary-daily')
        's3://data-lake/gold/batch-summary-daily/year=2024/month=01/day=15/'
    """
    if date is None:
        date = datetime.now()
    
    year = date.strftime('%Y')
    month = date.strftime('%m')
    day = date.strftime('%d')
    
    return f"s3://{bucket_name}/gold/{aggregation_type}/year={year}/month={month}/day={day}/"


def generate_quarantine_path(
    bucket_name: str,
    contract_id: str,
    timestamp: Optional[datetime] = None
) -> str:
    """
    Generate quarantine path for failed validation records.
    Pattern: s3://bucket/bronze/quarantine/{contract-id}/{timestamp}/
    
    Args:
        bucket_name: S3 bucket name
        contract_id: Data contract ID
        timestamp: Timestamp for quarantine batch (defaults to current time)
        
    Returns:
        S3 path for quarantine location
        
    Example:
        >>> generate_quarantine_path('data-lake', 'CMO-ALPHA-BATCH-001')
        's3://data-lake/bronze/quarantine/CMO-ALPHA-BATCH-001/20240115T143022/'
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    timestamp_str = timestamp.strftime('%Y%m%dT%H%M%S')
    return f"s3://{bucket_name}/bronze/quarantine/{contract_id}/{timestamp_str}/"


def parse_s3_path(s3_path: str) -> dict:
    """
    Parse an S3 path into its components.
    
    Args:
        s3_path: S3 path to parse
        
    Returns:
        Dictionary with path components
        
    Example:
        >>> parse_s3_path('s3://data-lake/bronze/cmo-alpha/batch-records/year=2024/month=01/day=15/')
        {
            'bucket': 'data-lake',
            'layer': 'bronze',
            'cmo_id': 'cmo-alpha',
            'data_domain': 'batch-records',
            'year': '2024',
            'month': '01',
            'day': '15'
        }
    """
    if not s3_path.startswith('s3://'):
        raise ValueError(f"Path must start with 's3://', got: {s3_path}")
    
    # Remove s3:// prefix and trailing slash
    path = s3_path[5:].rstrip('/')
    
    parts = path.split('/')
    
    if len(parts) < 4:
        raise ValueError(f"Invalid S3 path structure: {s3_path}")
    
    result = {
        'bucket': parts[0],
        'layer': parts[1]
    }
    
    # Handle quarantine paths differently
    if parts[1] == 'bronze' and len(parts) > 2 and parts[2] == 'quarantine':
        result['is_quarantine'] = True
        result['contract_id'] = parts[3] if len(parts) > 3 else None
        result['timestamp'] = parts[4] if len(parts) > 4 else None
    # Handle gold layer (no CMO ID)
    elif parts[1] == 'gold':
        result['aggregation_type'] = parts[2] if len(parts) > 2 else None
        # Parse partitions if present
        for part in parts[3:]:
            if '=' in part:
                key, value = part.split('=', 1)
                result[key] = value
    # Handle bronze/silver layers
    else:
        result['cmo_id'] = parts[2] if len(parts) > 2 else None
        result['data_domain'] = parts[3] if len(parts) > 3 else None
        
        # Parse partitions if present
        for part in parts[4:]:
            if '=' in part:
                key, value = part.split('=', 1)
                result[key] = value
    
    return result


def validate_s3_path_format(s3_path: str, layer: Optional[str] = None) -> bool:
    """
    Validate that an S3 path follows the expected format.
    
    Args:
        s3_path: S3 path to validate
        layer: Optional layer to validate against ('bronze', 'silver', 'gold')
        
    Returns:
        True if path is valid, False otherwise
        
    Example:
        >>> validate_s3_path_format('s3://data-lake/bronze/cmo-alpha/batch-records/', 'bronze')
        True
    """
    try:
        parsed = parse_s3_path(s3_path)
        
        # Check if layer matches if specified
        if layer and parsed.get('layer') != layer:
            return False
        
        # Validate layer is one of the expected values
        if parsed.get('layer') not in ['bronze', 'silver', 'gold']:
            return False
        
        # For bronze/silver, must have CMO ID and data domain (unless quarantine)
        if parsed.get('layer') in ['bronze', 'silver']:
            if parsed.get('is_quarantine'):
                return parsed.get('contract_id') is not None
            else:
                return (parsed.get('cmo_id') is not None and 
                       parsed.get('data_domain') is not None)
        
        # For gold, must have aggregation type
        if parsed.get('layer') == 'gold':
            return parsed.get('aggregation_type') is not None
        
        return True
    except (ValueError, KeyError):
        return False
