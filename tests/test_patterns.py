"""
Integration tests for the seed pattern library.

Requires a live Weaviate instance (configured via .env).
Run with: pytest tests/test_patterns.py -v
"""
import pytest

from src.db.client import get_client
from src.db.schema import init_schema
from src.bootstrap.seed_patterns import seed_patterns


PATTERNS_DIR = "patterns/seed"


@pytest.fixture(scope="module")
def weaviate_client():
    """Shared Weaviate client for the test module. Ensures schema exists."""
    client = get_client()
    init_schema(client)
    yield client
    client.close()


@pytest.fixture(scope="module")
def seeded_client(weaviate_client):
    """Run seed_patterns once and return the client for all pattern tests."""
    seed_patterns(weaviate_client, patterns_dir=PATTERNS_DIR)
    return weaviate_client


def _get_all_patterns(client) -> list[dict]:
    """Fetch all objects from the Patterns collection."""
    collection = client.collections.get("Patterns")
    return [obj.properties for obj in collection.iterator()]


def test_seed_patterns_count(seeded_client):
    """Patterns collection must contain at least 15 objects after seeding."""
    patterns = _get_all_patterns(seeded_client)
    assert len(patterns) >= 15, (
        f"Expected >= 15 patterns in Weaviate, found {len(patterns)}. "
        "Run seed_patterns() and check the patterns/seed/ directory."
    )


def test_patterns_have_required_fields(seeded_client):
    """Every pattern must have non-empty name, description, keywords, maturity, contrarian_take."""
    patterns = _get_all_patterns(seeded_client)
    assert patterns, "No patterns found — run seeding first."

    for p in patterns:
        name = p.get("name", "")
        assert name, f"Pattern missing 'name': {p}"
        assert p.get("description", "").strip(), f"Pattern '{name}' has empty description"
        keywords = p.get("keywords", [])
        assert isinstance(keywords, list) and len(keywords) >= 1, (
            f"Pattern '{name}' must have at least 1 keyword, got: {keywords}"
        )
        assert p.get("maturity", "").strip(), f"Pattern '{name}' has empty maturity"
        assert p.get("contrarian_take", "").strip(), f"Pattern '{name}' has empty contrarian_take"


def test_patterns_cover_domains(seeded_client):
    """
    Patterns must cover both Agentic Systems and LLMOps / Observability domains.

    - At least one pattern name contains 'agent' (case-insensitive)
    - At least one pattern name or description contains 'LLM', 'observability', or 'eval'
    """
    patterns = _get_all_patterns(seeded_client)
    assert patterns, "No patterns found — run seeding first."

    names_lower = [p.get("name", "").lower() for p in patterns]
    text_corpus = " ".join(
        (p.get("name", "") + " " + p.get("description", "")).lower()
        for p in patterns
    )

    has_agent = any("agent" in n for n in names_lower)
    has_llmops = any(
        term in text_corpus
        for term in ("llm", "observability", "eval")
    )

    assert has_agent, (
        "No pattern with 'agent' in name found. "
        "Expected patterns covering Agentic Systems domain."
    )
    assert has_llmops, (
        "No pattern with 'LLM', 'observability', or 'eval' in name/description found. "
        "Expected patterns covering LLMOps & Observability domain."
    )


def test_seed_idempotent(seeded_client):
    """Running seed_patterns() a second time must not change the total pattern count."""
    patterns_before = _get_all_patterns(seeded_client)
    count_before = len(patterns_before)
    assert count_before >= 15, f"Pre-condition failed: only {count_before} patterns before idempotency test"

    # Run seeder again
    newly_inserted = seed_patterns(seeded_client, patterns_dir=PATTERNS_DIR)

    patterns_after = _get_all_patterns(seeded_client)
    count_after = len(patterns_after)

    assert newly_inserted == 0, (
        f"Expected 0 new inserts on second run, got {newly_inserted}. "
        "Idempotency check failed — duplicate detection is broken."
    )
    assert count_after == count_before, (
        f"Pattern count changed: {count_before} -> {count_after}. "
        "Seed loader is not idempotent."
    )
