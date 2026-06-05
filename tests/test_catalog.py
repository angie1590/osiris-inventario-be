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
    assert resp.json()["detail"]["code"] == "CATEGORY_HAS_CHILDREN"


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
    assert resp.json()["detail"]["code"] == "DUPLICATE_ATTRIBUTE_IN_HIERARCHY"


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
