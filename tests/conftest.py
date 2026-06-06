import os
from typing import AsyncGenerator

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.database import Base, get_db
from app.core.redis import close_redis
from app.main import app

# Tests run against a DEDICATED database — never the dev one — because the
# setup fixture drops all tables before each test. The default points at
# `osiris_inventario_test`; it is created automatically if it does not exist.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://osiris:osiris_dev_pass@postgres:5432/osiris_inventario_test",
)

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

_test_db_ready = False


async def _ensure_test_database() -> None:
    """Create the dedicated test database if it does not exist yet.

    Connects to the `postgres` maintenance database to run CREATE DATABASE
    (which cannot run inside a transaction, hence AUTOCOMMIT). Runs only once
    per session via the module-level guard.
    """
    global _test_db_ready
    if _test_db_ready:
        return

    url = make_url(TEST_DATABASE_URL)
    db_name = url.database
    admin_engine = create_async_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    try:
        async with admin_engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        await admin_engine.dispose()

    _test_db_ready = True


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await _ensure_test_database()
    await close_redis()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

        # Recreate DB functions/trigger declared in migration 0001 used by stock tests.
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION update_product_stock(p_product_id INTEGER, p_delta NUMERIC)
            RETURNS void AS $$
            DECLARE
                v_new_stock NUMERIC;
            BEGIN
                SELECT stock_actual + p_delta INTO v_new_stock
                FROM products WHERE id = p_product_id FOR UPDATE;

                IF v_new_stock < 0 THEN
                    RAISE EXCEPTION 'INSUFFICIENT_STOCK: stock would become negative (%.4f)', v_new_stock;
                END IF;

                PERFORM set_config('app.allow_stock_update', '1', true);
                UPDATE products SET stock_actual = v_new_stock, updated_at = now()
                WHERE id = p_product_id;
                PERFORM set_config('app.allow_stock_update', '0', true);
            END;
            $$ LANGUAGE plpgsql;
        """))

        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION prevent_direct_stock_update()
            RETURNS trigger AS $$
            BEGIN
                IF current_setting('app.allow_stock_update', true) = '1' THEN
                    RETURN NEW;
                END IF;

                IF NEW.stock_actual IS DISTINCT FROM OLD.stock_actual THEN
                    RAISE EXCEPTION 'DIRECT_STOCK_UPDATE_FORBIDDEN: use update_product_stock() function';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))

        await conn.execute(text("""
            CREATE TRIGGER trg_prevent_direct_stock_update
            BEFORE UPDATE ON products
            FOR EACH ROW
            EXECUTE FUNCTION prevent_direct_stock_update();
        """))
    yield
    await close_redis()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, db_session: AsyncSession) -> str:
    from app.core.security import hash_password
    from app.models.user import User
    from app.models.enums import UserRole

    user = User(
        username="test_admin",
        hashed_password=hash_password("TestAdmin@123"),
        full_name="Test Admin",
        role=UserRole.admin,
        is_active=True,
        must_change_password=False,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", data={"username": "test_admin", "password": "TestAdmin@123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def operator_token(client: AsyncClient, db_session: AsyncSession) -> str:
    from app.core.security import hash_password
    from app.models.user import User
    from app.models.enums import UserRole

    user = User(
        username="test_operator",
        hashed_password=hash_password("TestOp@123"),
        full_name="Test Operator",
        role=UserRole.operator,
        is_active=True,
        must_change_password=False,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", data={"username": "test_operator", "password": "TestOp@123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def supervisor_token(client: AsyncClient, db_session: AsyncSession) -> str:
    from app.core.security import hash_password
    from app.models.user import User
    from app.models.enums import UserRole

    user = User(
        username="test_supervisor",
        hashed_password=hash_password("TestSup@123"),
        full_name="Test Supervisor",
        role=UserRole.supervisor,
        is_active=True,
        must_change_password=False,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login", data={"username": "test_supervisor", "password": "TestSup@123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def stock_mode_integer(db_session: AsyncSession):
    from app.models.system_param import SystemParam
    param = SystemParam(key="stock_quantity_mode", value="integer", description="test")
    db_session.add(param)
    await db_session.commit()
    return param


@pytest_asyncio.fixture
async def stock_mode_decimal(db_session: AsyncSession):
    from app.models.system_param import SystemParam
    param = SystemParam(key="stock_quantity_mode", value="decimal", description="test")
    db_session.add(param)
    await db_session.commit()
    return param


@pytest_asyncio.fixture
async def company_config(db_session: AsyncSession):
    """Create a complete company config so require_company_configured passes."""
    from app.models.company_config import CompanyConfig

    company = CompanyConfig(
        razon_social="Empresa de Prueba S.A.",
        nombre_comercial="Empresa Test",
        ruc="1234567890001",
        direccion="Av. Ejemplo 123",
        telefono="0991234567",
        email="empresa@test.com",
    )
    db_session.add(company)
    await db_session.commit()
    await db_session.refresh(company)
    return company
