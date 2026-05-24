from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ChargingStation(Base):
    """
    DB 최종 스키마 기준: station
    """

    __tablename__ = "station"

    stat_id: Mapped[str] = mapped_column(String(8), primary_key=True)
    stat_nm: Mapped[str] = mapped_column(String(100), nullable=False)
    lat: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    lng: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    addr: Mapped[str | None] = mapped_column(String(200))
    use_time: Mapped[str | None] = mapped_column(String(100))
    busi_id: Mapped[str | None] = mapped_column(String(10))
    parking_free: Mapped[str | None] = mapped_column(String(1))
    limit_yn: Mapped[str | None] = mapped_column(String(1))
    limit_detail: Mapped[str | None] = mapped_column(String(100))

    chargers: Mapped[list["Charger"]] = relationship(
        back_populates="station",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Charger(Base):
    """
    DB 최종 스키마 기준: charger
    """

    __tablename__ = "charger"
    __table_args__ = (
        UniqueConstraint("stat_id", "chger_id", name="uq_charger_station_chger"),
    )

    charger_pk: Mapped[str] = mapped_column(String(20), primary_key=True)
    stat_id: Mapped[str] = mapped_column(String(8), ForeignKey("station.stat_id"), index=True)
    chger_id: Mapped[str] = mapped_column(String(2), nullable=False)
    chger_type: Mapped[str | None] = mapped_column(String(2))
    output: Mapped[int | None] = mapped_column(Integer)
    method: Mapped[str | None] = mapped_column(String(20))

    station: Mapped[ChargingStation] = relationship(back_populates="chargers")


class Toilet(Base):
    """
    DB 최종 스키마 기준: toilet

    김종규 담당 충전소 API에서는 직접 사용하지 않지만,
    팀 공통 DB 스키마와 명칭을 맞추기 위해 모델에 포함한다.
    """

    __tablename__ = "toilet"

    amenity_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(200))
    lat: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    lng: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    operating_hours: Mapped[str | None] = mapped_column(String(50))
    has_disabled: Mapped[int | None] = mapped_column(Integer)
    has_diaper_table: Mapped[int | None] = mapped_column(Integer)


class RegionalChargingStat(Base):
    """
    한국에너지공단 지역별 급속충전기 통계용 테이블.
    화면에 제시된 station/charger/toilet 스키마와 별도로 사용한다.
    """

    __tablename__ = "regional_charging_stats"
    __table_args__ = (
        UniqueConstraint(
            "region_major",
            "region_sub",
            "data_registered_at",
            name="uq_regional_stat",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_major: Mapped[str | None] = mapped_column(String(100), index=True)
    region_sub: Mapped[str | None] = mapped_column(String(100), index=True)
    fast_50kw_count: Mapped[float | None] = mapped_column(Numeric(10, 2))
    fast_100kw_single_count: Mapped[float | None] = mapped_column(Numeric(10, 2))
    fast_100kw_dual_count: Mapped[float | None] = mapped_column(Numeric(10, 2))
    fast_200kw_dual_count: Mapped[float | None] = mapped_column(Numeric(10, 2))
    fast_300kw_plus_count: Mapped[float | None] = mapped_column(Numeric(10, 2))
    usage_amount: Mapped[float | None] = mapped_column(Numeric(15, 2))
    data_registered_at: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)