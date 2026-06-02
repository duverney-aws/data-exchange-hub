"""
Data Contract Data Model
Defines the structure for data contracts stored in DynamoDB
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, List, Optional


@dataclass
class QualityRule:
    """Data quality validation rule"""
    rule_id: str
    rule_name: str
    rule_type: Literal['completeness', 'accuracy', 'uniqueness', 'consistency']
    expression: str  # Glue Data Quality DQDL expression
    threshold: float  # 0-100 percentage
    severity: Literal['warning', 'error']
    
    def to_dict(self) -> dict:
        return {
            'ruleId': self.rule_id,
            'ruleName': self.rule_name,
            'ruleType': self.rule_type,
            'expression': self.expression,
            'threshold': self.threshold,
            'severity': self.severity,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'QualityRule':
        return cls(
            rule_id=data['ruleId'],
            rule_name=data['ruleName'],
            rule_type=data['ruleType'],
            expression=data['expression'],
            threshold=data['threshold'],
            severity=data['severity'],
        )


@dataclass
class SLA:
    """Service Level Agreement thresholds"""
    timeliness: dict  # {'maxDelayHours': int, 'measurementWindow': str}
    availability: dict  # {'uptimePercentage': float, 'measurementWindow': str}
    quality: dict  # {'minQualityScore': float, 'measurementWindow': str}
    
    def to_dict(self) -> dict:
        return {
            'timeliness': self.timeliness,
            'availability': self.availability,
            'quality': self.quality,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SLA':
        return cls(
            timeliness=data['timeliness'],
            availability=data['availability'],
            quality=data['quality'],
        )



@dataclass
class DataElementSLA:
    """SLA for a specific required data element (e.g., CoA within 5 days of batch completion)."""
    element_type: str  # 'bmr', 'coa', 'in_process', 'yield'
    max_days_after_batch: int  # business days after manufacturing_date

    def to_dict(self) -> dict:
        return {'elementType': self.element_type, 'maxDaysAfterBatch': self.max_days_after_batch}

    @classmethod
    def from_dict(cls, data: dict) -> 'DataElementSLA':
        return cls(element_type=data['elementType'], max_days_after_batch=data['maxDaysAfterBatch'])

@dataclass
class DeliverySchedule:
    """Data delivery schedule configuration"""
    frequency: Literal['real-time', 'hourly', 'daily', 'weekly', 'monthly']
    cron_expression: Optional[str] = None
    timezone: str = 'UTC'
    
    def to_dict(self) -> dict:
        result = {
            'frequency': self.frequency,
            'timezone': self.timezone,
        }
        if self.cron_expression:
            result['cronExpression'] = self.cron_expression
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DeliverySchedule':
        return cls(
            frequency=data['frequency'],
            cron_expression=data.get('cronExpression'),
            timezone=data.get('timezone', 'UTC'),
        )


@dataclass
class Governance:
    """Data governance and access control settings"""
    data_classification: Literal['public', 'internal', 'confidential', 'restricted']
    retention_years: int
    allowed_users: List[str]
    allowed_groups: List[str]
    pii_fields: List[str]
    encryption_required: bool
    
    def to_dict(self) -> dict:
        return {
            'dataClassification': self.data_classification,
            'retentionYears': self.retention_years,
            'allowedUsers': self.allowed_users,
            'allowedGroups': self.allowed_groups,
            'piiFields': self.pii_fields,
            'encryptionRequired': self.encryption_required,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Governance':
        return cls(
            data_classification=data['dataClassification'],
            retention_years=data['retentionYears'],
            allowed_users=data['allowedUsers'],
            allowed_groups=data['allowedGroups'],
            pii_fields=data['piiFields'],
            encryption_required=data['encryptionRequired'],
        )


@dataclass
class DataContract:
    """
    Data Contract stored in data-contracts DynamoDB table
    
    Attributes:
        contract_id: Unique identifier in format CMO-{NAME}-{DOMAIN}-{NUMBER}
        cmo_id: Reference to CMO profile
        data_domain: Data domain (e.g., 'batch-records', 'quality-data')
        schema_id: Reference to schema in Glue Schema Registry
        schema_version: Version of the schema
        quality_rules: List of data quality validation rules
        sla: Service level agreement thresholds
        delivery_schedule: Data delivery frequency and schedule
        governance: Access control and retention settings
        status: Current status of the contract
        created_at: Timestamp when contract was created
        updated_at: Timestamp when contract was last updated
    """
    contract_id: str
    cmo_id: str
    product_id: str
    data_domain: str
    schema_id: str
    schema_version: str
    quality_rules: List[QualityRule]
    sla: SLA
    delivery_schedule: DeliverySchedule
    governance: Governance
    element_slas: List['DataElementSLA']
    created_at: datetime
    updated_at: datetime
    status: Literal['draft', 'pending_cmo_review', 'pending_merck_approval', 'active', 'rejected', 'suspended'] = 'draft'
    submitted_by: Optional[str] = None
    submitted_at: Optional[str] = None
    accepted_by: Optional[str] = None
    accepted_at: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    connection_id: Optional[str] = None  # reference to connections table
    integration_pattern: Optional[str] = None  # native-connector | secure-transfer | ai-unstructured
    integration_config: Optional[dict] = None  # pattern-specific config (SFTP creds, connection details, etc.)
    
    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format"""
        return {
            'contractId': self.contract_id,
            'cmoId': self.cmo_id,
            'productId': self.product_id,
            'dataDomain': self.data_domain,
            'schemaId': self.schema_id,
            'schemaVersion': self.schema_version,
            'qualityRules': [rule.to_dict() for rule in self.quality_rules],
            'sla': self.sla.to_dict(),
            'deliverySchedule': self.delivery_schedule.to_dict(),
            'governance': self.governance.to_dict(),
            'elementSlas': [s.to_dict() for s in self.element_slas],
            'status': self.status,
            'createdAt': self.created_at.isoformat(),
            'updatedAt': self.updated_at.isoformat(),
            'connectionId': self.connection_id or '',
            'integrationPattern': self.integration_pattern or '',
            'integrationConfig': self.integration_config or {},
        }
    
    @classmethod
    def from_dynamodb_item(cls, item: dict) -> 'DataContract':
        """Create instance from DynamoDB item"""
        return cls(
            contract_id=item['contractId'],
            cmo_id=item['cmoId'],
            product_id=item.get('productId', ''),
            data_domain=item['dataDomain'],
            schema_id=item['schemaId'],
            schema_version=item['schemaVersion'],
            quality_rules=[QualityRule.from_dict(rule) for rule in item['qualityRules']],
            sla=SLA.from_dict(item['sla']),
            delivery_schedule=DeliverySchedule.from_dict(item['deliverySchedule']),
            governance=Governance.from_dict(item['governance']),
            element_slas=[DataElementSLA.from_dict(s) for s in item.get('elementSlas', [])],
            status=item['status'],
            created_at=datetime.fromisoformat(item['createdAt']),
            updated_at=datetime.fromisoformat(item['updatedAt']),
            connection_id=item.get('connectionId') or None,
            integration_pattern=item.get('integrationPattern') or None,
            integration_config=item.get('integrationConfig') or None,
        )
