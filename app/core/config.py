import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Sistema ESAVI v2"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Database
    DATABASE_URL: str = "postgresql://esavi_user:esavi_password@10.0.0.3:5432/esavi_db"

    # Security & JWT
    SECRET_KEY: str = "cambiar_por_clave_secreta_super_segura_de_produccion_64bytes"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 horas
    COOKIE_NAME: str = "esavi_access_token"
    COOKIE_SECURE: bool = False  # True en producción con HTTPS

    # Initial Admin
    FIRST_SUPERUSER_USERNAME: str = "admin"
    FIRST_SUPERUSER_EMAIL: Optional[str] = "admin@esavi.salud.gob.mx"
    FIRST_SUPERUSER_PASSWORD: str = "AdminEsavi2026!"
    FIRST_SUPERUSER_NAME: str = "Administrador del Sistema"

    # Export configuration
    COLUMNS_CONFIG_PATH: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config",
        "concentrado_columns.json"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
