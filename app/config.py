import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
STATIC_DIR = APP_DIR / "static"
TEMPLATES_DIR = APP_DIR / "templates"
SERVICES_IMG_DIR = STATIC_DIR / "images" / "services"

if IS_VERCEL:
    UPLOADS_DIR = Path("/tmp/uploads")
    DB_PATH = Path("/tmp/usta_xizmati.db")
else:
    UPLOADS_DIR = STATIC_DIR / "uploads"
    DB_PATH = BASE_DIR / "usta_xizmati.db"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
SERVICES_IMG_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    APP_TITLE: str = "UstaBor - Professional Usta Chaqirish Xizmati"
    HOST: str = "127.0.0.1"
    PORT: int = 5002
    CLIENT_PORT: int = 5003
    ADMIN_PORT: int = 5004
    SECRET_KEY: str = "ustabor-super-secret-change-in-production-2026"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    TELEGRAM_BOT_TOKEN: str = ""
    ADMIN_TELEGRAM_IDS: str = ""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
