import os
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.models.category import Category
from app.models.enums import DocumentStatus, ProductStatus, UserRole
from app.models.inventory import InventoryDocument, InventoryDocumentLine, InventorySupplier
from app.models.kardex import InventoryLot, KardexEntry
from app.models.product import Product
from app.models.user import User
from scripts.migrate_legacy_dump import (
    apply_plan,
    build_plan,
    initial_unit_cost,
)
from tests.conftest import TestSessionLocal


def _product(product_id, barcode, pvp, quantity, category_id=1, status="\x01"):
    return (
        product_id,
        f"PRODUCTO {product_id}",
        barcode,
        "\x01",
        None,
        None,
        "2020-01-01 00:00:00",
        None,
        None,
        None,
        pvp,
        None,
        status,
        quantity,
        1,
        category_id,
        1,
        1,
        None,
    )


def _sql_value(value):
    if value is None:
        return "NULL"
    if isinstance(value, str):
        return "'" + value.replace("'", "\\'") + "'"
    return str(value)


def _insert(table, rows):
    values = ",".join("(" + ",".join(_sql_value(value) for value in row) + ")" for row in rows)
    return f"INSERT INTO `{table}` VALUES {values};\r\n"


def _dump(tmp_path):
    dump = tmp_path / "legacy.sql"
    dump.write_text(
        "".join(
            (
                _insert("categoria", [(1, "CALZADO", "\x00", None)]),
                _insert("tipo_de_producto", [(1, "ZAPATO", "\x01")]),
                _insert("atributo", [(1, "TALLA", "\x01", None, 1)]),
                _insert(
                    "atributo_descripcion",
                    [
                        (1, "40", "\x01", 1, 1),
                        (2, "41", "\x01", 1, 2),
                        (3, "", "\x01", 1, 3),
                        (4, "ROJO", "\x01", None, 3),
                        (5, "42", "\x01", 1, 4),
                    ],
                ),
                _insert(
                    "proveedor",
                    [
                        (1, "9999999999999", "A", "1234567", None, None, "INVALIDO", "INVALIDO", None, "\x01", None, 1),
                        (2, "1890010667001", "B", "1234567", None, None, "VALIDO", "VALIDO", None, "\x00", None, 1),
                        (3, "1890010667001", "B", "1234567", None, None, "VALIDO", "VALIDO", None, "\x01", None, 1),
                    ],
                ),
                _insert(
                    "producto",
                    [
                        _product(1, "DUPLICADO", 20, 2),
                        _product(2, "DUPLICADO", 20, 3),
                        _product(3, "UNICO-NEG", 20, -2),
                        _product(4, "UNICO-STOCK", 10, 3),
                    ],
                ),
            )
        ),
        encoding="utf-8",
        newline="",
    )
    return dump


def _dump_with_shoe_child(tmp_path):
    dump = tmp_path / "legacy-shoes.sql"
    dump.write_text(
        "".join(
            (
                _insert("categoria", [(1, "ZAPATO", "\x01", None), (2, "MOCASIN", "\x01", 1)]),
                _insert("tipo_de_producto", [(1, "ZAPATO", "\x01")]),
                _insert("atributo", [(1, "TALLA", "\x01", None, 1)]),
                _insert("atributo_descripcion", [(1, "40", "\x01", 1, 1), (2, "41", "\x01", 1, 2)]),
                _insert("proveedor", [(1, "1890010667001", "A", "1234567", None, None, "VALIDO", "VALIDO", None, "\x01", None, 1)]),
                _insert("producto", [_product(1, "ZAPATO-1", 20, 1), _product(2, "MOCASIN-1", 20, 1, category_id=2)]),
            )
        ),
        encoding="utf-8",
        newline="",
    )
    return dump


def _dump_with_aseo_child(tmp_path):
    dump = tmp_path / "legacy-aseo.sql"
    dump.write_text(
        "".join(
            (
                _insert("categoria", [(62, "ASEO", "\x01", None), (63, "ASEO", "\x01", 62)]),
                _insert("tipo_de_producto", [(1, "ASEO", "\x01")]),
                _insert("atributo", [(1, "MARCA", "\x01", None, 1)]),
                _insert("atributo_descripcion", [(1, "MARCA A", "\x01", 1, 1), (2, "MARCA B", "\x01", 1, 2)]),
                _insert("proveedor", [(1, "1890010667001", "A", "1234567", None, None, "VALIDO", "VALIDO", None, "\x01", None, 1)]),
                _insert("producto", [_product(1, "ASEO-1", 20, 1, category_id=62), _product(2, "ASEO-2", 20, 1, category_id=63)]),
            )
        ),
        encoding="utf-8",
        newline="",
    )
    return dump


def test_build_plan_applies_migration_rules(tmp_path):
    dump = _dump(tmp_path)

    plan = build_plan(dump)

    assert plan.duplicate_barcodes == {"duplicado"}
    assert plan.excluded_product_ids == {1, 2}
    assert [row[0] for row in plan.products] == [3, 4]
    assert [row[0] for row in plan.initial_stock] == [4]
    assert plan.invalid_supplier_ids == {1}
    assert [row[0] for row in plan.suppliers] == [3]
    assert plan.reactivated_category_ids == {1}
    assert plan.product_attributes[3] == {"TIPO DE PRODUCTO": "ZAPATO"}
    assert plan.product_attributes[4] == {"TIPO DE PRODUCTO": "ZAPATO", "TALLA": "42"}


def test_initial_unit_cost_is_65_percent_rounded_to_cents():
    assert initial_unit_cost(20) == Decimal("13.00")
    assert initial_unit_cost(19.99) == Decimal("12.99")


async def test_apply_plan_flattens_mocasin_into_zapato(tmp_path):
    async with TestSessionLocal() as session:
        session.add(User(username="admin", hashed_password=hash_password("Admin@12345!"), full_name="Administrador", role=UserRole.admin, is_active=True))
        await session.commit()

    plan = build_plan(_dump_with_shoe_child(tmp_path))
    assert plan.flattened_category_parents == {2: 1}
    await apply_plan(plan, "admin", TestSessionLocal)

    async with TestSessionLocal() as session:
        categories = list((await session.execute(select(Category))).scalars())
        assert [(category.name, category.parent_id) for category in categories] == [("ZAPATO", None)]
        products = list((await session.execute(select(Product).order_by(Product.isbn))).scalars())
        assert {product.category_id for product in products} == {categories[0].id}


async def test_apply_plan_flattens_aseo_child_into_parent(tmp_path):
    async with TestSessionLocal() as session:
        session.add(User(username="admin", hashed_password=hash_password("Admin@12345!"), full_name="Administrador", role=UserRole.admin, is_active=True))
        await session.commit()

    plan = build_plan(_dump_with_aseo_child(tmp_path))
    assert plan.flattened_category_parents == {63: 62}
    await apply_plan(plan, "admin", TestSessionLocal)

    async with TestSessionLocal() as session:
        categories = list((await session.execute(select(Category))).scalars())
        assert [(category.name, category.parent_id) for category in categories] == [("ASEO", None)]
        products = list((await session.execute(select(Product))).scalars())
        assert {product.category_id for product in products} == {categories[0].id}


async def test_apply_plan_replaces_existing_inventory_data(tmp_path):
    async with TestSessionLocal() as session:
        session.add(User(username="admin", hashed_password=hash_password("Admin@12345!"), full_name="Administrador", role=UserRole.admin, is_active=True))
        session.add(Category(name="CATEGORIA ANTERIOR"))
        await session.commit()

    await apply_plan(build_plan(_dump_with_shoe_child(tmp_path)), "admin", TestSessionLocal)

    async with TestSessionLocal() as session:
        categories = list((await session.execute(select(Category))).scalars())
        assert [(category.name, category.parent_id) for category in categories] == [("ZAPATO", None)]
        products = list((await session.execute(select(Product))).scalars())
        assert {product.category_id for product in products} == {categories[0].id}


async def test_apply_plan_creates_initial_inventory(tmp_path):
    async with TestSessionLocal() as session:
        session.add(
            User(
                username="admin",
                hashed_password=hash_password("Admin@12345!"),
                full_name="Administrador",
                role=UserRole.admin,
                is_active=True,
            )
        )
        await session.commit()

    await apply_plan(build_plan(_dump(tmp_path)), "admin", TestSessionLocal)

    async with TestSessionLocal() as session:
        products = list((await session.execute(select(Product).order_by(Product.isbn))).scalars())
        assert [product.isbn for product in products] == ["UNICO-NEG", "UNICO-STOCK"]
        assert products[0].stock_actual == Decimal("0.0000")
        assert products[1].stock_actual == Decimal("3.0000")
        assert products[1].pvp == Decimal("10.0000")
        assert products[1].status == ProductStatus.active

        supplier = (await session.execute(select(InventorySupplier))).scalar_one()
        assert supplier.ruc == "1890010667001"
        assert supplier.is_active is True

        document = (await session.execute(select(InventoryDocument))).scalar_one()
        assert document.status == DocumentStatus.approved
        assert document.ingreso_type == "initial_inventory"
        assert "65% del PVP" in document.notes

        line = (await session.execute(select(InventoryDocumentLine))).scalar_one()
        assert line.quantity == Decimal("3.0000")
        assert line.unit_cost == Decimal("6.5000")

        lot = (await session.execute(select(InventoryLot))).scalar_one()
        assert lot.quantity_available == Decimal("3.0000")
        assert lot.unit_cost == Decimal("6.5000")

        kardex = (await session.execute(select(KardexEntry))).scalar_one()
        assert kardex.balance_quantity == Decimal("3.0000")
        assert kardex.balance_value == Decimal("19.5000")
        assert await session.scalar(select(func.count()).select_from(Product)) == 2


@pytest.mark.skipif(not os.getenv("LEGACY_DUMP_PATH"), reason="LEGACY_DUMP_PATH no configurado")
async def test_apply_real_legacy_dump():
    async with TestSessionLocal() as session:
        session.add(
            User(
                username="admin",
                hashed_password=hash_password("Admin@12345!"),
                full_name="Administrador",
                role=UserRole.admin,
                is_active=True,
            )
        )
        await session.commit()

    plan = build_plan(Path(os.environ["LEGACY_DUMP_PATH"]))
    await apply_plan(plan, "admin", TestSessionLocal)

    async with TestSessionLocal() as session:
        assert await session.scalar(select(func.count()).select_from(Product)) == 11184
        assert await session.scalar(select(func.count()).select_from(InventorySupplier)) == 43
        assert await session.scalar(select(func.count()).select_from(InventoryDocumentLine)) == 3772
        assert await session.scalar(select(func.sum(Product.stock_actual))) == Decimal("15229.0000")
        assert await session.scalar(select(func.count()).select_from(InventoryLot)) == 3772
        assert await session.scalar(select(func.count()).select_from(KardexEntry)) == 3772
        aseo = list(
            (
                await session.execute(
                    select(Category).where(func.upper(Category.name) == "ASEO")
                )
            ).scalars()
        )
        assert len(aseo) == 1
        assert aseo[0].parent_id is None
        assert await session.scalar(
            select(func.count()).select_from(Product).where(Product.category_id == aseo[0].id)
        ) == 8