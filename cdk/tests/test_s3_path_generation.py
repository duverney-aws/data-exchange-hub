"""
Unit Tests for S3 Path Generation

This test validates S3 path generation for Bronze/Silver/Gold layers with CMO-specific partitioning.

Task: 1.2 Write unit tests for S3 path generation
- Test Bronze/Silver/Gold path formatting
- Test CMO-specific partitioning
- Requirements: 4.6, 9.1, 9.2
"""
import pytest
from datetime import datetime
from utils.s3_path_utils import (
    generate_s3_path,
    generate_bronze_path,
    generate_silver_path,
    generate_gold_path,
    generate_quarantine_path,
    parse_s3_path,
    validate_s3_path_format
)


class TestBronzeLayerPathGeneration:
    """Test Bronze layer S3 path generation (Requirements 9.1, 9.2)"""
    
    def test_bronze_path_basic_format(self):
        """Test basic Bronze layer path format"""
        date = datetime(2024, 1, 15, 14, 30, 0)
        path = generate_bronze_path('data-lake', 'cmo-alpha', 'batch-records', date)
        
        assert path == 's3://data-lake/bronze/cmo-alpha/batch-records/year=2024/month=01/day=15/'
        assert path.startswith('s3://data-lake/bronze/')
        assert 'cmo-alpha' in path
        assert 'batch-records' in path
    
    def test_bronze_path_with_different_cmo(self):
        """Test Bronze path with different CMO identifiers"""
        date = datetime(2024, 1, 15)
        
        path1 = generate_bronze_path('data-lake', 'cmo-alpha', 'batch-records', date)
        path2 = generate_bronze_path('data-lake', 'cmo-beta', 'batch-records', date)
        path3 = generate_bronze_path('data-lake', 'cmo-gamma', 'batch-records', date)
        
        assert 'cmo-alpha' in path1
        assert 'cmo-beta' in path2
        assert 'cmo-gamma' in path3
        assert path1 != path2 != path3
    
    def test_bronze_path_with_different_domains(self):
        """Test Bronze path with different data domains"""
        date = datetime(2024, 1, 15)
        
        path1 = generate_bronze_path('data-lake', 'cmo-alpha', 'batch-records', date)
        path2 = generate_bronze_path('data-lake', 'cmo-alpha', 'quality-data', date)
        path3 = generate_bronze_path('data-lake', 'cmo-alpha', 'manufacturing-data', date)
        
        assert 'batch-records' in path1
        assert 'quality-data' in path2
        assert 'manufacturing-data' in path3
        assert path1 != path2 != path3
    
    def test_bronze_path_date_partitioning(self):
        """Test Bronze path date partitioning format (Requirement 9.2)"""
        date = datetime(2024, 3, 7, 10, 45, 30)
        path = generate_bronze_path('data-lake', 'cmo-alpha', 'batch-records', date)
        
        assert 'year=2024' in path
        assert 'month=03' in path
        assert 'day=07' in path
        assert path.endswith('/')
    
    def test_bronze_path_default_date(self):
        """Test Bronze path with default date (current date)"""
        path = generate_bronze_path('data-lake', 'cmo-alpha', 'batch-records')
        
        # Should contain year/month/day partitions
        assert 'year=' in path
        assert 'month=' in path
        assert 'day=' in path
    
    def test_bronze_path_multi_word_domain(self):
        """Test Bronze path with multi-word data domain"""
        date = datetime(2024, 1, 15)
        path = generate_bronze_path('data-lake', 'cmo-alpha', 'environmental-monitoring-data', date)
        
        assert 'environmental-monitoring-data' in path
        assert path == 's3://data-lake/bronze/cmo-alpha/environmental-monitoring-data/year=2024/month=01/day=15/'


class TestSilverLayerPathGeneration:
    """Test Silver layer S3 path generation (Requirements 9.3, 9.4)"""
    
    def test_silver_path_basic_format(self):
        """Test basic Silver layer path format"""
        date = datetime(2024, 1, 15, 14, 30, 0)
        path = generate_silver_path('data-lake', 'cmo-alpha', 'batch-records', date)
        
        assert path == 's3://data-lake/silver/cmo-alpha/batch-records/year=2024/month=01/day=15/'
        assert path.startswith('s3://data-lake/silver/')
        assert 'cmo-alpha' in path
        assert 'batch-records' in path
    
    def test_silver_path_cmo_isolation(self):
        """Test Silver path maintains CMO isolation"""
        date = datetime(2024, 1, 15)
        
        path1 = generate_silver_path('data-lake', 'cmo-alpha', 'batch-records', date)
        path2 = generate_silver_path('data-lake', 'cmo-beta', 'batch-records', date)
        
        # Each CMO should have separate path
        assert 'cmo-alpha' in path1
        assert 'cmo-beta' in path2
        assert 'cmo-alpha' not in path2
        assert 'cmo-beta' not in path1
    
    def test_silver_path_date_partitioning(self):
        """Test Silver path date partitioning"""
        date = datetime(2024, 12, 31, 23, 59, 59)
        path = generate_silver_path('data-lake', 'cmo-alpha', 'quality-data', date)
        
        assert 'year=2024' in path
        assert 'month=12' in path
        assert 'day=31' in path
    
    def test_silver_path_different_bucket(self):
        """Test Silver path with different bucket names"""
        date = datetime(2024, 1, 15)
        
        path1 = generate_silver_path('data-lake-prod', 'cmo-alpha', 'batch-records', date)
        path2 = generate_silver_path('data-lake-dev', 'cmo-alpha', 'batch-records', date)
        
        assert path1.startswith('s3://data-lake-prod/')
        assert path2.startswith('s3://data-lake-dev/')


class TestGoldLayerPathGeneration:
    """Test Gold layer S3 path generation (Requirement 9.5)"""
    
    def test_gold_path_basic_format(self):
        """Test basic Gold layer path format"""
        date = datetime(2024, 1, 15, 14, 30, 0)
        path = generate_gold_path('data-lake', 'batch-summary-daily', date)
        
        assert path == 's3://data-lake/gold/batch-summary-daily/year=2024/month=01/day=15/'
        assert path.startswith('s3://data-lake/gold/')
        assert 'batch-summary-daily' in path
    
    def test_gold_path_no_cmo_id(self):
        """Test Gold path does not include CMO ID (aggregated across CMOs)"""
        date = datetime(2024, 1, 15)
        path = generate_gold_path('data-lake', 'quality-metrics-monthly', date)
        
        # Gold layer should not have CMO-specific paths
        assert 'cmo-' not in path
        assert 'quality-metrics-monthly' in path
    
    def test_gold_path_different_aggregations(self):
        """Test Gold path with different aggregation types"""
        date = datetime(2024, 1, 15)
        
        path1 = generate_gold_path('data-lake', 'batch-summary-daily', date)
        path2 = generate_gold_path('data-lake', 'quality-metrics-monthly', date)
        path3 = generate_gold_path('data-lake', 'cmo-performance-dashboard', date)
        
        assert 'batch-summary-daily' in path1
        assert 'quality-metrics-monthly' in path2
        assert 'cmo-performance-dashboard' in path3
        assert path1 != path2 != path3
    
    def test_gold_path_date_partitioning(self):
        """Test Gold path date partitioning"""
        date = datetime(2024, 6, 15, 12, 0, 0)
        path = generate_gold_path('data-lake', 'batch-summary-daily', date)
        
        assert 'year=2024' in path
        assert 'month=06' in path
        assert 'day=15' in path


class TestQuarantinePathGeneration:
    """Test quarantine path generation for failed validation (Requirement 8.4)"""
    
    def test_quarantine_path_basic_format(self):
        """Test basic quarantine path format"""
        timestamp = datetime(2024, 1, 15, 14, 30, 22)
        path = generate_quarantine_path('data-lake', 'CMO-ALPHA-BATCH-001', timestamp)
        
        assert path == 's3://data-lake/bronze/quarantine/CMO-ALPHA-BATCH-001/20240115T143022/'
        assert 'bronze/quarantine' in path
        assert 'CMO-ALPHA-BATCH-001' in path
    
    def test_quarantine_path_with_contract_id(self):
        """Test quarantine path includes contract ID"""
        timestamp = datetime(2024, 1, 15, 14, 30, 22)
        
        path1 = generate_quarantine_path('data-lake', 'CMO-ALPHA-BATCH-001', timestamp)
        path2 = generate_quarantine_path('data-lake', 'CMO-BETA-QUALITY-002', timestamp)
        
        assert 'CMO-ALPHA-BATCH-001' in path1
        assert 'CMO-BETA-QUALITY-002' in path2
        assert path1 != path2
    
    def test_quarantine_path_timestamp_format(self):
        """Test quarantine path timestamp format"""
        timestamp = datetime(2024, 3, 7, 9, 5, 3)
        path = generate_quarantine_path('data-lake', 'CMO-ALPHA-BATCH-001', timestamp)
        
        # Timestamp should be in format YYYYMMDDTHHMMSS
        assert '20240307T090503' in path
    
    def test_quarantine_path_default_timestamp(self):
        """Test quarantine path with default timestamp (current time)"""
        path = generate_quarantine_path('data-lake', 'CMO-ALPHA-BATCH-001')
        
        # Should contain a timestamp
        assert 'bronze/quarantine' in path
        assert 'CMO-ALPHA-BATCH-001' in path
        # Timestamp should be present (format: YYYYMMDDTHHMMSS)
        assert 'T' in path


class TestGeneralS3PathGeneration:
    """Test general S3 path generation function (Requirement 4.6)"""
    
    def test_s3_path_with_all_layers(self):
        """Test S3 path generation for all layers"""
        date = datetime(2024, 1, 15)
        
        bronze = generate_s3_path('data-lake', 'bronze', 'cmo-alpha', 'batch-records', date)
        silver = generate_s3_path('data-lake', 'silver', 'cmo-alpha', 'batch-records', date)
        gold_path = generate_gold_path('data-lake', 'batch-summary-daily', date)
        
        assert 'bronze' in bronze
        assert 'silver' in silver
        assert 'gold' in gold_path
    
    def test_s3_path_without_partition(self):
        """Test S3 path generation without date partitioning"""
        path = generate_s3_path('data-lake', 'bronze', 'cmo-alpha', 'batch-records', 
                               include_partition=False)
        
        assert path == 's3://data-lake/bronze/cmo-alpha/batch-records/'
        assert 'year=' not in path
        assert 'month=' not in path
        assert 'day=' not in path
    
    def test_s3_path_invalid_layer(self):
        """Test S3 path generation with invalid layer"""
        with pytest.raises(ValueError, match="Layer must be one of"):
            generate_s3_path('data-lake', 'invalid-layer', 'cmo-alpha', 'batch-records')
    
    def test_s3_path_invalid_cmo_id(self):
        """Test S3 path generation with invalid CMO ID format"""
        with pytest.raises(ValueError, match="CMO ID must start with 'cmo-'"):
            generate_s3_path('data-lake', 'bronze', 'invalid-id', 'batch-records')
    
    def test_s3_path_pattern_compliance(self):
        """Test S3 path follows required pattern (Requirement 4.6)"""
        date = datetime(2024, 1, 15)
        path = generate_s3_path('data-lake', 'bronze', 'cmo-alpha', 'batch-records', date)
        
        # Pattern: s3://bucket/{layer}/{cmo-id}/{data-domain}/year=YYYY/month=MM/day=DD/
        expected_pattern = 's3://data-lake/bronze/cmo-alpha/batch-records/year=2024/month=01/day=15/'
        assert path == expected_pattern


class TestS3PathParsing:
    """Test S3 path parsing functionality"""
    
    def test_parse_bronze_path(self):
        """Test parsing Bronze layer path"""
        path = 's3://data-lake/bronze/cmo-alpha/batch-records/year=2024/month=01/day=15/'
        parsed = parse_s3_path(path)
        
        assert parsed['bucket'] == 'data-lake'
        assert parsed['layer'] == 'bronze'
        assert parsed['cmo_id'] == 'cmo-alpha'
        assert parsed['data_domain'] == 'batch-records'
        assert parsed['year'] == '2024'
        assert parsed['month'] == '01'
        assert parsed['day'] == '15'
    
    def test_parse_silver_path(self):
        """Test parsing Silver layer path"""
        path = 's3://data-lake/silver/cmo-beta/quality-data/year=2024/month=03/day=07/'
        parsed = parse_s3_path(path)
        
        assert parsed['layer'] == 'silver'
        assert parsed['cmo_id'] == 'cmo-beta'
        assert parsed['data_domain'] == 'quality-data'
    
    def test_parse_gold_path(self):
        """Test parsing Gold layer path"""
        path = 's3://data-lake/gold/batch-summary-daily/year=2024/month=01/day=15/'
        parsed = parse_s3_path(path)
        
        assert parsed['layer'] == 'gold'
        assert parsed['aggregation_type'] == 'batch-summary-daily'
        assert 'cmo_id' not in parsed or parsed.get('cmo_id') is None
    
    def test_parse_quarantine_path(self):
        """Test parsing quarantine path"""
        path = 's3://data-lake/bronze/quarantine/CMO-ALPHA-BATCH-001/20240115T143022/'
        parsed = parse_s3_path(path)
        
        assert parsed['layer'] == 'bronze'
        assert parsed['is_quarantine'] is True
        assert parsed['contract_id'] == 'CMO-ALPHA-BATCH-001'
        assert parsed['timestamp'] == '20240115T143022'
    
    def test_parse_path_without_partition(self):
        """Test parsing path without date partitioning"""
        path = 's3://data-lake/bronze/cmo-alpha/batch-records/'
        parsed = parse_s3_path(path)
        
        assert parsed['bucket'] == 'data-lake'
        assert parsed['layer'] == 'bronze'
        assert parsed['cmo_id'] == 'cmo-alpha'
        assert parsed['data_domain'] == 'batch-records'
        assert 'year' not in parsed
    
    def test_parse_invalid_path(self):
        """Test parsing invalid S3 path"""
        with pytest.raises(ValueError, match="Path must start with 's3://'"):
            parse_s3_path('invalid-path')
        
        with pytest.raises(ValueError, match="Invalid S3 path structure"):
            parse_s3_path('s3://bucket/')


class TestS3PathValidation:
    """Test S3 path validation functionality"""
    
    def test_validate_bronze_path(self):
        """Test validation of Bronze layer paths"""
        valid_path = 's3://data-lake/bronze/cmo-alpha/batch-records/year=2024/month=01/day=15/'
        assert validate_s3_path_format(valid_path, 'bronze') is True
    
    def test_validate_silver_path(self):
        """Test validation of Silver layer paths"""
        valid_path = 's3://data-lake/silver/cmo-alpha/batch-records/year=2024/month=01/day=15/'
        assert validate_s3_path_format(valid_path, 'silver') is True
    
    def test_validate_gold_path(self):
        """Test validation of Gold layer paths"""
        valid_path = 's3://data-lake/gold/batch-summary-daily/year=2024/month=01/day=15/'
        assert validate_s3_path_format(valid_path, 'gold') is True
    
    def test_validate_quarantine_path(self):
        """Test validation of quarantine paths"""
        valid_path = 's3://data-lake/bronze/quarantine/CMO-ALPHA-BATCH-001/20240115T143022/'
        assert validate_s3_path_format(valid_path, 'bronze') is True
    
    def test_validate_path_wrong_layer(self):
        """Test validation fails when layer doesn't match"""
        bronze_path = 's3://data-lake/bronze/cmo-alpha/batch-records/'
        assert validate_s3_path_format(bronze_path, 'silver') is False
    
    def test_validate_invalid_paths(self):
        """Test validation of invalid paths"""
        invalid_paths = [
            'invalid-path',
            's3://bucket/',
            's3://bucket/invalid-layer/cmo-alpha/data/',
            's3://bucket/bronze/',  # Missing CMO ID and domain
            's3://bucket/gold/',  # Missing aggregation type
        ]
        
        for invalid_path in invalid_paths:
            assert validate_s3_path_format(invalid_path) is False


class TestCMOPartitioning:
    """Test CMO-specific partitioning (Requirements 9.1, 9.2)"""
    
    def test_cmo_data_isolation_in_paths(self):
        """Test that different CMOs have isolated paths"""
        date = datetime(2024, 1, 15)
        
        cmo_alpha_bronze = generate_bronze_path('data-lake', 'cmo-alpha', 'batch-records', date)
        cmo_beta_bronze = generate_bronze_path('data-lake', 'cmo-beta', 'batch-records', date)
        
        cmo_alpha_silver = generate_silver_path('data-lake', 'cmo-alpha', 'batch-records', date)
        cmo_beta_silver = generate_silver_path('data-lake', 'cmo-beta', 'batch-records', date)
        
        # Each CMO should have separate paths
        assert 'cmo-alpha' in cmo_alpha_bronze
        assert 'cmo-beta' in cmo_beta_bronze
        assert 'cmo-alpha' in cmo_alpha_silver
        assert 'cmo-beta' in cmo_beta_silver
        
        # Paths should not overlap
        assert cmo_alpha_bronze != cmo_beta_bronze
        assert cmo_alpha_silver != cmo_beta_silver
    
    def test_same_domain_different_cmos(self):
        """Test same data domain for different CMOs creates separate paths"""
        date = datetime(2024, 1, 15)
        
        paths = [
            generate_bronze_path('data-lake', f'cmo-{name}', 'batch-records', date)
            for name in ['alpha', 'beta', 'gamma', 'delta']
        ]
        
        # All paths should be unique
        assert len(paths) == len(set(paths))
        
        # Each should contain the correct CMO ID
        for i, name in enumerate(['alpha', 'beta', 'gamma', 'delta']):
            assert f'cmo-{name}' in paths[i]
    
    def test_date_partitioning_format(self):
        """Test date partitioning follows Hive-style format (Requirement 9.2)"""
        date = datetime(2024, 1, 15)
        path = generate_bronze_path('data-lake', 'cmo-alpha', 'batch-records', date)
        
        # Should use Hive-style partitioning: year=YYYY/month=MM/day=DD
        assert 'year=2024' in path
        assert 'month=01' in path
        assert 'day=15' in path
        
        # Verify order: year before month before day
        year_pos = path.index('year=')
        month_pos = path.index('month=')
        day_pos = path.index('day=')
        
        assert year_pos < month_pos < day_pos


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
