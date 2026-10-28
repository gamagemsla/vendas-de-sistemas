import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Banco de Dados
    DATABASE_URL: str
    DATABASE_URL_TEST: str = os.getenv(
        "DATABASE_URL_TEST", "postgresql://postgres:password@localhost:5432/vendas_db_test"
    )

    # Flags de Segurança e Operação (DRY_RUN obrigatório como True por padrão)
    DRY_RUN: bool = True
    AUTOMATION_ENABLED: bool = False
    KILL_SWITCH: bool = False
    CADENCE_GLOBAL_PAUSE: bool = False

    # Worker agendamento
    WORKER_POLL_INTERVAL_SECONDS: int = 60
    WORKER_BATCH_SIZE: int = 10
    WORKER_INGEST_INTERVAL_SECONDS: int = 300
    WORKER_ENRICH_INTERVAL_SECONDS: int = 60
    INGEST_SEARCH_QUERY: str = '{"location": "BR", "industry": "software"}'

    # Orçamentos Diários dos Provedores
    APIFY_DAILY_BUDGET: float = 10.0
    FIRECRAWL_DAILY_BUDGET: float = 10.0
    GEMINI_DAILY_BUDGET: float = 10.0

    # Limites de Envio (single-tenant, global por canal)
    DAILY_SEND_CAP: int = 1000
    MIN_SEND_INTERVAL_SECONDS: int = 60

    # Chaves e Endpoints Externos
    APIFY_API_KEY: str = ""
    APIFY_ACTOR_ID: str = ""
    FIRECRAWL_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    EVOLUTION_API_URL: str = "http://localhost:8080"
    EVOLUTION_API_KEY: str = ""

    # Configurações de E-mail (SMTP)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    EMAIL_FROM: str = "noreply@vendas.local"
    UNSUBSCRIBE_BASE_URL: str = "http://localhost:8000/unsubscribe"

    # Autenticação da API (tokens de desenvolvimento; sobrescrever em produção via .env)
    API_ADMIN_TOKEN: str = "dev-admin-token"
    API_OPERATOR_TOKEN: str = "dev-operator-token"

    # Segredo compartilhado para validação de assinatura do webhook (HMAC)
    WEBHOOK_SECRET: str = ""


def get_settings() -> Settings:
    """Retorna uma instância de Settings validada."""
    return Settings()


settings = get_settings()
