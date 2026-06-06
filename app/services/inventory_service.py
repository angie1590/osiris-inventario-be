import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.enums import AdjustType, AuditAction, DocumentStatus, DocumentType
from app.models.inventory import (
    AuthorizationCode,
    InventoryDocument,
    InventoryDocumentLine,
)
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.product_repository import ProductRepository
from app.services.audit_service import AuditService
from app.services.kardex_service import KardexService


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class InventoryService:
    def __init__(self, db: AsyncSession, kardex_method: str = "PEPS"):
        self.db = db
        self.repo = InventoryRepository(db)
        self.product_repo = ProductRepository(db)
        self.audit = AuditService(db)
        self.kardex = KardexService(db, method=kardex_method)

    async def _get_kardex_method(self) -> str:
        from app.models.system_param import SystemParam

        result = await self.db.execute(
            select(SystemParam).where(SystemParam.key == "kardex_method")
        )
        param = result.scalar_one_or_none()
        return param.value if param else "PEPS"

    async def _get_auth_code_expire_minutes(self) -> int:
        from app.models.system_param import SystemParam

        result = await self.db.execute(
            select(SystemParam).where(SystemParam.key == "auth_code_expire_minutes")
        )
        param = result.scalar_one_or_none()
        default_value = 15
        if not param:
            return default_value
        try:
            value = int(param.value)
        except (TypeError, ValueError):
            return default_value
        return value if value > 0 else default_value

    async def _validate_products_active(self, lines: list) -> None:
        for line in lines:
            p = await self.product_repo.get_by_id(line.product_id)
            if not p:
                raise ValidationAppError(
                    "PRODUCT_NOT_FOUND", f"Product {line.product_id} not found"
                )
            if p.status.value != "active":
                raise ValidationAppError(
                    "PRODUCT_INACTIVE", f"Product {line.product_id} is inactive"
                )

    async def _validate_sufficient_stock(self, lines: list) -> None:
        for line in lines:
            p = await self.product_repo.get_by_id(line.product_id)
            if not p:
                raise ValidationAppError(
                    "PRODUCT_NOT_FOUND", f"Product {line.product_id} not found"
                )
            if p.stock_actual < line.quantity:
                raise ValidationAppError(
                    "INSUFFICIENT_STOCK",
                    f"Product {p.name}: available {p.stock_actual}, requested {line.quantity}",
                )

    async def _assert_not_immutable(self, document: InventoryDocument) -> None:
        if document.status == DocumentStatus.approved:
            raise ConflictError(
                "DOCUMENT_IS_IMMUTABLE", "Approved documents cannot be modified"
            )

    async def create_ingreso(
        self,
        reference: str | None,
        notes: str | None,
        lines_data: list,
        actor_id: int,
        actor_name: str,
        request=None,
    ) -> InventoryDocument:
        if not lines_data:
            raise ValidationAppError(
                "DOCUMENT_REQUIRES_LINES", "Document must have at least one line"
            )

        await self._validate_products_active(lines_data)

        year = datetime.now(timezone.utc).year
        number = await self.repo.generate_document_number(DocumentType.IN, year)

        doc = InventoryDocument(
            number=number,
            doc_type=DocumentType.IN,
            status=DocumentStatus.approved,
            reference=reference,
            notes=notes,
            created_by=actor_id,
        )
        lines = [
            InventoryDocumentLine(
                product_id=l.product_id,
                quantity=l.quantity,
                unit_cost=l.unit_cost,
                unit_price=l.unit_price,
            )
            for l in lines_data
        ]
        doc = await self.repo.create_document(doc, lines)

        # Update stock
        for line in doc.lines:
            await self.product_repo.update_stock(line.product_id, line.quantity)

        # Update Kardex
        method = await self._get_kardex_method()
        kardex = KardexService(self.db, method)
        await kardex.record_entry(doc, doc.lines)

        await self.audit.log(
            AuditAction.CREATE,
            user_id=actor_id,
            username=actor_name,
            entity_type="inventory_document",
            entity_id=doc.id,
            new={"number": number, "type": "IN"},
            request=request,
        )
        await self.db.commit()
        return await self.repo.get_by_id(doc.id)

    async def create_egreso(
        self,
        reference: str | None,
        notes: str | None,
        lines_data: list,
        actor_id: int,
        actor_name: str,
        request=None,
    ) -> InventoryDocument:
        if not lines_data:
            raise ValidationAppError(
                "DOCUMENT_REQUIRES_LINES", "Document must have at least one line"
            )

        await self._validate_products_active(lines_data)
        await self._validate_sufficient_stock(lines_data)

        year = datetime.now(timezone.utc).year
        number = await self.repo.generate_document_number(DocumentType.EG, year)

        doc = InventoryDocument(
            number=number,
            doc_type=DocumentType.EG,
            status=DocumentStatus.approved,
            reference=reference,
            notes=notes,
            created_by=actor_id,
        )
        lines = [
            InventoryDocumentLine(
                product_id=l.product_id,
                quantity=l.quantity,
                unit_cost=l.unit_cost,
                unit_price=l.unit_price,
            )
            for l in lines_data
        ]
        doc = await self.repo.create_document(doc, lines)

        for line in doc.lines:
            await self.product_repo.update_stock(line.product_id, -line.quantity)

        method = await self._get_kardex_method()
        kardex = KardexService(self.db, method)
        await kardex.record_entry(doc, doc.lines)

        await self.audit.log(
            AuditAction.CREATE,
            user_id=actor_id,
            username=actor_name,
            entity_type="inventory_document",
            entity_id=doc.id,
            new={"number": number, "type": "EG"},
            request=request,
        )
        await self.db.commit()
        return await self.repo.get_by_id(doc.id)

    async def create_baja(
        self,
        reference: str | None,
        notes: str | None,
        lines_data: list,
        actor_id: int,
        actor_name: str,
        request=None,
    ) -> InventoryDocument:
        if not lines_data:
            raise ValidationAppError(
                "DOCUMENT_REQUIRES_LINES", "Document must have at least one line"
            )

        await self._validate_products_active(lines_data)

        year = datetime.now(timezone.utc).year
        number = await self.repo.generate_document_number(DocumentType.BI, year)

        doc = InventoryDocument(
            number=number,
            doc_type=DocumentType.BI,
            status=DocumentStatus.pending,
            reference=reference,
            notes=notes,
            created_by=actor_id,
        )
        lines = [
            InventoryDocumentLine(
                product_id=l.product_id,
                quantity=l.quantity,
                unit_cost=l.unit_cost,
                unit_price=l.unit_price,
            )
            for l in lines_data
        ]
        doc = await self.repo.create_document(doc, lines)

        await self.audit.log(
            AuditAction.CREATE,
            user_id=actor_id,
            username=actor_name,
            entity_type="inventory_document",
            entity_id=doc.id,
            new={"number": number, "type": "BI", "status": "pending"},
            request=request,
        )
        await self.db.commit()
        return await self.repo.get_by_id(doc.id)

    async def create_ajuste(
        self,
        adjust_type: AdjustType,
        reference: str | None,
        notes: str | None,
        lines_data: list,
        actor_id: int,
        actor_name: str,
        request=None,
    ) -> InventoryDocument:
        if not lines_data:
            raise ValidationAppError(
                "DOCUMENT_REQUIRES_LINES", "Document must have at least one line"
            )

        await self._validate_products_active(lines_data)
        if adjust_type == AdjustType.decrement:
            await self._validate_sufficient_stock(lines_data)

        year = datetime.now(timezone.utc).year
        number = await self.repo.generate_document_number(DocumentType.AI, year)

        doc = InventoryDocument(
            number=number,
            doc_type=DocumentType.AI,
            status=DocumentStatus.pending,
            adjust_type=adjust_type,
            reference=reference,
            notes=notes,
            created_by=actor_id,
        )
        lines = [
            InventoryDocumentLine(
                product_id=l.product_id,
                quantity=l.quantity,
                unit_cost=l.unit_cost,
                unit_price=l.unit_price,
            )
            for l in lines_data
        ]
        doc = await self.repo.create_document(doc, lines)

        await self.audit.log(
            AuditAction.CREATE,
            user_id=actor_id,
            username=actor_name,
            entity_type="inventory_document",
            entity_id=doc.id,
            new={"number": number, "type": "AI", "status": "pending"},
            request=request,
        )
        await self.db.commit()
        return await self.repo.get_by_id(doc.id)

    async def generate_auth_code(
        self, document_id: int, actor_id: int, actor_name: str, request=None
    ) -> str:
        doc = await self.repo.get_by_id(document_id)
        if not doc:
            raise NotFoundError("DOCUMENT_NOT_FOUND", "Document not found")
        if doc.status != DocumentStatus.pending:
            raise ConflictError(
                "DOCUMENT_NOT_PENDING", "Document is not in pending state"
            )

        raw_code = secrets.token_hex(4).upper()  # 8 char hex
        expire_minutes = await self._get_auth_code_expire_minutes()
        auth_code = AuthorizationCode(
            document_id=document_id,
            code_hash=_hash_code(raw_code),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=expire_minutes),
            created_by=actor_id,
        )
        await self.repo.create_auth_code(auth_code)

        await self.audit.log(
            AuditAction.CREATE,
            user_id=actor_id,
            username=actor_name,
            entity_type="authorization_code",
            entity_id=document_id,
            description=f"Authorization code generated for document {doc.number}",
            request=request,
        )
        await self.db.commit()
        return raw_code

    async def approve_document(
        self,
        document_id: int,
        raw_code: str,
        actor_id: int,
        actor_name: str,
        request=None,
    ) -> InventoryDocument:
        doc = await self.repo.get_by_id(document_id)
        if not doc:
            raise NotFoundError("DOCUMENT_NOT_FOUND", "Document not found")
        if doc.status != DocumentStatus.pending:
            raise ConflictError(
                "DOCUMENT_NOT_PENDING", "Document is not in pending state"
            )

        now = datetime.now(timezone.utc)
        auth_code_rec = await self.repo.get_valid_auth_code(document_id, now)

        if not auth_code_rec or auth_code_rec.code_hash != _hash_code(raw_code):
            raise ValidationAppError(
                "AUTHORIZATION_CODE_INVALID", "Invalid or expired authorization code"
            )

        # Validate stock at approval time
        if doc.doc_type in (DocumentType.BI,) or (
            doc.doc_type == DocumentType.AI and doc.adjust_type == AdjustType.decrement
        ):
            await self._validate_sufficient_stock(doc.lines)

        # Mark code as used
        auth_code_rec.used_at = now

        # Apply stock changes
        for line in doc.lines:
            if doc.doc_type == DocumentType.BI:
                await self.product_repo.update_stock(line.product_id, -line.quantity)
            elif doc.doc_type == DocumentType.AI:
                delta = (
                    line.quantity
                    if doc.adjust_type == AdjustType.increment
                    else -line.quantity
                )
                await self.product_repo.update_stock(line.product_id, delta)

        # Update document status
        doc.status = DocumentStatus.approved
        doc.authorized_by = actor_id
        doc.authorized_at = now

        # Update Kardex
        method = await self._get_kardex_method()
        kardex = KardexService(self.db, method)
        await kardex.record_entry(doc, doc.lines)

        await self.audit.log(
            AuditAction.APPROVE,
            user_id=actor_id,
            username=actor_name,
            entity_type="inventory_document",
            entity_id=doc.id,
            new={"status": "approved", "authorized_by": actor_id},
            request=request,
        )
        await self.db.commit()
        return await self.repo.get_by_id(doc.id)

    async def cancel_document(
        self, document_id: int, actor_id: int, actor_name: str, request=None
    ) -> InventoryDocument:
        doc = await self.repo.get_by_id(document_id)
        if not doc:
            raise NotFoundError("DOCUMENT_NOT_FOUND", "Document not found")
        await self._assert_not_immutable(doc)
        if doc.status != DocumentStatus.pending:
            raise ConflictError(
                "DOCUMENT_NOT_PENDING", "Only pending documents can be cancelled"
            )

        doc.status = DocumentStatus.cancelled
        await self.audit.log(
            AuditAction.CANCEL,
            user_id=actor_id,
            username=actor_name,
            entity_type="inventory_document",
            entity_id=doc.id,
            previous={"status": "pending"},
            new={"status": "cancelled"},
            request=request,
        )
        await self.db.commit()
        return await self.repo.get_by_id(doc.id)
