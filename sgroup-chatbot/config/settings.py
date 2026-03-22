from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Gemini
    google_api_key: str = ""
    google_model: str = "gemini-2.5-flash"
    google_timeout_ms: int = 8000

    # OpenWeather
    openweather_api_key: str = ""
    weather_default_city: str = "Ho Chi Minh City"

    # Exa Search
    exa_api_key: str = ""

    # NewsAPI
    news_api_key: str = ""

    # Brave Search
    brave_api_key: str = ""

    # GitHub (optional, for IT knowledge agent)
    github_personal_access_token: str = ""

    # Knowledge base path
    data_dir: str = "../data"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
