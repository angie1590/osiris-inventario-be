"""Tests: master catalogs + catalog-backed attributes."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_catalog_crud_and_normalized_uniqueness(client: AsyncClient, admin_token: str):
    h = {"Authorization": f"Bearer {admin_token}"}
    cat = (await client.post("/api/v1/catalogs", json={"name": "Marcas"}, headers=h)).json()
    assert cat["id"]

    r1 = await client.post(f"/api/v1/catalogs/{cat['id']}/values", json={"value": "Lenovo"}, headers=h)
    assert r1.status_code == 201
    # Normalized duplicate (case + spaces) is rejected
    r2 = await client.post(f"/api/v1/catalogs/{cat['id']}/values", json={"value": "  LENOVO "}, headers=h)
    assert r2.status_code == 409 and r2.json()["code"] == "CATALOG_VALUE_EXISTS"

    listed = (await client.get("/api/v1/catalogs", headers=h)).json()
    marcas = next(c for c in listed if c["id"] == cat["id"])
    assert marcas["value_count"] == 1


@pytest.mark.asyncio
async def test_operator_cannot_manage_catalogs(client: AsyncClient, operator_token: str, supervisor_token: str):
    op = {"Authorization": f"Bearer {operator_token}"}
    assert (await client.get("/api/v1/catalogs", headers=op)).status_code == 200  # read ok
    blocked = await client.post("/api/v1/catalogs", json={"name": "X"}, headers=op)
    assert blocked.status_code == 403
    # supervisor can create
    sup = {"Authorization": f"Bearer {supervisor_token}"}
    assert (await client.post("/api/v1/catalogs", json={"name": "SupCat"}, headers=sup)).status_code == 201


@pytest.mark.asyncio
async def test_catalog_attribute_validates_product_values(client: AsyncClient, admin_token: str):
    h = {"Authorization": f"Bearer {admin_token}"}
    catalog = (await client.post("/api/v1/catalogs", json={"name": "MarcasP"}, headers=h)).json()
    await client.post(f"/api/v1/catalogs/{catalog['id']}/values", json={"value": "Lenovo"}, headers=h)

    category = (await client.post("/api/v1/categories", json={"name": "CatalogCat"}, headers=h)).json()
    attr = await client.post(
        f"/api/v1/categories/{category['id']}/attributes",
        json={"name": "Marca", "data_type": "catalog", "catalog_id": catalog["id"], "is_required": True},
        headers=h,
    )
    assert attr.status_code == 201, attr.text
    assert attr.json()["catalog_id"] == catalog["id"]

    # Valid catalog value
    ok = await client.post(
        "/api/v1/products",
        json={"name": "P1", "category_id": category["id"], "pvp": "5.00", "custom_attributes": {"Marca": "Lenovo"}},
        headers=h,
    )
    assert ok.status_code == 201, ok.text
    # Value not in the catalog is rejected
    bad = await client.post(
        "/api/v1/products",
        json={"name": "P2", "category_id": category["id"], "pvp": "5.00", "custom_attributes": {"Marca": "Acer"}},
        headers=h,
    )
    assert bad.status_code == 422 and bad.json()["code"] == "INVALID_ATTRIBUTE_VALUE"

    # Catalog in use by an attribute cannot be deleted
    blocked = await client.delete(f"/api/v1/catalogs/{catalog['id']}", headers=h)
    assert blocked.status_code == 409 and blocked.json()["code"] == "CATALOG_IN_USE"


@pytest.mark.asyncio
async def test_catalog_attribute_auto_creates_plural_catalog(client: AsyncClient, admin_token: str):
    h = {"Authorization": f"Bearer {admin_token}"}
    category = (await client.post("/api/v1/categories", json={"name": "AutoCatCat"}, headers=h)).json()
    # No catalog_id -> a catalog "Marcas" (plural of "Marca") is auto-created and linked.
    r = await client.post(
        f"/api/v1/categories/{category['id']}/attributes",
        json={"name": "Marca", "data_type": "catalog"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    catalog_id = r.json()["catalog_id"]
    assert catalog_id
    catalogs = (await client.get("/api/v1/catalogs", headers=h)).json()
    created = next(c for c in catalogs if c["id"] == catalog_id)
    assert created["name"] == "Marcas"

    # A second 'Marca' attribute (different branch) reuses the same "Marcas" catalog.
    cat2 = (await client.post("/api/v1/categories", json={"name": "AutoCatCat2"}, headers=h)).json()
    r2 = await client.post(
        f"/api/v1/categories/{cat2['id']}/attributes",
        json={"name": "Marca", "data_type": "catalog"},
        headers=h,
    )
    assert r2.status_code == 201 and r2.json()["catalog_id"] == catalog_id
