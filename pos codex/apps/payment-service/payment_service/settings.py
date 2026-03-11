from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    payment_service_port: int = 8003
    payment_provider: str = "razorpay"
    payment_webhook_secret: str = "replace-with-secure-secret"
    order_service_url: str = "http://localhost:8002"


settings = Settings()
