
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "VEXA Backend"

    environment: str = "development"

    database_url: str = "sqlite:///./vexa.db"

    secret_key: str = "CHANGE_ME_BEFORE_DEPLOYMENT"

    access_token_minutes: int = Field(default=60, gt=0)

    # Настройки маршрутизации
    routing_provider: str = "osrm"

    osrm_base_url: str = ""
    osrm_timeout_seconds: float = Field(
        default=8.0,
        gt=0,
        le=30,
    )

    routing_timeout_seconds: float = Field(
        default=8.0,
        gt=0,
        le=30,
    )

    two_gis_api_key: str = ""
    yandex_api_key: str = ""

    default_city_id: str = "obolensk"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
    )

    @model_validator(mode="after")
    def validate_production_settings(self):
        environment = self.environment.strip().lower()

        if environment in {"production", "prod"}:
            if (
                self.secret_key == "CHANGE_ME_BEFORE_DEPLOYMENT"
                or len(self.secret_key) < 32
            ):
                raise ValueError(
                    "Production requires a SECRET_KEY "
                    "of at least 32 characters."
                )

            if self.database_url.startswith("sqlite"):
                raise ValueError(
                    "Production must use PostgreSQL, not SQLite."
                )

        if not self.default_city_id.strip():
            raise ValueError(
                "DEFAULT_CITY_ID cannot be empty."
            )

        provider = self.routing_provider.strip().lower()

        allowed_providers = {
            "osrm",
            "2gis",
            "two_gis",
            "2гис",
            "yandex",
            "yandex_maps",
            "яндекс",
        }

        if provider not in allowed_providers:
            raise ValueError(
                f"Unsupported ROUTING_PROVIDER: {provider}"
            )

        return self


settings = Settings()
