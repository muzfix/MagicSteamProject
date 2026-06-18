from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql://mtguser:mtgpass@localhost:5432/mtg_marketplace"
    SECRET_KEY: str = "CHANGE_THIS_IN_PRODUCTION"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 259200  # 6 months
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    SCRYFALL_BASE_URL: str = "https://api.scryfall.com"
    ENVIRONMENT: str = "development"

    TAP_SECRET_KEY: str = ""
    TAP_WEBHOOK_SECRET: str = ""
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""


settings = Settings()
