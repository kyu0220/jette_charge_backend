from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis_client import get_redis_client
from app.external.keco_client import KecoEvChargerClient
from app.repositories.station_repository import StationRepository
from app.services.normalizer import (
    charger_to_response,
    normalize_keco_status_item,
    station_to_detail,
    station_to_summary,
    summarize_charger_statuses,
)
from app.services.redis_status_service import RedisStatusService
from app.utils.mapping import distance_meter, extract_items

settings = get_settings()


def _as_float(value) -> float | None:
    if value is None:
        return None

    if isinstance(value, Decimal):
        return float(value)

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class StationService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = StationRepository(db)
        self.keco = KecoEvChargerClient()
        self.redis_service = RedisStatusService(get_redis_client())

    async def _station_chargers_with_redis(self, station) -> list[dict]:
        charger_ids = [charger.chger_id for charger in station.chargers]

        status_map = await self.redis_service.get_statuses_for_station(
            station.stat_id,
            charger_ids,
        )

        return [
            charger_to_response(charger, status_map.get(charger.chger_id))
            for charger in station.chargers
        ]

    @staticmethod
    def _filter_chargers(
        chargers: list[dict],
        charger_speed: str | None,
    ) -> list[dict]:
        if not charger_speed or charger_speed.upper() == "ALL":
            return chargers

        return [
            charger
            for charger in chargers
            if charger.get("speedType") == charger_speed.upper()
        ]

    async def list_map_stations(
        self,
        sw_lat: float,
        sw_lng: float,
        ne_lat: float,
        ne_lng: float,
        charger_speed: str | None,
        available_only: bool,
        limit: int,
    ) -> list[dict]:
        stations = await self.repo.list_stations_in_bounds(
            sw_lat,
            sw_lng,
            ne_lat,
            ne_lng,
            zscodes=settings.supported_zscode_list,
            limit=limit,
        )

        result = []

        for station in stations:
            chargers = await self._station_chargers_with_redis(station)
            chargers = self._filter_chargers(chargers, charger_speed)

            if not chargers:
                continue

            if available_only and not any(
                charger.get("status") == "AVAILABLE" for charger in chargers
            ):
                continue

            result.append(station_to_summary(station, chargers))

        return result

    async def list_nearby_stations(
        self,
        lat: float,
        lng: float,
        radius: int,
        charger_speed: str | None,
        available_only: bool,
        operator: str | None,
        open24h: bool | None,
        limit: int,
    ) -> list[dict]:
        stations = await self.repo.list_all_supported(
            settings.supported_zscode_list,
            limit=2000,
        )

        result = []

        for station in stations:
            station_lat = _as_float(station.lat)
            station_lng = _as_float(station.lng)

            if station_lat is None or station_lng is None:
                continue

            dist = distance_meter(lat, lng, station_lat, station_lng)

            if dist > radius:
                continue

            # 최종 station 스키마에는 기관명 컬럼이 없으므로 busi_id 기준 필터만 지원
            if operator and operator not in (station.busi_id or ""):
                continue

            if open24h is True and "24" not in (station.use_time or ""):
                continue

            chargers = await self._station_chargers_with_redis(station)
            chargers = self._filter_chargers(chargers, charger_speed)

            if not chargers:
                continue

            if available_only and not any(
                charger.get("status") == "AVAILABLE" for charger in chargers
            ):
                continue

            result.append(station_to_summary(station, chargers, dist))

        result.sort(
            key=lambda item: item.get("distanceMeter")
            if item.get("distanceMeter") is not None
            else 10**9
        )

        return result[:limit]

    async def get_station_detail(self, station_id: str) -> dict | None:
        station = await self.repo.get_station(station_id)

        if not station:
            return None

        chargers = await self._station_chargers_with_redis(station)

        return station_to_detail(station, chargers)

    async def get_station_status(self, station_id: str) -> dict | None:
        station = await self.repo.get_station(station_id)

        if not station:
            return None

        charger_ids = [charger.chger_id for charger in station.chargers]

        status_map = await self.redis_service.get_statuses_for_station(
            station_id,
            charger_ids,
        )

        summary_chargers = [
            charger_to_response(charger, status_map.get(charger.chger_id))
            for charger in station.chargers
        ]

        summary = summarize_charger_statuses(summary_chargers)

        redis_values = [
            status
            for status in status_map.values()
            if status is not None
        ]

        if not redis_values:
            return {
                "stationId": station_id,
                "source": "REDIS_MISS",
                "cacheStatus": "MISS",
                "isStale": True,
                "fetchedAt": None,
                "refreshPolicy": "FETCH_FROM_OPEN_API_REQUIRED",
                "summary": {
                    "totalCount": summary["totalChargerCount"],
                    "availableCount": summary["availableCount"],
                    "chargingCount": summary["chargingCount"],
                    "unavailableCount": summary["unavailableCount"],
                    "markerStatus": summary["markerStatus"],
                },
                "chargers": [
                    {
                        "chargerId": charger.chger_id,
                        "statusCode": "0",
                        "status": "UNKNOWN",
                        "statusLabel": "알 수 없음",
                        "statusUpdatedAt": None,
                        "lastStartTime": None,
                        "lastEndTime": None,
                        "nowStartTime": None,
                    }
                    for charger in station.chargers
                ],
            }

        statuses = [
            self.redis_service.status_payload_for_response(
                status_map.get(charger_id)
            )
            for charger_id in charger_ids
        ]

        statuses = [
            status
            for status in statuses
            if status is not None
        ]

        cache = self.redis_service.get_cache_status(redis_values)

        if cache["cacheStatus"] == "MISS":
            refresh_policy = "FETCH_FROM_OPEN_API_REQUIRED"
        elif cache["isStale"]:
            refresh_policy = "STALE_RETURN_AND_REFRESH_RECOMMENDED"
        else:
            refresh_policy = "RETURN_FRESH_CACHE"

        return {
            "stationId": station_id,
            "source": "REDIS",
            **cache,
            "refreshPolicy": refresh_policy,
            "summary": {
                "totalCount": summary["totalChargerCount"],
                "availableCount": summary["availableCount"],
                "chargingCount": summary["chargingCount"],
                "unavailableCount": summary["unavailableCount"],
                "markerStatus": summary["markerStatus"],
            },
            "chargers": statuses,
        }

    async def refresh_station_status(self, station_id: str) -> dict | None:
        station = await self.repo.get_station(station_id)

        if not station:
            return None

        # 최종 station 스키마에는 zcode/zscode 컬럼이 없으므로 statId 기준으로만 재조회
        payload = await self.keco.get_charger_info(
            page_no=1,
            num_of_rows=9999,
            stat_id=station_id,
        )

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
                failed_items.append(
                    {
                        "stationId": item.get("statId"),
                        "chargerId": item.get("chgerId"),
                        "reason": str(exc),
                    }
                )

        return {
            "stationId": station_id,
            "syncedCount": synced,
            "failedCount": len(failed_items),
            "failedItems": failed_items[:20],
        }