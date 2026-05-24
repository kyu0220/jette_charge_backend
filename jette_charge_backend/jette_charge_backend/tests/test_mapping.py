from app.utils.mapping import extract_items, get_charger_type_info, get_status_info, speed_type_from_output
from app.services.normalizer import normalize_keco_status_item, normalize_energy_item


def test_status_mapping():
    assert get_status_info("2")["status"] == "AVAILABLE"
    assert get_status_info("3")["statusLabel"] == "충전 중"


def test_charger_type_mapping():
    info = get_charger_type_info("04")
    assert info["chargerType"] == "DC_COMBO"


def test_speed_type():
    assert speed_type_from_output(7, "02") == "SLOW"
    assert speed_type_from_output(50, "04") == "FAST"


def test_extract_items_root():
    payload = {"items": {"item": [{"a": 1}]}}
    assert extract_items(payload) == [{"a": 1}]


def test_normalize_status():
    item = {"statId": "S1", "chgerId": "01", "stat": "2", "statUpdDt": "20260421121020"}
    normalized = normalize_keco_status_item(item)
    assert normalized["stationId"] == "S1"
    assert normalized["status"] == "AVAILABLE"


def test_normalize_energy():
    item = {"RGN_MST": "경상북도", "RGN_SUB": "구미시", "ITEM_1": "1", "ITEM_6": "19655.15"}
    normalized = normalize_energy_item(item)
    assert normalized["regionMajor"] == "경상북도"
    assert normalized["usageAmount"] == 19655.15
