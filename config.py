
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "VEXA Backend"
    environment: str = "development"
    database_url: str = "sqlite:///./vexa.db"
    secret_key: str = "CHANGE_ME_BEFORE_DEPLOYMENT"

    access_token_minutes: int = Field(default=60, gt=0)

    # Маршрутизация
    routing_provider: str = "osrm"
    osrm_base_url: str = ""
    osrm_timeout_seconds: float = Field(default=8.0, gt=0, le=30)
    routing_timeout_seconds: float = Field(default=8.0, gt=0, le=30)
    yandex_api_key: str = ""
    default_city_id: str = "obolensk"

    # SMS-авторизация пассажиров
    sms_auth_primary_provider: str = "sms_aero"
    sms_auth_session_minutes: int = Field(default=5, gt=0, le=15)
    sms_auth_max_attempts: int = Field(default=5, gt=0, le=10)
    sms_auth_max_requests_per_hour: int = Field(
        default=3,
        gt=0,
        le=10,
    )

    # One dedicated background matcher, independent from HTTP application.
    dispatch_search_timeout_seconds: int = Field(default=180, ge=30, le=1800)
    dispatch_poll_interval_seconds: float = Field(default=2.0, ge=0.5, le=30)
    dispatch_batch_size: int = Field(default=100, ge=1, le=500)

    # Fail-closed by default; dev-only opt-out is explicit and forbidden in production.
    legal_dispatch_enforcement: bool = True

    public_api_base_url: str = "https://45.143.139.162"

    # SMS Aero
    sms_aero_email: str = ""
    sms_aero_api_key: str = ""
    sms_aero_sign: str = "SMS Aero"

    # SMSGold
    smsgold_user: str = ""
    smsgold_pass: str = ""

    # Секрет для callback-путей провайдеров.
    # Заменить длинным случайным значением до включения SMS.
    sms_auth_callback_secret: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
    )

    @model_validator(mode="after")
    def validate_settings(self):
        environment = self.environment.strip().lower()

        if environment in {"production", "prod"}:
            if not self.legal_dispatch_enforcement:
                raise ValueError("Production requires LEGAL_DISPATCH_ENFORCEMENT=true")
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
            raise ValueError("DEFAULT_CITY_ID cannot be empty.")

        provider = self.routing_provider.strip().lower()

        allowed_providers = {
            "osrm",
            "yandex",
            "yandex_maps",
            "яндекс",
        }

        if provider not in allowed_providers:
            raise ValueError(
                f"Unsupported ROUTING_PROVIDER: {provider}"
            )

        if self.sms_auth_primary_provider not in {
            "sms_aero",
            "smsgold",
        }:
            raise ValueError(
                "SMS_AUTH_PRIMARY_PROVIDER must be sms_aero or smsgold"
            )

        return self


settings = Settings()
