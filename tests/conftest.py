import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry import trace


@pytest.fixture(autouse=True)
def otel_test_provider():
    """Set up an in-memory TracerProvider for every test.

    Resets the global OTel state so each test gets a clean provider
    and exporter — spans from one test don't leak into the next.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Reset global state to allow re-setting the provider per test
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace.set_tracer_provider(provider)

    yield exporter

    exporter.clear()
    provider.shutdown()
    # Clean up for next test
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE._done = False


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
