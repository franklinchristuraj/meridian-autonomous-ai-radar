import pytest

# NOTE: Weaviate fixtures are placeholders for Phase 1 Plan 03 (db layer).
# They are skipped here to avoid import errors before src.db is implemented.

try:
    from src.db.client import get_client
    from src.db.schema import init_schema

    @pytest.fixture
    def weaviate_client():
        client = get_client()
        yield client
        client.close()

    @pytest.fixture(scope="session")
    def init_schema_fixture():
        client = get_client()
        init_schema(client)
        client.close()

except ImportError:
    # src.db not yet implemented — fixtures will be defined in a later plan
    pass
