from typing import Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("redis_url", "order_service_url", "payment_service_url", mode="before")
    @classmethod
    def clean_urls(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip('"').strip("'").strip()
            if v.lower() in ("none", "undefined", ""):
                return ""
            return v
        return v

    ai_agent_port: int = 8001
    redis_url: str = "redis://localhost:6379/0"

    order_service_url: str = "http://localhost:5000"
    payment_service_url: str = "http://localhost:5000"

    local_model_name: str = "groq"
    remote_model_name: str = "gpt-5"
    reasoning_complexity_threshold: int = 2
    enable_langgraph: bool = False

    single_restaurant_name: str = "NoHunger AI"

    enable_llm_chat: bool = True
    openai_api_key: str = ""
    openai_base_url: str = "https://api.groq.com/openai/v1"
    openai_chat_model: str = "openai/gpt-oss-120b"
    llm_timeout_seconds: float = 18.0
    llm_max_history_turns: int = 8

    enable_local_llm_chat: bool = True
    local_llm_type: str = "openai_api"
    local_llm_api_key: str = ""
    local_llm_base_url: str = "https://api.groq.com/openai/v1"
    local_llm_model: str = "openai/gpt-oss-120b"
    local_llm_timeout_seconds: float = 120.0


settings = Settings()
