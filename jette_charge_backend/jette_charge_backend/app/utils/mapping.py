from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from typing import Any

STATUS_MAP = {
    "0": ("UNKNOWN", "알 수 없음", "GRAY"),
    "1": ("COMMUNICATION_ERROR", "통신 이상", "GRAY"),
    "2": ("AVAILABLE", "사용 가능", "GREEN"),
    "3": ("CHARGING", "충전 중", "YELLOW"),
    "4": ("STOPPED", "운영 중지", "RED"),
    "5": ("INSPECTION", "점검 중", "RED"),
}

CHARGER_TYPE_MAP = {
    "01": ("CHADEMO", "DC차데모"),
    "02": ("AC_SLOW", "AC완속"),
    "03": ("CHADEMO_AC3", "DC차데모+AC3상"),
    "04": ("DC_COMBO", "DC콤보"),
    "05": ("CHADEMO_DC_COMBO", "DC차데모+DC콤보"),
    "06": ("CHADEMO_AC3_DC_COMBO", "DC차데모+AC3상+DC콤보"),
    "07": ("AC3", "AC3상"),
    "08": ("DC_COMBO_SLOW", "DC콤보(완속)"),
    "09": ("NACS", "NACS"),
    "10": ("DC_COMBO_NACS", "DC콤보+NACS"),
    "11": ("DC_COMBO2_BUS", "DC콤보2(버스전용)"),
}

REGION_NAME_BY_ZSCODE = {
    "47190": "구미시",
    "47150": "김천시",
    "47850": "칠곡군",
}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def yn_to_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    return str(value).strip().upper() == "Y"


def to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def format_keco_datetime(value: Any) -> str | None:
    if not value:
        return None

    text = str(value).strip()

    if len(text) != 14 or not text.isdigit():
        return text

    try:
        dt = datetime.strptime(text, "%Y%m%d%H%M%S")
        return dt.isoformat()
    except ValueError:
        return text


def get_status_info(stat: Any) -> dict[str, str]:
    status_code = str(stat).strip() if stat is not None else "0"
    status, label, color = STATUS_MAP.get(status_code, STATUS_MAP["0"])

    return {
        "statusCode": status_code,
        "status": status,
        "statusLabel": label,
        "markerColor": color,
    }


def get_charger_type_info(chger_type: Any) -> dict[str, str | None]:
    code = str(chger_type).zfill(2) if chger_type is not None and str(chger_type).strip() else None

    if code and code in CHARGER_TYPE_MAP:
        value, label = CHARGER_TYPE_MAP[code]
    else:
        value, label = "UNKNOWN", "알 수 없음"

    return {
        "chargerTypeCode": code,
        "chargerType": value,
        "chargerTypeLabel": label,
    }


def speed_type_from_output(output: float | None, chger_type: str | None) -> str:
    # 한국환경공단 기준 02 AC완속, 08 DC콤보(완속)은 완속 취급
    if chger_type in {"02", "08"}:
        return "SLOW"

    if output is not None and output <= 11:
        return "SLOW"

    return "FAST"


def distance_meter(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    radius = 6371000

    d_lat = radians(lat2 - lat1)
    d_lng = radians(lng2 - lng1)

    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lng / 2) ** 2
    )

    return int(2 * radius * asin(sqrt(a)))


def _looks_like_api_item(value: dict[str, Any]) -> bool:
    """
    공공데이터 item 1건처럼 보이는 dict인지 확인한다.
    한국환경공단, 한국에너지공단 응답을 모두 처리하기 위한 함수.
    """
    item_keys = {
        # 한국환경공단
        "statId",
        "statNm",
        "chgerId",
        "addr",
        "lat",
        "lng",
        "stat",
        # 한국에너지공단
        "RGN_MST",
        "RGN_SUB",
        "ITEM_1",
        "ITEM_2",
        "ITEM_3",
        "ITEM_4",
        "ITEM_5",
        "ITEM_6",
        "DATA_REG_DT",
    }

    return any(key in value for key in item_keys)


def _collect_items_recursively(value: Any) -> list[dict[str, Any]]:
    """
    공공데이터 API마다 JSON 구조가 다르기 때문에 재귀적으로 item 후보를 찾는다.
    """
    results: list[dict[str, Any]] = []

    if isinstance(value, list):
        for element in value:
            if isinstance(element, dict) and _looks_like_api_item(element):
                results.append(element)
            else:
                results.extend(_collect_items_recursively(element))

    elif isinstance(value, dict):
        if _looks_like_api_item(value):
            results.append(value)
        else:
            for child in value.values():
                results.extend(_collect_items_recursively(child))

    return results


def extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    공공데이터 API 응답에서 item 목록을 추출한다.

    처리 가능한 구조 예시:
    1. {"items": {"item": [...]}}
    2. {"response": {"body": {"items": {"item": [...]}}}}
    3. {"body": {"items": [...]}}
    4. {"data": [...]}
    5. {"DATA": [...]}
    6. item 1개가 dict로 오는 경우
    """
    candidates = [
        payload.get("items"),
        payload.get("item"),
        payload.get("data"),
        payload.get("DATA"),
        payload.get("response", {}).get("body", {}).get("items"),
        payload.get("response", {}).get("body", {}).get("item"),
        payload.get("response", {}).get("body", {}).get("data"),
        payload.get("response", {}).get("body", {}).get("DATA"),
        payload.get("body", {}).get("items"),
        payload.get("body", {}).get("item"),
        payload.get("body", {}).get("data"),
        payload.get("body", {}).get("DATA"),
    ]

    for candidate in candidates:
        if candidate is None:
            continue

        if isinstance(candidate, dict) and "item" in candidate:
            items = [x for x in as_list(candidate.get("item")) if isinstance(x, dict)]
            if items:
                return items

        if isinstance(candidate, list):
            items = [x for x in candidate if isinstance(x, dict)]
            if items:
                return items

        if isinstance(candidate, dict) and _looks_like_api_item(candidate):
            return [candidate]

        recursive_items = _collect_items_recursively(candidate)
        if recursive_items:
            return recursive_items

    return _collect_items_recursively(payload)


def extract_total_count(payload: dict[str, Any], fallback: int = 0) -> int:
    """
    공공데이터 API 응답에서 totalCount를 최대한 안전하게 추출한다.
    """
    candidates = [
        payload.get("totalCount"),
        payload.get("response", {}).get("body", {}).get("totalCount"),
        payload.get("body", {}).get("totalCount"),
        payload.get("TOTAL_COUNT"),
        payload.get("total_count"),
    ]

    for candidate in candidates:
        if candidate is None or candidate == "":
            continue

        try:
            return int(candidate)
        except (TypeError, ValueError):
            continue

    return fallback