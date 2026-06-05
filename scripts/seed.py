"""Seed initial admin user and system parameters.

Usage:
    python -m scripts.seed
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.models.system_param import SystemParam
from app.models.enums import UserRole


INITIAL_PARAMS = [
    ("session_timeout_minutes", "30", "Tiempo de inactividad en minutos antes de cerrar sesión"),
    ("kardex_method", "PEPS", "Método de valoración de inventario: PEPS o WEIGHTED_AVERAGE"),
    ("max_export_date_range_days", "90", "Máximo de días permitidos en exportaciones de auditoría"),
    ("auth_code_expire_minutes", "15", "Minutos de validez del código de autorización para BI/AI"),
    ("doc_number_prefix", "OSR", "Prefijo para la numeración de documentos transaccionales"),
    ("doc_number_padding", "6", "Cantidad de dígitos en la numeración de documentos"),
    ("report_include_logo", "true", "Incluir logo de empresa en exportaciones PDF"),
]


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        # Create admin user if it doesn't exist
        result = await session.execute(select(User).where(User.username == "admin"))
        existing_admin = result.scalar_one_or_none()

        if not existing_admin:
            admin = User(
                username="admin",
                hashed_password=hash_password("Admin@12345!"),
                full_name="Administrador del Sistema",
                role=UserRole.admin,
                is_active=True,
                must_change_password=True,
            )
            session.add(admin)
            print("Created initial admin user (username: admin, password: Admin@12345!) — change on first login!")
        else:
            print("Admin user already exists, skipping.")

        # Create system params if they don't exist
        for key, value, description in INITIAL_PARAMS:
            result = await session.execute(select(SystemParam).where(SystemParam.key == key))
            if not result.scalar_one_or_none():
                session.add(SystemParam(key=key, value=value, description=description))
                print(f"Created param: {key} = {value}")

        await session.commit()
        print("Seed completed.")


if __name__ == "__main__":
    asyncio.run(seed())
