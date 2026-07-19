import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.enums import AdjustType, AuditAction, DocumentStatus, DocumentType
from app.models.enums import UserRole
from app.models.inventory import (
    AuthorizationCode,
    InventoryDocument,
    InventoryDocumentLine,
    InventorySupplier,
)
from app.models.user import User
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.product_repository import ProductRepository
from app.core.security import verify_password
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

    async def _get_stock_mode(self) -> str:
        from app.models.system_param import SystemParam

        result = await self.db.execute(
            select(SystemParam).where(SystemParam.key == "stock_quantity_mode")
        )
        param = result.scalar_one_or_none()
        return param.value if param else "integer"

    async def _validate_quantity_mode(self, lines: list) -> None:
        """When stock_quantity_mode is 'integer', reject fractional quantities."""
        if await self._get_stock_mode() != "integer":
            return
        for line in lines:
            q = Decimal(str(line.quantity))
            if q != q.to_integral_value():
                raise ValidationAppError(
                    "INVALID_QUANTITY",
                    "La cantidad debe ser un número entero (modo de stock entero).",
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
        ingreso_type: str,
        supplier_id: int | None,
        purchase_document_type: str,
        purchase_document_number: str | None,
        purchase_document_date: datetime | None,
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
        await self._validate_quantity_mode(lines_data)

        if ingreso_type == "purchase" and supplier_id:
            supplier = await self.db.get(InventorySupplier, supplier_id)
            if not supplier or not supplier.is_active:
                raise ValidationAppError(
                    "SUPPLIER_NOT_FOUND", f"Supplier {supplier_id} not found"
                )

        year = datetime.now(timezone.utc).year
        number = await self.repo.generate_document_number(DocumentType.IN, year)

        doc = InventoryDocument(
            number=number,
            doc_type=DocumentType.IN,
            status=DocumentStatus.approved,
            ingreso_type=ingreso_type,
            supplier_id=supplier_id,
            purchase_document_type=purchase_document_type,
            purchase_document_number=purchase_document_number,
            purchase_document_date=purchase_document_date,
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
        await self._validate_quantity_mode(lines_data)
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
        await self._validate_quantity_mode(lines_data)
        await self._validate_sufficient_stock(lines_data)

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
        await self._validate_quantity_mode(lines_data)
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

        approver = await self.db.get(User, actor_id)
        if not approver or approver.role not in (UserRole.admin, UserRole.supervisor):
            raise ValidationAppError(
                "APPROVAL_ROLE_REQUIRED",
                "Only admin or supervisor can approve this document",
            )

        if not approver.approval_code_hash:
            raise ValidationAppError(
                "APPROVAL_CODE_NOT_CONFIGURED",
                "Approver does not have a configured approval code",
            )

        normalized_code = raw_code.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{8}", normalized_code):
            raise ValidationAppError(
                "APPROVAL_CODE_INVALID", "Approval code is invalid"
            )

        if not verify_password(normalized_code, approver.approval_code_hash):
            raise ValidationAppError(
                "APPROVAL_CODE_INVALID", "Approval code is invalid"
            )

        now = datetime.now(timezone.utc)
        auth_code_rec = await self.repo.get_valid_auth_code(document_id, now)
        if auth_code_rec:
            auth_code_rec.used_at = now

        # Validate stock at approval time
        if doc.doc_type in (DocumentType.BI,) or (
            doc.doc_type == DocumentType.AI and doc.adjust_type == AdjustType.decrement
        ):
            await self._validate_sufficient_stock(doc.lines)

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

    def _void_stock_delta(
        self, doc: InventoryDocument, line: InventoryDocumentLine
    ) -> Decimal:
        """Stock delta that REVERSES the document's original effect on stock."""
        if doc.doc_type == DocumentType.IN:
            return -line.quantity
        if doc.doc_type in (DocumentType.EG, DocumentType.BI):
            return line.quantity
        if doc.doc_type == DocumentType.AI:
            return (
                -line.quantity
                if doc.adjust_type == AdjustType.increment
                else line.quantity
            )
        return Decimal("0")

    async def _resolve_void_authorizer(
        self, actor: User, authorizer_pin: str | None
    ) -> User:
        """Resolve who authorizes the void.

        Admin/supervisor authorize themselves (no PIN). Operators must supply
        an admin/supervisor PIN (the approval code — a secret distinct from the
        login password); the matching authorizer is recorded for audit.
        """
        if actor.role in (UserRole.admin, UserRole.supervisor):
            return actor
        if actor.role != UserRole.operator:
            raise ValidationAppError(
                "VOID_ROLE_FORBIDDEN", "No autorizado para anular documentos"
            )
        if not authorizer_pin or not authorizer_pin.strip():
            raise ValidationAppError(
                "VOID_PIN_REQUIRED",
                "Se requiere el PIN de un supervisor o administrador",
            )

        pin = authorizer_pin.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{8}", pin):
            raise ValidationAppError("VOID_PIN_INVALID", "PIN de autorización inválido")

        result = await self.db.execute(
            select(User).where(
                User.is_active.is_(True),
                User.role.in_([UserRole.admin, UserRole.supervisor]),
                User.approval_code_hash.is_not(None),
            )
        )
        for candidate in result.scalars().all():
            if verify_password(pin, candidate.approval_code_hash):
                return candidate
        raise ValidationAppError("VOID_PIN_INVALID", "PIN de autorización inválido")

    async def void_document(
        self,
        document_id: int,
        actor_id: int,
        actor_name: str,
        authorizer_pin: str | None = None,
        request=None,
    ) -> InventoryDocument:
        doc = await self.repo.get_by_id(document_id)
        if not doc:
            raise NotFoundError("DOCUMENT_NOT_FOUND", "Document not found")
        if doc.status != DocumentStatus.approved:
            raise ConflictError(
                "DOCUMENT_NOT_APPROVED",
                "Solo se pueden anular documentos aprobados",
            )

        actor = await self.db.get(User, actor_id)
        if not actor:
            raise NotFoundError("USER_NOT_FOUND", "User not found")
        authorizer = await self._resolve_void_authorizer(actor, authorizer_pin)

        # Pre-check: voiding must not drive any product's stock negative (it
        # would mean the document's stock was already consumed by later
        # movements). Done BEFORE any mutation so the failure is a clean 409 and
        # never an aborted-transaction 500. Works for PEPS and weighted average.
        from collections import defaultdict
        from app.models.product import Product

        deltas: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        for line in doc.lines:
            deltas[line.product_id] += self._void_stock_delta(doc, line)
        for product_id, delta in deltas.items():
            product = await self.db.get(Product, product_id)
            if product is not None and (product.stock_actual + delta) < 0:
                raise ConflictError(
                    "CANNOT_VOID_STOCK_CONSUMED",
                    "No se puede anular: el stock de este documento ya fue consumido por movimientos posteriores.",
                )

        # Reverse Kardex (restores lots / appends a reversal entry).
        method = await self._get_kardex_method()
        kardex = KardexService(self.db, method)
        await kardex.reverse_document(doc)

        # Reverse stock (opposite of original delta).
        for line in doc.lines:
            await self.product_repo.update_stock(
                line.product_id, self._void_stock_delta(doc, line)
            )

        doc.status = DocumentStatus.voided
        doc.authorized_by = authorizer.id

        await self.audit.log(
            AuditAction.CANCEL,
            user_id=actor_id,
            username=actor_name,
            entity_type="inventory_document",
            entity_id=doc.id,
            previous={"status": "approved"},
            new={
                "status": "voided",
                "voided": True,
                "authorized_by": authorizer.id,
                "authorizer": authorizer.username,
            },
            description=f"Documento {doc.number} anulado (autorizó: {authorizer.username})",
            request=request,
        )
        await self.db.commit()
        return await self.repo.get_by_id(doc.id)
