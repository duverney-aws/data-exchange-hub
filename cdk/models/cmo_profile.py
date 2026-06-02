"""
CMO Profile Data Model
Defines the structure for CMO organization profiles stored in DynamoDB
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class CMOProfile:
    """
    CMO Profile stored in cmo-profiles DynamoDB table
    
    Attributes:
        cmo_id: Unique identifier in format cmo-{name}
        organization_name: Legal name of the CMO organization
        contact_email: Primary contact email address
        contact_phone: Primary contact phone number
        address: Physical address of the organization
        gxp_certified: Whether the CMO is GxP certified
        created_at: Timestamp when profile was created
        status: Current status of the CMO profile
    """
    cmo_id: str
    organization_name: str
    contact_email: str
    contact_phone: str
    address: str
    gxp_certified: bool
    created_at: datetime
    status: Literal['active', 'inactive', 'suspended'] = 'active'
    
    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item format"""
        return {
            'cmoId': self.cmo_id,
            'organizationName': self.organization_name,
            'contactEmail': self.contact_email,
            'contactPhone': self.contact_phone,
            'address': self.address,
            'gxpCertified': self.gxp_certified,
            'createdAt': self.created_at.isoformat(),
            'status': self.status,
        }
    
    @classmethod
    def from_dynamodb_item(cls, item: dict) -> 'CMOProfile':
        """Create instance from DynamoDB item"""
        return cls(
            cmo_id=item['cmoId'],
            organization_name=item['organizationName'],
            contact_email=item['contactEmail'],
            contact_phone=item['contactPhone'],
            address=item['address'],
            gxp_certified=item['gxpCertified'],
            created_at=datetime.fromisoformat(item['createdAt']),
            status=item['status'],
        )
