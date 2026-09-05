"""Central configuration — Pydantic Settings, never hardcoded secrets."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "RecoverPay AI"
    app_version: str = "1.0.0"
    environment: str = "dev"  # dev | staging | production
    database_url: str = "sqlite+aiosqlite:///./recoverpay.db"

    # Auth
    jwt_secret: str = "change-me-in-production-please-really"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    # Redis (optional — falls back to in-process stores)
    redis_url: str = ""

    # Razorpay (test mode). Empty => in-app test checkout that runs the same capture path.
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    # Channels
    resend_api_key: str = ""
    email_from: str = "RecoverPay <billing@recoverpay.ai>"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_sms: str = ""
    twilio_from_whatsapp: str = "whatsapp:+14155238886"
    twilio_whatsapp_content_sid: str = ""
    twilio_whatsapp_content_variables_json: str = ""
    twilio_voice_from: str = ""
    twilio_voice_to: str = ""

    # Vonage Messages API Sandbox (WhatsApp fallback)
    vonage_application_id: str = ""
    vonage_private_key_path: str = "./private.key"
    vonage_whatsapp_from: str = ""
    vonage_whatsapp_to: str = ""
    vonage_voice_from: str = ""
    vonage_voice_to: str = ""

    public_base_url: str = ""

    # LLM (optional — deterministic fallbacks otherwise). Gemini has a free tier:
    # key from https://aistudio.google.com/apikey
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-latest"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"

    # Demo contacts marked live at seed time
    founder_email: str = "syedsuhailm786@gmail.com"
    founder_phone: str = "+919380962272"

    # CORS: explicit origins only (no wildcard in production)
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Scheduler
    auto_tick: bool = True
    tick_interval_minutes: int = 5

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def razorpay_live(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()
