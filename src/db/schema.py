import os
import weaviate
from weaviate.classes.config import Configure, Property, DataType
from dotenv import load_dotenv

load_dotenv()


def init_schema(client: weaviate.WeaviateClient) -> None:
    """Create all 5 Meridian collections idempotently. Safe to call multiple times."""
    ollama_endpoint = os.getenv("OLLAMA_API_ENDPOINT", "http://localhost:11434")
    _create_signals(client, ollama_endpoint)
    _create_patterns(client, ollama_endpoint)
    _create_hypotheses(client, ollama_endpoint)
    _create_feedback(client, ollama_endpoint)
    _create_briefings(client, ollama_endpoint)


def _vector_config(ollama_endpoint: str):
    return Configure.Vectors.text2vec_ollama(
        api_endpoint=ollama_endpoint,
        model="nomic-embed-text",
    )


def _vector_index_config():
    return Configure.VectorIndex.hnsw(
        quantizer=Configure.VectorIndex.Quantizer.rq(compression_level=8)
    )


def _create_signals(client: weaviate.WeaviateClient, ollama_endpoint: str) -> None:
    if client.collections.exists("Signals"):
        return
    client.collections.create(
        name="Signals",
        description="Incoming AI research signals (papers, articles, posts) with scoring metadata",
        vector_config=_vector_config(ollama_endpoint),
        vector_index_config=_vector_index_config(),
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
        ],
    )


def _create_patterns(client: weaviate.WeaviateClient, ollama_endpoint: str) -> None:
    if client.collections.exists("Patterns"):
        return
    client.collections.create(
        name="Patterns",
        description="Curated technology patterns scored against incoming signals",
        vector_config=_vector_config(ollama_endpoint),
        vector_index_config=_vector_index_config(),
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


def _create_hypotheses(client: weaviate.WeaviateClient, ollama_endpoint: str) -> None:
    if client.collections.exists("Hypotheses"):
        return
    client.collections.create(
        name="Hypotheses",
        description="Forward-looking hypotheses derived from signal patterns",
        vector_config=_vector_config(ollama_endpoint),
        vector_index_config=_vector_index_config(),
        properties=[
            Property(name="statement",           data_type=DataType.TEXT),
            Property(name="confidence",          data_type=DataType.NUMBER),
            Property(name="evidence_signal_ids", data_type=DataType.TEXT_ARRAY),
            Property(name="created_date",        data_type=DataType.DATE),
            Property(name="status",              data_type=DataType.TEXT),
        ],
    )


def _create_feedback(client: weaviate.WeaviateClient, ollama_endpoint: str) -> None:
    if client.collections.exists("Feedback"):
        return
    client.collections.create(
        name="Feedback",
        description="User feedback on signal-pattern relevance ratings",
        vector_config=_vector_config(ollama_endpoint),
        vector_index_config=_vector_index_config(),
        properties=[
            Property(name="signal_id",    data_type=DataType.TEXT),
            Property(name="pattern_id",   data_type=DataType.TEXT),
            Property(name="rating",       data_type=DataType.INT),
            Property(name="comment",      data_type=DataType.TEXT),
            Property(name="created_date", data_type=DataType.DATE),
        ],
    )


def _create_briefings(client: weaviate.WeaviateClient, ollama_endpoint: str) -> None:
    if client.collections.exists("Briefings"):
        return
    client.collections.create(
        name="Briefings",
        description="Daily AI briefings with summarised signal items",
        vector_config=_vector_config(ollama_endpoint),
        vector_index_config=_vector_index_config(),
        properties=[
            Property(name="date",         data_type=DataType.DATE),
            Property(name="summary",      data_type=DataType.TEXT),
            Property(name="generated_at", data_type=DataType.DATE),
            Property(name="item_count",   data_type=DataType.INT),
            Property(name="items_json",   data_type=DataType.TEXT),  # serialized JSON array
        ],
    )
