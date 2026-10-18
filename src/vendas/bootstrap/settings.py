from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Banco de Dados
    DATABASE_URL: str

    # Flags de Segurança e Operação (DRY_RUN obrigatório como True por padrão)
    DRY_RUN: bool = True
    AUTOMATION_ENABLED: bool = False

    # Orçamentos Diários dos Provedores
    APIFY_DAILY_BUDGET: float = 10.0
    FIRECRAWL_DAILY_BUDGET: float = 10.0
    GEMINI_DAILY_BUDGET: float = 10.0

    # Chaves e Endpoints Externos
    APIFY_API_KEY: str = ""
    FIRECRAWL_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    EVOLUTION_API_URL: str = "http://localhost:8080"
    EVOLUTION_API_KEY: str = ""


def get_settings() -> Settings:
    """Retorna uma instância de Settings validada."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
