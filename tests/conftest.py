import pytest
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
