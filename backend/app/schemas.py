from pydantic import BaseModel, Field


class PointMetricsRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    year: int = Field(ge=2023, le=2100)
    month: int = Field(ge=1, le=12)


class PointInfo(BaseModel):
    lat: float
    lon: float
    h3_r7: str


class CloudInterpolationInfo(BaseModel):
    nearest_station_name: str
    nearest_station_distance_km: float


class DayMetric(BaseModel):
    date: str
    cloud_mean_pct: float | None = None
    lightning_count: int = 0


class MonthMetric(BaseModel):
    month: int
    cloud_mean_pct: float | None = None
    lightning_probability: float = 0.0
    lightning_count: int = 0


class YearMetric(BaseModel):
    year: int
    cloud_mean_pct: float | None = None
    lightning_probability: float = 0.0
    lightning_count: int = 0


class DailyMetrics(BaseModel):
    days: list[DayMetric]


class MonthlyMetrics(BaseModel):
    months: list[MonthMetric]


class YearlyMetrics(BaseModel):
    years: list[YearMetric]


class PointMetricsResponse(BaseModel):
    point: PointInfo
    cloud_interpolation: CloudInterpolationInfo | None
    daily: DailyMetrics
    monthly: MonthlyMetrics
    yearly: YearlyMetrics
