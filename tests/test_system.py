import pytest


@pytest.mark.asyncio
async def test_system_health_returns_server_host(client):
    resp = await client.get("/api/v1/system/health", headers={"Host": "192.168.0.26"})

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["server_ip"] == "192.168.0.26"
