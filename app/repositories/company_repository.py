from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_config import CompanyConfig


class CompanyRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self) -> CompanyConfig | None:
        result = await self.db.execute(select(CompanyConfig).limit(1))
        return result.scalar_one_or_none()

    async def create(self, data: CompanyConfig) -> CompanyConfig:
        self.db.add(data)
        await self.db.flush()
        await self.db.refresh(data)
        return data

    async def update(self, company: CompanyConfig, data: dict) -> CompanyConfig:
        for key, value in data.items():
            setattr(company, key, value)
        await self.db.flush()
        await self.db.refresh(company)
        return company
