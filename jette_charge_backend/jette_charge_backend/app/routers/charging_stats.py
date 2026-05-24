from fastapi import APIRouter, HTTPException, Query

from app.services.energy_service import EnergyService

router = APIRouter(prefix="/charging-stats", tags=["charging-stats"])


@router.get("/regions")
async def get_region_charging_stats(
    regionMajor: str | None = None,
    regionSub: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    try:
        service = EnergyService()
        data = await service.list_region_stats(regionMajor, regionSub, page, size)
        return {"success": True, "message": "지역별 급속충전기 통계 조회 성공", "data": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
