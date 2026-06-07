from datetime import datetime

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_company_configured, require_role
from app.models.enums import DocumentStatus, DocumentType, UserRole
from app.models.user import User
from app.repositories.inventory_repository import InventoryRepository
from app.schemas.inventory import (
    AjusteCreate,
    ApproveRequest,
    AuthCodeRequest,
    BajaCreate,
    DocumentResponse,
    EgresoCreate,
    IngresoCreate,
)
from app.services.inventory_service import InventoryService

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
        body.reference,
        body.notes,
        body.lines,
        current_user.id,
        current_user.username,
        request,
    )


@router.get("/ingresos", response_model=list[DocumentResponse])
async def list_ingresos(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    product_id: int | None = None,
    created_by: int | None = None,
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
        limit=limit,
        cursor=cursor,
    )


@router.get("/ingresos/{document_id}", response_model=DocumentResponse)
async def get_ingreso(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    from app.core.exceptions import NotFoundError

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
        limit=limit,
        cursor=cursor,
    )


@router.get("/egresos/{document_id}", response_model=DocumentResponse)
async def get_egreso(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    from app.core.exceptions import NotFoundError

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
    from app.core.exceptions import NotFoundError

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
    from app.core.exceptions import NotFoundError

    repo = InventoryRepository(db)
    doc = await repo.get_by_id(document_id)
    if not doc or doc.doc_type != DocumentType.AI:
        raise NotFoundError("DOCUMENT_NOT_FOUND", "Ajuste not found")
    return doc
