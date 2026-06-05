from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction
from app.repositories.audit_repository import AuditRepository


def _get_client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


class AuditService:
    def __init__(self, db: AsyncSession):
        self.repo = AuditRepository(db)

    async def log(
        self,
        action: AuditAction,
        *,
        user_id: int | None = None,
        username: str | None = None,
        entity_type: str | None = None,
        entity_id: str | int | None = None,
        previous: dict[str, Any] | None = None,
        new: dict[str, Any] | None = None,
        description: str | None = None,
        request: Request | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            user_id=user_id,
            username=username,
            ip_address=_get_client_ip(request),
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            previous_values=previous,
            new_values=new,
            description=description,
        )
        return await self.repo.create(entry)
