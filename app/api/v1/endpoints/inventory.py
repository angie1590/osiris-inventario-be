from datetime import date, datetime, time, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_company_configured, require_role
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationAppError
from app.models.enums import AuditAction, DocumentStatus, DocumentType, UserRole
from app.models.inventory import (
    InventoryCount,
    InventoryCustomer,
    InventoryDocument,
    InventoryDocumentAttachment,
    InventorySupplier,
)
from app.models.user import User
from app.repositories.inventory_repository import InventoryRepository
from app.schemas.inventory import (
    AjusteCreate,
    ApproveRequest,
    AuthCodeRequest,
    BajaCreate,
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    DocumentResponse,
    DocumentPageResponse,
    DocumentAttachmentResponse,
    EgresoCreate,
    AdjustmentIncrementCostPreview,
    InventoryCountCreate,
    InventoryCountApply,
    InventoryCountResponse,
    InventoryCountPageResponse,
    InventoryCountUpdate,
    IngresoCreate,
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
    SaleExchangeCreate,
    SaleExchangeResponse,
    VoidRequest,
)
from app.services.inventory_service import InventoryService
from app.services.audit_service import AuditService
from app.utils.sales_note_pdf import build_sales_note_pdf

router = APIRouter()

_operator_up = require_role(UserRole.admin, UserRole.supervisor, UserRole.operator)
_approver_roles = require_role(UserRole.admin, UserRole.supervisor)
_read_roles = require_role(UserRole.admin, UserRole.operator, UserRole.supervisor)


def _sale_only(user: User) -> bool:
    """El vendedor solo opera egresos de tipo venta."""
    return user.role == UserRole.operator


def _parse_document_date_bound(value: str | None, *, end_of_day: bool) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if "T" not in raw and " " not in raw:
        local_date = date.fromisoformat(raw)
        local_datetime = datetime.combine(
            local_date,
            time.max if end_of_day else time.min,
            tzinfo=ZoneInfo(settings.APP_TIMEZONE),
        )
        return local_datetime.astimezone(timezone.utc)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _page_response(items: list, total: int, page: int, page_size: int) -> dict:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


# --- Conteos ---


@router.post(
    "/conteos", response_model=InventoryCountResponse, status_code=status.HTTP_201_CREATED
)
async def create_count(
    body: InventoryCountCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_operator_up),
    _company: None = Depends(require_company_configured),
):
    svc = InventoryService(db)
    return await svc.create_count(
        body.description,
        body.lines,
        current_user.id,
        current_user.username,
        request,
    )


@router.get("/conteos", response_model=list[InventoryCountResponse])
async def list_counts(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status: str | None = None,
    limit: int = 50,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    repo = InventoryRepository(db)
    return await repo.list_counts(date_from, date_to, status, limit, cursor)


@router.get("/conteos/page", response_model=InventoryCountPageResponse)
async def list_counts_page(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    repo = InventoryRepository(db)
    items, total = await repo.list_counts_page(
        page, page_size, date_from, date_to, status
    )
    return _page_response(items, total, page, page_size)


@router.get("/conteos/{count_id}", response_model=InventoryCountResponse)
async def get_count(
    count_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    repo = InventoryRepository(db)
    count = await repo.get_count_by_id(count_id)
    if not count:
        raise NotFoundError("COUNT_NOT_FOUND", "Conteo no encontrado")
    return count


@router.patch("/conteos/{count_id}", response_model=InventoryCountResponse)
async def update_count(
    count_id: int,
    body: InventoryCountUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_operator_up),
):
    svc = InventoryService(db)
    return await svc.update_count(
        count_id,
        body.description,
        body.lines,
        current_user.id,
        current_user.username,
        request,
    )


@router.post("/conteos/{count_id}/apply", response_model=InventoryCountResponse)
async def apply_count(
    count_id: int,
    request: Request,
    body: InventoryCountApply | None = Body(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_operator_up),
):
    svc = InventoryService(db)
    return await svc.apply_count(
        count_id,
        current_user.id,
        current_user.username,
        body.line_costs if body else [],
        request,
    )


# --- Ingresos ---


@router.post(
    "/ingresos", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED
)
async def create_ingreso(
    body: IngresoCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_operator_up),
    _company: None = Depends(require_company_configured),
):
    svc = InventoryService(db)
    return await svc.create_ingreso(
        body.ingreso_type,
        body.supplier_id,
        body.purchase_document_type,
        body.purchase_document_number,
        body.purchase_document_date,
        body.reference,
        body.notes,
        body.lines,
        current_user.id,
        current_user.username,
        request,
        actor_role=current_user.role,
    )


@router.post(
    "/ingresos/{document_id}/attachments",
    response_model=DocumentAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_ingreso_attachment(
    document_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_approver_roles),
):
    doc = await db.get(InventoryDocument, document_id)
    if not doc or doc.doc_type != DocumentType.IN:
        raise NotFoundError("DOCUMENT_NOT_FOUND", "Ingreso not found")

    content_type = file.content_type or "application/octet-stream"
    if content_type not in {"application/pdf", "image/png", "image/jpeg", "image/webp"}:
        raise ValidationAppError(
            "INVALID_ATTACHMENT_TYPE",
            "Solo se permiten archivos PDF o imagen (PNG/JPG/WEBP).",
        )

    base_dir = Path(settings.DOCUMENT_UPLOAD_DIR)
    doc_dir = base_dir / f"IN-{document_id}"
    doc_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "documento").suffix or ".bin"
    file_name = f"{uuid4().hex}{ext}"
    target = doc_dir / file_name

    content = await file.read()
    target.write_bytes(content)

    attachment = InventoryDocumentAttachment(
        document_id=document_id,
        original_name=file.filename or file_name,
        mime_type=content_type,
        file_path=str(target),
        file_size=len(content),
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment


@router.get(
    "/ingresos/{document_id}/attachments",
    response_model=list[DocumentAttachmentResponse],
)
async def list_ingreso_attachments(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_approver_roles),
):
    doc = await db.get(InventoryDocument, document_id)
    if not doc or doc.doc_type != DocumentType.IN:
        raise NotFoundError("DOCUMENT_NOT_FOUND", "Ingreso not found")

    result = await db.execute(
        select(InventoryDocumentAttachment)
        .where(InventoryDocumentAttachment.document_id == document_id)
        .order_by(InventoryDocumentAttachment.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/ingresos/{document_id}/attachments/{attachment_id}")
async def download_ingreso_attachment(
    document_id: int,
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_approver_roles),
):
    attachment = await db.get(InventoryDocumentAttachment, attachment_id)
    if not attachment or attachment.document_id != document_id:
        raise NotFoundError("ATTACHMENT_NOT_FOUND", "Attachment not found")

    path = Path(attachment.file_path)
    if not path.exists():
        raise NotFoundError("ATTACHMENT_NOT_FOUND", "Attachment not found")

    return FileResponse(
        path=str(path),
        media_type=attachment.mime_type,
        filename=attachment.original_name,
    )


@router.get("/suppliers", response_model=list[SupplierResponse])
async def list_suppliers(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    q = select(InventorySupplier).order_by(InventorySupplier.trade_name.asc())
    if active_only:
        q = q.where(InventorySupplier.is_active.is_(True))
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post(
    "/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED
)
async def create_supplier(
    body: SupplierCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_operator_up),
):
    existing = await db.execute(
        select(InventorySupplier).where(
            InventorySupplier.identification_type == body.identification_type,
            InventorySupplier.ruc == body.identification_number,
        )
    )
    if existing.scalar_one_or_none():
        raise ValidationAppError(
            "SUPPLIER_IDENTIFICATION_EXISTS",
            "La identificación ya está registrada",
        )

    supplier = InventorySupplier(
        identification_type=body.identification_type,
        ruc=body.identification_number,
        trade_name=body.trade_name,
        legal_name=body.legal_name,
        address=body.address,
        phone=body.phone,
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)

    audit = AuditService(db)
    await audit.log(
        AuditAction.CREATE,
        user_id=current_user.id,
        username=current_user.username,
        entity_type="inventory_supplier",
        entity_id=supplier.id,
        new={
            "identification_type": supplier.identification_type,
            "identification_number": supplier.ruc,
            "trade_name": supplier.trade_name,
            "legal_name": supplier.legal_name,
            "address": supplier.address,
            "phone": supplier.phone,
            "is_active": supplier.is_active,
        },
        request=request,
    )
    await db.commit()
    return supplier


@router.patch("/suppliers/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: int,
    body: SupplierUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_operator_up),
):
    supplier = await db.get(InventorySupplier, supplier_id)
    if not supplier:
        raise NotFoundError("SUPPLIER_NOT_FOUND", "Proveedor no encontrado")

    payload = body.model_dump(exclude_unset=True)
    next_identification_type = payload.get(
        "identification_type", supplier.identification_type
    )
    next_identification_number = payload.get("identification_number", supplier.ruc)

    if (
        next_identification_type != supplier.identification_type
        or next_identification_number != supplier.ruc
    ):
        existing = await db.execute(
            select(InventorySupplier).where(
                InventorySupplier.id != supplier_id,
                InventorySupplier.identification_type == next_identification_type,
                InventorySupplier.ruc == next_identification_number,
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationAppError(
                "SUPPLIER_IDENTIFICATION_EXISTS",
                "La identificación ya está registrada",
            )

    previous = {
        "identification_type": supplier.identification_type,
        "identification_number": supplier.ruc,
        "trade_name": supplier.trade_name,
        "legal_name": supplier.legal_name,
        "address": supplier.address,
        "phone": supplier.phone,
        "is_active": supplier.is_active,
    }

    for key, value in payload.items():
        setattr(supplier, key, value)

    await db.commit()
    await db.refresh(supplier)

    audit = AuditService(db)
    await audit.log(
        AuditAction.UPDATE,
        user_id=current_user.id,
        username=current_user.username,
        entity_type="inventory_supplier",
        entity_id=supplier.id,
        previous=previous,
        new={
            "identification_type": supplier.identification_type,
            "identification_number": supplier.ruc,
            "trade_name": supplier.trade_name,
            "legal_name": supplier.legal_name,
            "address": supplier.address,
            "phone": supplier.phone,
            "is_active": supplier.is_active,
        },
        request=request,
    )
    await db.commit()
    return supplier


@router.delete("/suppliers/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    supplier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_operator_up),
):
    supplier = await db.get(InventorySupplier, supplier_id)
    if not supplier:
        raise NotFoundError("SUPPLIER_NOT_FOUND", "Proveedor no encontrado")

    previous = {
        "identification_type": supplier.identification_type,
        "identification_number": supplier.ruc,
        "trade_name": supplier.trade_name,
        "legal_name": supplier.legal_name,
        "address": supplier.address,
        "phone": supplier.phone,
        "is_active": supplier.is_active,
    }

    supplier.is_active = False
    await db.commit()

    audit = AuditService(db)
    await audit.log(
        AuditAction.DELETE,
        user_id=current_user.id,
        username=current_user.username,
        entity_type="inventory_supplier",
        entity_id=supplier.id,
        previous=previous,
        new={
            "identification_type": supplier.identification_type,
            "identification_number": supplier.ruc,
            "trade_name": supplier.trade_name,
            "legal_name": supplier.legal_name,
            "address": supplier.address,
            "phone": supplier.phone,
            "is_active": supplier.is_active,
        },
        request=request,
    )
    await db.commit()
    return None


@router.get("/customers", response_model=list[CustomerResponse])
async def list_customers(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    q = select(InventoryCustomer).order_by(InventoryCustomer.name.asc())
    if active_only:
        q = q.where(InventoryCustomer.is_active.is_(True))
    result = await db.execute(q)
    return list(result.scalars().all())


def _customer_snapshot(customer: InventoryCustomer) -> dict:
    return {
        "identification_type": customer.identification_type,
        "identification_number": customer.identification_number,
        "name": customer.name,
        "address": customer.address,
        "phone": customer.phone,
        "is_active": customer.is_active,
    }


@router.post(
    "/customers", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED
)
async def create_customer(
    body: CustomerCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_operator_up),
):
    existing = await db.execute(
        select(InventoryCustomer).where(
            InventoryCustomer.identification_type == body.identification_type,
            InventoryCustomer.identification_number == body.identification_number,
        )
    )
    if existing.scalar_one_or_none():
        raise ValidationAppError(
            "CUSTOMER_IDENTIFICATION_EXISTS",
            "La identificación ya está registrada",
        )

    customer = InventoryCustomer(
        identification_type=body.identification_type,
        identification_number=body.identification_number,
        name=body.name,
        address=body.address,
        phone=body.phone,
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)

    audit = AuditService(db)
    await audit.log(
        AuditAction.CREATE,
        user_id=current_user.id,
        username=current_user.username,
        entity_type="inventory_customer",
        entity_id=customer.id,
        new=_customer_snapshot(customer),
        request=request,
    )
    await db.commit()
    return customer


@router.patch("/customers/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: int,
    body: CustomerUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_operator_up),
):
    customer = await db.get(InventoryCustomer, customer_id)
    if not customer:
        raise NotFoundError("CUSTOMER_NOT_FOUND", "Cliente no encontrado")

    payload = body.model_dump(exclude_unset=True)
    next_type = payload.get("identification_type", customer.identification_type)
    next_number = payload.get(
        "identification_number", customer.identification_number
    )

    if (
        next_type != customer.identification_type
        or next_number != customer.identification_number
    ):
        existing = await db.execute(
            select(InventoryCustomer).where(
                InventoryCustomer.id != customer_id,
                InventoryCustomer.identification_type == next_type,
                InventoryCustomer.identification_number == next_number,
            )
        )
        if existing.scalar_one_or_none():
            raise ValidationAppError(
                "CUSTOMER_IDENTIFICATION_EXISTS",
                "La identificación ya está registrada",
            )

    previous = _customer_snapshot(customer)
    for key, value in payload.items():
        setattr(customer, key, value)

    await db.commit()
    await db.refresh(customer)

    audit = AuditService(db)
    await audit.log(
        AuditAction.UPDATE,
        user_id=current_user.id,
        username=current_user.username,
        entity_type="inventory_customer",
        entity_id=customer.id,
        previous=previous,
        new=_customer_snapshot(customer),
        request=request,
    )
    await db.commit()
    return customer


@router.delete("/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_operator_up),
):
    customer = await db.get(InventoryCustomer, customer_id)
    if not customer:
        raise NotFoundError("CUSTOMER_NOT_FOUND", "Cliente no encontrado")

    previous = _customer_snapshot(customer)
    customer.is_active = False
    await db.commit()

    audit = AuditService(db)
    await audit.log(
        AuditAction.DELETE,
        user_id=current_user.id,
        username=current_user.username,
        entity_type="inventory_customer",
        entity_id=customer.id,
        previous=previous,
        new=_customer_snapshot(customer),
        request=request,
    )
    await db.commit()
    return None


@router.get("/ingresos", response_model=list[DocumentResponse])
async def list_ingresos(
    date_from: str | None = None,
    date_to: str | None = None,
    product_id: int | None = None,
    created_by: int | None = None,
    type_: str | None = Query(None, alias="type"),
    limit: int = 50,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_approver_roles),
):
    repo = InventoryRepository(db)
    try:
        date_from_dt = _parse_document_date_bound(date_from, end_of_day=False)
        date_to_dt = _parse_document_date_bound(date_to, end_of_day=True)
    except ValueError:
        raise ValidationAppError(
            "INVALID_DATE_RANGE", "date_from/date_to must be valid ISO date or datetime"
        )
    if date_from_dt and date_to_dt and date_from_dt > date_to_dt:
        raise ValidationAppError(
            "INVALID_DATE_RANGE", "date_from must be before date_to"
        )
    return await repo.list(
        DocumentType.IN,
        date_from_dt,
        date_to_dt,
        product_id,
        created_by,
        type_,
        limit=limit,
        cursor=cursor,
    )


@router.get("/ingresos/page", response_model=DocumentPageResponse)
async def list_ingresos_page(
    date_from: str | None = None,
    date_to: str | None = None,
    product_id: int | None = None,
    created_by: int | None = None,
    type_: str | None = Query(None, alias="type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_approver_roles),
):
    try:
        date_from_dt = _parse_document_date_bound(date_from, end_of_day=False)
        date_to_dt = _parse_document_date_bound(date_to, end_of_day=True)
    except ValueError:
        raise ValidationAppError(
            "INVALID_DATE_RANGE", "date_from/date_to must be valid ISO date or datetime"
        )
    if date_from_dt and date_to_dt and date_from_dt > date_to_dt:
        raise ValidationAppError("INVALID_DATE_RANGE", "date_from must be before date_to")
    repo = InventoryRepository(db)
    items, total = await repo.list_page(
        DocumentType.IN,
        page,
        page_size,
        date_from_dt,
        date_to_dt,
        product_id,
        created_by,
        type_,
    )
    return _page_response(items, total, page, page_size)


@router.get("/ingresos/{document_id}", response_model=DocumentResponse)
async def get_ingreso(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_approver_roles),
):
    repo = InventoryRepository(db)
    doc = await repo.get_by_id(document_id)
    if not doc or doc.doc_type != DocumentType.IN:
        raise NotFoundError("DOCUMENT_NOT_FOUND", "Ingreso not found")
    return doc


# --- Egresos ---


@router.post(
    "/egresos", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED
)
async def create_egreso(
    body: EgresoCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_operator_up),
    _company: None = Depends(require_company_configured),
):
    if _sale_only(current_user) and body.egreso_type != "sale":
        raise ForbiddenError(
            detail="El rol Vendedor solo puede registrar egresos de tipo Venta."
        )
    svc = InventoryService(db)
    return await svc.create_egreso(
        body.egreso_type,
        body.purchase_document_type,
        body.purchase_document_number,
        body.seller_name,
        body.purchase_document_date,
        body.baja_reason,
        body.adjustment_reason,
        body.reference,
        body.notes,
        body.lines,
        current_user.id,
        current_user.username,
        request,
        payment_method=body.payment_method,
        bank_name=body.bank_name,
        amount_received=body.amount_received,
        customer_id=body.customer_id,
    )


@router.get("/egresos", response_model=list[DocumentResponse])
async def list_egresos(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    product_id: int | None = None,
    created_by: int | None = None,
    type_: str | None = Query(None, alias="type"),
    limit: int = 50,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read_roles),
):
    if _sale_only(current_user):
        type_ = "sale"
    repo = InventoryRepository(db)
    return await repo.list(
        DocumentType.EG,
        date_from,
        date_to,
        product_id,
        created_by,
        type_,
        limit=limit,
        cursor=cursor,
    )


@router.get("/egresos/page", response_model=DocumentPageResponse)
async def list_egresos_page(
    date_from: str | None = None,
    date_to: str | None = None,
    product_id: int | None = None,
    created_by: int | None = None,
    type_: str | None = Query(None, alias="type"),
    purchase_document_number: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read_roles),
):
    if _sale_only(current_user):
        type_ = "sale"
    try:
        date_from_dt = _parse_document_date_bound(date_from, end_of_day=False)
        date_to_dt = _parse_document_date_bound(date_to, end_of_day=True)
    except ValueError:
        raise ValidationAppError(
            "INVALID_DATE_RANGE", "date_from/date_to must be valid ISO date or datetime"
        )
    if date_from_dt and date_to_dt and date_from_dt > date_to_dt:
        raise ValidationAppError("INVALID_DATE_RANGE", "date_from must be before date_to")
    repo = InventoryRepository(db)
    items, total = await repo.list_page(
        DocumentType.EG,
        page,
        page_size,
        date_from_dt,
        date_to_dt,
        product_id,
        created_by,
        type_,
        purchase_document_number=purchase_document_number,
    )
    return _page_response(items, total, page, page_size)


@router.get("/egresos/{document_id}", response_model=DocumentResponse)
async def get_egreso(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read_roles),
):
    repo = InventoryRepository(db)
    doc = await repo.get_by_id(document_id)
    if not doc or doc.doc_type != DocumentType.EG:
        raise NotFoundError("DOCUMENT_NOT_FOUND", "Egreso not found")
    if _sale_only(current_user) and doc.egreso_type != "sale":
        raise NotFoundError("DOCUMENT_NOT_FOUND", "Egreso not found")
    return doc


@router.get("/egresos/{document_id}/print.pdf")
async def print_egreso_sales_note(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    repo = InventoryRepository(db)
    doc = await repo.get_by_id(document_id)
    if not doc or doc.doc_type != DocumentType.EG:
        raise NotFoundError("DOCUMENT_NOT_FOUND", "Egreso not found")
    if doc.status != DocumentStatus.approved:
        raise ValidationAppError(
            "DOCUMENT_NOT_PRINTABLE",
            "Only approved documents can be printed",
        )
    if doc.egreso_type != "sale" or doc.purchase_document_type != "sales_note":
        raise ValidationAppError(
            "INVALID_SALES_NOTE",
            "Document is not a sale with sales note",
        )
    return Response(
        build_sales_note_pdf(doc),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{doc.number}.pdf"'},
    )


@router.post(
    "/egresos/{document_id}/exchange",
    response_model=SaleExchangeResponse,
)
async def exchange_sale(
    document_id: int,
    body: SaleExchangeCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read_roles),
):
    svc = InventoryService(db)
    original_doc, return_doc, new_doc, return_total, new_total, difference_total = (
        await svc.exchange_sale_document(
            document_id,
            body.returned_lines,
            body.new_lines,
            body.purchase_document_type,
            body.purchase_document_number,
            body.purchase_document_date,
            body.reference,
            body.notes,
            current_user.id,
            current_user.username,
            body.authorizer_pin,
            request,
        )
    )
    return {
        "original_document": original_doc,
        "return_document": return_doc,
        "new_document": new_doc,
        "return_total": return_total,
        "new_total": new_total,
        "difference_total": difference_total,
    }


# --- Bajas ---


@router.post(
    "/bajas", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED
)
async def create_baja(
    body: BajaCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_approver_roles),
    _company: None = Depends(require_company_configured),
):
    svc = InventoryService(db)
    return await svc.create_baja(
        body.reference,
        body.notes,
        body.lines,
        current_user.id,
        current_user.username,
        request,
    )


@router.post(
    "/bajas/{document_id}/authorization-code", status_code=status.HTTP_201_CREATED
)
async def generate_baja_auth_code(
    document_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_approver_roles),
):
    svc = InventoryService(db)
    code = await svc.generate_auth_code(
        document_id, current_user.id, current_user.username, request
    )
    return {"authorization_code": code, "expires_in_minutes": 15}


@router.post("/bajas/{document_id}/approve", response_model=DocumentResponse)
async def approve_baja(
    document_id: int,
    body: ApproveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_approver_roles),
):
    svc = InventoryService(db)
    return await svc.approve_document(
        document_id,
        body.authorization_code,
        current_user.id,
        current_user.username,
        request,
    )


@router.post("/bajas/{document_id}/cancel", response_model=DocumentResponse)
async def cancel_baja(
    document_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_approver_roles),
):
    svc = InventoryService(db)
    return await svc.cancel_document(
        document_id, current_user.id, current_user.username, request
    )


@router.get("/bajas", response_model=list[DocumentResponse])
async def list_bajas(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status: DocumentStatus | None = None,
    created_by: int | None = None,
    limit: int = 50,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_approver_roles),
):
    repo = InventoryRepository(db)
    return await repo.list(
        DocumentType.BI,
        date_from,
        date_to,
        None,
        created_by,
        status=status,
        limit=limit,
        cursor=cursor,
    )


@router.get("/bajas/page", response_model=DocumentPageResponse)
async def list_bajas_page(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status: DocumentStatus | None = None,
    created_by: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_approver_roles),
):
    repo = InventoryRepository(db)
    items, total = await repo.list_page(
        DocumentType.BI,
        page,
        page_size,
        date_from,
        date_to,
        created_by=created_by,
        status=status,
    )
    return _page_response(items, total, page, page_size)


@router.get("/bajas/{document_id}", response_model=DocumentResponse)
async def get_baja(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_approver_roles),
):
    repo = InventoryRepository(db)
    doc = await repo.get_by_id(document_id)
    if not doc or doc.doc_type != DocumentType.BI:
        raise NotFoundError("DOCUMENT_NOT_FOUND", "Baja not found")
    return doc


# --- Ajustes ---


@router.get(
    "/ajustes/cost-preview",
    response_model=list[AdjustmentIncrementCostPreview],
)
async def list_adjustment_cost_preview(
    product_ids: list[int] = Query(default=[]),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_approver_roles),
):
    svc = InventoryService(db)
    return await svc.list_adjustment_increment_cost_previews(product_ids)


@router.post(
    "/ajustes", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED
)
async def create_ajuste(
    body: AjusteCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_approver_roles),
    _company: None = Depends(require_company_configured),
):
    svc = InventoryService(db)
    return await svc.create_ajuste(
        body.adjust_type,
        body.reference,
        body.notes,
        body.lines,
        current_user.id,
        current_user.username,
        request,
    )


@router.post(
    "/ajustes/{document_id}/authorization-code", status_code=status.HTTP_201_CREATED
)
async def generate_ajuste_auth_code(
    document_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_approver_roles),
):
    svc = InventoryService(db)
    code = await svc.generate_auth_code(
        document_id, current_user.id, current_user.username, request
    )
    return {"authorization_code": code, "expires_in_minutes": 15}


@router.post("/ajustes/{document_id}/approve", response_model=DocumentResponse)
async def approve_ajuste(
    document_id: int,
    body: ApproveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_approver_roles),
):
    svc = InventoryService(db)
    return await svc.approve_document(
        document_id,
        body.authorization_code,
        current_user.id,
        current_user.username,
        request,
    )


@router.post("/ajustes/{document_id}/cancel", response_model=DocumentResponse)
async def cancel_ajuste(
    document_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_approver_roles),
):
    svc = InventoryService(db)
    return await svc.cancel_document(
        document_id, current_user.id, current_user.username, request
    )


@router.get("/ajustes", response_model=list[DocumentResponse])
async def list_ajustes(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status: DocumentStatus | None = None,
    created_by: int | None = None,
    limit: int = 50,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_approver_roles),
):
    repo = InventoryRepository(db)
    return await repo.list(
        DocumentType.AI,
        date_from,
        date_to,
        None,
        created_by,
        status=status,
        limit=limit,
        cursor=cursor,
    )


@router.get("/ajustes/page", response_model=DocumentPageResponse)
async def list_ajustes_page(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status: DocumentStatus | None = None,
    created_by: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_approver_roles),
):
    repo = InventoryRepository(db)
    items, total = await repo.list_page(
        DocumentType.AI,
        page,
        page_size,
        date_from,
        date_to,
        created_by=created_by,
        status=status,
    )
    return _page_response(items, total, page, page_size)


@router.get("/ajustes/{document_id}", response_model=DocumentResponse)
async def get_ajuste(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_approver_roles),
):
    repo = InventoryRepository(db)
    doc = await repo.get_by_id(document_id)
    if not doc or doc.doc_type != DocumentType.AI:
        raise NotFoundError("DOCUMENT_NOT_FOUND", "Ajuste not found")
    return doc


# --- Anulación (void) de documentos aprobados ---


@router.post("/documents/{document_id}/void", response_model=DocumentResponse)
async def void_document(
    document_id: int,
    body: VoidRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read_roles),
):
    """Anula un documento aprobado revirtiendo su efecto en stock y Kardex.

    Operadores deben enviar el PIN de un admin/supervisor; admin y supervisor
    anulan sin PIN.
    """
    svc = InventoryService(db)
    return await svc.void_document(
        document_id,
        current_user.id,
        current_user.username,
        body.authorizer_pin,
        request,
    )
