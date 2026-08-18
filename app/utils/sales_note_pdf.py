from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.core.config import settings


def _customer_data(notes: str | None) -> dict[str, str]:
    values = {}
    for part in (notes or "").split("|"):
        label, _, value = part.partition(":")
        values[label.strip()] = value.strip()
    return {
        "name": values.get("Nombre", "CONSUMIDOR FINAL"),
        "ruc": values.get("RUC", ""),
        "phone": values.get("Teléfono", ""),
        "address": values.get("Dirección", ""),
    }


def _quantity(value: Decimal) -> str:
    return format(value.normalize(), "f")


def build_sales_note_pdf(document) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(110 * mm, 160 * mm))
    customer = _customer_data(document.notes)
    if getattr(document, "customer", None):
        customer = {
            "name": document.customer.name,
            "ruc": document.customer.identification_number,
            "phone": document.customer.phone or "",
            "address": document.customer.address or "",
        }
    document_date = document.purchase_document_date
    if document_date is None:
        raise ValueError("Sales note document date is required")
    local_date = document_date.astimezone(ZoneInfo(settings.APP_TIMEZONE))
    lines = list(document.lines)
    total = sum(
        (line.quantity * line.unit_price for line in lines),
        start=Decimal("0"),
    )

    for page_start in range(0, len(lines), 9):
        page_lines = lines[page_start : page_start + 9]
        pdf.setFont("Helvetica", 8)
        pdf.drawString(23 * mm, 110 * mm, local_date.strftime("%d/%m/%Y"))
        pdf.drawString(23 * mm, 104 * mm, customer["name"][:60])
        pdf.drawString(23 * mm, 97.5 * mm, customer["ruc"][:30])
        pdf.drawString(76 * mm, 97.5 * mm, customer["phone"][:20])
        pdf.drawString(23 * mm, 91 * mm, customer["address"][:70])

        for index, line in enumerate(page_lines):
            y = (80 - index * 5.8) * mm
            unit_price = line.unit_price or Decimal("0")
            pdf.drawCentredString(15 * mm, y, _quantity(line.quantity))
            pdf.drawString(22 * mm, y, (line.product_name or "")[:42])
            pdf.drawRightString(82 * mm, y - (0.2 * mm), f"{unit_price:.2f}")
            pdf.drawRightString(97 * mm, y - (0.2 * mm), f"{line.quantity * unit_price:.2f}")

        if page_start + 9 >= len(lines):
            seller_name = (document.seller_name or "").strip()
            if seller_name:
                pdf.setFont("Helvetica", 7)
                pdf.drawCentredString(50 * mm, 15 * mm, seller_name[:30])
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawRightString(97 * mm, 28 * mm, f"{total:.2f}")
        pdf.showPage()

    pdf.save()
    return buffer.getvalue()