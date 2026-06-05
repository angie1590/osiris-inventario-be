"""Export utilities for PDF and Excel report generation."""
import io
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


class ExportService:
    @staticmethod
    def to_pdf(
        headers: list[str],
        rows: list[list[Any]],
        title: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        generated_by: str = "",
        company_header: dict[str, Any] | None = None,
    ) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        story = []

        # Corporate header
        if company_header:
            razon = company_header.get("razon_social", "")
            nombre = company_header.get("nombre_comercial")
            ruc = company_header.get("ruc", "")
            story.append(Paragraph(f"<b>{razon}</b>", styles["Heading1"]))
            if nombre:
                story.append(Paragraph(nombre, styles["Normal"]))
            story.append(Paragraph(f"RUC: {ruc}", styles["Normal"]))
            story.append(Spacer(1, 6))

        # Header section
        story.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
        if date_from and date_to:
            story.append(Paragraph(f"Período: {date_from.strftime('%Y-%m-%d')} — {date_to.strftime('%Y-%m-%d')}", styles["Normal"]))
        story.append(Paragraph(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Usuario: {generated_by}", styles["Normal"]))
        story.append(Spacer(1, 12))

        # Data table
        table_data = [headers] + [[str(cell) for cell in row] for row in rows]
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(table)
        doc.build(story)
        return buffer.getvalue()

    @staticmethod
    def to_excel(
        headers: list[str],
        rows: list[list[Any]],
        title: str,
        sheet_name: str = "Reporte",
        company_header: dict[str, Any] | None = None,
    ) -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name[:31]

        header_fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

        row_offset = 1

        # Corporate header rows
        if company_header:
            razon = company_header.get("razon_social", "")
            nombre = company_header.get("nombre_comercial")
            ruc = company_header.get("ruc", "")
            generated_at = company_header.get("generated_at", "")

            ws.merge_cells(start_row=row_offset, start_column=1, end_row=row_offset, end_column=len(headers))
            c = ws.cell(row=row_offset, column=1, value=razon)
            c.font = Font(bold=True, size=13)
            c.alignment = Alignment(horizontal="center")
            row_offset += 1

            if nombre:
                ws.merge_cells(start_row=row_offset, start_column=1, end_row=row_offset, end_column=len(headers))
                ws.cell(row=row_offset, column=1, value=nombre).alignment = Alignment(horizontal="center")
                row_offset += 1

            ws.merge_cells(start_row=row_offset, start_column=1, end_row=row_offset, end_column=len(headers))
            ws.cell(row=row_offset, column=1, value=f"RUC: {ruc}").alignment = Alignment(horizontal="center")
            row_offset += 1

            ws.merge_cells(start_row=row_offset, start_column=1, end_row=row_offset, end_column=len(headers))
            ws.cell(row=row_offset, column=1, value=f"Generado: {generated_at}").alignment = Alignment(horizontal="center")
            row_offset += 1

        # Title row
        ws.merge_cells(start_row=row_offset, start_column=1, end_row=row_offset, end_column=len(headers))
        title_cell = ws.cell(row=row_offset, column=1, value=title)
        title_cell.font = Font(bold=True, size=14)
        title_cell.alignment = Alignment(horizontal="center")
        ws.row_dimensions[row_offset].height = 25
        row_offset += 1

        # Headers
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=row_offset, column=col_idx, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_align
        ws.row_dimensions[row_offset].height = 20
        row_offset += 1

        # Data rows
        for row_idx, row in enumerate(rows, row_offset):
            for col_idx, value in enumerate(row, 1):
                ws.cell(row=row_idx, column=col_idx, value=value)

        # Auto-width columns
        for col_idx in range(1, len(headers) + 1):
            max_len = max(
                len(str(ws.cell(row=r, column=col_idx).value or ""))
                for r in range(row_offset - 1, min(len(rows) + row_offset, row_offset + 100))
            )
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 40)

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()
