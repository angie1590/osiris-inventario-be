from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.inventory import _parse_document_date_bound
from app.models.enums import DocumentStatus, DocumentType
from app.models.inventory import InventoryDocument
from app.models.user import User


def test_document_date_bounds_cover_full_business_day():
    date_from = _parse_document_date_bound("2026-07-31", end_of_day=False)
    date_to = _parse_document_date_bound("2026-07-31", end_of_day=True)

    assert date_from == datetime(2026, 7, 31, 5, 0, tzinfo=timezone.utc)
    assert date_to is not None
    assert date_to.date().isoformat() == "2026-08-01"
    assert datetime(2026, 8, 1, 0, 30, tzinfo=timezone.utc) <= date_to


@pytest.mark.asyncio
async def test_list_ingresos_includes_end_of_local_day(
    client: AsyncClient, admin_token: str, db_session: AsyncSession
):
    user = await db_session.scalar(select(User).where(User.username == "test_admin"))
    db_session.add(
        InventoryDocument(
            number="IN-2026-000001",
            doc_type=DocumentType.IN,
            status=DocumentStatus.approved,
            ingreso_type="initial_inventory",
            created_by=user.id,
            created_at=datetime(2026, 8, 1, 0, 30, tzinfo=timezone.utc),
        )
    )
    await db_session.commit()

    response = await client.get(
        "/api/v1/inventory/ingresos",
        params={"date_from": "2026-07-31", "date_to": "2026-07-31"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert [document["number"] for document in response.json()] == ["IN-2026-000001"]


@pytest.mark.asyncio
async def test_list_ingresos_page_returns_total_and_second_page(
    client: AsyncClient, admin_token: str, db_session: AsyncSession
):
    user = await db_session.scalar(select(User).where(User.username == "test_admin"))
    db_session.add_all(
        [
            InventoryDocument(
                number=f"IN-2026-{index:06d}",
                doc_type=DocumentType.IN,
                status=DocumentStatus.approved,
                ingreso_type="initial_inventory",
                created_by=user.id,
            )
            for index in range(1, 13)
        ]
    )
    await db_session.commit()

    response = await client.get(
        "/api/v1/inventory/ingresos/page",
        params={"page": 2, "page_size": 10},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 12
    assert body["total_pages"] == 2
    assert body["page"] == 2
    assert len(body["items"]) == 2