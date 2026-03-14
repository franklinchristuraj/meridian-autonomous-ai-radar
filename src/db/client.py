import os
import weaviate
from weaviate.auth import AuthApiKey
from dotenv import load_dotenv

load_dotenv()


def get_client() -> weaviate.WeaviateClient:
    """Return a connected Weaviate client using env-configured host/ports."""
    host = os.getenv("WEAVIATE_HOST", "148.230.124.28")
    http_port = int(os.getenv("WEAVIATE_HTTP_PORT", "8081"))
    grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
    api_key = os.getenv("WEAVIATE_API_KEY", "")
    return weaviate.connect_to_custom(
        http_host=host,
        http_port=http_port,
        http_secure=False,
        grpc_host=host,
        grpc_port=grpc_port,
        grpc_secure=False,
        auth_credentials=AuthApiKey(api_key) if api_key else None,
    )
