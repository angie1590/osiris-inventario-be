"""Reset admin password in the database.

Usage:
    python -m scripts.reset_admin_password
    python -m scripts.reset_admin_password --password "NuevoPassword123!"
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.models.enums import UserRole

DEFAULT_ADMIN_PASSWORD = "Admin@12345!"


async def reset_admin_password(password: str) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        admin = result.scalar_one_or_none()

        created = False
        if not admin:
            admin = User(
                username="admin",
                hashed_password=hash_password(password),
                full_name="Administrador del Sistema",
                role=UserRole.admin,
                is_active=True,
                must_change_password=True,
            )
            session.add(admin)
            created = True
        else:
            admin.hashed_password = hash_password(password)
            admin.is_active = True
            admin.must_change_password = True

        await session.commit()
        await session.refresh(admin)

        verified = verify_password(password, admin.hashed_password)

        if created:
            print("Usuario 'admin' no existia: fue creado.")
        else:
            print("Contrasena de 'admin' restablecida correctamente.")
        print("Usuario:", admin.username)
        print("Activo:", admin.is_active)
        print("Contrasena temporal:", password)
        print("Verificacion de contrasena:", "OK" if verified else "FALLO")
        print("Se solicitara cambio de contrasena en el siguiente login.")

        if not verified:
            raise RuntimeError(
                "La verificacion de la contrasena fallo tras el reset. "
                "Revisa la version de bcrypt/passlib en el contenedor."
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resetea la contrasena del admin")
    parser.add_argument(
        "--password",
        default=DEFAULT_ADMIN_PASSWORD,
        help="Nueva contrasena temporal para admin",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(reset_admin_password(args.password))
