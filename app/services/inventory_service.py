import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.company_config import CompanyConfig
from app.models.enums import AdjustType, AuditAction, DocumentStatus, DocumentType
from app.models.enums import UserRole
from app.models.inventory import (
    AuthorizationCode,
    InventoryDocument,
    InventoryDocumentLine,
    InventorySupplier,
)
from app.models.kardex import InventoryLot
from app.models.user import User
from app.repositories.inventory_repository import InventoryRepository
from app.repositories.product_repository import ProductRepository
from app.core.security import verify_password
from app.services.audit_service import AuditService
from app.services.kardex_service import KardexService


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


INGRESO_DOCUMENT_TYPES: dict[str, set[str]] = {
    "purchase": {
        "invoice",
        "sales_note",
        "liquidation_purchase",
        "receipt",
        "other",
    },
    "initial_inventory": {"inventory_act", "none"},
    "adjustment_positive": {"adjustment_act", "none"},
    "customer_return": {"invoice", "credit_note", "other"},
    "production": {"production_act", "none"},
    "transfer_received": {"transfer_note", "none"},
    "other": {"other", "none"},
}

EGRESO_DOCUMENT_TYPES: dict[str, set[str]] = {
    "sale": {"invoice", "sales_note"},
    "baja": {"disposal_act", "none"},
    "adjustment_negative": {"adjustment_act", "none"},
    "supplier_return": {"supplier_return", "invoice", "transfer_note"},
    "internal_consumption": {"internal_consumption_act", "none"},
    "transfer_sent": {"transfer_note", "transfer_act"},
    "other": {"other", "none"},
}

DEFAULT_BAJA_REASONS = {
    "damage",
    "expiration",
    "loss",
    "theft",
    "donation",
    "gift",
    "destruction",
    "sample",
    "other",
}

DEFAULT_ADJUSTMENT_REASONS = {
    "physical_count",
    "record_error",
    "administrative_correction",
    "other",
}

INVENTORY_EGRESO_TYPES = {
    "baja",
    "adjustment_negative",
    "supplier_return",
    "internal_consumption",
    "transfer_sent",
    "other",
}


def _normalize_egreso_types(types: list[str] | None) -> list[str]:
    legacy_baja_types = {
        "damage_disposal",
        "expiration_disposal",
        "loss_theft_disposal",
        "donation",
    }
    values: list[str] = []
    for item in types or []:
        normalized = "baja" if item in legacy_baja_types else item
        if normalized not in values:
            values.append(normalized)
    return values


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

    async def _validate_enabled_ingreso_type(self, ingreso_type: str) -> None:
        result = await self.db.execute(select(CompanyConfig).limit(1))
        company = result.scalar_one_or_none()
        enabled = company.enabled_ingreso_types if company else [
            "purchase",
            "initial_inventory",
            "adjustment_positive",
            "customer_return",
            "production",
            "transfer_received",
            "other",
        ]
        if ingreso_type not in enabled:
            raise ValidationAppError(
                "INGRESO_TYPE_DISABLED",
                "El tipo de ingreso no está habilitado para la empresa",
            )

    async def _validate_enabled_egreso_type(self, egreso_type: str) -> None:
        result = await self.db.execute(select(CompanyConfig).limit(1))
        company = result.scalar_one_or_none()
        enabled = _normalize_egreso_types(company.enabled_egreso_types if company else [
            "sale",
            "baja",
            "adjustment_negative",
            "supplier_return",
            "internal_consumption",
            "transfer_sent",
            "other",
        ])
        if egreso_type not in enabled:
            raise ValidationAppError(
                "EGRESO_TYPE_DISABLED",
                "El tipo de egreso no está habilitado para la empresa",
            )

    async def _validate_enabled_baja_reason(self, baja_reason: str) -> None:
        result = await self.db.execute(select(CompanyConfig).limit(1))
        company = result.scalar_one_or_none()
        enabled = company.enabled_baja_reasons if company else sorted(DEFAULT_BAJA_REASONS)
        if baja_reason not in enabled:
            raise ValidationAppError(
                "BAJA_REASON_DISABLED",
                "El motivo de la baja no está habilitado para la empresa",
            )

    def _validate_adjustment_reason(self, adjustment_reason: str) -> None:
        if adjustment_reason not in DEFAULT_ADJUSTMENT_REASONS:
            raise ValidationAppError(
                "ADJUSTMENT_REASON_INVALID",
                "Motivo del ajuste inválido",
            )

    async def _resolve_egreso_unit_costs(self, lines_data: list, method: str) -> list[Decimal]:
        if method == "PEPS":
            product_ids = list({line.product_id for line in lines_data})
            lots_result = await self.db.execute(
                select(InventoryLot)
                .where(
                    InventoryLot.product_id.in_(product_ids),
                    InventoryLot.quantity_available > 0,
                )
                .order_by(
                    InventoryLot.product_id.asc(),
                    InventoryLot.lot_date.asc(),
                    InventoryLot.id.asc(),
                )
            )
            lots_by_product: dict[int, list[dict[str, Decimal]]] = {}
            for lot in lots_result.scalars().all():
                lots_by_product.setdefault(lot.product_id, []).append(
                    {
                        "available": Decimal(str(lot.quantity_available)),
                        "unit_cost": Decimal(str(lot.unit_cost)),
                    }
                )

            costs: list[Decimal] = []
            for line in lines_data:
                qty = Decimal(str(line.quantity))
                remaining = qty
                consumed_value = Decimal("0")
                product_lots = lots_by_product.get(line.product_id, [])

                for lot in product_lots:
                    if remaining <= 0:
                        break
                    available = lot["available"]
                    if available <= 0:
                        continue
                    consumed = min(available, remaining)
                    consumed_value += consumed * lot["unit_cost"]
                    lot["available"] = available - consumed
                    remaining -= consumed

                unit_cost = (consumed_value / qty) if qty > 0 else Decimal("0")
                costs.append(unit_cost)

            return costs

        avg_by_product: dict[int, Decimal] = {}
        for line in lines_data:
            if line.product_id in avg_by_product:
                continue
            _, _, avg_cost = await self.kardex._get_current_balance(line.product_id)
            avg_by_product[line.product_id] = Decimal(str(avg_cost))

        return [avg_by_product.get(line.product_id, Decimal("0")) for line in lines_data]

    def _validate_document_type_for_ingreso(
        self, ingreso_type: str, document_type: str
    ) -> None:
        allowed = INGRESO_DOCUMENT_TYPES.get(ingreso_type)
        if allowed and document_type not in allowed:
            raise ValidationAppError(
                "INVALID_PURCHASE_DOCUMENT_TYPE",
                "El tipo de documento no está permitido para este tipo de ingreso",
            )

    def _validate_document_type_for_egreso(
        self, egreso_type: str, document_type: str
    ) -> None:
        allowed = EGRESO_DOCUMENT_TYPES.get(egreso_type)
        if allowed and document_type not in allowed:
            raise ValidationAppError(
                "INVALID_PURCHASE_DOCUMENT_TYPE",
                "El tipo de documento no está permitido para este tipo de egreso",
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

        await self._validate_enabled_ingreso_type(ingreso_type)
        self._validate_document_type_for_ingreso(ingreso_type, purchase_document_type)
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
                unit_price_base=l.unit_price_base,
                discount_type=l.discount_type,
                discount_value=l.discount_value,
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
        egreso_type: str,
        purchase_document_type: str,
        purchase_document_number: str | None,
        purchase_document_date: datetime | None,
        baja_reason: str | None,
        adjustment_reason: str | None,
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
        await self._validate_enabled_egreso_type(egreso_type)
        self._validate_document_type_for_egreso(egreso_type, purchase_document_type)

        if egreso_type == "baja":
            if not baja_reason:
                raise ValidationAppError(
                    "BAJA_REASON_REQUIRED",
                    "Motivo de la baja es obligatorio",
                )
            await self._validate_enabled_baja_reason(baja_reason)
        else:
            baja_reason = None

        if egreso_type == "adjustment_negative":
            if not adjustment_reason:
                raise ValidationAppError(
                    "ADJUSTMENT_REASON_REQUIRED",
                    "Motivo del ajuste es obligatorio",
                )
            self._validate_adjustment_reason(adjustment_reason)
        else:
            adjustment_reason = None

        if purchase_document_date is None:
            purchase_document_date = datetime.now(timezone.utc)

        if purchase_document_type == "other" and not (notes or "").strip():
            raise ValidationAppError(
                "NOTES_REQUIRED_FOR_OTHER_DOCUMENT",
                "Observaciones es obligatorio cuando el documento es Otro",
            )

        year = datetime.now(timezone.utc).year
        number = await self.repo.generate_document_number(DocumentType.EG, year)

        doc = InventoryDocument(
            number=number,
            doc_type=DocumentType.EG,
            status=DocumentStatus.approved,
            ingreso_type=egreso_type,
            purchase_document_type=purchase_document_type,
            purchase_document_number=purchase_document_number,
            purchase_document_date=purchase_document_date,
            baja_reason=baja_reason,
            adjustment_reason=adjustment_reason,
            reference=reference,
            notes=notes,
            created_by=actor_id,
        )
        is_inventory_egreso = egreso_type in INVENTORY_EGRESO_TYPES
        method = await self._get_kardex_method()
        costs = (
            await self._resolve_egreso_unit_costs(lines_data, method)
            if is_inventory_egreso
            else [Decimal(str(getattr(l, "unit_cost", 0) or 0)) for l in lines_data]
        )
        lines = [
            InventoryDocumentLine(
                product_id=l.product_id,
                quantity=l.quantity,
                unit_cost=costs[idx],
                unit_price=l.unit_price if not is_inventory_egreso else Decimal("0"),
                unit_price_base=(
                    l.unit_price_base if not is_inventory_egreso else None
                ),
                discount_type=(l.discount_type if not is_inventory_egreso else None),
                discount_value=(l.discount_value if not is_inventory_egreso else None),
            )
            for idx, l in enumerate(lines_data)
        ]
        doc = await self.repo.create_document(doc, lines)

        for line in doc.lines:
            await self.product_repo.update_stock(line.product_id, -line.quantity)

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
