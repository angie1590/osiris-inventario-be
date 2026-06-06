"""Tests: inventory movements IN/EG/BI/AI (tasks 13.5, 13.6)"""
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture(autouse=True)
async def _company(company_config):
    """All inventory tests require a configured company."""
    return company_config


async def _create_product(client, admin_token, operator_token, name="Test Product", pvp="10.00"):
    cat = await client.post("/api/v1/categories", json={"name": f"Cat {name}"}, headers={"Authorization": f"Bearer {admin_token}"})
    cat_id = cat.json()["id"]
    prod = await client.post(
        "/api/v1/products",
        json={"name": name, "category_id": cat_id, "pvp": pvp},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    return prod.json()["id"]


@pytest.mark.asyncio
async def test_ingreso_increases_stock(client: AsyncClient, admin_token: str, operator_token: str):
    prod_id = await _create_product(client, admin_token, operator_token, "Ingreso Test")
    resp = await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "10.00", "unit_cost": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 201
    doc = resp.json()
    assert doc["doc_type"] == "IN"
    assert doc["status"] == "approved"

    # Verify stock updated
    prod_resp = await client.get(f"/api/v1/products/{prod_id}", headers={"Authorization": f"Bearer {operator_token}"})
    assert float(prod_resp.json()["stock_actual"]) == 10.0


@pytest.mark.asyncio
async def test_egreso_decreases_stock(client: AsyncClient, admin_token: str, operator_token: str):
    prod_id = await _create_product(client, admin_token, operator_token, "Egreso Test")

    # First add stock
    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "20.00", "unit_cost": "3.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    resp = await client.post(
        "/api/v1/inventory/egresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5.00", "unit_price": "10.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "approved"

    prod_resp = await client.get(f"/api/v1/products/{prod_id}", headers={"Authorization": f"Bearer {operator_token}"})
    assert float(prod_resp.json()["stock_actual"]) == 15.0


@pytest.mark.asyncio
async def test_egreso_insufficient_stock(client: AsyncClient, admin_token: str, operator_token: str):
    prod_id = await _create_product(client, admin_token, operator_token, "Low Stock Product")

    resp = await client.post(
        "/api/v1/inventory/egresos",
        json={"lines": [{"product_id": prod_id, "quantity": "100.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INSUFFICIENT_STOCK"


@pytest.mark.asyncio
async def test_ingreso_nonexistent_product(client: AsyncClient, operator_token: str):
    resp = await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": 999999, "quantity": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "PRODUCT_NOT_FOUND"


@pytest.mark.asyncio
async def test_document_numbering_consecutive(client: AsyncClient, admin_token: str, operator_token: str):
    prod_id = await _create_product(client, admin_token, operator_token, "Numbering Test")
    await client.post("/api/v1/inventory/ingresos", json={"lines": [{"product_id": prod_id, "quantity": "5.00"}]}, headers={"Authorization": f"Bearer {operator_token}"})
    r2 = await client.post("/api/v1/inventory/ingresos", json={"lines": [{"product_id": prod_id, "quantity": "3.00"}]}, headers={"Authorization": f"Bearer {operator_token}"})

    from datetime import datetime
    year = datetime.now().year
    assert r2.json()["number"].startswith(f"IN-{year}-")


@pytest.mark.asyncio
async def test_document_numbering_uses_configured_padding(
    client: AsyncClient,
    admin_token: str,
    operator_token: str,
    db_session: AsyncSession,
):
    from app.models.system_param import SystemParam

    db_session.add(SystemParam(key="doc_number_padding", value="4", description="test"))
    await db_session.commit()

    prod_id = await _create_product(client, admin_token, operator_token, "Padding Test")
    resp = await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert resp.status_code == 201
    number = resp.json()["number"]
    sequence = number.rsplit("-", 1)[1]
    assert sequence == "0001"


@pytest.mark.asyncio
async def test_baja_flow(client: AsyncClient, admin_token: str, operator_token: str):
    prod_id = await _create_product(client, admin_token, operator_token, "Baja Flow Test")

    # Add stock first
    await client.post("/api/v1/inventory/ingresos", json={"lines": [{"product_id": prod_id, "quantity": "10.00"}]}, headers={"Authorization": f"Bearer {operator_token}"})

    # Create BI request — should be pending, no stock change
    bi_resp = await client.post(
        "/api/v1/inventory/bajas",
        json={"notes": "Damaged", "lines": [{"product_id": prod_id, "quantity": "2.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert bi_resp.status_code == 201
    assert bi_resp.json()["status"] == "pending"
    bi_id = bi_resp.json()["id"]

    # Stock should not have changed
    prod_resp = await client.get(f"/api/v1/products/{prod_id}", headers={"Authorization": f"Bearer {operator_token}"})
    assert float(prod_resp.json()["stock_actual"]) == 10.0

    # Generate auth code
    code_resp = await client.post(f"/api/v1/inventory/bajas/{bi_id}/authorization-code", headers={"Authorization": f"Bearer {admin_token}"})
    assert code_resp.status_code == 201
    auth_code = code_resp.json()["authorization_code"]

    # Approve
    approve_resp = await client.post(
        f"/api/v1/inventory/bajas/{bi_id}/approve",
        json={"authorization_code": auth_code},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"

    # Stock should decrease
    prod_resp2 = await client.get(f"/api/v1/products/{prod_id}", headers={"Authorization": f"Bearer {operator_token}"})
    assert float(prod_resp2.json()["stock_actual"]) == 8.0


@pytest.mark.asyncio
async def test_baja_invalid_auth_code(client: AsyncClient, admin_token: str, operator_token: str):
    prod_id = await _create_product(client, admin_token, operator_token, "Invalid Code Test")
    await client.post("/api/v1/inventory/ingresos", json={"lines": [{"product_id": prod_id, "quantity": "5.00"}]}, headers={"Authorization": f"Bearer {operator_token}"})

    bi_resp = await client.post("/api/v1/inventory/bajas", json={"lines": [{"product_id": prod_id, "quantity": "1.00"}]}, headers={"Authorization": f"Bearer {operator_token}"})
    bi_id = bi_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/inventory/bajas/{bi_id}/approve",
        json={"authorization_code": "BADCODE1"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "AUTHORIZATION_CODE_INVALID"


@pytest.mark.asyncio
async def test_immutable_approved_document(client: AsyncClient, admin_token: str, operator_token: str):
    prod_id = await _create_product(client, admin_token, operator_token, "Immutable Test")
    await client.post("/api/v1/inventory/ingresos", json={"lines": [{"product_id": prod_id, "quantity": "5.00"}]}, headers={"Authorization": f"Bearer {operator_token}"})
    bi_resp = await client.post("/api/v1/inventory/bajas", json={"lines": [{"product_id": prod_id, "quantity": "1.00"}]}, headers={"Authorization": f"Bearer {operator_token}"})
    bi_id = bi_resp.json()["id"]

    code_resp = await client.post(f"/api/v1/inventory/bajas/{bi_id}/authorization-code", headers={"Authorization": f"Bearer {admin_token}"})
    auth_code = code_resp.json()["authorization_code"]
    await client.post(f"/api/v1/inventory/bajas/{bi_id}/approve", json={"authorization_code": auth_code}, headers={"Authorization": f"Bearer {admin_token}"})

    # Try to cancel approved document
    cancel_resp = await client.post(f"/api/v1/inventory/bajas/{bi_id}/cancel", headers={"Authorization": f"Bearer {operator_token}"})
    assert cancel_resp.status_code == 409
    assert cancel_resp.json()["code"] == "DOCUMENT_IS_IMMUTABLE"
