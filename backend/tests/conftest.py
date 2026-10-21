import os

import pytest

# Os testes nunca devem ler o `.env` real nem usar segredos reais.
os.environ["BOARDINSIGHT_ENV_FILE"] = os.devnull


@pytest.fixture
def settings_factory():
    from app.core.config import Settings

    def make(**overrides):
        return Settings(_env_file=None, **overrides)

    return make
