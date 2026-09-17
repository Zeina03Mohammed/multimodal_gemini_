"""
Central settings for the whole app.

Why this file exists:
Instead of every file doing `os.environ["ANTHROPIC_API_KEY"]` (typo-prone,
no validation, hard to find), we declare the settings ONCE here as a typed
class. pydantic-settings automatically reads matching values from the .env
file / real environment variables and validates them for us.

Everywhere else in the app, we just do:
    from app.config import settings
    settings.gemini_api_key
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str
    gemini_model: str = "gemini-3.6-flash"
    chroma_db_path: str = "data/chroma_db"

    # Tells pydantic-settings: "load values from a file named .env,
    # and match field names case-insensitively to env var names."
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Created once, on import, and reused everywhere (this is called a
# "singleton" pattern - one shared instance instead of many copies).
settings = Settings()
