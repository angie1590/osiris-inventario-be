"""Tests: categories and products catalog (task 13.4)"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient, Response


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
    parent = await client.post(
        "/api/v1/categories",
        json={"name": "Parent Cat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    parent_id = parent.json()["id"]

    child = await client.post(
        "/api/v1/categories",
        json={"name": "Child Cat", "parent_id": parent_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert child.status_code == 201
    assert child.json()["parent_id"] == parent_id


@pytest.mark.asyncio
async def test_delete_category_with_children_fails(
    client: AsyncClient, admin_token: str
):
    parent = await client.post(
        "/api/v1/categories",
        json={"name": "Parent With Child"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    parent_id = parent.json()["id"]
    await client.post(
        "/api/v1/categories",
        json={"name": "Child", "parent_id": parent_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    resp = await client.delete(
        f"/api/v1/categories/{parent_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "CATEGORY_HAS_CHILDREN"


@pytest.mark.asyncio
async def test_attribute_inheritance(client: AsyncClient, admin_token: str):
    parent = await client.post(
        "/api/v1/categories",
        json={"name": "Parent Attr"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    parent_id = parent.json()["id"]

    # Add attribute to parent
    await client.post(
        f"/api/v1/categories/{parent_id}/attributes",
        json={"name": "brand", "data_type": "text"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    child = await client.post(
        "/api/v1/categories",
        json={"name": "Child Attr", "parent_id": parent_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    child_id = child.json()["id"]

    attrs = await client.get(
        f"/api/v1/categories/{child_id}/attributes",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert attrs.status_code == 200
    names = [a["name"] for a in attrs.json()]
    assert "brand" in names
    # Check it's marked as inherited
    brand_attr = next(a for a in attrs.json() if a["name"] == "brand")
    assert brand_attr["inherited"] is True


@pytest.mark.asyncio
async def test_duplicate_attribute_in_hierarchy_fails(
    client: AsyncClient, admin_token: str
):
    parent = await client.post(
        "/api/v1/categories",
        json={"name": "Dup Parent"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    parent_id = parent.json()["id"]
    await client.post(
        f"/api/v1/categories/{parent_id}/attributes",
        json={"name": "color", "data_type": "text"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    child = await client.post(
        "/api/v1/categories",
        json={"name": "Dup Child", "parent_id": parent_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    child_id = child.json()["id"]

    resp = await client.post(
        f"/api/v1/categories/{child_id}/attributes",
        json={"name": "color", "data_type": "text"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "DUPLICATE_ATTRIBUTE_IN_HIERARCHY"


@pytest.mark.asyncio
async def test_product_stock_readonly(
    client: AsyncClient, operator_token: str, admin_token: str
):
    cat = await client.post(
        "/api/v1/categories",
        json={"name": "Stock Test Cat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
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
async def test_list_products_can_exclude_descendants(
    client: AsyncClient, admin_token: str
):
    h = {"Authorization": f"Bearer {admin_token}"}

    parent = await client.post(
        "/api/v1/categories", json={"name": "Parent Filter"}, headers=h
    )
    parent_id = parent.json()["id"]
    child = await client.post(
        "/api/v1/categories",
        json={"name": "Child Filter", "parent_id": parent_id},
        headers=h,
    )
    child_id = child.json()["id"]

    # Product exists only in child category.
    created = await client.post(
        "/api/v1/products",
        json={"name": "Only Child Product", "category_id": child_id, "pvp": "5.00"},
        headers=h,
    )
    assert created.status_code == 201
    child_product_id = created.json()["id"]

    # Backward-compatible default: include descendants when filtering by parent.
    with_descendants = await client.get(
        f"/api/v1/products?category_id={parent_id}",
        headers=h,
    )
    assert with_descendants.status_code == 200
    with_descendants_ids = {p["id"] for p in with_descendants.json()}
    assert child_product_id in with_descendants_ids

    # New behavior: only direct products in the selected category.
    direct_only = await client.get(
        f"/api/v1/products?category_id={parent_id}&include_descendants=false",
        headers=h,
    )
    assert direct_only.status_code == 200
    assert direct_only.json() == []


@pytest.mark.asyncio
async def test_create_product_with_required_attribute(
    client: AsyncClient, admin_token: str, operator_token: str
):
    cat = await client.post(
        "/api/v1/categories",
        json={"name": "Attr Required Cat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat_id = cat.json()["id"]
    await client.post(
        f"/api/v1/categories/{cat_id}/attributes",
        json={"name": "model", "data_type": "text", "is_required": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Without required attribute — should fail
    resp = await client.post(
        "/api/v1/products",
        json={"name": "Missing Attr Product", "category_id": cat_id, "pvp": "5.00"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_product_with_photo_url(
    client: AsyncClient, admin_token: str, operator_token: str
):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url):
            return Response(200, headers={"content-type": "image/png"})

        async def get(self, url, headers=None):
            return Response(200, headers={"content-type": "image/png"})

    import app.services.product_service as product_service_module

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(product_service_module.httpx, "AsyncClient", FakeAsyncClient)
    cat = await client.post(
        "/api/v1/categories",
        json={"name": "Photo Cat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat_id = cat.json()["id"]

    resp = await client.post(
        "/api/v1/products",
        json={
            "name": "Photo Product",
            "category_id": cat_id,
            "pvp": "5.00",
            "photo": "https://example.com/notebook.psd?fmt=png-alpha&wid=3350&hei=2357",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 201, resp.text
    assert (
        resp.json()["photo"]
        == "https://example.com/notebook.psd?fmt=png-alpha&wid=3350&hei=2357"
    )
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_reject_product_with_invalid_photo_url(
    client: AsyncClient, admin_token: str, operator_token: str
):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url):
            return Response(200, headers={"content-type": "text/html"})

        async def get(self, url, headers=None):
            return Response(200, headers={"content-type": "text/html"})

    import app.services.product_service as product_service_module

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(product_service_module.httpx, "AsyncClient", FakeAsyncClient)
    cat = await client.post(
        "/api/v1/categories",
        json={"name": "Invalid Photo Cat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat_id = cat.json()["id"]

    resp = await client.post(
        "/api/v1/products",
        json={
            "name": "Invalid Photo Product",
            "category_id": cat_id,
            "pvp": "5.00",
            "photo": "https://example.com/photo.jpg",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 422
    assert (
        resp.json()["errors"]["photo"]
        == "La URL debe corresponder a una imagen PNG, JPG, JPEG o HEIC."
    )
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_update_product_photo_url(
    client: AsyncClient, admin_token: str, operator_token: str
):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url):
            return Response(200, headers={"content-type": "image/jpeg"})

        async def get(self, url, headers=None):
            return Response(200, headers={"content-type": "image/jpeg"})

    import app.services.product_service as product_service_module

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(product_service_module.httpx, "AsyncClient", FakeAsyncClient)

    cat = await client.post(
        "/api/v1/categories",
        json={"name": "Photo Update Cat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat_id = cat.json()["id"]

    created = await client.post(
        "/api/v1/products",
        json={"name": "Photo Update Product", "category_id": cat_id, "pvp": "5.00"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]

    new_photo = "https://images.example.com/item?id=10"
    updated = await client.patch(
        f"/api/v1/products/{product_id}",
        json={"photo": new_photo},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["photo"] == new_photo

    fetched = await client.get(
        f"/api/v1/products/{product_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["photo"] == new_photo
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_update_product_photo_audit_includes_full_new_values(
    client: AsyncClient, admin_token: str, operator_token: str
):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url):
            return Response(200, headers={"content-type": "image/jpeg"})

        async def get(self, url, headers=None):
            return Response(200, headers={"content-type": "image/jpeg"})

    import app.services.product_service as product_service_module

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(product_service_module.httpx, "AsyncClient", FakeAsyncClient)

    cat = await client.post(
        "/api/v1/categories",
        json={"name": "Photo Audit Cat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat_id = cat.json()["id"]

    created = await client.post(
        "/api/v1/products",
        json={
            "name": "Photo Audit Product",
            "category_id": cat_id,
            "pvp": "18.00",
            "stock_minimo": "10",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert created.status_code == 201, created.text
    product = created.json()
    product_id = product["id"]

    new_photo = "https://images.example.com/audit-photo.jpg"
    updated = await client.patch(
        f"/api/v1/products/{product_id}",
        json={"photo": new_photo},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert updated.status_code == 200, updated.text

    now = datetime.now(timezone.utc)
    logs_resp = await client.get(
        "/api/v1/audit",
        params={
            "date_from": (now - timedelta(hours=1)).isoformat(),
            "date_to": (now + timedelta(minutes=5)).isoformat(),
            "action": "UPDATE",
            "entity_type": "product",
            "entity_id": str(product_id),
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert logs_resp.status_code == 200, logs_resp.text
    logs = logs_resp.json()
    assert len(logs) > 0
    log = logs[0]

    previous_values = log["previous_values"]
    new_values = log["new_values"]
    assert isinstance(previous_values, dict)
    assert isinstance(new_values, dict)

    assert "category_id" in previous_values
    assert "category_name" in previous_values
    assert "stock_minimo" in previous_values
    assert "photo" in previous_values
    assert "photos" in previous_values
    assert "description" in previous_values

    assert "category_id" in new_values
    assert "category_name" in new_values
    assert "stock_minimo" in new_values
    assert "photo" in new_values
    assert "photos" in new_values
    assert "description" in new_values
    assert new_values["photo"] == new_photo

    monkeypatch.undo()


@pytest.mark.asyncio
async def test_create_product_with_multiple_photos_and_cover(
    client: AsyncClient, admin_token: str, operator_token: str
):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def head(self, url):
            return Response(200, headers={"content-type": "image/jpeg"})

        async def get(self, url, headers=None):
            return Response(200, headers={"content-type": "image/jpeg"})

    import app.services.product_service as product_service_module

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(product_service_module.httpx, "AsyncClient", FakeAsyncClient)

    cat = await client.post(
        "/api/v1/categories",
        json={"name": "Gallery Cat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat_id = cat.json()["id"]

    photos = [
        {"url": "https://example.com/p1.jpg", "is_cover": False},
        {"url": "https://example.com/p2.jpg", "is_cover": True},
        {"url": "https://example.com/p3.jpg", "is_cover": False},
    ]
    created = await client.post(
        "/api/v1/products",
        json={
            "name": "Gallery Product",
            "category_id": cat_id,
            "pvp": "5.00",
            "photos": photos,
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["photo"] == "https://example.com/p2.jpg"
    assert len(data["photos"]) == 3
    assert sum(1 for item in data["photos"] if item["is_cover"]) == 1
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_reject_product_photos_with_multiple_covers(
    client: AsyncClient, admin_token: str, operator_token: str
):
    cat = await client.post(
        "/api/v1/categories",
        json={"name": "Gallery Invalid Cat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat_id = cat.json()["id"]

    resp = await client.post(
        "/api/v1/products",
        json={
            "name": "Invalid Gallery Product",
            "category_id": cat_id,
            "pvp": "5.00",
            "photos": [
                {"url": "https://example.com/a.jpg", "is_cover": True},
                {"url": "https://example.com/b.jpg", "is_cover": True},
            ],
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 422
    assert "Debe existir una sola imagen de portada" in resp.text


@pytest.mark.asyncio
async def test_attribute_type_change_migrates_values(
    client: AsyncClient, admin_token: str, operator_token: str
):
    h = {"Authorization": f"Bearer {admin_token}"}
    cat = (
        await client.post(
            "/api/v1/categories", json={"name": "TypeChange Cat"}, headers=h
        )
    ).json()
    attr = (
        await client.post(
            f"/api/v1/categories/{cat['id']}/attributes",
            json={"name": "color", "data_type": "text"},
            headers=h,
        )
    ).json()

    # castable value + non-castable value
    p_ok = (
        await client.post(
            "/api/v1/products",
            json={
                "name": "P num",
                "category_id": cat["id"],
                "pvp": "5.00",
                "custom_attributes": {"color": "16"},
            },
            headers=h,
        )
    ).json()
    p_bad = (
        await client.post(
            "/api/v1/products",
            json={
                "name": "P word",
                "category_id": cat["id"],
                "pvp": "5.00",
                "custom_attributes": {"color": "red"},
            },
            headers=h,
        )
    ).json()

    # text -> integer: "16" casts, "red" goes to remap (not blocked)
    resp = await client.patch(
        f"/api/v1/categories/{cat['id']}/attributes/{attr['id']}",
        json={"data_type": "integer"},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["remap_pending"] == 1

    # castable product got the integer value
    assert (await client.get(f"/api/v1/products/{p_ok['id']}", headers=h)).json()[
        "custom_attributes"
    ]["color"] == 16

    # pending list shows the non-castable one
    pending = (await client.get("/api/v1/attribute-remap/pending", headers=h)).json()
    assert pending["total"] == 1
    item = pending["groups"][0]["items"][0]
    assert item["product_id"] == p_bad["id"] and item["old_value"] == "red"

    # resolve it with a valid integer
    res = await client.post(
        "/api/v1/attribute-remap/resolve",
        json={"assignments": [{"id": item["id"], "value": 99}]},
        headers=h,
    )
    assert res.status_code == 200 and res.json()["resolved"] == 1
    assert (await client.get(f"/api/v1/products/{p_bad['id']}", headers=h)).json()[
        "custom_attributes"
    ]["color"] == 99
    assert (await client.get("/api/v1/attribute-remap/pending", headers=h)).json()[
        "total"
    ] == 0


@pytest.mark.asyncio
async def test_select_to_catalog_migration(client: AsyncClient, admin_token: str):
    h = {"Authorization": f"Bearer {admin_token}"}
    cat = (
        await client.post("/api/v1/categories", json={"name": "Sel2Cat"}, headers=h)
    ).json()
    attr = (
        await client.post(
            f"/api/v1/categories/{cat['id']}/attributes",
            json={
                "name": "Talla",
                "data_type": "select",
                "select_options": ["S", "M", "L"],
            },
            headers=h,
        )
    ).json()
    await client.post(
        "/api/v1/products",
        json={
            "name": "Shirt",
            "category_id": cat["id"],
            "pvp": "5.00",
            "custom_attributes": {"Talla": "M"},
        },
        headers=h,
    )

    # select -> catalog: creates a catalog from the options, existing value stays valid
    resp = await client.patch(
        f"/api/v1/categories/{cat['id']}/attributes/{attr['id']}",
        json={"data_type": "catalog"},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["remap_pending"] == 0
    assert resp.json()["data_type"] == "catalog"
    new_catalog_id = resp.json()["catalog_id"]
    assert new_catalog_id

    vals = (
        await client.get(f"/api/v1/catalogs/{new_catalog_id}/values", headers=h)
    ).json()
    assert {v["value"] for v in vals} == {"S", "M", "L"}


@pytest.mark.asyncio
async def test_deactivate_attribute_preserves_product_values(
    client: AsyncClient, admin_token: str, operator_token: str
):
    cat = await client.post(
        "/api/v1/categories",
        json={"name": "Deactivate Cat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
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
        json={
            "name": "Sized Product",
            "category_id": cat_id,
            "pvp": "5.00",
            "custom_attributes": {"size": "M"},
        },
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
    prod = await client.get(
        f"/api/v1/products/{prod_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert prod.json()["custom_attributes"]["size"] == "M"


@pytest.mark.asyncio
async def test_delete_attribute_blocked_when_in_use(
    client: AsyncClient, admin_token: str, operator_token: str
):
    cat = await client.post(
        "/api/v1/categories",
        json={"name": "Delete Blocked Cat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
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
        json={
            "name": "Heavy Product",
            "category_id": cat_id,
            "pvp": "5.00",
            "custom_attributes": {"weight": "1.5"},
        },
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
async def test_decimal_stock_min_rejected_in_integer_mode(
    client: AsyncClient, admin_token: str, operator_token: str, stock_mode_integer
):
    cat = await client.post(
        "/api/v1/categories",
        json={"name": "StockMode Cat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat_id = cat.json()["id"]

    resp = await client.post(
        "/api/v1/products",
        json={
            "name": "Decimal StockMin Product",
            "category_id": cat_id,
            "pvp": "5.00",
            "stock_minimo": "1.5",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_QUANTITY"


@pytest.mark.asyncio
async def test_decimal_stock_min_accepted_in_decimal_mode(
    client: AsyncClient, admin_token: str, operator_token: str, stock_mode_decimal
):
    cat = await client.post(
        "/api/v1/categories",
        json={"name": "DecimalMode Cat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat_id = cat.json()["id"]

    resp = await client.post(
        "/api/v1/products",
        json={
            "name": "Decimal StockMin OK",
            "category_id": cat_id,
            "pvp": "5.00",
            "stock_minimo": "1.5",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 201
    assert float(resp.json()["stock_minimo"]) == 1.5


@pytest.mark.asyncio
async def test_integer_stock_min_accepted_in_integer_mode(
    client: AsyncClient, admin_token: str, operator_token: str, stock_mode_integer
):
    cat = await client.post(
        "/api/v1/categories",
        json={"name": "IntMode Cat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat_id = cat.json()["id"]

    resp = await client.post(
        "/api/v1/products",
        json={
            "name": "Integer StockMin OK",
            "category_id": cat_id,
            "pvp": "5.00",
            "stock_minimo": "5",
        },
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
    parent = (
        await client.post(
            "/api/v1/categories", json={"name": "Branch Parent"}, headers=h
        )
    ).json()
    child = (
        await client.post(
            "/api/v1/categories",
            json={"name": "Branch Child", "parent_id": parent["id"]},
            headers=h,
        )
    ).json()

    # Attribute created on the CHILD
    r1 = await client.post(
        f"/api/v1/categories/{child['id']}/attributes",
        json={"name": "color", "data_type": "text"},
        headers=h,
    )
    assert r1.status_code == 201

    # Adding the same attribute to the PARENT must be blocked (would duplicate via inheritance)
    r2 = await client.post(
        f"/api/v1/categories/{parent['id']}/attributes",
        json={"name": "Color", "data_type": "text"},
        headers=h,
    )
    assert r2.status_code == 409
    assert r2.json()["code"] == "DUPLICATE_ATTRIBUTE_IN_DESCENDANTS"


@pytest.mark.asyncio
async def test_attribute_blocked_when_ancestor_has_it(
    client: AsyncClient, admin_token: str
):
    h = {"Authorization": f"Bearer {admin_token}"}
    parent = (
        await client.post("/api/v1/categories", json={"name": "Anc Parent"}, headers=h)
    ).json()
    child = (
        await client.post(
            "/api/v1/categories",
            json={"name": "Anc Child", "parent_id": parent["id"]},
            headers=h,
        )
    ).json()

    await client.post(
        f"/api/v1/categories/{parent['id']}/attributes",
        json={"name": "brand", "data_type": "text"},
        headers=h,
    )

    # Adding the same attribute to the CHILD must be blocked (already inherited)
    r = await client.post(
        f"/api/v1/categories/{child['id']}/attributes",
        json={"name": "Brand", "data_type": "text"},
        headers=h,
    )
    assert r.status_code == 409
    assert r.json()["code"] == "DUPLICATE_ATTRIBUTE_IN_HIERARCHY"


@pytest.mark.asyncio
async def test_delete_category_blocked_if_product_has_stock(
    client: AsyncClient, admin_token: str, db_session
):
    from sqlalchemy import text

    h = {"Authorization": f"Bearer {admin_token}"}
    cat = (
        await client.post(
            "/api/v1/categories", json={"name": "Cat With Stock"}, headers=h
        )
    ).json()
    prod = (
        await client.post(
            "/api/v1/products",
            json={"name": "Prod With Stock", "category_id": cat["id"], "pvp": "5.00"},
            headers=h,
        )
    ).json()
    # Give the product stock via the protected DB function (bypasses the guard trigger)
    await db_session.execute(
        text("SELECT update_product_stock(:pid, :d)"), {"pid": prod["id"], "d": 5}
    )
    await db_session.commit()

    # Even with delete_products=true, a category with stocked products cannot be deleted
    resp = await client.delete(
        f"/api/v1/categories/{cat['id']}?delete_products=true", headers=h
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "CATEGORY_HAS_PRODUCTS_WITH_STOCK"


@pytest.mark.asyncio
async def test_reactivate_product_requires_category_if_deleted(
    client: AsyncClient, admin_token: str
):
    h = {"Authorization": f"Bearer {admin_token}"}
    cat_a = (
        await client.post(
            "/api/v1/categories", json={"name": "Reactivate Cat A"}, headers=h
        )
    ).json()
    prod = (
        await client.post(
            "/api/v1/products",
            json={"name": "Reactivate Prod", "category_id": cat_a["id"], "pvp": "5.00"},
            headers=h,
        )
    ).json()

    # Delete category A with cascade (no stock) -> product becomes inactive, category gone
    r = await client.delete(
        f"/api/v1/categories/{cat_a['id']}?delete_products=true", headers=h
    )
    assert r.status_code == 204

    # Reactivating without a category must be blocked (dangling reference)
    bad = await client.patch(
        f"/api/v1/products/{prod['id']}/status", json={"status": "active"}, headers=h
    )
    assert bad.status_code == 409
    assert bad.json()["code"] == "PRODUCT_CATEGORY_INACTIVE"

    # Reactivating with a valid active category succeeds and reassigns it
    cat_b = (
        await client.post(
            "/api/v1/categories", json={"name": "Reactivate Cat B"}, headers=h
        )
    ).json()
    ok = await client.patch(
        f"/api/v1/products/{prod['id']}/status",
        json={"status": "active", "category_id": cat_b["id"]},
        headers=h,
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["status"] == "active"
    assert body["category_id"] == cat_b["id"]


@pytest.mark.asyncio
async def test_update_product_can_change_category(
    client: AsyncClient, admin_token: str
):
    h = {"Authorization": f"Bearer {admin_token}"}
    cat1 = (
        await client.post("/api/v1/categories", json={"name": "Move Cat 1"}, headers=h)
    ).json()
    cat2 = (
        await client.post("/api/v1/categories", json={"name": "Move Cat 2"}, headers=h)
    ).json()
    prod = (
        await client.post(
            "/api/v1/products",
            json={"name": "Movable Prod", "category_id": cat1["id"], "pvp": "5.00"},
            headers=h,
        )
    ).json()

    upd = await client.patch(
        f"/api/v1/products/{prod['id']}", json={"category_id": cat2["id"]}, headers=h
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["category_id"] == cat2["id"]

    # Reassigning to a non-existent/inactive category is rejected
    bad = await client.patch(
        f"/api/v1/products/{prod['id']}", json={"category_id": 999999}, headers=h
    )
    assert bad.status_code == 404


@pytest.mark.asyncio
async def test_product_cannot_be_assigned_to_non_leaf_category(
    client: AsyncClient, admin_token: str
):
    h = {"Authorization": f"Bearer {admin_token}"}
    parent = (
        await client.post("/api/v1/categories", json={"name": "Leaf Parent"}, headers=h)
    ).json()
    await client.post(
        "/api/v1/categories",
        json={"name": "Leaf Child", "parent_id": parent["id"]},
        headers=h,
    )

    # parent now has a child -> not a leaf -> products rejected
    r = await client.post(
        "/api/v1/products",
        json={"name": "Bad Cat Prod", "category_id": parent["id"], "pvp": "5.00"},
        headers=h,
    )
    assert r.status_code == 409
    assert r.json()["code"] == "CATEGORY_NOT_LEAF"


@pytest.mark.asyncio
async def test_recategorization_flow(client: AsyncClient, admin_token: str):
    h = {"Authorization": f"Bearer {admin_token}"}
    # Parent with a directly-assigned product
    parent = (
        await client.post(
            "/api/v1/categories", json={"name": "Recat Parent"}, headers=h
        )
    ).json()
    prod = (
        await client.post(
            "/api/v1/products",
            json={"name": "Recat Prod", "category_id": parent["id"], "pvp": "5.00"},
            headers=h,
        )
    ).json()

    # Adding a subcategory to the parent should spawn a "Sin clasificar" default
    # and move the product there.
    child = (
        await client.post(
            "/api/v1/categories",
            json={"name": "Recat Child", "parent_id": parent["id"]},
            headers=h,
        )
    ).json()

    cats = (await client.get("/api/v1/categories", headers=h)).json()
    default = next(
        (c for c in cats if c.get("is_default") and c["parent_id"] == parent["id"]),
        None,
    )
    assert default is not None, "default bucket not created"
    assert default["name"] == "Sin clasificar"

    moved = (await client.get(f"/api/v1/products/{prod['id']}", headers=h)).json()
    assert moved["category_id"] == default["id"]

    # New products cannot be assigned to the default bucket
    bad = await client.post(
        "/api/v1/products",
        json={"name": "Nope", "category_id": default["id"], "pvp": "1.00"},
        headers=h,
    )
    assert bad.status_code == 409 and bad.json()["code"] == "CATEGORY_IS_DEFAULT"

    # Pending list shows the product
    pending = (
        await client.get("/api/v1/products/pending-recategorization", headers=h)
    ).json()
    assert any(p["id"] == prod["id"] for p in pending)

    # Bulk recategorize to the real child leaf
    res = await client.post(
        "/api/v1/products/recategorize",
        json={"assignments": [{"product_id": prod["id"], "category_id": child["id"]}]},
        headers=h,
    )
    assert res.status_code == 200, res.text
    assert res.json()["recategorized"] == 1

    # Product moved + default bucket auto-deleted
    after = (await client.get(f"/api/v1/products/{prod['id']}", headers=h)).json()
    assert after["category_id"] == child["id"]
    cats2 = (await client.get("/api/v1/categories", headers=h)).json()
    assert not any(
        c["id"] == default["id"] for c in cats2
    ), "default bucket should be gone"
    pending2 = (
        await client.get("/api/v1/products/pending-recategorization", headers=h)
    ).json()
    assert not any(p["id"] == prod["id"] for p in pending2)


@pytest.mark.asyncio
async def test_numeric_attribute_rejects_negative_unless_allowed(
    client: AsyncClient, admin_token: str
):
    h = {"Authorization": f"Bearer {admin_token}"}
    cat = (
        await client.post("/api/v1/categories", json={"name": "NegCat"}, headers=h)
    ).json()
    # default: no negatives
    await client.post(
        f"/api/v1/categories/{cat['id']}/attributes",
        json={"name": "Peso", "data_type": "decimal"},
        headers=h,
    )
    # allow_negative: allowed
    await client.post(
        f"/api/v1/categories/{cat['id']}/attributes",
        json={"name": "Temperatura", "data_type": "decimal", "allow_negative": True},
        headers=h,
    )

    bad = await client.post(
        "/api/v1/products",
        json={
            "name": "P",
            "category_id": cat["id"],
            "pvp": "5.00",
            "custom_attributes": {"Peso": -1},
        },
        headers=h,
    )
    assert bad.status_code == 422 and bad.json()["code"] == "INVALID_ATTRIBUTE_VALUE"

    ok = await client.post(
        "/api/v1/products",
        json={
            "name": "P2",
            "category_id": cat["id"],
            "pvp": "5.00",
            "custom_attributes": {"Peso": 2, "Temperatura": -10},
        },
        headers=h,
    )
    assert ok.status_code == 201, ok.text


@pytest.mark.asyncio
async def test_stock_minimo_zero_is_not_low_stock(
    client: AsyncClient, admin_token: str
):
    h = {"Authorization": f"Bearer {admin_token}"}
    cat = (
        await client.post("/api/v1/categories", json={"name": "LowStockCat"}, headers=h)
    ).json()
    # stock_minimo defaults to 0; stock_actual is 0 -> NOT low stock
    p = (
        await client.post(
            "/api/v1/products",
            json={"name": "ZeroMin", "category_id": cat["id"], "pvp": "5.00"},
            headers=h,
        )
    ).json()
    assert float(p["stock_minimo"]) == 0
    fetched = (await client.get(f"/api/v1/products/{p['id']}", headers=h)).json()
    assert fetched["bajo_stock"] is False


@pytest.mark.asyncio
async def test_isbn_required_param(client: AsyncClient, admin_token: str, db_session):
    from app.models.system_param import SystemParam
    from sqlalchemy import select

    h = {"Authorization": f"Bearer {admin_token}"}
    cat = (
        await client.post("/api/v1/categories", json={"name": "IsbnCat"}, headers=h)
    ).json()
    # enable barcode_required
    param = (
        await db_session.execute(
            select(SystemParam).where(SystemParam.key == "barcode_required")
        )
    ).scalar_one_or_none()
    if param:
        param.value = "true"
    else:
        db_session.add(
            SystemParam(key="barcode_required", value="true", description="x")
        )
    await db_session.commit()

    bad = await client.post(
        "/api/v1/products",
        json={"name": "NoIsbn", "category_id": cat["id"], "pvp": "5.00"},
        headers=h,
    )
    assert bad.status_code == 422 and bad.json()["code"] == "ISBN_REQUIRED"
    ok = await client.post(
        "/api/v1/products",
        json={
            "name": "WithIsbn",
            "category_id": cat["id"],
            "pvp": "5.00",
            "isbn": "9780000000000",
        },
        headers=h,
    )
    assert ok.status_code == 201, ok.text
