"""
Connection Data Model
Represents an integration connection for a CMO (SFTP, native connector, AI unstructured).
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Connection:
    connection_id: str
    cmo_id: str
    connection_type: str  # secure-transfer | native-connector | ai-unstructured
    name: str
    status: str  # pending | active | inactive
    config: Optional[dict] = None  # type-specific config (hostname, username, password, etc.)
    created_at: str = ''
    updated_at: str = ''
    activated_by: Optional[str] = None
    activated_at: Optional[str] = None

    def to_dynamodb_item(self) -> dict:
        item = {
            'connectionId': self.connection_id,
            'cmoId': self.cmo_id,
            'connectionType': self.connection_type,
            'name': self.name,
            'status': self.status,
            'config': self.config or {},
            'createdAt': self.created_at,
            'updatedAt': self.updated_at,
        }
        if self.activated_by:
            item['activatedBy'] = self.activated_by
        if self.activated_at:
            item['activatedAt'] = self.activated_at
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> 'Connection':
        return cls(
            connection_id=item['connectionId'],
            cmo_id=item['cmoId'],
            connection_type=item['connectionType'],
            name=item['name'],
            status=item['status'],
            config=item.get('config') or {},
            created_at=item.get('createdAt', ''),
            updated_at=item.get('updatedAt', ''),
            activated_by=item.get('activatedBy'),
            activated_at=item.get('activatedAt'),
        )
