from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_company_configured, require_role
from app.core.exceptions import ValidationAppError
from app.models.enums import DocumentType, UserRole
from app.models.inventory import InventoryDocument, InventoryDocumentLine
from app.models.kardex import KardexEntry
from app.models.product import Product
from app.models.system_param import SystemParam
from app.models.user import User
from app.repositories.category_repository import CategoryRepository
from app.repositories.company_repository import CompanyRepository
from app.utils.export_service import ExportService
from app.utils.report_header import build_header

router = APIRouter()

_read_roles = require_role(UserRole.admin, UserRole.supervisor)


def _validate_date_range(date_from: datetime, date_to: datetime) -> None:
    if date_from > date_to:
        raise ValidationAppError(
            "INVALID_DATE_RANGE", "date_from must be before date_to"
        )


def _export_response(fmt: str, data: bytes, filename: str) -> Response:
    if fmt == "pdf":
        return Response(
            content=data,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'},
        )
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
    )


async def _include_logo_in_reports(db: AsyncSession) -> bool:
    result = await db.execute(
        select(SystemParam).where(SystemParam.key == "report_include_logo")
    )
    param = result.scalar_one_or_none()
    if not param:
        return True
    return str(param.value).strip().lower() in {"true", "1", "yes", "si"}


async def _build_export_header(db: AsyncSession, title: str) -> dict | None:
    if not await _include_logo_in_reports(db):
        return None
    company = await CompanyRepository(db).get()
    return build_header(company, title) if company else None


@router.get("/ingresos")
async def report_ingresos(
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    product_id: int | None = None,
    category_id: int | None = None,
    created_by: int | None = None,
    format: Literal["json", "pdf", "excel"] = "json",
    limit: int = 100,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read_roles),
    _company: None = Depends(require_company_configured),
):
    _validate_date_range(date_from, date_to)
    q = select(InventoryDocument).where(
        InventoryDocument.doc_type == DocumentType.IN,
        InventoryDocument.created_at >= date_from,
        InventoryDocument.created_at <= date_to,
    )
    if created_by:
        q = q.where(InventoryDocument.created_by == created_by)
    if product_id:
        q = q.join(InventoryDocumentLine).where(
            InventoryDocumentLine.product_id == product_id
        )
    if cursor:
        q = q.where(InventoryDocument.id < cursor)
    q = q.order_by(InventoryDocument.created_at.desc()).limit(limit)
    result = await db.execute(q)
    docs = list(result.scalars().unique().all())

    if format == "json":
        return [
            {
                "id": d.id,
                "number": d.number,
                "status": d.status.value,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ]

    headers = ["Número", "Estado", "Referencia", "Fecha", "Creado por"]
    rows = [
        [
            d.number,
            d.status.value,
            d.reference or "",
            d.created_at.strftime("%Y-%m-%d"),
            d.created_by,
        ]
        for d in docs
    ]
    title = f"Reporte de Ingresos — {date_from.date()} a {date_to.date()}"
    ch = await _build_export_header(db, title)

    if format == "pdf":
        data = ExportService.to_pdf(
            headers,
            rows,
            title,
            date_from,
            date_to,
            current_user.username,
            company_header=ch,
        )
        return _export_response("pdf", data, "reporte_ingresos")
    data = ExportService.to_excel(headers, rows, title, company_header=ch)
    return _export_response("excel", data, "reporte_ingresos")


@router.get("/egresos")
async def report_egresos(
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    product_id: int | None = None,
    created_by: int | None = None,
    format: Literal["json", "pdf", "excel"] = "json",
    limit: int = 100,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.supervisor)),
    _company: None = Depends(require_company_configured),
):
    _validate_date_range(date_from, date_to)
    q = select(InventoryDocument).where(
        InventoryDocument.doc_type == DocumentType.EG,
        InventoryDocument.created_at >= date_from,
        InventoryDocument.created_at <= date_to,
    )
    if created_by:
        q = q.where(InventoryDocument.created_by == created_by)
    if product_id:
        q = q.join(InventoryDocumentLine).where(
            InventoryDocumentLine.product_id == product_id
        )
    if cursor:
        q = q.where(InventoryDocument.id < cursor)
    q = q.order_by(InventoryDocument.created_at.desc()).limit(limit)
    result = await db.execute(q)
    docs = list(result.scalars().unique().all())

    if format == "json":
        return [
            {
                "id": d.id,
                "number": d.number,
                "status": d.status.value,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ]

    headers = ["Número", "Estado", "Referencia", "Fecha"]
    rows = [
        [d.number, d.status.value, d.reference or "", d.created_at.strftime("%Y-%m-%d")]
        for d in docs
    ]
    title = f"Reporte de Egresos — {date_from.date()} a {date_to.date()}"
    ch = await _build_export_header(db, title)
    if format == "pdf":
        data = ExportService.to_pdf(
            headers,
            rows,
            title,
            date_from,
            date_to,
            current_user.username,
            company_header=ch,
        )
        return _export_response("pdf", data, "reporte_egresos")
    data = ExportService.to_excel(headers, rows, title, company_header=ch)
    return _export_response("excel", data, "reporte_egresos")


@router.get("/bajas")
async def report_bajas(
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    created_by: int | None = None,
    format: Literal["json", "pdf", "excel"] = "json",
    limit: int = 100,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read_roles),
    _company: None = Depends(require_company_configured),
):
    _validate_date_range(date_from, date_to)
    q = select(InventoryDocument).where(
        InventoryDocument.doc_type == DocumentType.BI,
        InventoryDocument.created_at >= date_from,
        InventoryDocument.created_at <= date_to,
    )
    if created_by:
        q = q.where(InventoryDocument.created_by == created_by)
    if cursor:
        q = q.where(InventoryDocument.id < cursor)
    q = q.order_by(InventoryDocument.created_at.desc()).limit(limit)
    result = await db.execute(q)
    docs = list(result.scalars().unique().all())
    if format == "json":
        return [
            {
                "id": d.id,
                "number": d.number,
                "status": d.status.value,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ]
    headers = ["Número", "Estado", "Notas", "Fecha"]
    rows = [
        [d.number, d.status.value, d.notes or "", d.created_at.strftime("%Y-%m-%d")]
        for d in docs
    ]
    title = f"Reporte de Bajas — {date_from.date()} a {date_to.date()}"
    ch = await _build_export_header(db, title)
    if format == "pdf":
        return _export_response(
            "pdf",
            ExportService.to_pdf(
                headers,
                rows,
                title,
                date_from,
                date_to,
                current_user.username,
                company_header=ch,
            ),
            "reporte_bajas",
        )
    return _export_response(
        "excel",
        ExportService.to_excel(headers, rows, title, company_header=ch),
        "reporte_bajas",
    )


@router.get("/ajustes")
async def report_ajustes(
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    created_by: int | None = None,
    format: Literal["json", "pdf", "excel"] = "json",
    limit: int = 100,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read_roles),
    _company: None = Depends(require_company_configured),
):
    _validate_date_range(date_from, date_to)
    q = select(InventoryDocument).where(
        InventoryDocument.doc_type == DocumentType.AI,
        InventoryDocument.created_at >= date_from,
        InventoryDocument.created_at <= date_to,
    )
    if created_by:
        q = q.where(InventoryDocument.created_by == created_by)
    if cursor:
        q = q.where(InventoryDocument.id < cursor)
    q = q.order_by(InventoryDocument.created_at.desc()).limit(limit)
    result = await db.execute(q)
    docs = list(result.scalars().unique().all())
    if format == "json":
        return [
            {
                "id": d.id,
                "number": d.number,
                "status": d.status.value,
                "adjust_type": d.adjust_type.value if d.adjust_type else None,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ]
    headers = ["Número", "Estado", "Tipo", "Fecha"]
    rows = [
        [
            d.number,
            d.status.value,
            d.adjust_type.value if d.adjust_type else "",
            d.created_at.strftime("%Y-%m-%d"),
        ]
        for d in docs
    ]
    title = f"Reporte de Ajustes — {date_from.date()} a {date_to.date()}"
    ch = await _build_export_header(db, title)
    if format == "pdf":
        return _export_response(
            "pdf",
            ExportService.to_pdf(
                headers,
                rows,
                title,
                date_from,
                date_to,
                current_user.username,
                company_header=ch,
            ),
            "reporte_ajustes",
        )
    return _export_response(
        "excel",
        ExportService.to_excel(headers, rows, title, company_header=ch),
        "reporte_ajustes",
    )


@router.get("/stock")
async def report_stock(
    category_id: int | None = None,
    bajo_stock: bool | None = None,
    format: Literal["json", "pdf", "excel"] = "json",
    limit: int = 100,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read_roles),
    _company: None = Depends(require_company_configured),
):
    q = select(Product).where(Product.status == "active")
    if category_id:
        cat_repo = CategoryRepository(db)
        ids = await cat_repo.get_descendant_category_ids(category_id)
        q = q.where(Product.category_id.in_(ids))
    if bajo_stock is True:
        q = q.where(Product.stock_actual <= Product.stock_minimo)
    if cursor:
        q = q.where(Product.id > cursor)
    q = q.order_by(Product.id).limit(limit)
    result = await db.execute(q)
    products = list(result.scalars().all())

    if format == "json":
        return [
            {
                "id": p.id,
                "name": p.name,
                "stock_actual": float(p.stock_actual),
                "stock_minimo": float(p.stock_minimo),
                "bajo_stock": p.stock_actual <= p.stock_minimo,
                "pvp": float(p.pvp),
            }
            for p in products
        ]
    headers = ["ID", "Nombre", "Stock Actual", "Stock Mínimo", "Bajo Stock", "PVP"]
    rows = [
        [
            p.id,
            p.name,
            float(p.stock_actual),
            float(p.stock_minimo),
            "Sí" if p.stock_actual <= p.stock_minimo else "No",
            float(p.pvp),
        ]
        for p in products
    ]
    title = "Reporte de Stock Actual"
    ch = await _build_export_header(db, title)
    if format == "pdf":
        return _export_response(
            "pdf",
            ExportService.to_pdf(
                headers,
                rows,
                title,
                None,
                None,
                current_user.username,
                company_header=ch,
            ),
            "reporte_stock",
        )
    return _export_response(
        "excel",
        ExportService.to_excel(headers, rows, title, company_header=ch),
        "reporte_stock",
    )


@router.get("/stock-valorizado")
async def report_stock_valorizado(
    category_id: int | None = None,
    as_of_date: datetime | None = None,
    format: Literal["json", "pdf", "excel"] = "json",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read_roles),
    _company: None = Depends(require_company_configured),
):
    result = await db.execute(
        select(SystemParam).where(SystemParam.key == "kardex_method")
    )
    param = result.scalar_one_or_none()
    method = param.value if param else "PEPS"

    q = select(Product).where(Product.status == "active")
    if category_id:
        cat_repo = CategoryRepository(db)
        ids = await cat_repo.get_descendant_category_ids(category_id)
        q = q.where(Product.category_id.in_(ids))

    result = await db.execute(q)
    products = list(result.scalars().all())

    items = []
    total = Decimal("0")
    for p in products:
        last_kardex_q = select(KardexEntry).where(KardexEntry.product_id == p.id)
        if as_of_date:
            last_kardex_q = last_kardex_q.where(KardexEntry.created_at <= as_of_date)
        last_kardex_q = last_kardex_q.order_by(
            KardexEntry.created_at.desc(), KardexEntry.id.desc()
        ).limit(1)
        kres = await db.execute(last_kardex_q)
        last_entry = kres.scalar_one_or_none()
        cost = last_entry.weighted_avg_cost if last_entry else Decimal("0")
        stock = last_entry.balance_quantity if last_entry else p.stock_actual
        value = stock * cost
        total += value
        items.append(
            {
                "id": p.id,
                "name": p.name,
                "stock": float(stock),
                "cost": float(cost),
                "value": float(value),
                "category_id": p.category_id,
            }
        )

    if format == "json":
        return {"method": method, "items": items, "total_value": float(total)}
    headers = ["ID", "Nombre", "Stock", "Costo Unit.", "Valor Total"]
    rows = [[i["id"], i["name"], i["stock"], i["cost"], i["value"]] for i in items]
    rows.append(["", "TOTAL", "", "", float(total)])
    title = "Inventario Valorizado"
    ch = await _build_export_header(db, title)
    if format == "pdf":
        return _export_response(
            "pdf",
            ExportService.to_pdf(
                headers,
                rows,
                title,
                None,
                None,
                current_user.username,
                company_header=ch,
            ),
            "inventario_valorizado",
        )
    return _export_response(
        "excel",
        ExportService.to_excel(headers, rows, title, company_header=ch),
        "inventario_valorizado",
    )


@router.get("/movimientos-por-usuario")
async def report_movimientos_por_usuario(
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    user_id: int = Query(...),
    format: Literal["json", "pdf", "excel"] = "json",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read_roles),
    _company: None = Depends(require_company_configured),
):
    _validate_date_range(date_from, date_to)
    q = (
        select(InventoryDocument)
        .where(
            InventoryDocument.created_by == user_id,
            InventoryDocument.created_at >= date_from,
            InventoryDocument.created_at <= date_to,
        )
        .order_by(InventoryDocument.created_at.desc())
    )
    result = await db.execute(q)
    docs = list(result.scalars().all())

    if format == "json":
        return [
            {
                "id": d.id,
                "number": d.number,
                "doc_type": d.doc_type.value,
                "status": d.status.value,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ]
    headers = ["Número", "Tipo", "Estado", "Fecha"]
    rows = [
        [d.number, d.doc_type.value, d.status.value, d.created_at.strftime("%Y-%m-%d")]
        for d in docs
    ]
    title = f"Movimientos del Usuario {user_id}"
    ch = await _build_export_header(db, title)
    if format == "pdf":
        return _export_response(
            "pdf",
            ExportService.to_pdf(
                headers,
                rows,
                title,
                date_from,
                date_to,
                current_user.username,
                company_header=ch,
            ),
            "movimientos_usuario",
        )
    return _export_response(
        "excel",
        ExportService.to_excel(headers, rows, title, company_header=ch),
        "movimientos_usuario",
    )


@router.get("/consolidado")
async def report_consolidado(
    date_from: datetime = Query(...),
    date_to: datetime = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    _validate_date_range(date_from, date_to)

    # Totals per doc type
    counts = {}
    for doc_type in DocumentType:
        result = await db.execute(
            select(func.count(InventoryDocument.id)).where(
                InventoryDocument.doc_type == doc_type,
                InventoryDocument.created_at >= date_from,
                InventoryDocument.created_at <= date_to,
            )
        )
        counts[doc_type.value] = result.scalar() or 0

    total_products = await db.execute(
        select(func.count(Product.id)).where(Product.status == "active")
    )
    bajo_stock_count = await db.execute(
        select(func.count(Product.id)).where(
            Product.status == "active", Product.stock_actual <= Product.stock_minimo
        )
    )

    return {
        "period": {"from": date_from.isoformat(), "to": date_to.isoformat()},
        "movements": counts,
        "active_products": total_products.scalar(),
        "products_below_minimum": bajo_stock_count.scalar(),
    }
