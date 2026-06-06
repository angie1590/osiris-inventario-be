from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.company_config import CompanyConfig
from app.models.enums import AuditAction
from app.models.user import User
from app.repositories.company_repository import CompanyRepository
from app.schemas.company import CompanyConfigCreate, CompanyConfigUpdate
from app.services.audit_service import AuditService


def _is_complete(company: CompanyConfig) -> bool:
    return bool(company.razon_social and company.ruc and company.email)


class CompanyService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CompanyRepository(db)
        self.audit = AuditService(db)

    async def get_or_none(self) -> CompanyConfig | None:
        return await self.repo.get()

    async def create(self, payload: CompanyConfigCreate, user: User, request: Request) -> CompanyConfig:
        existing = await self.repo.get()
        if existing:
            raise ConflictError("COMPANY_ALREADY_EXISTS", "Company configuration already exists")

        company = CompanyConfig(
            razon_social=payload.razon_social,
            nombre_comercial=payload.nombre_comercial,
            ruc=payload.ruc,
            direccion=payload.direccion,
            telefono=payload.telefono,
            email=payload.email,
            logo=payload.logo,
            updated_by=user.id,
        )
        company = await self.repo.create(company)

        await self.audit.log(
            AuditAction.CREATE,
            user_id=user.id,
            username=user.username,
            entity_type="company_config",
            entity_id=company.id,
            new=payload.model_dump(exclude={"logo"}),
            request=request,
        )
        await self.db.commit()
        await self.db.refresh(company)
        return company

    async def update(self, payload: CompanyConfigUpdate, user: User, request: Request) -> CompanyConfig:
        company = await self.repo.get()
        if not company:
            raise NotFoundError("COMPANY_NOT_FOUND", "Company configuration not found")

        previous = {
            "razon_social": company.razon_social,
            "nombre_comercial": company.nombre_comercial,
            "ruc": company.ruc,
            "email": company.email,
            "direccion": company.direccion,
            "telefono": company.telefono,
        }

        changes = payload.model_dump(exclude_unset=True)
        changes["updated_by"] = user.id

        company = await self.repo.update(company, changes)

        await self.audit.log(
            AuditAction.UPDATE,
            user_id=user.id,
            username=user.username,
            entity_type="company_config",
            entity_id=company.id,
            previous=previous,
            new={k: v for k, v in changes.items() if k not in ("logo", "updated_by")},
            request=request,
        )
        await self.db.commit()
        await self.db.refresh(company)
        return company
