from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.charging import Charger, ChargingStation
from app.utils.mapping import REGION_NAME_BY_ZSCODE, to_float


def _clean_text(value: Any, max_len: int | None = None) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    return text[:max_len] if max_len else text


def _to_output_int(value: Any) -> int | None:
    number = to_float(value)

    if number is None:
        return None

    return int(number)


class StationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert_from_keco_item(self, item: dict[str, Any]) -> tuple[ChargingStation, Charger]:
        stat_id = str(item.get("statId", "")).strip()
        chger_id = str(item.get("chgerId", "")).strip().zfill(2)

        if not stat_id or not chger_id:
            raise ValueError("statId, chgerId는 필수입니다.")

        station = await self.db.get(ChargingStation, stat_id)

        if station is None:
            station = ChargingStation(
                stat_id=stat_id,
                stat_nm=_clean_text(item.get("statNm"), 100) or stat_id,
            )
            self.db.add(station)

        # 최종 DB 스키마 station 컬럼 기준으로만 저장
        station.stat_nm = _clean_text(item.get("statNm"), 100) or station.stat_nm
        station.lat = to_float(item.get("lat"))
        station.lng = to_float(item.get("lng"))
        station.addr = _clean_text(item.get("addr"), 200)
        station.use_time = _clean_text(item.get("useTime"), 100)
        station.busi_id = _clean_text(item.get("busiId"), 10)
        station.parking_free = _clean_text(item.get("parkingFree"), 1)
        station.limit_yn = _clean_text(item.get("limitYn"), 1)
        station.limit_detail = _clean_text(item.get("limitDetail"), 100)

        charger_pk = f"{stat_id}_{chger_id}"
        charger = await self.db.get(Charger, charger_pk)

        if charger is None:
            charger = Charger(
                charger_pk=charger_pk,
                stat_id=stat_id,
                chger_id=chger_id,
            )
            self.db.add(charger)

        # 최종 DB 스키마 charger 컬럼 기준으로만 저장
        charger.chger_type = _clean_text(item.get("chgerType"), 2)
        charger.output = _to_output_int(item.get("output"))
        charger.method = _clean_text(item.get("method"), 20)

        return station, charger

    async def list_stations_in_bounds(
        self,
        sw_lat: float,
        sw_lng: float,
        ne_lat: float,
        ne_lng: float,
        zscodes: list[str] | None = None,
        limit: int = 200,
    ) -> list[ChargingStation]:
        query = (
            select(ChargingStation)
            .options(selectinload(ChargingStation.chargers))
            .where(ChargingStation.lat.between(sw_lat, ne_lat))
            .where(ChargingStation.lng.between(sw_lng, ne_lng))
        )

        query = self._apply_region_filter(query, zscodes)
        query = query.limit(limit)

        return list((await self.db.execute(query)).scalars().all())

    async def list_all_supported(
        self,
        zscodes: list[str],
        limit: int = 1000,
    ) -> list[ChargingStation]:
        query = select(ChargingStation).options(selectinload(ChargingStation.chargers))
        query = self._apply_region_filter(query, zscodes)
        query = query.limit(limit)

        return list((await self.db.execute(query)).scalars().all())

    async def get_station(self, station_id: str) -> ChargingStation | None:
        query = (
            select(ChargingStation)
            .options(selectinload(ChargingStation.chargers))
            .where(ChargingStation.stat_id == station_id)
        )

        return (await self.db.execute(query)).scalar_one_or_none()

    @staticmethod
    def _apply_region_filter(query, zscodes: list[str] | None):
        """
        최종 station 스키마에는 zscode 컬럼이 없으므로,
        지원 지역 제한은 addr에 지역명이 포함되는지로 처리한다.
        """

        if not zscodes:
            return query

        region_names = [
            REGION_NAME_BY_ZSCODE[zscode]
            for zscode in zscodes
            if zscode in REGION_NAME_BY_ZSCODE
        ]

        if not region_names:
            return query

        return query.where(
            or_(*[ChargingStation.addr.like(f"%{region_name}%") for region_name in region_names])
        )