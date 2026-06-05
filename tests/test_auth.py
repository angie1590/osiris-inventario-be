"""Tests: authentication (task 13.2)"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, admin_token: str):
    assert admin_token is not None
    assert len(admin_token) > 10


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, db_session: AsyncSession):
    from app.core.security import hash_password
    from app.models.user import User
    from app.models.enums import UserRole

    user = User(
        username="wrong_pass_user", hashed_password=hash_password("correct"),
        full_name="Test", role=UserRole.operator, is_active=True, must_change_password=False,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", data={"username": "wrong_pass_user", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_unknown_user(client: AsyncClient):
    resp = await client.post("/api/v1/auth/login", data={"username": "nonexistent", "password": "whatever"})
    assert resp.status_code == 401
    # Same message as wrong password (no user enumeration)
    assert resp.json()["detail"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_inactive_user(client: AsyncClient, db_session: AsyncSession):
    from app.core.security import hash_password
    from app.models.user import User
    from app.models.enums import UserRole

    user = User(
        username="inactive_user", hashed_password=hash_password("pass123"),
        full_name="Inactive", role=UserRole.operator, is_active=False, must_change_password=False,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", data={"username": "inactive_user", "password": "pass123"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, admin_token: str):
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "admin"
    assert "require_password_change" in data


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, admin_token: str):
    resp = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200

    # Token should now be revoked
    resp2 = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_must_change_password_flag(client: AsyncClient, db_session: AsyncSession):
    from app.core.security import hash_password
    from app.models.user import User
    from app.models.enums import UserRole

    user = User(
        username="new_user_password", hashed_password=hash_password("pass123"),
        full_name="New User", role=UserRole.operator, is_active=True, must_change_password=True,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", data={"username": "new_user_password", "password": "pass123"})
    assert resp.status_code == 200
    assert resp.json()["require_password_change"] is True
