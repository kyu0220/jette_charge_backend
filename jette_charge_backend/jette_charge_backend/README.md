# 제때차지 김종규 담당 백엔드 코드

담당 범위:
- 한국환경공단 getChargerInfo 파싱 및 연동
- 한국환경공단 getChargerStatus 파싱 및 Redis 캐싱
- 한국에너지공단 ELECTRIC_CHARGING 파싱 및 연동
- 앱에서 사용할 충전소 지도/주변/상세/상태 API 제공

## 실행 방법

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## 핵심 API

```text
GET  /api/v2/health
GET  /api/v2/dev/external/keco/charger-info
GET  /api/v2/dev/external/keco/charger-status
POST /api/v2/admin/stations/sync
POST /api/v2/admin/chargers/status/sync
GET  /api/v2/stations/map
GET  /api/v2/stations/nearby
GET  /api/v2/stations/{stationId}
GET  /api/v2/stations/{stationId}/chargers/status
GET  /api/v2/charging-stats/regions
```

## 팀원에게 설명할 데이터 흐름

1. `POST /api/v2/admin/stations/sync`를 호출하면 한국환경공단 `getChargerInfo`를 호출한다.
2. 응답을 충전소와 충전기로 분리해 DB에 저장한다.
3. `POST /api/v2/admin/chargers/status/sync`를 호출하면 한국환경공단 `getChargerStatus`를 호출한다.
4. 상태 데이터는 `charger:status:{stationId}:{chargerId}` 형태로 Redis에 저장한다.
5. 앱이 `GET /api/v2/stations/nearby` 또는 `GET /api/v2/stations/map`을 호출하면 DB의 정적 정보와 Redis의 상태 정보를 합쳐서 JSON으로 반환한다.

## 주의

- 인증키는 절대 Git에 올리지 말고 `.env`에만 넣으세요.
- Redis가 꺼져 있어도 서버는 동작하지만, 상태 API는 `UNKNOWN` 또는 DB 기준 fallback이 될 수 있습니다.
