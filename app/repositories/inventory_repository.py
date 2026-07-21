from __future__ import annotations

import secrets
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.inventory import (
    AuthorizationCode,
    DocumentSequence,
    InventoryDocument,
    InventoryDocumentLine,
)
from app.models.enums import DocumentStatus, DocumentType
from app.models.system_param import SystemParam


LEGACY_BAJA_TYPES = {
    "damage_disposal",
    "expiration_disposal",
    "loss_theft_disposal",
    "donation",
}


class InventoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_doc_number_padding(self) -> int:
        result = await self.db.execute(
            select(SystemParam).where(SystemParam.key == "doc_number_padding")
        )
        param = result.scalar_one_or_none()
        if not param:
            return 6

        try:
            padding = int(param.value)
        except (TypeError, ValueError):
            return 6

        return padding if padding > 0 else 6

    async def generate_document_number(self, doc_type: DocumentType, year: int) -> str:
        """Generate next sequential document number with row-level lock."""
        result = await self.db.execute(
            select(DocumentSequence)
            .where(DocumentSequence.doc_type == doc_type, DocumentSequence.year == year)
            .with_for_update()
        )
        seq = result.scalar_one_or_none()

        if not seq:
            seq = DocumentSequence(doc_type=doc_type, year=year, last_number=0)
            self.db.add(seq)
            await self.db.flush()

        seq.last_number += 1
        await self.db.flush()
        padding = await self._get_doc_number_padding()
        return f"{doc_type.value}-{year}-{seq.last_number:0{padding}d}"

    async def create_document(
        self, document: InventoryDocument, lines: list[InventoryDocumentLine]
    ) -> InventoryDocument:
        self.db.add(document)
        await self.db.flush()
        for line in lines:
            line.document_id = document.id
            self.db.add(line)
        await self.db.flush()

        result = await self.db.execute(
            select(InventoryDocument)
            .where(InventoryDocument.id == document.id)
            .options(
                selectinload(InventoryDocument.supplier),
                selectinload(InventoryDocument.attachments),
                selectinload(InventoryDocument.lines).selectinload(
                    InventoryDocumentLine.product
                )
            )
        )
        return result.scalar_one()

    async def get_by_id(self, document_id: int) -> InventoryDocument | None:
        result = await self.db.execute(
            select(InventoryDocument)
            .where(InventoryDocument.id == document_id)
            .options(
                selectinload(InventoryDocument.supplier),
                selectinload(InventoryDocument.attachments),
                selectinload(InventoryDocument.lines).selectinload(
                    InventoryDocumentLine.product
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_number(self, number: str) -> InventoryDocument | None:
        result = await self.db.execute(
            select(InventoryDocument)
            .where(InventoryDocument.number == number)
            .options(
                selectinload(InventoryDocument.supplier),
                selectinload(InventoryDocument.attachments),
                selectinload(InventoryDocument.lines).selectinload(
                    InventoryDocumentLine.product
                )
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        doc_type: DocumentType,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        product_id: int | None = None,
        created_by: int | None = None,
        movement_type: str | None = None,
        status: DocumentStatus | None = None,
        limit: int = 50,
        cursor: int | None = None,
    ) -> list[InventoryDocument]:
        q = (
            select(InventoryDocument)
            .options(
                selectinload(InventoryDocument.supplier),
                selectinload(InventoryDocument.attachments),
                selectinload(InventoryDocument.lines).selectinload(
                    InventoryDocumentLine.product
                )
            )
            .where(InventoryDocument.doc_type == doc_type)
            .order_by(InventoryDocument.id.desc())
        )
        if date_from:
            q = q.where(InventoryDocument.created_at >= date_from)
        if date_to:
            q = q.where(InventoryDocument.created_at <= date_to)
        if created_by:
            q = q.where(InventoryDocument.created_by == created_by)
        if movement_type:
            if doc_type == DocumentType.IN:
                q = q.where(InventoryDocument.ingreso_type == movement_type)
            elif doc_type == DocumentType.EG:
                if movement_type == "baja":
                    q = q.where(
                        InventoryDocument.ingreso_type.in_(
                            [movement_type, *LEGACY_BAJA_TYPES]
                        )
                    )
                else:
                    q = q.where(InventoryDocument.ingreso_type == movement_type)
        if status:
            q = q.where(InventoryDocument.status == status)
        if product_id:
            q = q.join(InventoryDocumentLine).where(
                InventoryDocumentLine.product_id == product_id
            )
        if cursor:
            q = q.where(InventoryDocument.id < cursor)
        q = q.limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().unique().all())

    async def create_auth_code(self, code: AuthorizationCode) -> AuthorizationCode:
        self.db.add(code)
        await self.db.flush()
        return code

    async def get_valid_auth_code(
        self, document_id: int, now: datetime
    ) -> AuthorizationCode | None:
        result = await self.db.execute(
            select(AuthorizationCode)
            .where(
                AuthorizationCode.document_id == document_id,
                AuthorizationCode.expires_at > now,
                AuthorizationCode.used_at.is_(None),
            )
            .order_by(AuthorizationCode.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
