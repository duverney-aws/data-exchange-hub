"""
Product (Material Master) Data Model
Represents a drug product manufactured by a CMO on behalf of Merck.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Product:
    """
    Product stored in the products DynamoDB table.

    Attributes:
        product_id: Unique identifier (e.g., 'prod-keytruda-50mg')
        product_name: Drug product name (e.g., 'Keytruda')
        strength: Dosage strength (e.g., '50mg/mL')
        dosage_form: Form of the product (e.g., 'injection', 'tablet', 'capsule')
        cmo_id: CMO that manufactures this product for Merck
        created_at: When the product record was created
        updated_at: When the product record was last updated
        is_active: Whether this product is currently active
    """
    product_id: str
    product_name: str
    strength: str
    dosage_form: str
    cmo_id: str
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    description: Optional[str] = None

    def to_dynamodb_item(self) -> dict:
        item = {
            'productId': self.product_id,
            'productName': self.product_name,
            'strength': self.strength,
            'dosageForm': self.dosage_form,
            'cmoId': self.cmo_id,
            'isActive': self.is_active,
            'createdAt': self.created_at.isoformat(),
            'updatedAt': self.updated_at.isoformat(),
        }
        if self.description:
            item['description'] = self.description
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> 'Product':
        return cls(
            product_id=item['productId'],
            product_name=item['productName'],
            strength=item['strength'],
            dosage_form=item['dosageForm'],
            cmo_id=item['cmoId'],
            is_active=item.get('isActive', True),
            description=item.get('description'),
            created_at=datetime.fromisoformat(item['createdAt']),
            updated_at=datetime.fromisoformat(item['updatedAt']),
        )
