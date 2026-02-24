from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="WEATHER_EVAL_")

    app_name: str = "weather-eval"
    frontend_origin: str = "http://localhost:5173"

    weather_data_dir: Path = Path(__file__).resolve().parents[1] / "data"
    processed_data_dir: Path = Path(__file__).resolve().parents[1] / "data" / "processed"
    weather_start_year: int = 2023
    weather_h3_resolution: int = 7

    sweden_min_lat: float = 55.0
    sweden_max_lat: float = 69.5
    sweden_min_lon: float = 10.5
    sweden_max_lon: float = 24.5


settings = Settings()
