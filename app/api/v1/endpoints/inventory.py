from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_company_configured, require_role
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.enums import DocumentStatus, DocumentType, UserRole
from app.models.inventory import (
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
    DocumentResponse,
    DocumentAttachmentResponse,
    EgresoCreate,
    IngresoCreate,
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
    VoidRequest,
)
from app.services.inventory_service import InventoryService
from app.services.audit_service import AuditService

router = APIRouter()

_operator_up = require_role(UserRole.admin, UserRole.operator)
_admin_only = require_role(UserRole.admin)
_approver_roles = require_role(UserRole.admin, UserRole.supervisor)
_read_roles = require_role(UserRole.admin, UserRole.operator, UserRole.supervisor)


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
    _: User = Depends(_operator_up),
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
    _: User = Depends(_read_roles),
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
    _: User = Depends(_read_roles),
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


@router.get("/ingresos", response_model=list[DocumentResponse])
async def list_ingresos(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    product_id: int | None = None,
    created_by: int | None = None,
    type_: str | None = Query(None, alias="type"),
    limit: int = 50,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    repo = InventoryRepository(db)
    return await repo.list(
        DocumentType.IN,
        date_from,
        date_to,
        product_id,
        created_by,
        type_,
        limit=limit,
        cursor=cursor,
    )


@router.get("/ingresos/{document_id}", response_model=DocumentResponse)
async def get_ingreso(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
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
    svc = InventoryService(db)
    return await svc.create_egreso(
        body.egreso_type,
        body.purchase_document_type,
        body.purchase_document_number,
        body.purchase_document_date,
        body.baja_reason,
        body.adjustment_reason,
        body.reference,
        body.notes,
        body.lines,
        current_user.id,
        current_user.username,
        request,
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
    _: User = Depends(_read_roles),
):
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


@router.get("/egresos/{document_id}", response_model=DocumentResponse)
async def get_egreso(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    repo = InventoryRepository(db)
    doc = await repo.get_by_id(document_id)
    if not doc or doc.doc_type != DocumentType.EG:
        raise NotFoundError("DOCUMENT_NOT_FOUND", "Egreso not found")
    return doc


# --- Bajas ---


@router.post(
    "/bajas", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED
)
async def create_baja(
    body: BajaCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_operator_up),
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
    current_user: User = Depends(_admin_only),
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
    current_user: User = Depends(_operator_up),
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
    _: User = Depends(_read_roles),
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


@router.get("/bajas/{document_id}", response_model=DocumentResponse)
async def get_baja(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    repo = InventoryRepository(db)
    doc = await repo.get_by_id(document_id)
    if not doc or doc.doc_type != DocumentType.BI:
        raise NotFoundError("DOCUMENT_NOT_FOUND", "Baja not found")
    return doc


# --- Ajustes ---


@router.post(
    "/ajustes", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED
)
async def create_ajuste(
    body: AjusteCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_operator_up),
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
    current_user: User = Depends(_admin_only),
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
    current_user: User = Depends(_operator_up),
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
    _: User = Depends(_read_roles),
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


@router.get("/ajustes/{document_id}", response_model=DocumentResponse)
async def get_ajuste(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
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
