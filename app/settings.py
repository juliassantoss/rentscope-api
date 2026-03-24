from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from_email: str
    smtp_from_name: str = "RentScope"
    smtp_use_tls: bool = True

    backend_base_url: str = "http://127.0.0.1:8000"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()