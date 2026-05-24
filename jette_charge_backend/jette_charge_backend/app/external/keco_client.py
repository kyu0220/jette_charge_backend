from typing import Any
from urllib.parse import unquote

import httpx

from app.core.config import get_settings

settings = get_settings()


class KecoEvChargerClient:
    BASE_URL = "http://apis.data.go.kr/B552584/EvCharger"

    def __init__(self, service_key: str | None = None) -> None:
        raw_key = service_key if service_key is not None else settings.keco_service_key
        self.service_key = unquote(raw_key) if raw_key else ""

    async def get_charger_info(
        self,
        *,
        page_no: int = 1,
        num_of_rows: int = 10,
        zcode: str | None = None,
        zscode: str | None = None,
        stat_id: str | None = None,
        chger_id: str | None = None,
        data_type: str = "JSON",
    ) -> dict[str, Any]:
        return await self._get(
            "/getChargerInfo",
            {
                "serviceKey": self.service_key,
                "pageNo": page_no,
                "numOfRows": num_of_rows,
                "zcode": zcode,
                "zscode": zscode,
                "statId": stat_id,
                "chgerId": chger_id,
                "dataType": data_type,
            },
        )

    async def get_charger_status(
        self,
        *,
        page_no: int = 1,
        num_of_rows: int = 10,
        period: int = 5,
        zcode: str | None = None,
        zscode: str | None = None,
        stat_id: str | None = None,
        chger_id: str | None = None,
        data_type: str = "JSON",
    ) -> dict[str, Any]:
        return await self._get(
            "/getChargerStatus",
            {
                "serviceKey": self.service_key,
                "pageNo": page_no,
                "numOfRows": num_of_rows,
                "period": period,
                "zcode": zcode,
                "zscode": zscode,
                "statId": stat_id,
                "chgerId": chger_id,
                "dataType": data_type,
            },
        )

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.service_key or self.service_key.startswith("YOUR_"):
            raise ValueError(
                "KECO_SERVICE_KEY가 설정되지 않았습니다. .env 파일에 인증키를 넣어주세요."
            )

        clean_params = {
            key: value
            for key, value in params.items()
            if value is not None and value != ""
        }

        timeout = httpx.Timeout(
            connect=10.0,
            read=60.0,
            write=10.0,
            pool=10.0,
        )

        last_error: Exception | None = None

        for attempt in range(1, 4):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    request = client.build_request(
                        "GET",
                        f"{self.BASE_URL}{path}",
                        params=clean_params,
                    )

                    # 디버깅용 출력
                    # 터미널에서 실제 한국환경공단 API 요청 URL을 확인하기 위함
                    print("KECO REQUEST URL:", request.url)

                    response = await client.send(request)
                    response.raise_for_status()

                    try:
                        payload = response.json()
                    except ValueError as exc:
                        raise RuntimeError(
                            f"한국환경공단 JSON 응답 파싱 실패: {response.text[:500]}"
                        ) from exc

                result_code = str(
                    payload.get("resultCode")
                    or payload.get("response", {}).get("header", {}).get("resultCode")
                    or ""
                )

                result_msg = str(
                    payload.get("resultMsg")
                    or payload.get("response", {}).get("header", {}).get("resultMsg")
                    or ""
                )

                if result_code and result_code not in {"00", "0"}:
                    raise RuntimeError(
                        f"한국환경공단 API 오류: resultCode={result_code}, resultMsg={result_msg}"
                    )

                return payload

            except httpx.ReadTimeout as exc:
                last_error = exc

                if attempt == 3:
                    raise RuntimeError(
                        "한국환경공단 API 응답 시간이 초과되었습니다. "
                        "잠시 후 다시 시도하거나 요청 파라미터를 확인해주세요."
                    ) from exc

            except httpx.ConnectTimeout as exc:
                last_error = exc

                if attempt == 3:
                    raise RuntimeError(
                        "한국환경공단 API 연결 시간이 초과되었습니다. "
                        "네트워크 상태 또는 공공데이터 API 서버 상태를 확인해주세요."
                    ) from exc

            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"한국환경공단 HTTP 오류: "
                    f"status={exc.response.status_code}, "
                    f"body={exc.response.text[:500]}"
                ) from exc

        raise RuntimeError(f"한국환경공단 API 호출 실패: {repr(last_error)}")