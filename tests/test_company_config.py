"""Tests: company config CRUD, guards, and audit (company-config change)"""
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Bracket the current moment by ±1 day so the audit-range filter is robust to
# the UTC/local-day boundary (the API filters by APP_TIMEZONE local day).
_TODAY = (date.today() - timedelta(days=1)).isoformat()
_TOMORROW = (date.today() + timedelta(days=1)).isoformat()

VALID_PAYLOAD = {
    "razon_social": "Acme S.A.",
    "ruc": "1234567890001",
    "email": "acme@example.com",
    "nombre_comercial": "Acme",
    "direccion": "Av. Test 123",
    "telefono": "0991234567",
}


# --- CRUD ---

@pytest.mark.asyncio
async def test_get_company_not_configured(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/company", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 404
    assert resp.json()["code"] == "COMPANY_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_company(client: AsyncClient, admin_token: str):
    resp = await client.post("/api/v1/company", json=VALID_PAYLOAD, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["razon_social"] == "Acme S.A."
    assert data["ruc"] == "1234567890001"
    assert data["is_complete"] is True


@pytest.mark.asyncio
async def test_get_company_after_create(client: AsyncClient, admin_token: str, operator_token: str):
    await client.post("/api/v1/company", json=VALID_PAYLOAD, headers={"Authorization": f"Bearer {admin_token}"})
    resp = await client.get("/api/v1/company", headers={"Authorization": f"Bearer {operator_token}"})
    assert resp.status_code == 200
    assert resp.json()["razon_social"] == "Acme S.A."


@pytest.mark.asyncio
async def test_update_company(client: AsyncClient, admin_token: str):
    await client.post("/api/v1/company", json=VALID_PAYLOAD, headers={"Authorization": f"Bearer {admin_token}"})
    resp = await client.patch(
        "/api/v1/company",
        json={"nombre_comercial": "Acme Corp"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["nombre_comercial"] == "Acme Corp"
    assert resp.json()["razon_social"] == "Acme S.A."


@pytest.mark.asyncio
async def test_create_company_duplicate_returns_409(client: AsyncClient, admin_token: str):
    await client.post("/api/v1/company", json=VALID_PAYLOAD, headers={"Authorization": f"Bearer {admin_token}"})
    resp = await client.post("/api/v1/company", json=VALID_PAYLOAD, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "COMPANY_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_create_company_forbidden_for_non_admin(client: AsyncClient, operator_token: str):
    resp = await client.post("/api/v1/company", json=VALID_PAYLOAD, headers={"Authorization": f"Bearer {operator_token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_patch_company_forbidden_for_non_admin(client: AsyncClient, admin_token: str, operator_token: str):
    await client.post("/api/v1/company", json=VALID_PAYLOAD, headers={"Authorization": f"Bearer {admin_token}"})
    resp = await client.patch("/api/v1/company", json={"nombre_comercial": "X"}, headers={"Authorization": f"Bearer {operator_token}"})
    assert resp.status_code == 403


# --- Guard: COMPANY_NOT_CONFIGURED ---

@pytest.mark.asyncio
async def test_ingreso_blocked_without_company(client: AsyncClient, admin_token: str, operator_token: str, db_session: AsyncSession):
    cat = await client.post("/api/v1/categories", json={"name": "Cat Guard"}, headers={"Authorization": f"Bearer {admin_token}"})
    cat_id = cat.json()["id"]
    prod = await client.post(
        "/api/v1/products",
        json={"name": "Prod Guard", "category_id": cat_id, "pvp": "5.00"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    prod_id = prod.json()["id"]

    resp = await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5", "unit_cost": "2.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "COMPANY_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_report_blocked_without_company(client: AsyncClient, admin_token: str):
    from datetime import datetime, timezone, timedelta
    to = datetime.now(timezone.utc)
    frm = to - timedelta(days=1)
    resp = await client.get(
        "/api/v1/reports/ingresos",
        params={"date_from": frm.isoformat(), "date_to": to.isoformat(), "format": "json"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "COMPANY_NOT_CONFIGURED"


# --- Audit ---

@pytest.mark.asyncio
async def test_create_company_missing_required_fields_returns_errors(client: AsyncClient, admin_token: str):
    resp = await client.post("/api/v1/company", json={}, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "errors" in body
    assert "razon_social" in body["errors"] or "ruc" in body["errors"] or "email" in body["errors"]


@pytest.mark.asyncio
async def test_create_company_missing_ruc_returns_field_error(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/company",
        json={"razon_social": "Test", "email": "t@t.com"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "ruc" in body["errors"]


@pytest.mark.asyncio
async def test_audit_on_create(client: AsyncClient, admin_token: str):
    await client.post("/api/v1/company", json=VALID_PAYLOAD, headers={"Authorization": f"Bearer {admin_token}"})
    resp = await client.get(
        "/api/v1/audit",
        params={"entity_type": "company_config", "action": "CREATE", "limit": 5, "date_from": _TODAY, "date_to": _TOMORROW},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    entries = resp.json()
    assert any(e["entity_type"] == "company_config" and e["action"] == "CREATE" for e in entries)


@pytest.mark.asyncio
async def test_audit_on_update(client: AsyncClient, admin_token: str):
    await client.post("/api/v1/company", json=VALID_PAYLOAD, headers={"Authorization": f"Bearer {admin_token}"})
    await client.patch("/api/v1/company", json={"telefono": "0999999999"}, headers={"Authorization": f"Bearer {admin_token}"})
    resp = await client.get(
        "/api/v1/audit",
        params={"entity_type": "company_config", "action": "UPDATE", "limit": 5, "date_from": _TODAY, "date_to": _TOMORROW},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    entries = resp.json()
    assert any(e["entity_type"] == "company_config" and e["action"] == "UPDATE" for e in entries)
