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
async def test_operator_can_create_product(client: AsyncClient, operator_token: str, db_session):
    # First create a category
    cat_resp = await client.post(
        "/api/v1/categories",
        json={"name": "Test Cat RBAC"},
        headers={"Authorization": f"Bearer {operator_token}"},
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
async def test_supervisor_cannot_create_product(client: AsyncClient, supervisor_token: str):
    resp = await client.post(
        "/api/v1/products",
        json={"name": "Should Fail", "category_id": 1, "pvp": "10.00"},
        headers={"Authorization": f"Bearer {supervisor_token}"},
    )
    assert resp.status_code == 403
