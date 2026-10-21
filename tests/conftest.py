import os

import pytest

from vendas.bootstrap.settings import settings


@pytest.fixture(scope="session", autouse=True)
def override_database_url():
    """Use DATABASE_URL_TEST em toda a suíte de integração."""
    os.environ["DATABASE_URL"] = settings.DATABASE_URL_TEST
    yield
    # Cleanup não é estritamente necessário pois é session-scoped
