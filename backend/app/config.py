from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "VEXA Backend"
    environment: str = "development"
    database_url: str = "sqlite:///./vexa.db"
    secret_key: str = "CHANGE_ME_BEFORE_DEPLOYMENT"
    access_token_minutes: int = 60
    default_city_id: str = "obolensk"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
