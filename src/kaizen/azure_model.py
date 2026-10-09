"""Resolves the actual model object/string to hand to `create_agent()` for
the ``langgraph`` backend - a plain "provider:model" string in the common
case, or a constructed Azure chat model instance when `model.azure` names a
deployment for that role.

AAD (Entra ID) token auth is the default for Azure: no API key is ever
generated, stored, or distributed. Every user authenticates with their own
`az login` session (or a managed identity in CI/production).

Reasoning models (gpt-6/gpt-5.6 family) only support function/tool calls
through Azure's **Responses API**, which lives on a separate, versionless
"v1" surface (``{endpoint}/openai/v1/``) - distinct from the classic dated
``api-version=...`` Chat Completions surface, and using a different AAD
token audience (``https://ai.azure.com/.default`` vs
``https://cognitiveservices.azure.com/.default``). `use_responses_api`
(default True) selects that path; set it False only for a deployment that
doesn't support/need it, which falls back to the classic `AzureChatOpenAI`
surface with the "Cognitive Services OpenAI User" data-plane role.
"""
from __future__ import annotations

from typing import Any

from kaizen.config import AzureModelConfig, ModelConfig


def _responses_api_token() -> str:
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential().get_token("https://ai.azure.com/.default").token


def _classic_token_provider():
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider

    return get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )


def _api_key_from_env() -> str:
    import os

    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    if not api_key:
        raise ValueError("model.azure.auth_mode is 'api_key' but AZURE_OPENAI_API_KEY is not set.")
    return api_key


def build_azure_chat_model(azure: AzureModelConfig, deployment: str) -> Any:
    if azure.use_responses_api:
        from langchain_openai import ChatOpenAI

        api_key = _api_key_from_env() if azure.auth_mode == "api_key" else _responses_api_token()
        return ChatOpenAI(
            base_url=azure.endpoint.rstrip("/") + "/openai/v1/",
            api_key=api_key,
            model=deployment,
            use_responses_api=True,
        )

    from langchain_openai import AzureChatOpenAI

    kwargs: dict[str, Any] = {
        "azure_endpoint": azure.endpoint,
        "api_version": azure.api_version,
        "azure_deployment": deployment,
        "use_responses_api": False,
    }
    if azure.auth_mode == "api_key":
        kwargs["api_key"] = _api_key_from_env()
    else:
        kwargs["azure_ad_token_provider"] = _classic_token_provider()

    return AzureChatOpenAI(**kwargs)


def resolve_model(model_config: ModelConfig, role: str) -> Any:
    """`role` is "runner" or "fixer". Returns either a plain
    "provider:model" string or a constructed Azure chat model instance -
    `create_agent()` accepts both.
    """
    azure = model_config.azure
    if azure is not None:
        deployment = azure.runner_deployment if role == "runner" else azure.fixer_deployment
        if deployment:
            return build_azure_chat_model(azure, deployment)
    return model_config.runner_model if role == "runner" else model_config.fixer_model
