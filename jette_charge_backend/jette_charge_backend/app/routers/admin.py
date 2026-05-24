from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.services.sync_service import SyncService

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()


class StationSyncRequest(BaseModel):
    zcode: Optional[str] = Field(default="47")
    zscode: Optional[str] = Field(default="47190")
    pageNo: int = 1
    numOfRows: int = 9999
    saveToMysql: bool = True
    includeDeleted: bool = False


class ChargerStatusSyncRequest(BaseModel):
    zcode: Optional[str] = Field(default="47")
    zscode: Optional[str] = Field(default="47190")
    period: int = Field(default=5, ge=1, le=10)
    force: bool = False


@router.post("/stations/sync")
async def sync_stations(body: StationSyncRequest, db: AsyncSession = Depends(get_db)):
    started_at = datetime.now(timezone.utc).isoformat()
    service = SyncService(db)
    data = await service.sync_stations(body.zcode, body.zscode, body.pageNo, body.numOfRows, body.saveToMysql, body.includeDeleted)
    data["startedAt"] = started_at
    data["finishedAt"] = datetime.now(timezone.utc).isoformat()
    return {"success": True, "message": "충전소 정적 데이터 동기화 완료", "data": data}


@router.post("/chargers/status/sync")
async def sync_charger_status(body: ChargerStatusSyncRequest, db: AsyncSession = Depends(get_db)):
    started_at = datetime.now(timezone.utc).isoformat()
    service = SyncService(db)
    data = await service.sync_charger_status(body.zcode, body.zscode, body.period, body.force)
    data["startedAt"] = started_at
    data["finishedAt"] = datetime.now(timezone.utc).isoformat()
    return {"success": True, "message": "충전기 상태 Redis 동기화 완료", "data": data}
