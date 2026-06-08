"""Tests: Kardex PEPS and Weighted Average (tasks 13.7, 13.8)"""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.core.config import settings

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.system_param import SystemParam


@pytest_asyncio.fixture(autouse=True)
async def _company(company_config):
    """All kardex tests require a configured company."""
    return company_config


async def _ensure_kardex_method(db: AsyncSession, method: str) -> None:
    result = await db.execute(
        select(SystemParam).where(SystemParam.key == "kardex_method")
    )
    param = result.scalar_one_or_none()
    if param:
        param.value = method
    else:
        db.add(SystemParam(key="kardex_method", value=method, description="Test"))
    await db.commit()


async def _create_product_for_kardex(client, admin_token, operator_token, name):
    cat = await client.post(
        "/api/v1/categories",
        json={"name": f"KardexCat {name}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat_id = cat.json()["id"]
    prod = await client.post(
        "/api/v1/products",
        json={"name": name, "category_id": cat_id, "pvp": "0"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    return prod.json()["id"]


@pytest.mark.asyncio
async def test_kardex_peps_single_lot(
    client: AsyncClient, admin_token: str, operator_token: str, db_session: AsyncSession
):
    await _ensure_kardex_method(db_session, "PEPS")
    prod_id = await _create_product_for_kardex(
        client, admin_token, operator_token, "PEPS Single Lot"
    )

    await client.post(
        "/api/v1/inventory/ingresos",
        json={
            "lines": [{"product_id": prod_id, "quantity": "10", "unit_cost": "5.00"}]
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    await client.post(
        "/api/v1/inventory/egresos",
        json={"lines": [{"product_id": prod_id, "quantity": "3"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    kardex_resp = await client.get(
        f"/api/v1/kardex/{prod_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert kardex_resp.status_code == 200
    data = kardex_resp.json()
    assert float(data["closing_balance_quantity"]) == 7.0

    # Check cost of output entry
    out_entries = [e for e in data["entries"] if float(e["quantity_out"]) > 0]
    assert len(out_entries) > 0
    assert float(out_entries[0]["cost_out"]) == 5.0


@pytest.mark.asyncio
async def test_kardex_peps_multiple_lots(
    client: AsyncClient, admin_token: str, operator_token: str, db_session: AsyncSession
):
    await _ensure_kardex_method(db_session, "PEPS")
    prod_id = await _create_product_for_kardex(
        client, admin_token, operator_token, "PEPS Multi Lot"
    )

    # Two ingresos with different costs
    await client.post(
        "/api/v1/inventory/ingresos",
        json={
            "lines": [{"product_id": prod_id, "quantity": "5", "unit_cost": "10.00"}]
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    await client.post(
        "/api/v1/inventory/ingresos",
        json={
            "lines": [{"product_id": prod_id, "quantity": "5", "unit_cost": "20.00"}]
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    # Egress of 7 — should consume first lot (5) + 2 from second (at 20.00)
    await client.post(
        "/api/v1/inventory/egresos",
        json={"lines": [{"product_id": prod_id, "quantity": "7"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    kardex_resp = await client.get(
        f"/api/v1/kardex/{prod_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    data = kardex_resp.json()
    assert float(data["closing_balance_quantity"]) == 3.0


@pytest.mark.asyncio
async def test_kardex_weighted_average(
    client: AsyncClient, admin_token: str, operator_token: str, db_session: AsyncSession
):
    await _ensure_kardex_method(db_session, "WEIGHTED_AVERAGE")
    prod_id = await _create_product_for_kardex(
        client, admin_token, operator_token, "WA Test"
    )

    # First purchase: 10 units at 10.00 → avg = 10.00
    await client.post(
        "/api/v1/inventory/ingresos",
        json={
            "lines": [{"product_id": prod_id, "quantity": "10", "unit_cost": "10.00"}]
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    # Second purchase: 10 units at 20.00 → avg = (100 + 200) / 20 = 15.00
    await client.post(
        "/api/v1/inventory/ingresos",
        json={
            "lines": [{"product_id": prod_id, "quantity": "10", "unit_cost": "20.00"}]
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    # Egress of 5 at weighted avg 15.00
    await client.post(
        "/api/v1/inventory/egresos",
        json={"lines": [{"product_id": prod_id, "quantity": "5"}]},
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    kardex_resp = await client.get(
        f"/api/v1/kardex/{prod_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    data = kardex_resp.json()
    assert "weighted_avg_cost" in data
    out_entries = [e for e in data["entries"] if float(e["quantity_out"]) > 0]
    assert abs(float(out_entries[0]["cost_out"]) - 15.0) < 0.01


@pytest.mark.asyncio
async def test_kardex_date_only_filter_includes_full_day(
    client: AsyncClient,
    admin_token: str,
    operator_token: str,
    db_session: AsyncSession,
):
    await _ensure_kardex_method(db_session, "PEPS")
    prod_id = await _create_product_for_kardex(
        client, admin_token, operator_token, "Date-only Kardex"
    )

    await client.post(
        "/api/v1/inventory/ingresos",
        json={
            "lines": [{"product_id": prod_id, "quantity": "2", "unit_cost": "10.00"}]
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )

    full_resp = await client.get(
        f"/api/v1/kardex/{prod_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert full_resp.status_code == 200
    full_data = full_resp.json()
    assert len(full_data["entries"]) >= 1

    # Use the movement's APP_TIMEZONE local date (the API filters date-only
    # bounds by local day), so this is robust to the UTC/local-day boundary.
    created_utc = datetime.fromisoformat(
        full_data["entries"][0]["created_at"].replace("Z", "+00:00")
    )
    movement_date = created_utc.astimezone(ZoneInfo(settings.APP_TIMEZONE)).date().isoformat()
    filtered_resp = await client.get(
        f"/api/v1/kardex/{prod_id}",
        params={"date_from": movement_date, "date_to": movement_date},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert filtered_resp.status_code == 200
    filtered_data = filtered_resp.json()
    assert len(filtered_data["entries"]) >= 1
