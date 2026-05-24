from app.external.energy_client import EnergyChargingClient
from app.services.normalizer import normalize_energy_item
from app.utils.mapping import extract_items, extract_total_count


class EnergyService:
    def __init__(self) -> None:
        self.client = EnergyChargingClient()

    async def list_region_stats(
        self,
        region_major: str | None,
        region_sub: str | None,
        page: int,
        size: int,
    ) -> dict:
        payload = await self.client.get_electric_charging(
            page_no=page,
            num_of_rows=size,
            region_major=region_major,
            region_sub=region_sub,
        )

        items = extract_items(payload)

        normalized_regions = [
            normalize_energy_item(item)
            for item in items
        ]

        # 혹시 외부 API가 필터를 제대로 적용하지 않고 전체를 내려줄 경우를 대비해
        # 백엔드에서 한 번 더 필터링한다.
        if region_major:
            normalized_regions = [
                region
                for region in normalized_regions
                if region.get("regionMajor") == region_major
            ]

        if region_sub:
            normalized_regions = [
                region
                for region in normalized_regions
                if region.get("regionSub") == region_sub
            ]

        return {
            "page": page,
            "size": size,
            "totalCount": extract_total_count(payload, fallback=len(normalized_regions)),
            "regions": normalized_regions,
        }