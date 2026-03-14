"""
Round-trip integration tests for all 5 Weaviate collections.
Requires a running Weaviate instance (configured via .env).
"""
import uuid
import pytest
from src.db.client import get_client
from src.db.schema import init_schema


COLLECTION_NAMES = ["Signals", "Patterns", "Hypotheses", "Feedback", "Briefings"]


@pytest.fixture(scope="module")
def schema_ready():
    """Open a module-scoped Weaviate client, init schema, yield client, close."""
    client = get_client()
    init_schema(client)
    yield client
    client.close()


def test_collections_exist(schema_ready):
    """All 5 collection names exist in Weaviate after schema init."""
    client = schema_ready
    for name in COLLECTION_NAMES:
        assert client.collections.exists(name), f"Collection '{name}' does not exist"


def test_round_trip_signals(schema_ready):
    """Insert 10 synthetic Signal objects, query back, count == 10, then clean up."""
    client = schema_ready
    collection = client.collections.get("Signals")
    inserted_uuids = []
    for i in range(10):
        obj_uuid = str(uuid.uuid4())
        collection.data.insert(
            properties={
                "source_url": f"https://arxiv.org/abs/2501.{i:05d}",
                "title": f"Test Signal {i}",
                "abstract": f"Abstract text for synthetic signal {i}",
                "score": float(i) / 10,
                "tier": "A",
                "status": "pending",
                "arxiv_id": f"2501.{i:05d}",
                "matched_pattern_ids": ["pattern-1", "pattern-2"],
            },
            uuid=obj_uuid,
        )
        inserted_uuids.append(obj_uuid)

    result = collection.query.fetch_objects(limit=10)
    assert len(result.objects) == 10

    for obj_uuid in inserted_uuids:
        collection.data.delete_by_id(obj_uuid)


def test_round_trip_patterns(schema_ready):
    """Insert 10 synthetic Pattern objects, query back, count == 10, then clean up."""
    client = schema_ready
    collection = client.collections.get("Patterns")
    inserted_uuids = []
    for i in range(10):
        obj_uuid = str(uuid.uuid4())
        collection.data.insert(
            properties={
                "name": f"Test Pattern {i}",
                "description": f"Description for synthetic pattern {i}",
                "keywords": ["agentic", "llmops", f"keyword-{i}"],
                "maturity": "emerging",
                "contrarian_take": f"Contrarian perspective {i}",
                "related_patterns": [f"pattern-{i+1}"],
                "vault_source": f"05_knowledge/pattern_{i}.md",
                "example_signals": [f"signal-{i}"],
            },
            uuid=obj_uuid,
        )
        inserted_uuids.append(obj_uuid)

    result = collection.query.fetch_objects(limit=10)
    assert len(result.objects) == 10

    for obj_uuid in inserted_uuids:
        collection.data.delete_by_id(obj_uuid)


def test_round_trip_hypotheses(schema_ready):
    """Insert 10 synthetic Hypothesis objects, query back, count == 10, then clean up."""
    client = schema_ready
    collection = client.collections.get("Hypotheses")
    inserted_uuids = []
    for i in range(10):
        obj_uuid = str(uuid.uuid4())
        collection.data.insert(
            properties={
                "statement": f"Hypothesis statement {i}: agentic systems will dominate",
                "confidence": float(i) / 10,
                "evidence_signal_ids": [f"signal-{i}", f"signal-{i+1}"],
                "status": "open",
            },
            uuid=obj_uuid,
        )
        inserted_uuids.append(obj_uuid)

    result = collection.query.fetch_objects(limit=10)
    assert len(result.objects) == 10

    for obj_uuid in inserted_uuids:
        collection.data.delete_by_id(obj_uuid)


def test_round_trip_feedback(schema_ready):
    """Insert 10 synthetic Feedback objects, query back, count == 10, then clean up."""
    client = schema_ready
    collection = client.collections.get("Feedback")
    inserted_uuids = []
    for i in range(10):
        obj_uuid = str(uuid.uuid4())
        collection.data.insert(
            properties={
                "signal_id": f"signal-{i}",
                "pattern_id": f"pattern-{i}",
                "rating": (i % 5) + 1,
                "comment": f"Test feedback comment {i}",
            },
            uuid=obj_uuid,
        )
        inserted_uuids.append(obj_uuid)

    result = collection.query.fetch_objects(limit=10)
    assert len(result.objects) == 10

    for obj_uuid in inserted_uuids:
        collection.data.delete_by_id(obj_uuid)


def test_round_trip_briefings(schema_ready):
    """Insert 10 synthetic Briefing objects, query back, count == 10, then clean up."""
    client = schema_ready
    collection = client.collections.get("Briefings")
    inserted_uuids = []
    for i in range(10):
        obj_uuid = str(uuid.uuid4())
        collection.data.insert(
            properties={
                "summary": f"Daily briefing summary {i} covering top AI signals",
                "item_count": i + 1,
                "items_json": f'[{{"title": "Signal {i}", "url": "https://example.com/{i}"}}]',
            },
            uuid=obj_uuid,
        )
        inserted_uuids.append(obj_uuid)

    result = collection.query.fetch_objects(limit=10)
    assert len(result.objects) == 10

    for obj_uuid in inserted_uuids:
        collection.data.delete_by_id(obj_uuid)
