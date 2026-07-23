import hashlib
import re
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.company_config import CompanyConfig
from app.models.enums import AdjustType, AuditAction, DocumentStatus, DocumentType
from app.models.enums import UserRole
from app.models.inventory import (
    AuthorizationCode,
    InventoryCount,
    InventoryCountLine,
    InventoryDocument,
    InventoryDocumentLine,
    InventorySupplier,
)
from app.models.kardex import InventoryLot, KardexEntry
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
    "sale": {"invoice", "sales_note", "none"},
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

    async def _build_count_lines(self, lines_data: list) -> list[InventoryCountLine]:
        await self._validate_products_active(lines_data)
        quantity_lines = [
            SimpleNamespace(product_id=line.product_id, quantity=line.physical_quantity)
            for line in lines_data
        ]
        await self._validate_quantity_mode(quantity_lines)

        grouped: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        for line in lines_data:
            grouped[line.product_id] += Decimal(str(line.physical_quantity))

        count_lines: list[InventoryCountLine] = []
        for product_id, physical_quantity in grouped.items():
            product = await self.product_repo.get_by_id(product_id)
            if not product:
                raise ValidationAppError(
                    "PRODUCT_NOT_FOUND", f"Product {product_id} not found"
                )
            system_quantity = Decimal(str(product.stock_actual))
            count_lines.append(
                InventoryCountLine(
                    product_id=product_id,
                    product_name_snapshot=product.name,
                    product_isbn_snapshot=product.isbn,
                    product_codigo_interno_snapshot=product.codigo_interno,
                    system_quantity=system_quantity,
                    physical_quantity=physical_quantity,
                    difference_quantity=physical_quantity - system_quantity,
                )
            )

        count_lines.sort(key=lambda line: line.product_name_snapshot)
        return count_lines

    async def _get_count_or_fail(self, count_id: int) -> InventoryCount:
        count = await self.repo.get_count_by_id(count_id)
        if not count:
            raise NotFoundError("COUNT_NOT_FOUND", "Conteo no encontrado")
        return count

    def _assert_count_editable(self, count: InventoryCount) -> None:
        if count.status != "draft":
            raise ConflictError(
                "COUNT_NOT_EDITABLE", "Solo se puede editar un conteo en borrador"
            )

    async def _resolve_count_positive_unit_cost(self, product_id: int) -> Decimal:
        _, _, avg_cost = await self.kardex._get_current_balance(product_id)
        return Decimal(str(avg_cost or 0))

    async def _get_last_historical_unit_cost(self, product_id: int) -> Decimal | None:
        result = await self.db.execute(
            select(KardexEntry)
            .where(
                KardexEntry.product_id == product_id,
                (KardexEntry.cost_in > 0) | (KardexEntry.cost_out > 0),
            )
            .order_by(KardexEntry.created_at.desc(), KardexEntry.id.desc())
            .limit(1)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return None
        if entry.cost_in and entry.cost_in > 0:
            return Decimal(str(entry.cost_in))
        if entry.cost_out and entry.cost_out > 0:
            return Decimal(str(entry.cost_out))
        return None

    async def get_adjustment_increment_cost_preview(self, product_id: int) -> dict:
        balance_qty, balance_val, avg_cost = await self.kardex._get_current_balance(
            product_id
        )
        current_cost = Decimal(str(avg_cost or 0))
        current_value = Decimal(str(balance_val or 0))
        current_qty = Decimal(str(balance_qty or 0))

        if current_qty > 0 and current_value > 0 and current_cost > 0:
            return {"product_id": product_id, "mode": "auto", "unit_cost": current_cost}

        historical_cost = await self._get_last_historical_unit_cost(product_id)
        if historical_cost and historical_cost > 0:
            return {
                "product_id": product_id,
                "mode": "suggested",
                "unit_cost": historical_cost,
            }

        return {"product_id": product_id, "mode": "required_manual", "unit_cost": None}

    async def list_adjustment_increment_cost_previews(self, product_ids: list[int]) -> list[dict]:
        previews: list[dict] = []
        seen: set[int] = set()
        for product_id in product_ids:
            if product_id in seen:
                continue
            seen.add(product_id)
            previews.append(await self.get_adjustment_increment_cost_preview(product_id))
        return previews

    async def _resolve_increment_adjustment_unit_costs(self, lines_data: list) -> list[Decimal]:
        costs: list[Decimal] = []
        for line in lines_data:
            preview = await self.get_adjustment_increment_cost_preview(line.product_id)
            provided = Decimal(str(getattr(line, "unit_cost", 0) or 0))
            if preview["mode"] == "auto":
                costs.append(Decimal(str(preview["unit_cost"] or 0)))
                continue
            if preview["mode"] == "suggested":
                costs.append(
                    provided if provided > 0 else Decimal(str(preview["unit_cost"] or 0))
                )
                continue
            if provided <= 0:
                raise ValidationAppError(
                    "UNIT_COST_REQUIRED",
                    "Debe ingresar el costo unitario del inventario encontrado.",
                )
            costs.append(provided)
        return costs

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
        resolved_unit_costs = (
            await self._resolve_increment_adjustment_unit_costs(lines_data)
            if ingreso_type == "adjustment_positive"
            else [Decimal(str(getattr(l, "unit_cost", 0) or 0)) for l in lines_data]
        )
        if ingreso_type == "adjustment_positive":
            for idx, resolved_cost in enumerate(resolved_unit_costs):
                rounded_cost = Decimal(str(resolved_cost)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if rounded_cost <= 0:
                    raise ValidationAppError(
                        "UNIT_COST_REQUIRED",
                        f"Debe ingresar un costo unitario mayor a 0 para el producto {lines_data[idx].product_id}.",
                    )
        lines = [
            InventoryDocumentLine(
                product_id=l.product_id,
                quantity=l.quantity,
                unit_cost=resolved_unit_costs[idx],
                unit_price=l.unit_price,
                unit_price_base=l.unit_price_base,
                discount_type=l.discount_type,
                discount_value=l.discount_value,
            )
            for idx, l in enumerate(lines_data)
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
        seller_name: str | None,
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

        normalized_seller_name = (seller_name or "").strip().upper()
        if egreso_type == "sale":
            if not normalized_seller_name:
                raise ValidationAppError(
                    "SELLER_REQUIRED",
                    "Vendedor es obligatorio para ventas",
                )

            result = await self.db.execute(select(CompanyConfig).limit(1))
            company = result.scalar_one_or_none()
            allowed_sellers: list[str] = []
            for item in (company.sellers if company else []):
                value = str(item).strip().upper()
                if value and value not in allowed_sellers:
                    allowed_sellers.append(value)

            if normalized_seller_name not in allowed_sellers:
                raise ValidationAppError(
                    "SELLER_NOT_ALLOWED",
                    "El vendedor no está habilitado para la empresa",
                )

            seller_name = normalized_seller_name
        else:
            seller_name = None

        normalized_purchase_document_number = (purchase_document_number or "").strip()
        if egreso_type == "sale":
            if purchase_document_type == "none":
                purchase_document_number = "Venta sin documento"
            elif not normalized_purchase_document_number:
                raise ValidationAppError(
                    "PURCHASE_DOCUMENT_NUMBER_REQUIRED",
                    "Número de documento es obligatorio para ventas",
                )
            else:
                purchase_document_number = normalized_purchase_document_number
        else:
            purchase_document_number = normalized_purchase_document_number or None

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
            seller_name=seller_name,
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

    async def create_count(
        self,
        description: str,
        lines_data: list,
        actor_id: int,
        actor_name: str,
        request=None,
    ) -> InventoryCount:
        lines = await self._build_count_lines(lines_data)
        year = datetime.now(timezone.utc).year
        number = await self.repo.generate_count_number(year)

        count = InventoryCount(
            number=number,
            status="draft",
            description=description.strip(),
            created_by=actor_id,
        )
        count = await self.repo.create_count(count, lines)

        await self.audit.log(
            AuditAction.CREATE,
            user_id=actor_id,
            username=actor_name,
            entity_type="inventory_count",
            entity_id=count.id,
            new={"number": number, "status": "draft"},
            request=request,
        )
        await self.db.commit()
        return await self.repo.get_count_by_id(count.id)

    async def update_count(
        self,
        count_id: int,
        description: str,
        lines_data: list,
        actor_id: int,
        actor_name: str,
        request=None,
    ) -> InventoryCount:
        count = await self._get_count_or_fail(count_id)
        self._assert_count_editable(count)

        count.description = description.strip()
        count.lines = await self._build_count_lines(lines_data)
        await self.db.flush()

        await self.audit.log(
            AuditAction.UPDATE,
            user_id=actor_id,
            username=actor_name,
            entity_type="inventory_count",
            entity_id=count.id,
            new={"number": count.number, "status": count.status},
            request=request,
        )
        await self.db.commit()
        return await self.repo.get_count_by_id(count.id)

    async def apply_count(
        self,
        count_id: int,
        actor_id: int,
        actor_name: str,
        line_costs_data: list | None = None,
        request=None,
    ) -> InventoryCount:
        count = await self._get_count_or_fail(count_id)
        self._assert_count_editable(count)

        provided_cost_by_product: dict[int, Decimal] = {
            int(item.product_id): Decimal(str(item.unit_cost))
            for item in (line_costs_data or [])
        }

        positive_lines_raw = []
        negative_lines = []
        for line in count.lines:
            difference = Decimal(str(line.difference_quantity))
            if difference > 0:
                positive_lines_raw.append(
                    SimpleNamespace(
                        product_id=line.product_id,
                        quantity=difference,
                        unit_cost=provided_cost_by_product.get(
                            line.product_id, Decimal("0")
                        ),
                        unit_price=Decimal("0"),
                        unit_price_base=None,
                        discount_type=None,
                        discount_value=None,
                    )
                )
            elif difference < 0:
                negative_lines.append(
                    SimpleNamespace(
                        product_id=line.product_id,
                        quantity=abs(difference),
                        unit_cost=Decimal("0"),
                        unit_price=Decimal("0"),
                        unit_price_base=None,
                        discount_type=None,
                        discount_value=None,
                    )
                )

        notes = f"Conteo {count.number}: {count.description}"
        positive_doc = None
        negative_doc = None

        resolved_positive_costs = (
            await self._resolve_increment_adjustment_unit_costs(positive_lines_raw)
            if positive_lines_raw
            else []
        )
        positive_lines = [
            SimpleNamespace(
                product_id=line.product_id,
                quantity=line.quantity,
                unit_cost=resolved_positive_costs[idx],
                unit_price=line.unit_price,
                unit_price_base=line.unit_price_base,
                discount_type=line.discount_type,
                discount_value=line.discount_value,
            )
            for idx, line in enumerate(positive_lines_raw)
        ]

        if positive_lines:
            positive_doc = await self.create_ingreso(
                "adjustment_positive",
                None,
                "adjustment_act",
                None,
                None,
                count.number,
                notes,
                positive_lines,
                actor_id,
                actor_name,
                request,
            )
        if negative_lines:
            negative_doc = await self.create_egreso(
                "adjustment_negative",
                "adjustment_act",
                None,
                None,
                None,
                None,
                "physical_count",
                count.number,
                notes,
                negative_lines,
                actor_id,
                actor_name,
                request,
            )

        count.status = "applied"
        count.applied_at = datetime.now(timezone.utc)
        count.positive_adjustment_document_id = positive_doc.id if positive_doc else None
        count.negative_adjustment_document_id = negative_doc.id if negative_doc else None

        await self.audit.log(
            AuditAction.APPROVE,
            user_id=actor_id,
            username=actor_name,
            entity_type="inventory_count",
            entity_id=count.id,
            new={
                "number": count.number,
                "status": count.status,
                "positive_adjustment_document_id": count.positive_adjustment_document_id,
                "negative_adjustment_document_id": count.negative_adjustment_document_id,
            },
            request=request,
        )
        await self.db.commit()
        return await self.repo.get_count_by_id(count.id)

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
            resolved_unit_costs = [
                Decimal(str(getattr(l, "unit_cost", 0) or 0)) for l in lines_data
            ]
        else:
            resolved_unit_costs = await self._resolve_increment_adjustment_unit_costs(
                lines_data
            )

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
                unit_cost=resolved_unit_costs[idx],
                unit_price=l.unit_price,
            )
            for idx, l in enumerate(lines_data)
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
