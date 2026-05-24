# 김종규 담당 API 호출/응답 확인 가이드

## 1. 서버 실행

```bash
uvicorn app.main:app --reload
```

Swagger 확인:

```text
http://127.0.0.1:8000/docs
```

## 2. 충전소 정적 데이터 가져오기

한국환경공단 `getChargerInfo`를 호출하여 DB에 저장한다.

```http
POST /api/v2/admin/stations/sync
Content-Type: application/json
```

```json
{
  "zcode": "47",
  "zscode": "47190",
  "pageNo": 1,
  "numOfRows": 9999,
  "saveToMysql": true,
  "includeDeleted": false
}
```

응답 예시:

```json
{
  "success": true,
  "message": "충전소 정적 데이터 동기화 완료",
  "data": {
    "operation": "getChargerInfo",
    "stationUpsertCount": 35,
    "chargerUpsertCount": 92
  }
}
```

## 3. 충전기 상태 Redis에 저장하기

한국환경공단 `getChargerStatus`를 호출하여 Redis에 저장한다.

```http
POST /api/v2/admin/chargers/status/sync
Content-Type: application/json
```

```json
{
  "zcode": "47",
  "zscode": "47190",
  "period": 5,
  "force": true
}
```

Redis Key:

```text
charger:status:{stationId}:{chargerId}
```

Redis Value:

```json
{
  "stationId": "28260005",
  "chargerId": "02",
  "stat": "2",
  "status": "AVAILABLE",
  "statusLabel": "사용 가능",
  "statUpdDt": "20260421121020",
  "fetchedAt": "2026-05-10T14:21:27"
}
```

## 4. 앱에서 주변 충전소 조회하기

```http
GET /api/v2/stations/nearby?lat=36.1195&lng=128.3445&radius=3000&chargerSpeed=FAST&availableOnly=false
```

응답 핵심 구조:

```json
{
  "success": true,
  "data": {
    "center": {"lat": 36.1195, "lng": 128.3445},
    "stations": [
      {
        "stationId": "28260005",
        "stationName": "기후대기관",
        "lat": 37.56962,
        "lng": 126.641973,
        "distanceMeter": 430,
        "markerStatus": "AVAILABLE",
        "availableCount": 2,
        "totalChargerCount": 4,
        "maxOutput": 100
      }
    ]
  }
}
```

## 5. 앱에서 충전소 상세 조회하기

```http
GET /api/v2/stations/{stationId}
```

## 6. 앱에서 충전기 상태만 새로고침하기

```http
GET /api/v2/stations/{stationId}/chargers/status
```

캐시 상태:

| 값 | 의미 |
|---|---|
| HIT_FRESH | Redis에 있고 1분 이내 데이터 |
| HIT_STALE | Redis에 있지만 1분 초과 데이터 |
| MISS | Redis에 데이터 없음 |

## 7. 팀원에게 전달할 핵심

- 앱은 공공데이터 API를 직접 호출하지 않는다.
- 앱은 내부 API `/api/v2/stations/...`만 호출한다.
- 충전소 기본 정보는 MySQL에서 가져온다.
- 충전기 상태는 Redis에서 가져온다.
- Redis 데이터가 1분 이상 오래되면 기존 값을 먼저 반환하고 백그라운드 갱신 대상으로 본다.
