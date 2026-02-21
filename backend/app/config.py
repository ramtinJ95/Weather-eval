from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="WEATHER_EVAL_")

    app_name: str = "weather-eval"
    frontend_origin: str = "http://localhost:5173"

    firestore_project_id: str | None = None
    firestore_collection: str = "app"
    firestore_document: str = "hello"
    default_hello_message: str = "Hello from fallback (Firestore not configured yet)."


settings = Settings()
