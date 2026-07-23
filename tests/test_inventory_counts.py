from decimal import Decimal

import pytest
from httpx import AsyncClient


async def _create_product(client, admin_token, operator_token, name, stock="0.00"):
    category = await client.post(
        "/api/v1/categories",
        json={"name": f"Cat {name}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    category_id = category.json()["id"]
    product = await client.post(
        "/api/v1/products",
        json={"name": name, "category_id": category_id, "pvp": "10.00"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    product_id = product.json()["id"]
    if Decimal(stock) > 0:
        await client.post(
            "/api/v1/inventory/ingresos",
            json={
                "lines": [{"product_id": product_id, "quantity": stock, "unit_cost": "5.00"}]
            },
            headers={"Authorization": f"Bearer {operator_token}"},
        )
    return product_id


@pytest.mark.asyncio
async def test_create_count_consolidates_duplicate_products_on_save(
    client: AsyncClient, admin_token: str, operator_token: str
):
    product_id = await _create_product(
        client, admin_token, operator_token, "Conteo Consolidado", stock="3.00"
    )

    response = await client.post(
        "/api/v1/inventory/conteos",
        json={
            "description": "Conteo de prueba",
            "lines": [
                {"product_id": product_id, "physical_quantity": "4.00"},
                {"product_id": product_id, "physical_quantity": "2.00"},
            ],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["number"].startswith("CONT-")
    assert payload["status"] == "draft"
    assert len(payload["lines"]) == 1
    assert payload["lines"][0]["product_id"] == product_id
    assert float(payload["lines"][0]["physical_quantity"]) == 6.0
    assert float(payload["lines"][0]["system_quantity"]) == 3.0
    assert float(payload["lines"][0]["difference_quantity"]) == 3.0


@pytest.mark.asyncio
async def test_apply_count_creates_adjustment_documents_and_updates_stock(
    client: AsyncClient, admin_token: str, operator_token: str
):
    low_product_id = await _create_product(
        client, admin_token, operator_token, "Conteo Faltante", stock="5.00"
    )
    high_product_id = await _create_product(
        client, admin_token, operator_token, "Conteo Sobrante", stock="1.00"
    )

    created = await client.post(
        "/api/v1/inventory/conteos",
        json={
            "description": "Aplicar conteo",
            "lines": [
                {"product_id": low_product_id, "physical_quantity": "3.00"},
                {"product_id": high_product_id, "physical_quantity": "4.00"},
            ],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    count_id = created.json()["id"]

    applied = await client.post(
        f"/api/v1/inventory/conteos/{count_id}/apply",
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert applied.status_code == 200
    payload = applied.json()
    assert payload["status"] == "applied"
    assert payload["positive_adjustment_document_id"] is not None
    assert payload["negative_adjustment_document_id"] is not None

    low_product = await client.get(
        f"/api/v1/products/{low_product_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    high_product = await client.get(
        f"/api/v1/products/{high_product_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert float(low_product.json()["stock_actual"]) == 3.0
    assert float(high_product.json()["stock_actual"]) == 4.0


@pytest.mark.asyncio
async def test_update_count_replaces_lines_with_consolidated_result(
    client: AsyncClient, admin_token: str, operator_token: str
):
    first_product_id = await _create_product(
        client, admin_token, operator_token, "Conteo Uno", stock="2.00"
    )
    second_product_id = await _create_product(
        client, admin_token, operator_token, "Conteo Dos", stock="1.00"
    )

    created = await client.post(
        "/api/v1/inventory/conteos",
        json={
            "description": "Editable",
            "lines": [{"product_id": first_product_id, "physical_quantity": "2.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    count_id = created.json()["id"]

    updated = await client.patch(
        f"/api/v1/inventory/conteos/{count_id}",
        json={
            "description": "Editable actualizado",
            "lines": [
                {"product_id": second_product_id, "physical_quantity": "2.00"},
                {"product_id": second_product_id, "physical_quantity": "3.00"},
            ],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert updated.status_code == 200
    payload = updated.json()
    assert payload["description"] == "Editable actualizado"
    assert len(payload["lines"]) == 1
    assert payload["lines"][0]["product_id"] == second_product_id
    assert float(payload["lines"][0]["physical_quantity"]) == 5.0


@pytest.mark.asyncio
async def test_apply_count_blocks_positive_adjustment_without_valid_cost(
    client: AsyncClient, admin_token: str, operator_token: str
):
    product_id = await _create_product(
        client, admin_token, operator_token, "Conteo Sin Costo", stock="0.00"
    )

    created = await client.post(
        "/api/v1/inventory/conteos",
        json={
            "description": "Conteo requiere costo",
            "lines": [{"product_id": product_id, "physical_quantity": "1.00"}],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert created.status_code == 201

    count_id = created.json()["id"]
    applied = await client.post(
        f"/api/v1/inventory/conteos/{count_id}/apply",
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    assert applied.status_code == 422
    assert applied.json()["code"] == "UNIT_COST_REQUIRED"