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


_APPROVAL_PIN = "1234"


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
async def test_operator_can_create_purchase_but_not_other_ingreso(
    client: AsyncClient, admin_token: str, operator_token: str
):
    prod_id = await _create_product(client, admin_token, operator_token, "Operator Purchase")
    purchase = await client.post(
        "/api/v1/inventory/ingresos",
        json={
            "ingreso_type": "purchase",
            "purchase_document_type": "invoice",
            "lines": [{"product_id": prod_id, "quantity": "2", "unit_cost": "5"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert purchase.status_code == 201

    blocked = await client.post(
        "/api/v1/inventory/ingresos",
        json={
            "ingreso_type": "initial_inventory",
            "purchase_document_type": "inventory_act",
            "lines": [{"product_id": prod_id, "quantity": "1", "unit_cost": "5"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert blocked.status_code == 422
    assert blocked.json()["code"] == "INGRESO_TYPE_FORBIDDEN"


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
            "purchase_document_type": "none",
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
async def test_sales_note_rejects_more_than_nine_lines(
    client: AsyncClient, admin_token: str, operator_token: str
):
    resp = await client.post(
        "/api/v1/inventory/egresos",
        json={
            "egreso_type": "sale",
            "purchase_document_type": "sales_note",
            "purchase_document_number": "NV-10-LINEAS",
            "seller_name": "VENDEDOR TEST",
            "lines": [
                {"product_id": index, "quantity": "1", "unit_price": "1"}
                for index in range(1, 11)
            ],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "SALES_NOTE_LINE_LIMIT"


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
async def test_sale_document_number_must_be_unique(
    client: AsyncClient, admin_token: str, operator_token: str
):
    prod_id = await _create_product(
        client, admin_token, operator_token, "Sale Unique Document Number"
    )

    await client.post(
        "/api/v1/inventory/ingresos",
        json={"lines": [{"product_id": prod_id, "quantity": "10.00"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    first = await client.post(
        "/api/v1/inventory/egresos",
        json={
            "egreso_type": "sale",
            "purchase_document_type": "invoice",
            "purchase_document_number": "001-001-000123",
            "seller_name": "VENDEDOR TEST",
            "lines": [{"product_id": prod_id, "quantity": "1.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        "/api/v1/inventory/egresos",
        json={
            "egreso_type": "sale",
            "purchase_document_type": "invoice",
            "purchase_document_number": "001-001-000123",
            "seller_name": "VENDEDOR TEST",
            "lines": [{"product_id": prod_id, "quantity": "1.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert second.status_code == 422
    assert second.json()["code"] == "PURCHASE_DOCUMENT_NUMBER_DUPLICATE"


@pytest.mark.asyncio
async def test_sale_document_number_rejects_leading_or_trailing_spaces(
    client: AsyncClient, admin_token: str, operator_token: str
):
    prod_id = await _create_product(
        client, admin_token, operator_token, "Sale Document Number Spaces"
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
            "purchase_document_number": " 001-001-000124 ",
            "seller_name": "VENDEDOR TEST",
            "lines": [{"product_id": prod_id, "quantity": "1.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "PURCHASE_DOCUMENT_NUMBER_WHITESPACE"


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
    assert resp.json().get("code") in {"BAJA_REASON_REQUIRED", "VALIDATION_ERROR"}


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
        json={"authorization_code": "9999"},
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
            "purchase_document_type": "none",
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
        json={"approval_code": "1234"},
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
        json={"authorizer_pin": "0000"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert bad.status_code == 422
    assert bad.json()["code"] == "VOID_PIN_INVALID"

    ok = await client.post(
        f"/api/v1/inventory/documents/{doc['id']}/void",
        json={"authorizer_pin": "1234"},
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
            "purchase_document_type": "none",
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
            "purchase_document_type": "none",
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


@pytest.mark.asyncio
async def test_sale_exchange_keeps_original_and_creates_return_and_new_sale(
    client: AsyncClient, admin_token: str, operator_token: str
):
    await client.post(
        "/api/v1/auth/approval-code",
        json={"approval_code": "1234"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    prod_a = await _create_product(
        client, admin_token, operator_token, "Exchange A", pvp="10.00"
    )
    prod_b = await _create_product(
        client, admin_token, operator_token, "Exchange B", pvp="12.00"
    )

    await client.post(
        "/api/v1/inventory/ingresos",
        json={
            "lines": [
                {"product_id": prod_a, "quantity": "10.00", "unit_cost": "3.00"},
                {"product_id": prod_b, "quantity": "10.00", "unit_cost": "4.00"},
            ]
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    original_sale = (
        await client.post(
            "/api/v1/inventory/egresos",
            json={
                "egreso_type": "sale",
                "purchase_document_type": "none",
                "seller_name": "VENDEDOR TEST",
                "lines": [
                    {
                        "product_id": prod_a,
                        "quantity": "5.00",
                        "unit_price": "10.00",
                    }
                ],
            },
            headers={"Authorization": f"Bearer {operator_token}"},
        )
    ).json()

    resp = await client.post(
        f"/api/v1/inventory/egresos/{original_sale['id']}/exchange",
        json={
            "returned_lines": [
                {
                    "product_id": prod_a,
                    "quantity": "2.00",
                    "return_condition": "available",
                }
            ],
            "new_lines": [
                {"product_id": prod_b, "quantity": "2.00", "unit_price": "12.00"}
            ],
            "authorizer_pin": "1234",
            "notes": "Cambio por talla",
            "payment_method": "EFECTIVO",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["original_document"]["status"] == "approved"
    assert body["return_document"]["status"] == "approved"
    assert body["return_document"]["ingreso_type"] == "customer_return"
    assert body["new_document"]["status"] == "approved"
    assert body["original_document"]["exchange_return_document_id"] == body["return_document"]["id"]
    assert body["original_document"]["exchange_new_sale_document_id"] == body["new_document"]["id"]
    assert body["return_document"]["exchange_original_document_id"] == body["original_document"]["id"]
    assert body["new_document"]["exchange_original_document_id"] == body["original_document"]["id"]
    assert float(body["return_total"]) == 20.0
    assert float(body["new_total"]) == 24.0
    assert float(body["difference_total"]) == 4.0
    assert float(body["new_document"]["amount_received"]) == 4.0
    assert float(body["new_document"]["credit_applied_amount"]) == 20.0
    assert body["new_document"]["outstanding_amount"] is None

    closing = await client.get(
        "/api/v1/reports/cierre-dia",
        params={"date": datetime.now(timezone.utc).date().isoformat()},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert closing.status_code == 200, closing.text
    exchange_sale = next(
        item for item in closing.json()["documents"] if item["id"] == body["new_document"]["id"]
    )
    assert float(exchange_sale["amount_collected"]) == 4.0

    blocked_void = await client.post(
        f"/api/v1/inventory/documents/{body['new_document']['id']}/void",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert blocked_void.status_code == 422
    assert blocked_void.json()["code"] == "EXCHANGE_DOCUMENT_VOID_FORBIDDEN"

    stock_a = await _stock(client, admin_token, prod_a)
    stock_b = await _stock(client, admin_token, prod_b)
    assert stock_a == 7.0
    assert stock_b == 8.0

    reverted = await client.post(
        f"/api/v1/inventory/egresos/{body['new_document']['id']}/exchange/revert",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert reverted.status_code == 200, reverted.text
    reversed_body = reverted.json()
    assert reversed_body["new_document"]["status"] == "voided"
    assert reversed_body["return_document"]["status"] == "voided"
    assert reversed_body["original_document"]["exchange_new_sale_document_id"] is None
    assert float(reversed_body["refunded_amount"]) == 4.0
    assert await _stock(client, admin_token, prod_a) == 5.0
    assert await _stock(client, admin_token, prod_b) == 10.0


@pytest.mark.asyncio
async def test_sale_exchange_validates_return_cannot_exceed_sold(
    client: AsyncClient, admin_token: str, operator_token: str
):
    await client.post(
        "/api/v1/auth/approval-code",
        json={"approval_code": "1234"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    prod_id = await _create_product(
        client, admin_token, operator_token, "Exchange Block", pvp="10.00"
    )
    prod_new = await _create_product(
        client, admin_token, operator_token, "Exchange Block New", pvp="11.00"
    )
    await client.post(
        "/api/v1/inventory/ingresos",
        json={
            "lines": [
                {"product_id": prod_id, "quantity": "10.00", "unit_cost": "3.00"},
                {"product_id": prod_new, "quantity": "10.00", "unit_cost": "4.00"},
            ]
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    sale = (
        await client.post(
            "/api/v1/inventory/egresos",
            json={
                "egreso_type": "sale",
                "purchase_document_type": "none",
                "seller_name": "VENDEDOR TEST",
                "lines": [{"product_id": prod_id, "quantity": "5.00", "unit_price": "10.00"}],
            },
            headers={"Authorization": f"Bearer {operator_token}"},
        )
    ).json()
    resp = await client.post(
        f"/api/v1/inventory/egresos/{sale['id']}/exchange",
        json={
            "returned_lines": [
                {
                    "product_id": prod_id,
                    "quantity": "6.00",
                    "return_condition": "available",
                }
            ],
            "new_lines": [{"product_id": prod_new, "quantity": "1.00", "unit_price": "10.00"}],
            "authorizer_pin": "1234",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 422
    assert resp.json().get("code") == "EXCHANGE_RETURN_EXCEEDS_SOLD"

    below_return = await client.post(
        f"/api/v1/inventory/egresos/{sale['id']}/exchange",
        json={
            "returned_lines": [
                {
                    "product_id": prod_id,
                    "quantity": "2.00",
                    "return_condition": "available",
                }
            ],
            "new_lines": [
                {"product_id": prod_new, "quantity": "1.00", "unit_price": "10.00"}
            ],
            "authorizer_pin": "1234",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert below_return.status_code == 422
    assert below_return.json().get("code") == "EXCHANGE_NEW_TOTAL_BELOW_RETURN"


@pytest.mark.asyncio
async def test_sale_exchange_allows_original_seller_even_if_now_disabled(
    client: AsyncClient,
    admin_token: str,
    operator_token: str,
    db_session: AsyncSession,
):
    from app.models.company_config import CompanyConfig

    await client.post(
        "/api/v1/auth/approval-code",
        json={"approval_code": "1234"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    prod_a = await _create_product(
        client, admin_token, operator_token, "Exchange Seller A", pvp="100.00"
    )
    prod_b = await _create_product(
        client, admin_token, operator_token, "Exchange Seller B", pvp="90.00"
    )

    await client.post(
        "/api/v1/inventory/ingresos",
        json={
            "lines": [
                {"product_id": prod_a, "quantity": "5.00", "unit_cost": "10.00"},
                {"product_id": prod_b, "quantity": "5.00", "unit_cost": "10.00"},
            ]
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    sale = (
        await client.post(
            "/api/v1/inventory/egresos",
            json={
                "egreso_type": "sale",
                "purchase_document_type": "none",
                "seller_name": "VENDEDOR TEST",
                "lines": [{"product_id": prod_a, "quantity": "1.00", "unit_price": "100.00"}],
            },
            headers={"Authorization": f"Bearer {operator_token}"},
        )
    ).json()

    result = await db_session.execute(select(CompanyConfig).limit(1))
    company = result.scalar_one()
    company.sellers = ["OTRO VENDEDOR"]
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/inventory/egresos/{sale['id']}/exchange",
        json={
            "returned_lines": [
                {
                    "product_id": prod_a,
                    "quantity": "1.00",
                    "return_condition": "requires_review",
                }
            ],
            "new_lines": [{"product_id": prod_b, "quantity": "1.00", "unit_price": "90.00"}],
            "authorizer_pin": "1234",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["new_document"]["seller_name"] == "VENDEDOR TEST"
    assert body["original_document"]["status"] == "approved"


@pytest.mark.asyncio
async def test_sale_exchange_reuses_document_number_with_cambio_suffix(
    client: AsyncClient,
    admin_token: str,
    operator_token: str,
):
    await client.post(
        "/api/v1/auth/approval-code",
        json={"approval_code": "1234"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    prod_a = await _create_product(
        client, admin_token, operator_token, "Exchange Doc A", pvp="50.00"
    )
    prod_b = await _create_product(
        client, admin_token, operator_token, "Exchange Doc B", pvp="60.00"
    )

    await client.post(
        "/api/v1/inventory/ingresos",
        json={
            "lines": [
                {"product_id": prod_a, "quantity": "5.00", "unit_cost": "10.00"},
                {"product_id": prod_b, "quantity": "5.00", "unit_cost": "12.00"},
            ]
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    sale = (
        await client.post(
            "/api/v1/inventory/egresos",
            json={
                "egreso_type": "sale",
                "purchase_document_type": "invoice",
                "purchase_document_number": "001-001-000500",
                "seller_name": "VENDEDOR TEST",
                "lines": [{"product_id": prod_a, "quantity": "1.00", "unit_price": "50.00"}],
            },
            headers={"Authorization": f"Bearer {operator_token}"},
        )
    ).json()

    resp = await client.post(
        f"/api/v1/inventory/egresos/{sale['id']}/exchange",
        json={
            "returned_lines": [
                {
                    "product_id": prod_a,
                    "quantity": "1.00",
                    "return_condition": "available",
                }
            ],
            "new_lines": [{"product_id": prod_b, "quantity": "1.00", "unit_price": "60.00"}],
            "authorizer_pin": "1234",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["new_document"]["purchase_document_type"] == "invoice"
    assert body["new_document"]["purchase_document_number"] == "001-001-000500 (cambio)"


@pytest.mark.asyncio
async def test_sale_exchange_blocks_when_sale_already_from_change(
    client: AsyncClient,
    admin_token: str,
    operator_token: str,
):
    await client.post(
        "/api/v1/auth/approval-code",
        json={"approval_code": "1234"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    prod_a = await _create_product(
        client, admin_token, operator_token, "Exchange Chain A", pvp="20.00"
    )
    prod_b = await _create_product(
        client, admin_token, operator_token, "Exchange Chain B", pvp="25.00"
    )
    prod_c = await _create_product(
        client, admin_token, operator_token, "Exchange Chain C", pvp="30.00"
    )

    await client.post(
        "/api/v1/inventory/ingresos",
        json={
            "lines": [
                {"product_id": prod_a, "quantity": "10.00", "unit_cost": "5.00"},
                {"product_id": prod_b, "quantity": "10.00", "unit_cost": "6.00"},
                {"product_id": prod_c, "quantity": "10.00", "unit_cost": "7.00"},
            ]
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    sale = (
        await client.post(
            "/api/v1/inventory/egresos",
            json={
                "egreso_type": "sale",
                "purchase_document_type": "none",
                "seller_name": "VENDEDOR TEST",
                "lines": [{"product_id": prod_a, "quantity": "1.00", "unit_price": "20.00"}],
            },
            headers={"Authorization": f"Bearer {operator_token}"},
        )
    ).json()

    first_exchange = await client.post(
        f"/api/v1/inventory/egresos/{sale['id']}/exchange",
        json={
            "returned_lines": [
                {
                    "product_id": prod_a,
                    "quantity": "1.00",
                    "return_condition": "available",
                }
            ],
            "new_lines": [{"product_id": prod_b, "quantity": "1.00", "unit_price": "25.00"}],
            "authorizer_pin": "1234",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert first_exchange.status_code == 200, first_exchange.text
    new_sale_id = first_exchange.json()["new_document"]["id"]

    second_exchange = await client.post(
        f"/api/v1/inventory/egresos/{new_sale_id}/exchange",
        json={
            "returned_lines": [
                {
                    "product_id": prod_b,
                    "quantity": "1.00",
                    "return_condition": "available",
                }
            ],
            "new_lines": [{"product_id": prod_c, "quantity": "1.00", "unit_price": "30.00"}],
            "authorizer_pin": "1234",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert second_exchange.status_code == 422, second_exchange.text
    assert second_exchange.json()["code"] == "EXCHANGE_ALREADY_FROM_CHANGE"


@pytest.mark.asyncio
async def test_sale_exchange_blocks_when_sale_already_has_exchange_generated(
    client: AsyncClient,
    admin_token: str,
    operator_token: str,
):
    await client.post(
        "/api/v1/auth/approval-code",
        json={"approval_code": "1234"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    prod_a = await _create_product(
        client, admin_token, operator_token, "Exchange Repeated A", pvp="20.00"
    )
    prod_b = await _create_product(
        client, admin_token, operator_token, "Exchange Repeated B", pvp="25.00"
    )

    await client.post(
        "/api/v1/inventory/ingresos",
        json={
            "lines": [
                {"product_id": prod_a, "quantity": "10.00", "unit_cost": "5.00"},
                {"product_id": prod_b, "quantity": "10.00", "unit_cost": "6.00"},
            ]
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    sale = (
        await client.post(
            "/api/v1/inventory/egresos",
            json={
                "egreso_type": "sale",
                "purchase_document_type": "none",
                "seller_name": "VENDEDOR TEST",
                "lines": [{"product_id": prod_a, "quantity": "1.00", "unit_price": "20.00"}],
            },
            headers={"Authorization": f"Bearer {operator_token}"},
        )
    ).json()

    first_exchange = await client.post(
        f"/api/v1/inventory/egresos/{sale['id']}/exchange",
        json={
            "returned_lines": [
                {
                    "product_id": prod_a,
                    "quantity": "1.00",
                    "return_condition": "available",
                }
            ],
            "new_lines": [{"product_id": prod_b, "quantity": "1.00", "unit_price": "25.00"}],
            "authorizer_pin": "1234",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert first_exchange.status_code == 200, first_exchange.text

    repeated_exchange = await client.post(
        f"/api/v1/inventory/egresos/{sale['id']}/exchange",
        json={
            "returned_lines": [
                {
                    "product_id": prod_a,
                    "quantity": "1.00",
                    "return_condition": "available",
                }
            ],
            "new_lines": [{"product_id": prod_b, "quantity": "1.00", "unit_price": "25.00"}],
            "authorizer_pin": "1234",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert repeated_exchange.status_code == 422, repeated_exchange.text
    assert repeated_exchange.json()["code"] == "EXCHANGE_ALREADY_GENERATED"
