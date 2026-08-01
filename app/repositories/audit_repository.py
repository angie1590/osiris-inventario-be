from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
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

    async def list_page(
        self,
        date_from: datetime,
        date_to: datetime,
        page: int,
        page_size: int,
        user_id: int | None = None,
        action: AuditAction | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        filters = [AuditLog.timestamp >= date_from, AuditLog.timestamp <= date_to]
        if user_id is not None:
            filters.append(AuditLog.user_id == user_id)
        if action is not None:
            filters.append(AuditLog.action == action)
        if entity_type is not None:
            filters.append(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            filters.append(AuditLog.entity_id == entity_id)
        total = int((await self.db.scalar(select(func.count(AuditLog.id)).where(*filters))) or 0)
        result = await self.db.execute(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total
