from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Gemini
    google_api_key: str = ""
    google_model: str = "gemini-2.5-flash"
    google_timeout_ms: int = 8000

    # Groq LLM
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    llm_timeout_ms: int = 12000
    groq_models: str = (
        "allam-2-7b,"
        "groq/compound,"
        "groq/compound-mini,"
        "llama-3.1-8b-instant,"
        "llama-3.3-70b-versatile,"
        "meta-llama/llama-4-scout-17b-16e-instruct,"
        "meta-llama/llama-prompt-guard-2-22m,"
        "meta-llama/llama-prompt-guard-2-86m,"
        "moonshotai/kimi-k2-instruct,"
        "moonshotai/kimi-k2-instruct-0905,"
        "openai/gpt-oss-120b,"
        "openai/gpt-oss-20b,"
        "openai/gpt-oss-safeguard-20b,"
        "qwen/qwen3-32b"
    )

    # OpenWeather
    openweather_api_key: str = ""
    weather_default_city: str = "Ho Chi Minh City"

    # Visual Crossing Weather
    visualcrossing_api_key: str = "FXYZEBLW5H9YWE75XG8N84UTN"

    # Exa Search
    exa_api_key: str = ""

    # NewsAPI
    news_api_key: str = ""

    # Brave Search
    brave_api_key: str = ""

    # GitHub (optional, for IT knowledge agent)
    github_personal_access_token: str = ""

    # External MCP servers (optional, for IT knowledge agent)
    external_mcp_enabled: bool = False
    external_mcp_config_path: str = "mcp-external-servers.json"
    external_mcp_timeout_ms: int = 15000

    # Knowledge base path
    data_dir: str = "../data"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
