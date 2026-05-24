import json
from typing import Any

import httpx

from app.core.config import get_settings

settings = get_settings()


class EnergyChargingClient:
    BASE_URL = "http://apis.data.go.kr/B553530/TRANSPORTATION/ELECTRIC_CHARGING"

    def __init__(self, service_key: str | None = None) -> None:
        self.service_key = service_key if service_key is not None else settings.energy_service_key

    async def get_electric_charging(
        self,
        *,
        page_no: int = 1,
        num_of_rows: int = 10,
        region_major: str | None = None,
        region_sub: str | None = None,
        api_type: str = "json",
    ) -> dict[str, Any]:
        if not self.service_key or self.service_key.startswith("YOUR_"):
            raise ValueError("ENERGY_SERVICE_KEY가 설정되지 않았습니다. .env 파일에 인증키를 넣어주세요.")

        params = {
            "serviceKey": self.service_key,
            "pageNo": page_no,
            "numOfRows": num_of_rows,
            "apiType": api_type,
            "q1": region_major,
            "q2": region_sub,
        }

        clean_params = {key: value for key, value in params.items() if value is not None and value != ""}

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(self.BASE_URL, params=clean_params)
            response.raise_for_status()

            # 공공데이터 응답 한글/JSON 파싱 안정화
            text = response.content.decode("utf-8-sig", errors="replace")

            try:
                return json.loads(text)
            except ValueError as exc:
                raise RuntimeError(f"한국에너지공단 JSON 응답 파싱 실패: {text[:500]}") from exc