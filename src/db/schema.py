import weaviate
from weaviate.classes.config import Configure, Property, DataType


def init_schema(client: weaviate.WeaviateClient) -> None:
    """Create all 5 Meridian collections idempotently. Safe to call multiple times."""
    _create_signals(client)
    _create_patterns(client)
    _create_hypotheses(client)
    _create_feedback(client)
    _create_briefings(client)
    _migrate_signals_reasoning(client)
    _migrate_signals_body_source(client)
    _migrate_signals_cluster_id(client)
    _migrate_signals_confidence(client)



def _create_signals(client: weaviate.WeaviateClient) -> None:
    if client.collections.exists("Signals"):
        return
    client.collections.create(
        name="Signals",
        description="Incoming AI research signals (papers, articles, posts) with scoring metadata",
        vector_config=Configure.Vectors.text2vec_transformers(),
        properties=[
            Property(name="source_url",          data_type=DataType.TEXT),
            Property(name="title",               data_type=DataType.TEXT),
            Property(name="abstract",            data_type=DataType.TEXT),
            Property(name="published_date",      data_type=DataType.DATE),
            Property(name="score",               data_type=DataType.NUMBER),
            Property(name="tier",                data_type=DataType.TEXT),
            Property(name="status",              data_type=DataType.TEXT),   # pending/scored/archived
            Property(name="arxiv_id",            data_type=DataType.TEXT),
            Property(name="matched_pattern_ids", data_type=DataType.TEXT_ARRAY),
            Property(name="body",               data_type=DataType.TEXT),
            Property(name="source",             data_type=DataType.TEXT),
        ],
    )


def _migrate_signals_reasoning(client: weaviate.WeaviateClient) -> None:
    """Idempotent migration: add reasoning TEXT property to Signals if missing."""
    if not client.collections.exists("Signals"):
        return
    signals = client.collections.get("Signals")
    try:
        signals.config.add_property(Property(name="reasoning", data_type=DataType.TEXT))
    except Exception:
        # Property already exists — safe to ignore
        pass


def _migrate_signals_cluster_id(client: weaviate.WeaviateClient) -> None:
    """Idempotent migration: add cluster_id TEXT property to Signals if missing."""
    if not client.collections.exists("Signals"):
        return
    signals = client.collections.get("Signals")
    try:
        signals.config.add_property(Property(name="cluster_id", data_type=DataType.TEXT))
    except Exception:
        # Property already exists — safe to ignore
        pass


def _migrate_signals_confidence(client: weaviate.WeaviateClient) -> None:
    """Idempotent migration: add confidence NUMBER property to Signals if missing."""
    if not client.collections.exists("Signals"):
        return
    signals = client.collections.get("Signals")
    try:
        signals.config.add_property(Property(name="confidence", data_type=DataType.NUMBER))
    except Exception:
        # Property already exists — safe to ignore
        pass


def _migrate_signals_body_source(client: weaviate.WeaviateClient) -> None:
    """Idempotent migration: add body and source TEXT properties to Signals if missing."""
    if not client.collections.exists("Signals"):
        return
    signals = client.collections.get("Signals")
    for prop_name in ("body", "source"):
        try:
            signals.config.add_property(Property(name=prop_name, data_type=DataType.TEXT))
        except Exception:
            pass


def _create_patterns(client: weaviate.WeaviateClient) -> None:
    if client.collections.exists("Patterns"):
        return
    client.collections.create(
        name="Patterns",
        description="Curated technology patterns scored against incoming signals",
        vector_config=Configure.Vectors.text2vec_transformers(),
        properties=[
            Property(name="name",             data_type=DataType.TEXT),
            Property(name="description",      data_type=DataType.TEXT),
            Property(name="keywords",         data_type=DataType.TEXT_ARRAY),
            Property(name="maturity",         data_type=DataType.TEXT),    # emerging/established/declining
            Property(name="contrarian_take",  data_type=DataType.TEXT),
            Property(name="related_patterns", data_type=DataType.TEXT_ARRAY),
            Property(name="vault_source",     data_type=DataType.TEXT),
            Property(name="example_signals",  data_type=DataType.TEXT_ARRAY),
        ],
    )


def _create_hypotheses(client: weaviate.WeaviateClient) -> None:
    if client.collections.exists("Hypotheses"):
        return
    client.collections.create(
        name="Hypotheses",
        description="Forward-looking hypotheses derived from signal patterns",
        vector_config=Configure.Vectors.text2vec_transformers(),
        properties=[
            Property(name="statement",           data_type=DataType.TEXT),
            Property(name="confidence",          data_type=DataType.NUMBER),
            Property(name="evidence_signal_ids", data_type=DataType.TEXT_ARRAY),
            Property(name="created_date",        data_type=DataType.DATE),
            Property(name="status",              data_type=DataType.TEXT),
        ],
    )


def _create_feedback(client: weaviate.WeaviateClient) -> None:
    if client.collections.exists("Feedback"):
        return
    client.collections.create(
        name="Feedback",
        description="User feedback on signal-pattern relevance ratings",
        vector_config=Configure.Vectors.text2vec_transformers(),
        properties=[
            Property(name="signal_id",    data_type=DataType.TEXT),
            Property(name="pattern_id",   data_type=DataType.TEXT),
            Property(name="rating",       data_type=DataType.INT),
            Property(name="comment",      data_type=DataType.TEXT),
            Property(name="created_date", data_type=DataType.DATE),
        ],
    )


def _create_briefings(client: weaviate.WeaviateClient) -> None:
    if client.collections.exists("Briefings"):
        return
    client.collections.create(
        name="Briefings",
        description="Daily AI briefings with summarised signal items",
        vector_config=Configure.Vectors.text2vec_transformers(),
        properties=[
            Property(name="date",         data_type=DataType.DATE),
            Property(name="summary",      data_type=DataType.TEXT),
            Property(name="generated_at", data_type=DataType.DATE),
            Property(name="item_count",   data_type=DataType.INT),
            Property(name="items_json",   data_type=DataType.TEXT),  # serialized JSON array
        ],
    )
