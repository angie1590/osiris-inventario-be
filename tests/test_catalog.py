"""Tests: categories and products catalog (task 13.4)"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_category(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/categories",
        json={"name": "Electronics"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Electronics"
    assert data["parent_id"] is None


@pytest.mark.asyncio
async def test_create_subcategory(client: AsyncClient, admin_token: str):
    parent = await client.post("/api/v1/categories", json={"name": "Parent Cat"}, headers={"Authorization": f"Bearer {admin_token}"})
    parent_id = parent.json()["id"]

    child = await client.post(
        "/api/v1/categories",
        json={"name": "Child Cat", "parent_id": parent_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert child.status_code == 201
    assert child.json()["parent_id"] == parent_id


@pytest.mark.asyncio
async def test_delete_category_with_children_fails(client: AsyncClient, admin_token: str):
    parent = await client.post("/api/v1/categories", json={"name": "Parent With Child"}, headers={"Authorization": f"Bearer {admin_token}"})
    parent_id = parent.json()["id"]
    await client.post("/api/v1/categories", json={"name": "Child", "parent_id": parent_id}, headers={"Authorization": f"Bearer {admin_token}"})

    resp = await client.delete(f"/api/v1/categories/{parent_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "CATEGORY_HAS_CHILDREN"


@pytest.mark.asyncio
async def test_attribute_inheritance(client: AsyncClient, admin_token: str):
    parent = await client.post("/api/v1/categories", json={"name": "Parent Attr"}, headers={"Authorization": f"Bearer {admin_token}"})
    parent_id = parent.json()["id"]

    # Add attribute to parent
    await client.post(
        f"/api/v1/categories/{parent_id}/attributes",
        json={"name": "brand", "data_type": "text"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    child = await client.post("/api/v1/categories", json={"name": "Child Attr", "parent_id": parent_id}, headers={"Authorization": f"Bearer {admin_token}"})
    child_id = child.json()["id"]

    attrs = await client.get(f"/api/v1/categories/{child_id}/attributes", headers={"Authorization": f"Bearer {admin_token}"})
    assert attrs.status_code == 200
    names = [a["name"] for a in attrs.json()]
    assert "brand" in names
    # Check it's marked as inherited
    brand_attr = next(a for a in attrs.json() if a["name"] == "brand")
    assert brand_attr["inherited"] is True


@pytest.mark.asyncio
async def test_duplicate_attribute_in_hierarchy_fails(client: AsyncClient, admin_token: str):
    parent = await client.post("/api/v1/categories", json={"name": "Dup Parent"}, headers={"Authorization": f"Bearer {admin_token}"})
    parent_id = parent.json()["id"]
    await client.post(f"/api/v1/categories/{parent_id}/attributes", json={"name": "color", "data_type": "text"}, headers={"Authorization": f"Bearer {admin_token}"})

    child = await client.post("/api/v1/categories", json={"name": "Dup Child", "parent_id": parent_id}, headers={"Authorization": f"Bearer {admin_token}"})
    child_id = child.json()["id"]

    resp = await client.post(f"/api/v1/categories/{child_id}/attributes", json={"name": "color", "data_type": "text"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "DUPLICATE_ATTRIBUTE_IN_HIERARCHY"


@pytest.mark.asyncio
async def test_product_stock_readonly(client: AsyncClient, operator_token: str, admin_token: str):
    cat = await client.post("/api/v1/categories", json={"name": "Stock Test Cat"}, headers={"Authorization": f"Bearer {admin_token}"})
    cat_id = cat.json()["id"]

    # Create product with stock_actual provided — should be ignored
    resp = await client.post(
        "/api/v1/products",
        json={"name": "Stock Test", "category_id": cat_id, "pvp": "5.00"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 201
    assert float(resp.json()["stock_actual"]) == 0.0


@pytest.mark.asyncio
async def test_create_product_with_required_attribute(client: AsyncClient, admin_token: str, operator_token: str):
    cat = await client.post("/api/v1/categories", json={"name": "Attr Required Cat"}, headers={"Authorization": f"Bearer {admin_token}"})
    cat_id = cat.json()["id"]
    await client.post(f"/api/v1/categories/{cat_id}/attributes", json={"name": "model", "data_type": "text", "is_required": True}, headers={"Authorization": f"Bearer {admin_token}"})

    # Without required attribute — should fail
    resp = await client.post(
        "/api/v1/products",
        json={"name": "Missing Attr Product", "category_id": cat_id, "pvp": "5.00"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_attribute_type_change_blocked_when_values_exist(client: AsyncClient, admin_token: str, operator_token: str):
    cat = await client.post("/api/v1/categories", json={"name": "TypeChange Cat"}, headers={"Authorization": f"Bearer {admin_token}"})
    cat_id = cat.json()["id"]
    attr_resp = await client.post(
        f"/api/v1/categories/{cat_id}/attributes",
        json={"name": "color", "data_type": "text"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    attr_id = attr_resp.json()["id"]

    # Create a product with a value for this attribute
    await client.post(
        "/api/v1/products",
        json={"name": "Colored Product", "category_id": cat_id, "pvp": "5.00", "custom_attributes": {"color": "red"}},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    # Attempt to change the data_type — should be blocked
    resp = await client.patch(
        f"/api/v1/categories/{cat_id}/attributes/{attr_id}",
        json={"data_type": "integer"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ATTRIBUTE_TYPE_CHANGE_BLOCKED"


@pytest.mark.asyncio
async def test_deactivate_attribute_preserves_product_values(client: AsyncClient, admin_token: str, operator_token: str):
    cat = await client.post("/api/v1/categories", json={"name": "Deactivate Cat"}, headers={"Authorization": f"Bearer {admin_token}"})
    cat_id = cat.json()["id"]
    attr_resp = await client.post(
        f"/api/v1/categories/{cat_id}/attributes",
        json={"name": "size", "data_type": "text"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    attr_id = attr_resp.json()["id"]

    # Create product with value
    prod_resp = await client.post(
        "/api/v1/products",
        json={"name": "Sized Product", "category_id": cat_id, "pvp": "5.00", "custom_attributes": {"size": "M"}},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    prod_id = prod_resp.json()["id"]

    # Deactivate the attribute
    deact = await client.post(
        f"/api/v1/categories/{cat_id}/attributes/{attr_id}/deactivate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert deact.status_code == 200
    assert deact.json()["is_active"] is False

    # Product still has its value
    prod = await client.get(f"/api/v1/products/{prod_id}", headers={"Authorization": f"Bearer {operator_token}"})
    assert prod.json()["custom_attributes"]["size"] == "M"


@pytest.mark.asyncio
async def test_delete_attribute_blocked_when_in_use(client: AsyncClient, admin_token: str, operator_token: str):
    cat = await client.post("/api/v1/categories", json={"name": "Delete Blocked Cat"}, headers={"Authorization": f"Bearer {admin_token}"})
    cat_id = cat.json()["id"]
    attr_resp = await client.post(
        f"/api/v1/categories/{cat_id}/attributes",
        json={"name": "weight", "data_type": "decimal"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    attr_id = attr_resp.json()["id"]

    # Create product with value
    await client.post(
        "/api/v1/products",
        json={"name": "Heavy Product", "category_id": cat_id, "pvp": "5.00", "custom_attributes": {"weight": "1.5"}},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    # Delete should fail
    resp = await client.delete(
        f"/api/v1/categories/{cat_id}/attributes/{attr_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ATTRIBUTE_IN_USE"


@pytest.mark.asyncio
async def test_decimal_stock_min_rejected_in_integer_mode(client: AsyncClient, admin_token: str, operator_token: str, stock_mode_integer):
    cat = await client.post("/api/v1/categories", json={"name": "StockMode Cat"}, headers={"Authorization": f"Bearer {admin_token}"})
    cat_id = cat.json()["id"]

    resp = await client.post(
        "/api/v1/products",
        json={"name": "Decimal StockMin Product", "category_id": cat_id, "pvp": "5.00", "stock_minimo": "1.5"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_QUANTITY"


@pytest.mark.asyncio
async def test_decimal_stock_min_accepted_in_decimal_mode(client: AsyncClient, admin_token: str, operator_token: str, stock_mode_decimal):
    cat = await client.post("/api/v1/categories", json={"name": "DecimalMode Cat"}, headers={"Authorization": f"Bearer {admin_token}"})
    cat_id = cat.json()["id"]

    resp = await client.post(
        "/api/v1/products",
        json={"name": "Decimal StockMin OK", "category_id": cat_id, "pvp": "5.00", "stock_minimo": "1.5"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 201
    assert float(resp.json()["stock_minimo"]) == 1.5


@pytest.mark.asyncio
async def test_integer_stock_min_accepted_in_integer_mode(client: AsyncClient, admin_token: str, operator_token: str, stock_mode_integer):
    cat = await client.post("/api/v1/categories", json={"name": "IntMode Cat"}, headers={"Authorization": f"Bearer {admin_token}"})
    cat_id = cat.json()["id"]

    resp = await client.post(
        "/api/v1/products",
        json={"name": "Integer StockMin OK", "category_id": cat_id, "pvp": "5.00", "stock_minimo": "5"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_delete_category_with_products_blocks_then_cascades(
    client: AsyncClient, admin_token: str
):
    cat = await client.post(
        "/api/v1/categories",
        json={"name": "Cat With Products"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat_id = cat.json()["id"]
    prod = await client.post(
        "/api/v1/products",
        json={"name": "Prod In Cat", "category_id": cat_id, "pvp": "5.00"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    prod_id = prod.json()["id"]

    # Without delete_products -> blocked with descriptive 409
    blocked = await client.delete(
        f"/api/v1/categories/{cat_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "CATEGORY_HAS_PRODUCTS"
    assert "1" in blocked.json()["message"]

    # With delete_products=true -> category deleted and product deactivated
    ok = await client.delete(
        f"/api/v1/categories/{cat_id}?delete_products=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert ok.status_code == 204

    prod_after = await client.get(
        f"/api/v1/products/{prod_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert prod_after.json()["status"] == "inactive"


@pytest.mark.asyncio
async def test_attribute_blocked_when_descendant_has_it(
    client: AsyncClient, admin_token: str
):
    h = {"Authorization": f"Bearer {admin_token}"}
    parent = (await client.post("/api/v1/categories", json={"name": "Branch Parent"}, headers=h)).json()
    child = (await client.post("/api/v1/categories", json={"name": "Branch Child", "parent_id": parent["id"]}, headers=h)).json()

    # Attribute created on the CHILD
    r1 = await client.post(f"/api/v1/categories/{child['id']}/attributes", json={"name": "color", "data_type": "text"}, headers=h)
    assert r1.status_code == 201

    # Adding the same attribute to the PARENT must be blocked (would duplicate via inheritance)
    r2 = await client.post(f"/api/v1/categories/{parent['id']}/attributes", json={"name": "Color", "data_type": "text"}, headers=h)
    assert r2.status_code == 409
    assert r2.json()["code"] == "DUPLICATE_ATTRIBUTE_IN_DESCENDANTS"


@pytest.mark.asyncio
async def test_attribute_blocked_when_ancestor_has_it(
    client: AsyncClient, admin_token: str
):
    h = {"Authorization": f"Bearer {admin_token}"}
    parent = (await client.post("/api/v1/categories", json={"name": "Anc Parent"}, headers=h)).json()
    child = (await client.post("/api/v1/categories", json={"name": "Anc Child", "parent_id": parent["id"]}, headers=h)).json()

    await client.post(f"/api/v1/categories/{parent['id']}/attributes", json={"name": "brand", "data_type": "text"}, headers=h)

    # Adding the same attribute to the CHILD must be blocked (already inherited)
    r = await client.post(f"/api/v1/categories/{child['id']}/attributes", json={"name": "Brand", "data_type": "text"}, headers=h)
    assert r.status_code == 409
    assert r.json()["code"] == "DUPLICATE_ATTRIBUTE_IN_HIERARCHY"
