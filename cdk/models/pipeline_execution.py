"""
Pipeline Execution Data Model
Defines the structure for pipeline execution history stored in DynamoDB
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional, Dict, Any


@dataclass
class PipelineExecution:
    """
    Pipeline Execution record stored in pipeline-executions DynamoDB table
    
    Attributes:
        contract_id: Reference to data contract
        execution_timestamp: Unix timestamp (milliseconds) when execution started
        execution_id: Unique identifier for this execution
        status: Current status of the execution
        records_processed: Number of records processed
        records_failed: Number of records that failed validation
        execution_time_seconds: Total execution time in seconds
        quality_score: Overall quality score (0-100)
        error_message: Error message if execution failed
        metadata: Additional execution metadata
        ttl: Time-to-live timestamp for auto-deletion (90 days)
    """
    contract_id: str
    execution_timestamp: int  # Unix timestamp in milliseconds
    execution_id: str
    status: Literal['running', 'succeeded', 'failed', 'timeout']
    records_processed: int = 0
    records_failed: int = 0
    execution_time_seconds: float = 0.0
    quality_score: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    ttl: Optional[int] = None  # Unix timestamp for TTL
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        
        # Set TTL to 90 days from execution timestamp if not set
        if self.ttl is None:
            self.ttl = self.execution_timestamp + (90 * 24 * 60 * 60 * 1000)
    
    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format"""
        item = {
            'contractId': self.contract_id,
            'executionTimestamp': self.execution_timestamp,
            'executionId': self.execution_id,
            'status': self.status,
            'recordsProcessed': self.records_processed,
            'recordsFailed': self.records_failed,
            'executionTimeSeconds': self.execution_time_seconds,
            'qualityScore': self.quality_score,
            'metadata': self.metadata,
            'ttl': self.ttl,
        }
        
        if self.error_message:
            item['errorMessage'] = self.error_message
        
        return item
    
    @classmethod
    def from_dynamodb_item(cls, item: dict) -> 'PipelineExecution':
        """Create instance from DynamoDB item"""
        return cls(
            contract_id=item['contractId'],
            execution_timestamp=item['executionTimestamp'],
            execution_id=item['executionId'],
            status=item['status'],
            records_processed=item.get('recordsProcessed', 0),
            records_failed=item.get('recordsFailed', 0),
            execution_time_seconds=item.get('executionTimeSeconds', 0.0),
            quality_score=item.get('qualityScore', 0.0),
            error_message=item.get('errorMessage'),
            metadata=item.get('metadata', {}),
            ttl=item.get('ttl'),
        )
