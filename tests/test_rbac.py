"""Tests: RBAC (task 13.3)"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_can_list_users(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_operator_cannot_list_users(client: AsyncClient, operator_token: str):
    resp = await client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {operator_token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_supervisor_cannot_list_users(client: AsyncClient, supervisor_token: str):
    resp = await client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {supervisor_token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(client: AsyncClient):
    resp = await client.get("/api/v1/products")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_operator_can_create_product(client: AsyncClient, admin_token: str, operator_token: str, db_session):
    # Category is created by an admin (operators are read-only on categories).
    cat_resp = await client.post(
        "/api/v1/categories",
        json={"name": "Test Cat RBAC"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]

    resp = await client.post(
        "/api/v1/products",
        json={"name": "RBAC Test Product", "category_id": cat_id, "pvp": "10.00"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_operator_cannot_manage_categories_or_attributes(
    client: AsyncClient, admin_token: str, operator_token: str
):
    op = {"Authorization": f"Bearer {operator_token}"}
    # Operator can READ categories
    assert (await client.get("/api/v1/categories", headers=op)).status_code == 200
    # ...but cannot create one
    r = await client.post("/api/v1/categories", json={"name": "Op Cat"}, headers=op)
    assert r.status_code == 403 and r.json()["code"] == "INSUFFICIENT_PERMISSIONS"

    # Admin creates a category; operator cannot add an attribute to it
    cat = await client.post("/api/v1/categories", json={"name": "Perm Cat"}, headers={"Authorization": f"Bearer {admin_token}"})
    cat_id = cat.json()["id"]
    ra = await client.post(f"/api/v1/categories/{cat_id}/attributes", json={"name": "Marca", "data_type": "text"}, headers=op)
    assert ra.status_code == 403 and ra.json()["code"] == "INSUFFICIENT_PERMISSIONS"


@pytest.mark.asyncio
async def test_supervisor_can_manage_categories_and_attributes(
    client: AsyncClient, supervisor_token: str
):
    sup = {"Authorization": f"Bearer {supervisor_token}"}
    cat = await client.post("/api/v1/categories", json={"name": "Sup Cat"}, headers=sup)
    assert cat.status_code == 201, cat.text
    cat_id = cat.json()["id"]
    attr = await client.post(f"/api/v1/categories/{cat_id}/attributes", json={"name": "Color", "data_type": "text"}, headers=sup)
    assert attr.status_code == 201, attr.text


@pytest.mark.asyncio
async def test_supervisor_cannot_create_product(client: AsyncClient, supervisor_token: str):
    resp = await client.post(
        "/api/v1/products",
        json={"name": "Should Fail", "category_id": 1, "pvp": "10.00"},
        headers={"Authorization": f"Bearer {supervisor_token}"},
    )
    assert resp.status_code == 403
