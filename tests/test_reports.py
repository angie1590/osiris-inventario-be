"""Tests: reports with filters, date validation, PDF/Excel export (task 13.9)"""
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient


def _now():
    return datetime.now(timezone.utc)


def _range(days_back=1):
    to = _now()
    frm = to - timedelta(days=days_back)
    return frm.isoformat(), to.isoformat()


@pytest_asyncio.fixture(autouse=True)
async def _company(company_config):
    """All report tests require a configured company."""
    return company_config


async def _seed_ingreso(client, admin_token, operator_token):
    cat = await client.post(
        "/api/v1/categories",
        json={"name": "ReportCat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat_id = cat.json()["id"]
    prod = await client.post(
        "/api/v1/products",
        json={"name": "ReportProd", "category_id": cat_id, "pvp": "1.00"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    prod_id = prod.json()["id"]
    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5", "unit_cost": "2.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    return prod_id


@pytest.mark.asyncio
async def test_report_ingresos_json(client: AsyncClient, admin_token: str, operator_token: str):
    await _seed_ingreso(client, admin_token, operator_token)
    frm, to = _range(days_back=1)
    resp = await client.get(
        "/api/v1/reports/ingresos",
        params={"date_from": frm, "date_to": to, "format": "json"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "number" in data[0]


@pytest.mark.asyncio
async def test_report_ingresos_excel(client: AsyncClient, admin_token: str, operator_token: str):
    await _seed_ingreso(client, admin_token, operator_token)
    frm, to = _range(days_back=1)
    resp = await client.get(
        "/api/v1/reports/ingresos",
        params={"date_from": frm, "date_to": to, "format": "excel"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_report_ingresos_pdf(client: AsyncClient, admin_token: str, operator_token: str):
    await _seed_ingreso(client, admin_token, operator_token)
    frm, to = _range(days_back=1)
    resp = await client.get(
        "/api/v1/reports/ingresos",
        params={"date_from": frm, "date_to": to, "format": "pdf"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"


@pytest.mark.asyncio
async def test_report_ingresos_inverted_dates(client: AsyncClient, admin_token: str):
    to, frm = _range(days_back=1)  # intentionally swapped
    resp = await client.get(
        "/api/v1/reports/ingresos",
        params={"date_from": frm, "date_to": to},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "INVALID_DATE_RANGE"


@pytest.mark.asyncio
async def test_report_stock_json(client: AsyncClient, admin_token: str, operator_token: str):
    await _seed_ingreso(client, admin_token, operator_token)
    resp = await client.get(
        "/api/v1/reports/stock?format=json",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "stock_actual" in data[0]
    assert "bajo_stock" in data[0]


@pytest.mark.asyncio
async def test_report_stock_excel(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/api/v1/reports/stock?format=excel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_report_consolidado(client: AsyncClient, admin_token: str, operator_token: str):
    await _seed_ingreso(client, admin_token, operator_token)
    frm, to = _range(days_back=1)
    resp = await client.get(
        "/api/v1/reports/consolidado",
        params={"date_from": frm, "date_to": to},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "movements" in data
    assert "active_products" in data
    assert "products_below_minimum" in data
    assert data["movements"]["IN"] >= 1


@pytest.mark.asyncio
async def test_report_stock_valorizado(client: AsyncClient, admin_token: str, operator_token: str):
    await _seed_ingreso(client, admin_token, operator_token)
    resp = await client.get(
        "/api/v1/reports/stock-valorizado",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total_value" in data
    assert "method" in data


@pytest.mark.asyncio
async def test_report_requires_admin_or_supervisor(client: AsyncClient, operator_token: str):
    frm, to = _range(days_back=1)
    resp = await client.get(
        "/api/v1/reports/ingresos",
        params={"date_from": frm, "date_to": to},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 403
