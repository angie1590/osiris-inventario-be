from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction


class AuditRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, log: AuditLog) -> AuditLog:
        self.db.add(log)
        await self.db.flush()
        return log

    async def list(
        self,
        date_from: datetime,
        date_to: datetime,
        user_id: int | None = None,
        action: AuditAction | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        limit: int = 100,
        cursor: int | None = None,
    ) -> list[AuditLog]:
        q = (
            select(AuditLog)
            .where(AuditLog.timestamp >= date_from, AuditLog.timestamp <= date_to)
            .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        )
        if user_id is not None:
            q = q.where(AuditLog.user_id == user_id)
        if action is not None:
            q = q.where(AuditLog.action == action)
        if entity_type is not None:
            q = q.where(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            q = q.where(AuditLog.entity_id == entity_id)
        if cursor is not None:
            q = q.where(AuditLog.id < cursor)
        q = q.limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())
