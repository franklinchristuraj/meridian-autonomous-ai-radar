"""Manual seed ingestion for the Meridian pipeline.

Accepts user-supplied articles/insights (title, url, notes) and writes them
as manual Signals to Weaviate. Separate from the daily ArXiv Scout pipeline.
"""

import logging

from weaviate.classes.query import Filter

from src.db.client import get_client

logger = logging.getLogger(__name__)


def ingest_manual_seed(data: dict) -> str:
    """Ingest a manually provided seed into the Weaviate Signals collection.

    Args:
        data: dict with keys:
            - title (required): str
            - url (optional): str
            - notes (optional): str — stored as abstract if no abstract provided
            - abstract (optional): str — takes precedence over notes
            - body (optional): str — full text body of the article
            - source (optional): str — origin label (e.g. "make", "slack", "manual")

    Returns:
        UUID string of the created Signal, or the existing UUID if duplicate.
    """
    source_url = data.get("url", "")
    title = data["title"]
    abstract = data.get("abstract", data.get("notes", ""))

    client = get_client()
    try:
        signals = client.collections.get("Signals")

        # Deduplication: check if source_url already exists
        if source_url:
            response = signals.query.fetch_objects(
                filters=Filter.by_property("source_url").equal(source_url),
                limit=1,
            )
            if response.objects:
                existing_uuid = str(response.objects[0].uuid)
                logger.debug(f"ingest_manual_seed: skipping duplicate source_url={source_url}")
                return existing_uuid

        signal_data = {
            "title": title,
            "source_url": source_url,
            "abstract": abstract,
            "status": "manual",
            "tier": "BRIEF",
            "score": 0.0,
        }
        if data.get("body"):
            signal_data["body"] = data["body"]
        if data.get("source"):
            signal_data["source"] = data["source"]

        result_uuid = signals.data.insert(signal_data)
        logger.info(f"ingest_manual_seed: inserted signal uuid={result_uuid} title={title!r}")
        return str(result_uuid)
    finally:
        client.close()
