from datetime import datetime, timezone
from typing import Any

from app.models.company_config import CompanyConfig


def build_header(company: CompanyConfig, report_name: str) -> dict[str, Any]:
    return {
        "razon_social": company.razon_social,
        "nombre_comercial": company.nombre_comercial,
        "ruc": company.ruc,
        "logo": company.logo,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "report_name": report_name,
    }
