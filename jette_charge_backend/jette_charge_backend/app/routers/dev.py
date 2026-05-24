from fastapi import APIRouter, HTTPException, Query

from app.external.keco_client import KecoEvChargerClient
from app.utils.mapping import extract_items

router = APIRouter(prefix="/dev/external/keco", tags=["dev-external"])


@router.get("/charger-info")
async def get_raw_charger_info(
    zcode: str | None = Query(default="47"),
    zscode: str | None = Query(default="47190"),
    pageNo: int = 1,
    numOfRows: int = 10,
):
    try:
        client = KecoEvChargerClient()

        payload = await client.get_charger_info(
            page_no=pageNo,
            num_of_rows=numOfRows,
            zcode=zcode,
            zscode=zscode,
        )

        items = extract_items(payload)

        return {
            "success": True,
            "message": "한국환경공단 충전소 원본 데이터 조회 성공",
            "data": {
                "source": "KOREA_ENVIRONMENT_CORPORATION",
                "operation": "getChargerInfo",
                "pageNo": pageNo,
                "numOfRows": numOfRows,
                "zcode": zcode,
                "zscode": zscode,
                "totalCount": payload.get("totalCount") or len(items),
                "items": items,
            },
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=repr(exc)) from exc


@router.get("/charger-status")
async def get_raw_charger_status(
    zcode: str | None = Query(default="47"),
    zscode: str | None = Query(default="47190"),
    period: int = Query(default=5, ge=1, le=10),
    pageNo: int = 1,
    numOfRows: int = 10,
):
    try:
        client = KecoEvChargerClient()

        payload = await client.get_charger_status(
            page_no=pageNo,
            num_of_rows=numOfRows,
            period=period,
            zcode=zcode,
            zscode=zscode,
        )

        items = extract_items(payload)

        return {
            "success": True,
            "message": "한국환경공단 충전기 상태 원본 데이터 조회 성공",
            "data": {
                "source": "KOREA_ENVIRONMENT_CORPORATION",
                "operation": "getChargerStatus",
                "pageNo": pageNo,
                "numOfRows": numOfRows,
                "period": period,
                "zcode": zcode,
                "zscode": zscode,
                "totalCount": payload.get("totalCount") or len(items),
                "items": items,
            },
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=repr(exc)) from exc