"""
Batch (Lot) Data Model
Represents a manufacturing batch submitted by a CMO.
Every data submission in the platform must be tagged to a batch.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, List, Optional


# Required data elements per batch, per Quality Agreement
REQUIRED_DATA_ELEMENTS = [
    'bmr',           # Batch Manufacturing Record
    'coa',           # Certificate of Analysis
    'in_process',    # In-process test results
    'yield',         # Yield / reconciliation data
]

OPTIONAL_DATA_ELEMENTS = [
    'deviation',     # Deviation reports (required only if deviations occurred)
    'env_monitoring', # Environmental monitoring (required for sterile products)
    'equipment_logs', # Equipment logs / calibration records
]


@dataclass
class DataElementStatus:
    """Tracks whether a required data element has been received for a batch."""
    element_type: str  # e.g., 'bmr', 'coa', 'in_process', 'yield'
    received: bool = False
    received_at: Optional[str] = None
    s3_path: Optional[str] = None
    overdue: bool = False

    def to_dict(self) -> dict:
        return {
            'elementType': self.element_type,
            'received': self.received,
            'receivedAt': self.received_at,
            's3Path': self.s3_path,
            'overdue': self.overdue,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DataElementStatus':
        return cls(
            element_type=data['elementType'],
            received=data.get('received', False),
            received_at=data.get('receivedAt'),
            s3_path=data.get('s3Path'),
            overdue=data.get('overdue', False),
        )


@dataclass
class Batch:
    """
    Batch stored in the batches DynamoDB table.

    Attributes:
        batch_id: Unique identifier (generated, e.g., 'batch-abc123')
        lot_number: CMO-assigned lot/batch number (e.g., 'LOT-2024-001')
        product_id: Reference to the product being manufactured
        cmo_id: CMO that manufactured this batch
        contract_id: Data contract governing this batch's data submission
        manufacturing_date: Date manufacturing was completed
        status: Lifecycle status of the batch data submission
        data_elements: Tracking of required data elements received
        created_at: When the batch record was created
        updated_at: When the batch record was last updated
        submitted_at: When CMO marked the batch as fully submitted
        notes: Optional notes from CMO
    """
    batch_id: str
    lot_number: str
    product_id: str
    cmo_id: str
    contract_id: str
    manufacturing_date: str  # ISO date string YYYY-MM-DD
    created_at: datetime
    updated_at: datetime
    status: Literal['in_progress', 'submitted', 'complete'] = 'in_progress'
    data_elements: List[DataElementStatus] = field(default_factory=list)
    submitted_at: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self):
        # Initialize required data elements if not provided
        if not self.data_elements:
            self.data_elements = [
                DataElementStatus(element_type=e) for e in REQUIRED_DATA_ELEMENTS
            ]

    @property
    def is_complete(self) -> bool:
        """True if all required data elements have been received."""
        return all(e.received for e in self.data_elements if e.element_type in REQUIRED_DATA_ELEMENTS)

    @property
    def missing_elements(self) -> List[str]:
        """List of required data elements not yet received."""
        return [e.element_type for e in self.data_elements
                if e.element_type in REQUIRED_DATA_ELEMENTS and not e.received]

    def to_dynamodb_item(self) -> dict:
        item = {
            'batchId': self.batch_id,
            'lotNumber': self.lot_number,
            'productId': self.product_id,
            'cmoId': self.cmo_id,
            'contractId': self.contract_id,
            'manufacturingDate': self.manufacturing_date,
            'status': self.status,
            'dataElements': [e.to_dict() for e in self.data_elements],
            'isComplete': self.is_complete,
            'missingElements': self.missing_elements,
            'createdAt': self.created_at.isoformat(),
            'updatedAt': self.updated_at.isoformat(),
        }
        if self.submitted_at:
            item['submittedAt'] = self.submitted_at
        if self.notes:
            item['notes'] = self.notes
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> 'Batch':
        return cls(
            batch_id=item['batchId'],
            lot_number=item['lotNumber'],
            product_id=item['productId'],
            cmo_id=item['cmoId'],
            contract_id=item['contractId'],
            manufacturing_date=item['manufacturingDate'],
            status=item['status'],
            data_elements=[DataElementStatus.from_dict(e) for e in item.get('dataElements', [])],
            submitted_at=item.get('submittedAt'),
            notes=item.get('notes'),
            created_at=datetime.fromisoformat(item['createdAt']),
            updated_at=datetime.fromisoformat(item['updatedAt']),
        )
