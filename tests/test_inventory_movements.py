"""Tests: inventory movements IN/EG/BI/AI (tasks 13.5, 13.6)"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture(autouse=True)
async def _company(company_config):
    """All inventory tests require a configured company."""
    return company_config


async def _create_product(
    client, admin_token, operator_token, name="Test Product", pvp="10.00"
):
    cat = await client.post(
        "/api/v1/categories",
        json={"name": f"Cat {name}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat_id = cat.json()["id"]
    prod = await client.post(
        "/api/v1/products",
        json={"name": name, "category_id": cat_id, "pvp": pvp},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    return prod.json()["id"]


_APPROVAL_PIN = "ABCD1234"


async def _approve_baja(client, admin_token, bi_id, code=_APPROVAL_PIN):
    """Approve a BI using the approver's approval code (PIN). The approver must
    have a configured approval code; we set it here for the test."""
    await client.post(
        "/api/v1/auth/approval-code",
        json={"approval_code": _APPROVAL_PIN},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    return await client.post(
        f"/api/v1/inventory/bajas/{bi_id}/approve",
        json={"authorization_code": code},
        headers={"Authorization": f"Bearer {admin_token}"},
    )


@pytest.mark.asyncio
async def test_ingreso_increases_stock(
    client: AsyncClient, admin_token: str, operator_token: str
):
    prod_id = await _create_product(client, admin_token, operator_token, "Ingreso Test")
    resp = await client.post(
        "/api/v1/inventory/ingresos",
        json={
            "lines": [{"product_id": prod_id, "quantity": "10.00", "unit_cost": "5.00"}]
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 201
    doc = resp.json()
    assert doc["doc_type"] == "IN"
    assert doc["status"] == "approved"

    # Verify stock updated
    prod_resp = await client.get(
        f"/api/v1/products/{prod_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert float(prod_resp.json()["stock_actual"]) == 10.0


@pytest.mark.asyncio
async def test_egreso_decreases_stock(
    client: AsyncClient, admin_token: str, operator_token: str
):
    prod_id = await _create_product(client, admin_token, operator_token, "Egreso Test")

    # First add stock
    await client.post(
        "/api/v1/inventory/ingresos",
        json={
            "lines": [{"product_id": prod_id, "quantity": "20.00", "unit_cost": "3.00"}]
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    resp = await client.post(
        "/api/v1/inventory/egresos",
        json={
            "seller_name": "VENDEDOR TEST",
            "lines": [
                {"product_id": prod_id, "quantity": "5.00", "unit_price": "10.00"}
            ]
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "approved"

    prod_resp = await client.get(
        f"/api/v1/products/{prod_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert float(prod_resp.json()["stock_actual"]) == 15.0


@pytest.mark.asyncio
async def test_egreso_insufficient_stock(
    client: AsyncClient, admin_token: str, operator_token: str
):
    prod_id = await _create_product(
        client, admin_token, operator_token, "Low Stock Product"
    )

    resp = await client.post(
        "/api/v1/inventory/egresos",
        json={"lines": [{"product_id": prod_id, "quantity": "100.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INSUFFICIENT_STOCK"


@pytest.mark.asyncio
async def test_sale_allows_document_type_none(
    client: AsyncClient, admin_token: str, operator_token: str
):
    prod_id = await _create_product(
        client, admin_token, operator_token, "Egreso Without Document"
    )

    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    resp = await client.post(
        "/api/v1/inventory/egresos",
        json={
            "egreso_type": "sale",
            "purchase_document_type": "none",
            "seller_name": "VENDEDOR TEST",
            "lines": [{"product_id": prod_id, "quantity": "1.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert resp.status_code == 201
    assert resp.json()["purchase_document_type"] == "none"
    assert resp.json()["purchase_document_number"] == "Venta sin documento"


@pytest.mark.asyncio
async def test_sale_requires_document_number_when_document_is_not_none(
    client: AsyncClient, admin_token: str, operator_token: str
):
    prod_id = await _create_product(
        client, admin_token, operator_token, "Sale Requires Document Number"
    )

    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    resp = await client.post(
        "/api/v1/inventory/egresos",
        json={
            "egreso_type": "sale",
            "purchase_document_type": "invoice",
            "seller_name": "VENDEDOR TEST",
            "lines": [{"product_id": prod_id, "quantity": "1.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "PURCHASE_DOCUMENT_NUMBER_REQUIRED"


@pytest.mark.asyncio
async def test_sale_requires_seller_name(
    client: AsyncClient, admin_token: str, operator_token: str
):
    prod_id = await _create_product(
        client, admin_token, operator_token, "Sale Requires Seller"
    )

    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    resp = await client.post(
        "/api/v1/inventory/egresos",
        json={
            "egreso_type": "sale",
            "purchase_document_type": "none",
            "lines": [{"product_id": prod_id, "quantity": "1.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "SELLER_REQUIRED"


@pytest.mark.asyncio
async def test_sale_rejects_seller_not_in_company_config(
    client: AsyncClient,
    admin_token: str,
    operator_token: str,
    db_session: AsyncSession,
):
    from app.models.company_config import CompanyConfig

    prod_id = await _create_product(
        client, admin_token, operator_token, "Sale Invalid Seller"
    )

    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    result = await db_session.execute(select(CompanyConfig).limit(1))
    company = result.scalar_one()
    company.sellers = ["OTRO VENDEDOR"]
    await db_session.commit()

    resp = await client.post(
        "/api/v1/inventory/egresos",
        json={
            "egreso_type": "sale",
            "purchase_document_type": "none",
            "seller_name": "VENDEDOR TEST",
            "lines": [{"product_id": prod_id, "quantity": "1.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "SELLER_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_egreso_rejects_invalid_document_type_for_egreso_type(
    client: AsyncClient, admin_token: str, operator_token: str
):
    prod_id = await _create_product(
        client, admin_token, operator_token, "Egreso Invalid Doc Type"
    )

    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    resp = await client.post(
        "/api/v1/inventory/egresos",
        json={
            "egreso_type": "sale",
            "purchase_document_type": "disposal_act",
            "seller_name": "VENDEDOR TEST",
            "lines": [{"product_id": prod_id, "quantity": "1.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_PURCHASE_DOCUMENT_TYPE"


@pytest.mark.asyncio
async def test_baja_requires_reason(
    client: AsyncClient, admin_token: str, operator_token: str
):
    prod_id = await _create_product(client, admin_token, operator_token, "Baja Requires Reason")

    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    resp = await client.post(
        "/api/v1/inventory/egresos",
        json={
            "egreso_type": "baja",
            "purchase_document_type": "disposal_act",
            "lines": [{"product_id": prod_id, "quantity": "1.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "BAJA_REASON_REQUIRED"


@pytest.mark.asyncio
async def test_egreso_other_document_requires_notes(
    client: AsyncClient, admin_token: str, operator_token: str
):
    prod_id = await _create_product(
        client, admin_token, operator_token, "Egreso Other Requires Notes"
    )

    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    resp = await client.post(
        "/api/v1/inventory/egresos",
        json={
            "egreso_type": "other",
            "purchase_document_type": "other",
            "lines": [{"product_id": prod_id, "quantity": "1.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "NOTES_REQUIRED_FOR_OTHER_DOCUMENT"


@pytest.mark.asyncio
async def test_egreso_type_must_be_enabled_in_company_config(
    client: AsyncClient,
    admin_token: str,
    operator_token: str,
    db_session: AsyncSession,
):
    from app.models.company_config import CompanyConfig

    prod_id = await _create_product(
        client, admin_token, operator_token, "Egreso Disabled Type"
    )

    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    result = await db_session.execute(select(CompanyConfig).limit(1))
    company = result.scalar_one()
    company.enabled_egreso_types = ["sale"]
    await db_session.commit()

    resp = await client.post(
        "/api/v1/inventory/egresos",
        json={
            "egreso_type": "baja",
            "purchase_document_type": "disposal_act",
            "baja_reason": "damage",
            "notes": "Donación semanal",
            "lines": [{"product_id": prod_id, "quantity": "1.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "EGRESO_TYPE_DISABLED"


@pytest.mark.asyncio
async def test_egreso_persists_type_and_document_metadata(
    client: AsyncClient, admin_token: str, operator_token: str
):
    prod_id = await _create_product(
        client, admin_token, operator_token, "Egreso Metadata"
    )

    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    resp = await client.post(
        "/api/v1/inventory/egresos",
        json={
            "egreso_type": "baja",
            "purchase_document_type": "disposal_act",
            "baja_reason": "damage",
            "purchase_document_number": "TR-001",
            "reference": "Traslado bodega norte",
            "notes": "Salida por traslado interno",
            "lines": [{"product_id": prod_id, "quantity": "1.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["egreso_type"] == "baja"
    assert body["baja_reason"] == "damage"
    assert body["purchase_document_type"] == "disposal_act"
    assert body["purchase_document_number"] == "TR-001"
    assert body["purchase_document_date"] is not None


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
async def test_document_numbering_consecutive(
    client: AsyncClient, admin_token: str, operator_token: str
):
    prod_id = await _create_product(
        client, admin_token, operator_token, "Numbering Test"
    )
    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    r2 = await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "3.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

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
    prod_id = await _create_product(
        client, admin_token, operator_token, "Baja Flow Test"
    )

    # Add stock first
    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "10.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    # Create BI request — should be pending, no stock change
    bi_resp = await client.post(
        "/api/v1/inventory/bajas",
        json={
            "reference": "Damaged",
            "notes": "Damaged",
            "lines": [{"product_id": prod_id, "quantity": "2.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert bi_resp.status_code == 201
    assert bi_resp.json()["status"] == "pending"
    bi_id = bi_resp.json()["id"]

    # Stock should not have changed
    prod_resp = await client.get(
        f"/api/v1/products/{prod_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert float(prod_resp.json()["stock_actual"]) == 10.0

    # Approve using the approver's approval code (PIN)
    approve_resp = await _approve_baja(client, admin_token, bi_id)
    assert approve_resp.status_code == 200, approve_resp.text
    assert approve_resp.json()["status"] == "approved"

    # Stock should decrease
    prod_resp2 = await client.get(
        f"/api/v1/products/{prod_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert float(prod_resp2.json()["stock_actual"]) == 8.0


@pytest.mark.asyncio
async def test_baja_invalid_auth_code(
    client: AsyncClient, admin_token: str, operator_token: str
):
    prod_id = await _create_product(
        client, admin_token, operator_token, "Invalid Code Test"
    )
    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    bi_resp = await client.post(
        "/api/v1/inventory/bajas",
        json={"reference": "Baja test", "lines": [{"product_id": prod_id, "quantity": "1.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    bi_id = bi_resp.json()["id"]

    # Approver has a configured PIN, but the supplied code is wrong.
    await client.post(
        "/api/v1/auth/approval-code",
        json={"approval_code": _APPROVAL_PIN},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.post(
        f"/api/v1/inventory/bajas/{bi_id}/approve",
        json={"authorization_code": "BADCODE1"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "APPROVAL_CODE_INVALID"


@pytest.mark.asyncio
async def test_auth_code_expiration_uses_configured_param(
    client: AsyncClient,
    admin_token: str,
    operator_token: str,
    db_session: AsyncSession,
):
    from app.models.inventory import AuthorizationCode
    from app.models.system_param import SystemParam

    db_session.add(
        SystemParam(key="auth_code_expire_minutes", value="2", description="test")
    )
    await db_session.commit()

    prod_id = await _create_product(
        client, admin_token, operator_token, "Expire Param Test"
    )
    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5.00", "unit_cost": "1.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    bi_resp = await client.post(
        "/api/v1/inventory/bajas",
        json={"reference": "Baja test", "lines": [{"product_id": prod_id, "quantity": "1.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert bi_resp.status_code == 201, bi_resp.text
    bi_id = bi_resp.json()["id"]

    now = datetime.now(timezone.utc)
    code_resp = await client.post(
        f"/api/v1/inventory/bajas/{bi_id}/authorization-code",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert code_resp.status_code == 201

    result = await db_session.execute(
        select(AuthorizationCode)
        .where(AuthorizationCode.document_id == bi_id)
        .order_by(AuthorizationCode.created_at.desc())
        .limit(1)
    )
    rec = result.scalar_one()

    delta_seconds = (rec.expires_at - now).total_seconds()
    assert 90 <= delta_seconds <= 150


@pytest.mark.asyncio
async def test_immutable_approved_document(
    client: AsyncClient, admin_token: str, operator_token: str
):
    prod_id = await _create_product(
        client, admin_token, operator_token, "Immutable Test"
    )
    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    bi_resp = await client.post(
        "/api/v1/inventory/bajas",
        json={"reference": "Baja test", "lines": [{"product_id": prod_id, "quantity": "1.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    bi_id = bi_resp.json()["id"]

    approve_resp = await _approve_baja(client, admin_token, bi_id)
    assert approve_resp.status_code == 200, approve_resp.text

    # Try to cancel approved document
    cancel_resp = await client.post(
        f"/api/v1/inventory/bajas/{bi_id}/cancel",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert cancel_resp.status_code == 409
    assert cancel_resp.json()["code"] == "DOCUMENT_IS_IMMUTABLE"


# --- Anulación (void) de documentos aprobados ---


async def _stock(client, token, prod_id):
    r = await client.get(f"/api/v1/products/{prod_id}", headers={"Authorization": f"Bearer {token}"})
    return float(r.json()["stock_actual"])


@pytest.mark.asyncio
async def test_void_ingreso_reverts_stock(client, admin_token, operator_token):
    prod_id = await _create_product(client, admin_token, operator_token, "Void IN")
    doc = (await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "10.00", "unit_cost": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )).json()
    assert await _stock(client, admin_token, prod_id) == 10.0

    resp = await client.post(
        f"/api/v1/inventory/documents/{doc['id']}/void",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "voided"
    assert await _stock(client, admin_token, prod_id) == 0.0


@pytest.mark.asyncio
async def test_void_egreso_restores_stock(client, admin_token, operator_token):
    prod_id = await _create_product(client, admin_token, operator_token, "Void EG")
    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "20.00", "unit_cost": "3.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    eg = (await client.post(
        "/api/v1/inventory/egresos",
        json={
            "seller_name": "VENDEDOR TEST",
            "lines": [{"product_id": prod_id, "quantity": "5.00", "unit_price": "9.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )).json()
    assert await _stock(client, admin_token, prod_id) == 15.0

    resp = await client.post(
        f"/api/v1/inventory/documents/{eg['id']}/void",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert await _stock(client, admin_token, prod_id) == 20.0


@pytest.mark.asyncio
async def test_operator_void_requires_pin(client, admin_token, operator_token):
    prod_id = await _create_product(client, admin_token, operator_token, "Void NoPin")
    doc = (await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "4.00", "unit_cost": "1.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )).json()

    resp = await client.post(
        f"/api/v1/inventory/documents/{doc['id']}/void",
        json={},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VOID_PIN_REQUIRED"


@pytest.mark.asyncio
async def test_operator_void_with_valid_pin(client, admin_token, operator_token):
    # Admin configures an approval code (the PIN — distinct from login password).
    await client.post(
        "/api/v1/auth/approval-code",
        json={"approval_code": "ABCD1234"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    prod_id = await _create_product(client, admin_token, operator_token, "Void Pin")
    doc = (await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "7.00", "unit_cost": "2.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )).json()

    bad = await client.post(
        f"/api/v1/inventory/documents/{doc['id']}/void",
        json={"authorizer_pin": "00000000"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "VOID_PIN_INVALID"

    ok = await client.post(
        f"/api/v1/inventory/documents/{doc['id']}/void",
        json={"authorizer_pin": "abcd1234"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "voided"
    assert await _stock(client, admin_token, prod_id) == 0.0


@pytest.mark.asyncio
async def test_void_twice_fails(client, admin_token, operator_token):
    prod_id = await _create_product(client, admin_token, operator_token, "Void Twice")
    doc = (await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "3.00", "unit_cost": "1.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )).json()
    await client.post(f"/api/v1/inventory/documents/{doc['id']}/void", json={}, headers={"Authorization": f"Bearer {admin_token}"})
    again = await client.post(f"/api/v1/inventory/documents/{doc['id']}/void", json={}, headers={"Authorization": f"Bearer {admin_token}"})
    assert again.status_code == 409
    assert again.json()["code"] == "DOCUMENT_NOT_APPROVED"


@pytest.mark.asyncio
async def test_void_ingreso_consumed_fails(client, admin_token, operator_token):
    prod_id = await _create_product(client, admin_token, operator_token, "Void Consumed")
    ing = (await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "10.00", "unit_cost": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )).json()
    # Consume all stock with an egreso
    await client.post(
        "/api/v1/inventory/egresos",
        json={
            "seller_name": "VENDEDOR TEST",
            "lines": [{"product_id": prod_id, "quantity": "10.00", "unit_price": "9.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    resp = await client.post(
        f"/api/v1/inventory/documents/{ing['id']}/void",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "CANNOT_VOID_STOCK_CONSUMED"


@pytest.mark.asyncio
async def test_void_ingreso_consumed_fails_weighted_average(
    client, admin_token, operator_token, db_session
):
    # Regression: with WEIGHTED_AVERAGE (no PEPS lots) a consumed-stock void
    # must still fail cleanly (409), not raise a 500 from the stock function.
    from app.models.system_param import SystemParam

    db_session.add(SystemParam(key="kardex_method", value="WEIGHTED_AVERAGE"))
    await db_session.commit()

    prod_id = await _create_product(client, admin_token, operator_token, "Void WA Consumed")
    ing = (await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "10.00", "unit_cost": "5.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )).json()
    await client.post(
        "/api/v1/inventory/egresos",
        json={
            "seller_name": "VENDEDOR TEST",
            "lines": [{"product_id": prod_id, "quantity": "10.00", "unit_price": "9.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    resp = await client.post(
        f"/api/v1/inventory/documents/{ing['id']}/void",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "CANNOT_VOID_STOCK_CONSUMED"


@pytest.mark.asyncio
async def test_integer_mode_rejects_fractional_quantity(client, admin_token, operator_token):
    # Default stock_quantity_mode in tests is 'integer' (no seeded param).
    prod_id = await _create_product(client, admin_token, operator_token, "Int Qty")
    resp = await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "1.5", "unit_cost": "2.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_QUANTITY"


@pytest.mark.asyncio
async def test_decimal_mode_allows_fractional_quantity(client, admin_token, operator_token, db_session):
    from app.models.system_param import SystemParam

    db_session.add(SystemParam(key="stock_quantity_mode", value="decimal"))
    await db_session.commit()

    prod_id = await _create_product(client, admin_token, operator_token, "Dec Qty")
    resp = await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "1.5", "unit_cost": "2.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 201, resp.text
