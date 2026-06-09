from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_role
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.remap import RemapPendingResponse, RemapResolveRequest
from app.services.remap_service import RemapService

router = APIRouter()

_write_roles = require_role(UserRole.admin, UserRole.operator)
_read_roles = require_role(UserRole.admin, UserRole.operator, UserRole.supervisor)


@router.get("/pending", response_model=RemapPendingResponse)
async def list_pending(db: AsyncSession = Depends(get_db), _: User = Depends(_read_roles)):
    return await RemapService(db).list_pending()


@router.post("/resolve", response_model=dict)
async def resolve(
    body: RemapResolveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_write_roles),
):
    count = await RemapService(db).resolve(body.assignments, current_user.id, current_user.username, request)
    return {"resolved": count}
