"""Tests: audit log (task 13.10)"""

from datetime import datetime, timezone, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_audit_logged_on_login(client: AsyncClient, admin_token: str):
    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(minutes=5)).isoformat()
    date_to = (now + timedelta(minutes=1)).isoformat()

    resp = await client.get(
        "/api/v1/audit",
        params={"date_from": date_from, "date_to": date_to, "action": "LOGIN"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    logs = resp.json()
    assert any(log["action"] == "LOGIN" for log in logs)


@pytest.mark.asyncio
async def test_audit_requires_date_range(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/api/v1/audit", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_audit_export_excel(client: AsyncClient, admin_token: str):
    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=1)).isoformat()
    date_to = now.isoformat()

    resp = await client.get(
        "/api/v1/audit/export",
        params={"date_from": date_from, "date_to": date_to, "format": "excel"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_audit_export_range_too_large(client: AsyncClient, admin_token: str):
    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=100)).isoformat()
    date_to = now.isoformat()

    resp = await client.get(
        "/api/v1/audit/export",
        params={"date_from": date_from, "date_to": date_to},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "DATE_RANGE_TOO_LARGE"


@pytest.mark.asyncio
async def test_audit_export_uses_configured_max_range(
    client: AsyncClient, admin_token: str, db_session: AsyncSession
):
    from app.models.system_param import SystemParam

    db_session.add(
        SystemParam(
            key="max_export_date_range_days",
            value="1",
            description="test",
        )
    )
    await db_session.commit()

    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=2)).isoformat()
    date_to = now.isoformat()

    resp = await client.get(
        "/api/v1/audit/export",
        params={"date_from": date_from, "date_to": date_to},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "DATE_RANGE_TOO_LARGE"


@pytest.mark.asyncio
async def test_operator_cannot_access_audit(client: AsyncClient, operator_token: str):
    now = datetime.now(timezone.utc)
    resp = await client.get(
        "/api/v1/audit",
        params={
            "date_from": (now - timedelta(hours=1)).isoformat(),
            "date_to": now.isoformat(),
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 403
