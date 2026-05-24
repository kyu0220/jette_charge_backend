from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.charging import RegionalChargingStat


class RegionalChargingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_stats(self, region_major: str | None, region_sub: str | None, page: int, size: int) -> tuple[int, list[RegionalChargingStat]]:
        query = select(RegionalChargingStat)
        if region_major:
            query = query.where(RegionalChargingStat.region_major == region_major)
        if region_sub:
            query = query.where(RegionalChargingStat.region_sub == region_sub)
        query = query.offset((page - 1) * size).limit(size)
        rows = list((await self.db.execute(query)).scalars().all())
        return len(rows), rows
