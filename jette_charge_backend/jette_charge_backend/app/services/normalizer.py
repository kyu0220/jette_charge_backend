from decimal import Decimal
from typing import Any

from app.models.charging import Charger, ChargingStation
from app.utils.mapping import (
    format_keco_datetime,
    get_charger_type_info,
    get_status_info,
    speed_type_from_output,
    to_float,
)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, Decimal):
        return float(value)

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _yn_to_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None

    return str(value).strip().upper() == "Y"


def charger_to_response(
    charger: Charger,
    redis_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    type_info = get_charger_type_info(charger.chger_type)
    output = charger.output
    status_info = get_status_info(redis_status.get("stat") if redis_status else "0")

    return {
        "chargerId": charger.chger_id,
        **type_info,
        "speedType": speed_type_from_output(output, charger.chger_type),
        "output": output,
        "method": charger.method,
        "statusCode": status_info["statusCode"],
        "status": status_info["status"],
        "statusLabel": status_info["statusLabel"],
        "statusUpdatedAt": format_keco_datetime(redis_status.get("statUpdDt")) if redis_status else None,
    }


def summarize_charger_statuses(chargers: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(chargers)
    available = sum(1 for c in chargers if c.get("status") == "AVAILABLE")
    charging = sum(1 for c in chargers if c.get("status") == "CHARGING")
    unavailable = total - available - charging

    if available > 0:
        marker_status = "AVAILABLE"
        marker_color = "GREEN"
    elif charging > 0:
        marker_status = "CHARGING"
        marker_color = "YELLOW"
    elif total > 0:
        marker_status = "UNAVAILABLE"
        marker_color = "RED"
    else:
        marker_status = "UNKNOWN"
        marker_color = "GRAY"

    return {
        "totalChargerCount": total,
        "availableCount": available,
        "chargingCount": charging,
        "unavailableCount": unavailable,
        "markerStatus": marker_status,
        "markerColor": marker_color,
    }


def station_to_summary(
    station: ChargingStation,
    chargers: list[dict[str, Any]],
    distance_meter: int | None = None,
) -> dict[str, Any]:
    summary = summarize_charger_statuses(chargers)
    outputs = [c.get("output") for c in chargers if isinstance(c.get("output"), (int, float))]

    return {
        "stationId": station.stat_id,
        "stationName": station.stat_nm,
        "address": station.addr,
        "lat": _as_float(station.lat),
        "lng": _as_float(station.lng),
        "distanceMeter": distance_meter,
        "useTime": station.use_time,
        # 최종 station 스키마에는 bnm/busi_nm이 없으므로 busi_id를 운영기관 표시값으로 사용
        "operatorName": station.busi_id,
        "businessName": station.busi_id,
        "parkingFree": _yn_to_bool(station.parking_free),
        **summary,
        "maxOutput": max(outputs) if outputs else None,
    }


def station_to_detail(
    station: ChargingStation,
    chargers: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = summarize_charger_statuses(chargers)

    return {
        "stationId": station.stat_id,
        "stationName": station.stat_nm,
        "address": station.addr,
        "addressDetail": None,
        "location": None,
        "lat": _as_float(station.lat),
        "lng": _as_float(station.lng),
        "useTime": station.use_time,
        "operatorId": station.busi_id,
        "operatorName": station.busi_id,
        "businessName": station.busi_id,
        "businessCall": None,
        "parkingFree": _yn_to_bool(station.parking_free),
        "limitYn": _yn_to_bool(station.limit_yn),
        "limitDetail": station.limit_detail,
        "note": None,
        **summary,
        "chargers": chargers,
    }


def normalize_keco_status_item(item: dict[str, Any]) -> dict[str, Any]:
    status_info = get_status_info(item.get("stat"))

    return {
        "stationId": str(item.get("statId", "")).strip(),
        "chargerId": str(item.get("chgerId", "")).strip().zfill(2),
        "busiId": item.get("busiId"),
        "stat": status_info["statusCode"],
        "status": status_info["status"],
        "statusLabel": status_info["statusLabel"],
        "statUpdDt": item.get("statUpdDt"),
        "lastTsdt": item.get("lastTsdt"),
        "lastTedt": item.get("lastTedt"),
        "nowTsdt": item.get("nowTsdt"),
    }


def normalize_energy_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "regionMajor": item.get("RGN_MST"),
        "regionSub": item.get("RGN_SUB"),
        "fast50kwCount": to_float(item.get("ITEM_1")),
        "fast100kwSingleCount": to_float(item.get("ITEM_2")),
        "fast100kwDualCount": to_float(item.get("ITEM_3")),
        "fast200kwDualCount": to_float(item.get("ITEM_4")),
        "fast300kwPlusCount": to_float(item.get("ITEM_5")),
        "usageAmount": to_float(item.get("ITEM_6")),
        "dataRegisteredAt": item.get("DATA_REG_DT"),
    }