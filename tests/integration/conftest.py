import os

# Força o uso do banco de testes antes de qualquer import do projeto
os.environ["DATABASE_URL"] = "postgresql://postgres:password@localhost:5432/vendas_db_test"

import psycopg
import pytest

from vendas.bootstrap.settings import settings


@pytest.fixture(scope="session", autouse=True)
def create_test_database():
    """Cria o banco de testes se não existir."""
    admin_dsn = "postgresql://postgres:password@localhost:5432/postgres"
    with psycopg.connect(admin_dsn, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'vendas_db_test'")
        exists = cur.fetchone()
        if not exists:
            try:
                cur.execute("CREATE DATABASE vendas_db_test")
            except psycopg.errors.DuplicateDatabase:
                # Banco já criado por outra execução paralela
                pass


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Aplica as migrations do Alembic no banco de testes, garantindo estado limpo."""
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    from alembic import command

    engine = create_engine(settings.DATABASE_URL)
    # Trava de segurança: só operar em banco cujo nome termina com "_test"
    assert engine.url.database and engine.url.database.endswith("_test"), (
        f"ABORTADO: Tentativa de operacao no banco '{engine.url.database}'. "
        "O banco DEVE terminar em '_test'!"
    )
    # Limpa o schema public antes de aplicar as migrations
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    alembic_cfg = Config("alembic.ini")
    # Aplica todas as migrations até head
    command.upgrade(alembic_cfg, "head")
    yield
    # Não dropar tabelas ao final para evitar conflitos com fixtures de testes
