from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis_client import get_redis_client
from app.external.keco_client import KecoEvChargerClient
from app.repositories.station_repository import StationRepository
from app.services.normalizer import normalize_keco_status_item
from app.services.redis_status_service import RedisStatusService
from app.utils.mapping import REGION_NAME_BY_ZSCODE, extract_items, yn_to_bool

settings = get_settings()


class SyncService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = StationRepository(db)
        self.keco = KecoEvChargerClient()
        self.redis_service = RedisStatusService(get_redis_client())

    async def sync_stations(self, zcode: str | None, zscode: str | None, page_no: int, num_of_rows: int, save_to_mysql: bool, include_deleted: bool) -> dict[str, Any]:
        payload = await self.keco.get_charger_info(page_no=page_no, num_of_rows=num_of_rows, zcode=zcode, zscode=zscode)
        items = extract_items(payload)
        station_ids = set()
        charger_count = 0
        skipped_deleted = 0
        if save_to_mysql:
            for item in items:
                if not include_deleted and yn_to_bool(item.get("delYn")) is True:
                    skipped_deleted += 1
                    continue
                station, _charger = await self.repo.upsert_from_keco_item(item)
                station_ids.add(station.stat_id)
                charger_count += 1
            await self.db.commit()
        return {
            "source": "KOREA_ENVIRONMENT_CORPORATION",
            "operation": "getChargerInfo",
            "targetRegion": {"zcode": zcode, "zscode": zscode, "regionName": REGION_NAME_BY_ZSCODE.get(zscode or "")},
            "stationUpsertCount": len(station_ids),
            "chargerUpsertCount": charger_count,
            "skippedDeletedCount": skipped_deleted,
            "rawItemCount": len(items),
        }

    async def sync_charger_status(self, zcode: str | None, zscode: str | None, period: int, force: bool, page_no: int = 1, num_of_rows: int = 9999) -> dict[str, Any]:
        payload = await self.keco.get_charger_status(page_no=page_no, num_of_rows=num_of_rows, period=period, zcode=zcode, zscode=zscode)
        items = extract_items(payload)
        synced = 0
        failed_items = []
        for item in items:
            try:
                status = normalize_keco_status_item(item)
                if not status["stationId"] or not status["chargerId"]:
                    raise ValueError("statId/chgerId 누락")
                await self.redis_service.set_status(status)
                synced += 1
            except Exception as exc:
                failed_items.append({"stationId": item.get("statId"), "chargerId": item.get("chgerId"), "reason": str(exc)})
        return {
            "source": "KOREA_ENVIRONMENT_CORPORATION",
            "operation": "getChargerStatus",
            "targetRegion": {"zcode": zcode, "zscode": zscode, "regionName": REGION_NAME_BY_ZSCODE.get(zscode or "")},
            "syncedCount": synced,
            "failedCount": len(failed_items),
            "freshThresholdSeconds": settings.cache_fresh_seconds,
            "redisKeyPattern": "charger:status:{stationId}:{chargerId}",
            "failedItems": failed_items[:20],
        }
