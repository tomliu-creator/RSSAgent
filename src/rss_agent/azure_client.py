from __future__ import annotations

import ssl

import httpx
import truststore
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from .config import env


def build_azure_openai_client() -> AzureOpenAI:
    credential = DefaultAzureCredential(
        exclude_environment_credential=True,
        exclude_managed_identity_credential=True,
        exclude_shared_token_cache_credential=True,
    )
    token_provider = get_bearer_token_provider(
        credential,
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureOpenAI(
        azure_endpoint=env("AZURE_OPENAI_ENDPOINT"),
        api_version=env("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
        azure_ad_token_provider=token_provider,
        http_client=httpx.Client(
            verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
            timeout=60,
            follow_redirects=True,
        ),
    )
