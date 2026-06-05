"""Tests: PostgreSQL trigger prevents direct stock_actual update (task 13.11)"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_direct_stock_update_blocked_by_trigger(db_session: AsyncSession):
    """Direct UPDATE to stock_actual must raise the trigger's exception."""
    from app.core.security import hash_password
    from app.models.category import Category
    from app.models.product import Product
    from app.models.user import User
    from app.models.enums import UserRole

    user = User(
        username="trigger_test_user",
        hashed_password=hash_password("Trigger@123"),
        full_name="Trigger Tester",
        role=UserRole.operator,
        is_active=True,
        must_change_password=False,
    )
    db_session.add(user)
    await db_session.flush()

    cat = Category(name="TriggerCat", is_active=True)
    db_session.add(cat)
    await db_session.flush()

    product = Product(
        name="TriggerProduct",
        category_id=cat.id,
        pvp=10,
    )
    db_session.add(product)
    await db_session.flush()
    prod_id = product.id

    from sqlalchemy.exc import DBAPIError
    with pytest.raises(DBAPIError):
        await db_session.execute(
            text("UPDATE products SET stock_actual = 999 WHERE id = :pid"),
            {"pid": prod_id},
        )
        await db_session.flush()


@pytest.mark.asyncio
async def test_update_product_stock_function_works(db_session: AsyncSession):
    """The authorized function update_product_stock() must succeed."""
    from app.models.category import Category
    from app.models.product import Product

    cat = Category(name="FunctionCat", is_active=True)
    db_session.add(cat)
    await db_session.flush()

    product = Product(name="FunctionProduct", category_id=cat.id, pvp=5)
    db_session.add(product)
    await db_session.flush()
    prod_id = product.id

    await db_session.execute(
        text("SELECT update_product_stock(:pid, :delta)"),
        {"pid": prod_id, "delta": 10},
    )
    await db_session.flush()
    await db_session.refresh(product)

    from sqlalchemy import select
    result = await db_session.execute(select(Product).where(Product.id == prod_id))
    updated = result.scalar_one()
    assert float(updated.stock_actual) == 10.0


@pytest.mark.asyncio
async def test_update_product_stock_prevents_negative(db_session: AsyncSession):
    """update_product_stock() must raise when stock would become negative."""
    from app.models.category import Category
    from app.models.product import Product
    from sqlalchemy.exc import DBAPIError

    cat = Category(name="NegCat", is_active=True)
    db_session.add(cat)
    await db_session.flush()

    product = Product(name="NegProduct", category_id=cat.id, pvp=5)
    db_session.add(product)
    await db_session.flush()
    prod_id = product.id

    with pytest.raises(DBAPIError):
        await db_session.execute(
            text("SELECT update_product_stock(:pid, :delta)"),
            {"pid": prod_id, "delta": -1},
        )
        await db_session.flush()
