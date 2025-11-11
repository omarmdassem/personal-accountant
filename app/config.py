import os  # lets us read environment variables (from the OS)
from functools import (
    lru_cache,  # tiny built-in cache; we use it to reuse one Settings object
)

from dotenv import load_dotenv  # loads variables from a local .env file
from pydantic import BaseModel  # Pydantic gives us a typed, validated settings class

load_dotenv()  # read .env and put those key=value pairs into environment variables


class Settings(BaseModel):  # our typed container for config values
    # read SECRET_KEY from env; if missing, fall back to this default
    # change effect: new value changes how sessions/tokens are signed (must be secret)
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change")

    # database connection string; default is a SQLite file in the project folder
    # change effect: point to a different DB (e.g., Postgres) or file path
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")

    # the cookie name used to store the session ID in the browser
    # change effect: renames the cookie (harmless); users will be logged out on rename
    session_cookie: str = os.getenv("SESSION_COOKIE_NAME", "pa_session")

    # the default currency we convert into on the dashboard
    # change effect: changes the base currency label and conversions
    base_currency: str = os.getenv("BASE_CURRENCY", "EUR")


@lru_cache  # make sure Settings() is created once and reused (fast + consistent)
def get_settings() -> Settings:
    return Settings()  # build from env (already loaded by load_dotenv())
