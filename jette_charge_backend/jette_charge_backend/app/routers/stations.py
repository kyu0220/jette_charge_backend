from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_db
from app.services.station_service import StationService

router = APIRouter(prefix="/stations", tags=["stations"])


async def background_refresh_station_status(station_id: str) -> None:
    """
    Redis 캐시가 오래된 경우 응답은 먼저 반환하고,
    백그라운드에서 해당 충전소 상태를 외부 API로 다시 조회해 Redis를 갱신한다.
    """
    async with AsyncSessionLocal() as db:
        service = StationService(db)

        try:
            await service.refresh_station_status(station_id)
        except Exception as exc:
            # 백그라운드 작업 실패가 사용자 응답을 망치지 않도록 로그만 출력
            print(f"[BACKGROUND_REFRESH_FAILED] station_id={station_id}, error={repr(exc)}")


@router.get("/map")
async def get_map_stations(
    swLat: float = Query(..., description="지도 남서쪽 위도"),
    swLng: float = Query(..., description="지도 남서쪽 경도"),
    neLat: float = Query(..., description="지도 북동쪽 위도"),
    neLng: float = Query(..., description="지도 북동쪽 경도"),
    chargerSpeed: str = Query(default="ALL", description="ALL, FAST, SLOW"),
    availableOnly: bool = Query(default=False, description="사용 가능 충전소만 조회"),
    limit: int = Query(default=200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    service = StationService(db)

    stations = await service.list_map_stations(
        sw_lat=swLat,
        sw_lng=swLng,
        ne_lat=neLat,
        ne_lng=neLng,
        charger_speed=chargerSpeed,
        available_only=availableOnly,
        limit=limit,
    )

    return {
        "success": True,
        "message": "지도 충전소 현황 조회 성공",
        "data": {
            "bounds": {
                "swLat": swLat,
                "swLng": swLng,
                "neLat": neLat,
                "neLng": neLng,
            },
            "regionLimit": ["구미시", "김천시", "칠곡군"],
            "count": len(stations),
            "stations": stations,
        },
    }


@router.get("/nearby")
async def get_nearby_stations(
    lat: float = Query(..., description="사용자 현재 위도"),
    lng: float = Query(..., description="사용자 현재 경도"),
    radius: int = Query(default=3000, ge=100, le=20000, description="검색 반경 meter"),
    chargerSpeed: str = Query(default="ALL", description="ALL, FAST, SLOW"),
    availableOnly: bool = Query(default=False),
    operator: str | None = Query(default=None),
    open24h: bool | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    service = StationService(db)

    stations = await service.list_nearby_stations(
        lat=lat,
        lng=lng,
        radius=radius,
        charger_speed=chargerSpeed,
        available_only=availableOnly,
        operator=operator,
        open24h=open24h,
        limit=limit,
    )

    return {
        "success": True,
        "message": "주변 충전소 조회 성공",
        "data": {
            "center": {
                "lat": lat,
                "lng": lng,
            },
            "radius": radius,
            "regionLimit": ["구미시", "김천시", "칠곡군"],
            "count": len(stations),
            "stations": stations,
        },
    }


@router.get("/{station_id}")
async def get_station_detail(
    station_id: str,
    includeChargers: bool = Query(default=True),
    includeFacilities: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    service = StationService(db)

    station = await service.get_station_detail(station_id)

    if station is None:
        raise HTTPException(
            status_code=404,
            detail="충전소 정보를 찾을 수 없습니다.",
        )

    if not includeChargers:
        station.pop("chargers", None)

    # 편의시설은 소영민 담당 API에서 처리하므로 현재 응답에는 포함하지 않음
    if includeFacilities:
        station["facilities"] = []

    return {
        "success": True,
        "message": "충전소 상세 정보 조회 성공",
        "data": station,
    }


@router.get("/{station_id}/chargers/status")
async def get_station_charger_status(
    station_id: str,
    background_tasks: BackgroundTasks,
    refresh: bool = Query(default=False, description="true면 외부 API 즉시 재조회"),
    db: AsyncSession = Depends(get_db),
):
    """
    Redis 요구사항 반영 버전.

    1. refresh=true
       - 외부 API 즉시 호출
       - Redis 갱신
       - 최신 상태 반환

    2. cacheStatus == MISS
       - Redis에 상태 없음
       - 외부 API 즉시 호출
       - Redis 갱신 후 최신 상태 반환

    3. cacheStatus == HIT_STALE
       - 1분 이상 지난 Redis 데이터
       - 기존 stale 데이터 먼저 반환
       - 백그라운드에서 외부 API 호출 후 Redis 갱신

    4. cacheStatus == HIT_FRESH
       - Redis 최신 데이터 바로 반환
    """
    service = StationService(db)

    status_data = await service.get_station_status(station_id)

    if status_data is None:
        raise HTTPException(
            status_code=404,
            detail="충전소 정보를 찾을 수 없습니다.",
        )

    cache_status = status_data.get("cacheStatus")
    refresh_result = None

    # 1. 사용자가 강제 새로고침을 요청한 경우
    if refresh:
        refresh_result = await service.refresh_station_status(station_id)
        status_data = await service.get_station_status(station_id)

        if status_data is None:
            raise HTTPException(
                status_code=404,
                detail="충전소 정보를 찾을 수 없습니다.",
            )

        status_data["refreshResult"] = refresh_result
        status_data["refreshPolicy"] = "RETURN_FRESH_CACHE"

    # 2. Redis에 상태가 아예 없는 경우: 즉시 외부 API 호출 후 반환
    elif cache_status == "MISS":
        refresh_result = await service.refresh_station_status(station_id)
        status_data = await service.get_station_status(station_id)

        if status_data is None:
            raise HTTPException(
                status_code=404,
                detail="충전소 정보를 찾을 수 없습니다.",
            )

        status_data["refreshResult"] = refresh_result

        if refresh_result and refresh_result.get("syncedCount", 0) > 0:
            status_data["refreshPolicy"] = "MISS_FETCHED_FROM_OPEN_API"
        else:
            status_data["refreshPolicy"] = "MISS_OPEN_API_NO_DATA"

    # 3. Redis 데이터가 오래된 경우: 기존 값 반환 + 백그라운드 갱신
    elif cache_status == "HIT_STALE":
        background_tasks.add_task(background_refresh_station_status, station_id)
        status_data["refreshPolicy"] = "STALE_RETURN_AND_BACKGROUND_REFRESH"

    # 4. Redis 데이터가 최신인 경우
    elif cache_status == "HIT_FRESH":
        status_data["refreshPolicy"] = "RETURN_FRESH_CACHE"

    return {
        "success": True,
        "message": "충전기 실시간 상태 조회 성공",
        "data": status_data,
    }