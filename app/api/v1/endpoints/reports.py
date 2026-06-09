from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any, Callable, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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

_STATUS_LABELS = {
    "draft": "Borrador",
    "pending": "Pendiente",
    "approved": "Aprobado",
    "rejected": "Rechazado",
    "cancelled": "Cancelado",
    "voided": "Anulado",
}

_DOC_TYPE_LABELS = {
    DocumentType.IN.value: "Ingreso",
    DocumentType.EG.value: "Egreso",
    DocumentType.BI.value: "Baja",
    DocumentType.AI.value: "Ajuste",
}

_ADJUST_TYPE_LABELS = {
    "increment": "Incremento",
    "decrement": "Decremento",
}


def _status_label(value: str | None) -> str:
    if not value:
        return ""
    return _STATUS_LABELS.get(value.lower(), value)


def _doc_type_label(value: str | None) -> str:
    if not value:
        return ""
    return _DOC_TYPE_LABELS.get(value.upper(), value)


def _adjust_type_label(value: str | None) -> str:
    if not value:
        return ""
    return _ADJUST_TYPE_LABELS.get(value.lower(), value)


async def _username_map(db: AsyncSession, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    result = await db.execute(
        select(User.id, User.username).where(User.id.in_(user_ids))
    )
    return {uid: username for uid, username in result.all()}


def _validate_date_range(date_from: datetime, date_to: datetime) -> None:
    if date_from > date_to:
        raise ValidationAppError(
            "INVALID_DATE_RANGE", "date_from must be before date_to"
        )


def _parse_iso_datetime(
    value: str, *, end_of_day_for_date_only: bool
) -> tuple[datetime, bool, date | None]:
    raw = value.strip()

    # Date-only values are interpreted as full day bounds in business timezone.
    if "T" not in raw and " " not in raw:
        d = date.fromisoformat(raw)
        local_tz = ZoneInfo(settings.APP_TIMEZONE)
        local_dt = datetime.combine(
            d, time.max if end_of_day_for_date_only else time.min, tzinfo=local_tz
        )
        return local_dt.astimezone(timezone.utc), True, d

    # Datetime values keep their explicit precision.
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt, False, None


def _resolve_report_range(date_from: str, date_to: str) -> tuple[datetime, datetime]:
    try:
        date_from_dt, _, _ = _parse_iso_datetime(
            date_from, end_of_day_for_date_only=False
        )
        date_to_dt, _, _ = _parse_iso_datetime(date_to, end_of_day_for_date_only=True)
    except ValueError:
        raise ValidationAppError(
            "INVALID_DATE_RANGE", "date_from/date_to must be valid ISO date or datetime"
        )

    _validate_date_range(date_from_dt, date_to_dt)
    return date_from_dt, date_to_dt


def _local_date_for_title(dt: datetime) -> str:
    return dt.astimezone(ZoneInfo(settings.APP_TIMEZONE)).date().isoformat()


def _local_date_label(dt: datetime) -> str:
    return dt.astimezone(ZoneInfo(settings.APP_TIMEZONE)).strftime("%d/%m/%Y")


def _group_rows_by_date(
    items: list[Any],
    *,
    get_dt: Callable[[Any], datetime],
    build_row: Callable[[Any], list[object]],
    columns: int,
) -> list[list[object]]:
    rows: list[list[object]] = []
    current_date: str | None = None
    count_in_group = 0

    for item in items:
        label = _local_date_label(get_dt(item))
        if current_date != label:
            if current_date is not None:
                rows.append(
                    [f"__SUBTOTAL__:Total registros en la fecha: {count_in_group}"]
                )
            current_date = label
            count_in_group = 0
            rows.append([f"__SECTION__:Fecha: {label}"])

        row = list(build_row(item))
        if len(row) < columns:
            row.extend([""] * (columns - len(row)))
        rows.append(row)
        count_in_group += 1

    if current_date is not None:
        rows.append([f"__SUBTOTAL__:Total registros en la fecha: {count_in_group}"])

    return rows


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


async def _get_stock_quantity_mode(db: AsyncSession) -> str:
    result = await db.execute(
        select(SystemParam).where(SystemParam.key == "stock_quantity_mode")
    )
    param = result.scalar_one_or_none()
    if not param:
        return "integer"
    value = str(param.value).strip().lower()
    return "decimal" if value == "decimal" else "integer"


async def _get_bool_param(db: AsyncSession, key: str, default: bool = False) -> bool:
    result = await db.execute(select(SystemParam).where(SystemParam.key == key))
    param = result.scalar_one_or_none()
    if not param:
        return default
    return str(param.value).strip().lower() in ("true", "1", "yes")


@router.get("/settings")
async def report_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_read_roles),
):
    return {
        "stock_quantity_mode": await _get_stock_quantity_mode(db),
        "internal_code_enabled": await _get_bool_param(db, "internal_code_enabled", default=True),
        "isbn_required": await _get_bool_param(db, "isbn_required"),
    }


@router.get("/ingresos")
async def report_ingresos(
    date_from: str = Query(...),
    date_to: str = Query(...),
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
    date_from_dt, date_to_dt = _resolve_report_range(date_from, date_to)
    q = select(InventoryDocument).where(
        InventoryDocument.doc_type == DocumentType.IN,
        InventoryDocument.created_at >= date_from_dt,
        InventoryDocument.created_at <= date_to_dt,
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
                "reference": d.reference,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ]

    headers = ["Número", "Fecha", "Referencia", "Estado", "Creado por"]
    usernames = await _username_map(
        db,
        {d.created_by for d in docs if d.created_by is not None},
    )
    rows = _group_rows_by_date(
        docs,
        get_dt=lambda d: d.created_at,
        build_row=lambda d: [
            d.number,
            d.created_at.strftime("%Y-%m-%d"),
            d.reference or "",
            _status_label(d.status.value),
            usernames.get(d.created_by, ""),
        ],
        columns=len(headers),
    )
    title = (
        f"Reporte de Ingresos — {_local_date_for_title(date_from_dt)} "
        f"a {_local_date_for_title(date_to_dt)}"
    )
    ch = await _build_export_header(db, title)

    if format == "pdf":
        data = ExportService.to_pdf(
            headers,
            rows,
            title,
            date_from_dt,
            date_to_dt,
            current_user.username,
            company_header=ch,
        )
        return _export_response("pdf", data, "reporte_ingresos")
    data = ExportService.to_excel(headers, rows, title, company_header=ch)
    return _export_response("excel", data, "reporte_ingresos")


@router.get("/egresos")
async def report_egresos(
    date_from: str = Query(...),
    date_to: str = Query(...),
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
    date_from_dt, date_to_dt = _resolve_report_range(date_from, date_to)
    q = select(InventoryDocument).where(
        InventoryDocument.doc_type == DocumentType.EG,
        InventoryDocument.created_at >= date_from_dt,
        InventoryDocument.created_at <= date_to_dt,
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
                "reference": d.reference,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ]

    headers = ["Número", "Fecha", "Referencia", "Estado"]
    rows = _group_rows_by_date(
        docs,
        get_dt=lambda d: d.created_at,
        build_row=lambda d: [
            d.number,
            d.created_at.strftime("%Y-%m-%d"),
            d.reference or "",
            _status_label(d.status.value),
        ],
        columns=len(headers),
    )
    title = (
        f"Reporte de Egresos — {_local_date_for_title(date_from_dt)} "
        f"a {_local_date_for_title(date_to_dt)}"
    )
    ch = await _build_export_header(db, title)
    if format == "pdf":
        data = ExportService.to_pdf(
            headers,
            rows,
            title,
            date_from_dt,
            date_to_dt,
            current_user.username,
            company_header=ch,
        )
        return _export_response("pdf", data, "reporte_egresos")
    data = ExportService.to_excel(headers, rows, title, company_header=ch)
    return _export_response("excel", data, "reporte_egresos")


@router.get("/bajas")
async def report_bajas(
    date_from: str = Query(...),
    date_to: str = Query(...),
    created_by: int | None = None,
    format: Literal["json", "pdf", "excel"] = "json",
    limit: int = 100,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read_roles),
    _company: None = Depends(require_company_configured),
):
    date_from_dt, date_to_dt = _resolve_report_range(date_from, date_to)
    q = select(InventoryDocument).where(
        InventoryDocument.doc_type == DocumentType.BI,
        InventoryDocument.created_at >= date_from_dt,
        InventoryDocument.created_at <= date_to_dt,
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
                "reference": d.reference,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ]
    headers = ["Número", "Fecha", "Notas", "Estado"]
    rows = _group_rows_by_date(
        docs,
        get_dt=lambda d: d.created_at,
        build_row=lambda d: [
            d.number,
            d.created_at.strftime("%Y-%m-%d"),
            d.notes or "",
            _status_label(d.status.value),
        ],
        columns=len(headers),
    )
    title = (
        f"Reporte de Bajas — {_local_date_for_title(date_from_dt)} "
        f"a {_local_date_for_title(date_to_dt)}"
    )
    ch = await _build_export_header(db, title)
    if format == "pdf":
        return _export_response(
            "pdf",
            ExportService.to_pdf(
                headers,
                rows,
                title,
                date_from_dt,
                date_to_dt,
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
    date_from: str = Query(...),
    date_to: str = Query(...),
    created_by: int | None = None,
    format: Literal["json", "pdf", "excel"] = "json",
    limit: int = 100,
    cursor: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read_roles),
    _company: None = Depends(require_company_configured),
):
    date_from_dt, date_to_dt = _resolve_report_range(date_from, date_to)
    q = select(InventoryDocument).where(
        InventoryDocument.doc_type == DocumentType.AI,
        InventoryDocument.created_at >= date_from_dt,
        InventoryDocument.created_at <= date_to_dt,
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
                "reference": d.reference,
                "adjust_type": d.adjust_type.value if d.adjust_type else None,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ]
    headers = ["Número", "Fecha", "Tipo", "Estado"]
    rows = _group_rows_by_date(
        docs,
        get_dt=lambda d: d.created_at,
        build_row=lambda d: [
            d.number,
            d.created_at.strftime("%Y-%m-%d"),
            _adjust_type_label(d.adjust_type.value if d.adjust_type else ""),
            _status_label(d.status.value),
        ],
        columns=len(headers),
    )
    title = (
        f"Reporte de Ajustes — {_local_date_for_title(date_from_dt)} "
        f"a {_local_date_for_title(date_to_dt)}"
    )
    ch = await _build_export_header(db, title)
    if format == "pdf":
        return _export_response(
            "pdf",
            ExportService.to_pdf(
                headers,
                rows,
                title,
                date_from_dt,
                date_to_dt,
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
        q = q.where((Product.stock_minimo > 0) & (Product.stock_actual <= Product.stock_minimo))
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
                "bajo_stock": p.stock_minimo > 0 and p.stock_actual <= p.stock_minimo,
                "pvp": float(p.pvp),
            }
            for p in products
        ]
    headers = ["Nombre", "Bajo Stock", "Stock Mínimo", "Stock Actual", "PVP"]
    rows = [
        [
            p.name,
            "Sí" if (p.stock_minimo > 0 and p.stock_actual <= p.stock_minimo) else "No",
            float(p.stock_minimo),
            float(p.stock_actual),
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
        value = last_entry.balance_value if last_entry else (stock * cost)
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
    headers = ["Nombre", "Stock", "Costo Unit.", "Valor Total"]
    rows = [[i["name"], i["stock"], i["cost"], i["value"]] for i in items]
    rows.append(["TOTAL", "", "", float(total)])
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
    date_from: str = Query(...),
    date_to: str = Query(...),
    user_id: int = Query(...),
    format: Literal["json", "pdf", "excel"] = "json",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read_roles),
    _company: None = Depends(require_company_configured),
):
    date_from_dt, date_to_dt = _resolve_report_range(date_from, date_to)
    q = (
        select(InventoryDocument)
        .where(
            InventoryDocument.created_by == user_id,
            InventoryDocument.created_at >= date_from_dt,
            InventoryDocument.created_at <= date_to_dt,
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
                "reference": d.reference,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ]
    headers = ["Número", "Fecha", "Tipo", "Estado", "Referencia"]
    rows = _group_rows_by_date(
        docs,
        get_dt=lambda d: d.created_at,
        build_row=lambda d: [
            d.number,
            d.created_at.strftime("%Y-%m-%d"),
            _doc_type_label(d.doc_type.value),
            _status_label(d.status.value),
            d.reference or "",
        ],
        columns=len(headers),
    )
    user_result = await db.execute(
        select(User.full_name, User.username).where(User.id == user_id)
    )
    user_ref = user_result.first()
    user_label = user_ref[0] or user_ref[1] if user_ref else str(user_id)
    title = f"Movimientos de {user_label}"
    ch = await _build_export_header(db, title)
    if format == "pdf":
        return _export_response(
            "pdf",
            ExportService.to_pdf(
                headers,
                rows,
                title,
                date_from_dt,
                date_to_dt,
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


@router.get("/kardex")
async def report_kardex(
    product_id: int = Query(...),
    date_from: str = Query(...),
    date_to: str = Query(...),
    format: Literal["json", "pdf", "excel"] = "json",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read_roles),
    _company: None = Depends(require_company_configured),
):
    date_from_dt, date_to_dt = _resolve_report_range(date_from, date_to)

    result = await db.execute(
        select(SystemParam).where(SystemParam.key == "kardex_method")
    )
    param = result.scalar_one_or_none()
    method = param.value if param else "PEPS"

    q = (
        select(KardexEntry)
        .where(
            KardexEntry.product_id == product_id,
            KardexEntry.created_at >= date_from_dt,
            KardexEntry.created_at <= date_to_dt,
        )
        .order_by(KardexEntry.created_at.asc(), KardexEntry.id.asc())
    )
    result = await db.execute(q)
    entries = list(result.scalars().all())

    product_result = await db.execute(
        select(Product.name).where(Product.id == product_id)
    )
    product_name = product_result.scalar_one_or_none()
    product_label = product_name or f"ID {product_id}"

    if format == "json":
        return {
            "product_id": product_id,
            "method": method,
            "entries": [
                {
                    "id": e.id,
                    "created_at": e.created_at.isoformat(),
                    "quantity_in": float(e.quantity_in),
                    "quantity_out": float(e.quantity_out),
                    "balance_quantity": float(e.balance_quantity),
                    "weighted_avg_cost": float(e.weighted_avg_cost),
                }
                for e in entries
            ],
        }

    headers = ["Fecha", "Entrada", "Salida", "Saldo", "Costo Promedio"]
    rows = _group_rows_by_date(
        entries,
        get_dt=lambda e: e.created_at,
        build_row=lambda e: [
            e.created_at.strftime("%Y-%m-%d %H:%M"),
            float(e.quantity_in),
            float(e.quantity_out),
            float(e.balance_quantity),
            float(e.weighted_avg_cost),
        ],
        columns=len(headers),
    )
    title = (
        f"Kardex de {product_label} — "
        f"{_local_date_for_title(date_from_dt)} a {_local_date_for_title(date_to_dt)}"
    )
    ch = await _build_export_header(db, title)
    if format == "pdf":
        return _export_response(
            "pdf",
            ExportService.to_pdf(
                headers,
                rows,
                title,
                date_from_dt,
                date_to_dt,
                current_user.username,
                company_header=ch,
            ),
            "reporte_kardex",
        )
    return _export_response(
        "excel",
        ExportService.to_excel(headers, rows, title, company_header=ch),
        "reporte_kardex",
    )


@router.get("/consolidado")
async def report_consolidado(
    date_from: str = Query(...),
    date_to: str = Query(...),
    format: Literal["json", "pdf", "excel"] = "json",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_read_roles),
    _company: None = Depends(require_company_configured),
):
    date_from_dt, date_to_dt = _resolve_report_range(date_from, date_to)

    # Totals per doc type
    counts = {}
    for doc_type in DocumentType:
        result = await db.execute(
            select(func.count(InventoryDocument.id)).where(
                InventoryDocument.doc_type == doc_type,
                InventoryDocument.created_at >= date_from_dt,
                InventoryDocument.created_at <= date_to_dt,
            )
        )
        counts[doc_type.value] = result.scalar() or 0

    total_products = await db.execute(
        select(func.count(Product.id)).where(Product.status == "active")
    )
    bajo_stock_count = await db.execute(
        select(func.count(Product.id)).where(
            Product.status == "active", Product.stock_minimo > 0, Product.stock_actual <= Product.stock_minimo
        )
    )

    payload = {
        "period": {"from": date_from_dt.isoformat(), "to": date_to_dt.isoformat()},
        "movements": counts,
        "active_products": total_products.scalar(),
        "products_below_minimum": bajo_stock_count.scalar(),
    }
    if format == "json":
        return payload

    headers = ["Métrica", "Valor"]
    rows = [[f"Movimientos {_doc_type_label(k)}", v] for k, v in counts.items()]
    rows.extend(
        [
            ["Productos activos", payload["active_products"]],
            ["Productos bajo mínimo", payload["products_below_minimum"]],
        ]
    )
    title = (
        f"Reporte Consolidado — {_local_date_for_title(date_from_dt)} "
        f"a {_local_date_for_title(date_to_dt)}"
    )
    ch = await _build_export_header(db, title)
    if format == "pdf":
        return _export_response(
            "pdf",
            ExportService.to_pdf(
                headers,
                rows,
                title,
                date_from_dt,
                date_to_dt,
                current_user.username,
                company_header=ch,
            ),
            "reporte_consolidado",
        )
    return _export_response(
        "excel",
        ExportService.to_excel(headers, rows, title, company_header=ch),
        "reporte_consolidado",
    )
