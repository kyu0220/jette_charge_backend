import json
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

from app.core.config import get_settings
from app.utils.mapping import format_keco_datetime

settings = get_settings()


class RedisStatusService:
    def __init__(self, redis_client: Redis) -> None:
        self.redis = redis_client

    @staticmethod
    def key(station_id: str, charger_id: str) -> str:
        return f"charger:status:{station_id}:{charger_id}"

    async def set_status(self, status: dict[str, Any]) -> None:
        station_id = status["stationId"]
        charger_id = status["chargerId"]
        payload = {**status, "fetchedAt": datetime.now(timezone.utc).isoformat()}
        await self.redis.set(self.key(station_id, charger_id), json.dumps(payload, ensure_ascii=False))

    async def get_status(self, station_id: str, charger_id: str) -> dict[str, Any] | None:
        raw = await self.redis.get(self.key(station_id, charger_id))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def get_statuses_for_station(self, station_id: str, charger_ids: list[str]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for charger_id in charger_ids:
            status = await self.get_status(station_id, charger_id)
            if status:
                result[charger_id] = status
        return result

    @staticmethod
    def get_cache_status(payloads: list[dict[str, Any]]) -> dict[str, Any]:
        if not payloads:
            return {"cacheStatus": "MISS", "isStale": True, "fetchedAt": None}
        fetched_values = [p.get("fetchedAt") for p in payloads if p.get("fetchedAt")]
        if not fetched_values:
            return {"cacheStatus": "MISS", "isStale": True, "fetchedAt": None}
        latest = max(fetched_values)
        try:
            fetched_dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
            if fetched_dt.tzinfo is None:
                fetched_dt = fetched_dt.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - fetched_dt).total_seconds()
            is_stale = age > settings.cache_fresh_seconds
            return {
                "cacheStatus": "HIT_STALE" if is_stale else "HIT_FRESH",
                "isStale": is_stale,
                "fetchedAt": latest,
            }
        except ValueError:
            return {"cacheStatus": "HIT_STALE", "isStale": True, "fetchedAt": latest}

    @staticmethod
    def status_payload_for_response(payload: dict[str, Any] | None) -> dict[str, Any] | None:
        if payload is None:
            return None
        return {
            "chargerId": payload.get("chargerId"),
            "statusCode": payload.get("stat"),
            "status": payload.get("status"),
            "statusLabel": payload.get("statusLabel"),
            "statusUpdatedAt": format_keco_datetime(payload.get("statUpdDt")),
            "lastStartTime": format_keco_datetime(payload.get("lastTsdt")),
            "lastEndTime": format_keco_datetime(payload.get("lastTedt")),
            "nowStartTime": format_keco_datetime(payload.get("nowTsdt")),
        }
