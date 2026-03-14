import os
import weaviate
from dotenv import load_dotenv

load_dotenv()


def get_client() -> weaviate.WeaviateClient:
    """Return a connected Weaviate client using env-configured host/ports."""
    host = os.getenv("WEAVIATE_HOST", "localhost")
    http_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8080"))
    grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
    return weaviate.connect_to_local(
        host=host,
        port=http_port,
        grpc_port=grpc_port,
    )
