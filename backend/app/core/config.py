from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg:///zyorachit"
    jwt_secret_key: str = "development-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    login_attempt_limit: int = 5
    login_attempt_window_minutes: int = 15
    otp_send_limit: int = 5
    otp_send_window_minutes: int = 60
    otp_secret_key: str = "development-otp-secret-change-me"
    otp_expire_minutes: int = 10
    zeptomail_api_url: str = "https://api.zeptomail.in/v1.1/email"
    zeptomail_send_token: str = ""
    zeptomail_from_email: str = ""
    zeptomail_from_name: str = "zChit"
    upload_directory: str = "uploads"
    max_logo_size_mb: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
