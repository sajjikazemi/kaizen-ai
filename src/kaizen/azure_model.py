"""Resolves the actual model object/string to hand to `create_agent()` for
the ``langgraph`` backend - a plain "provider:model" string in the common
case, or a constructed `AzureChatOpenAI` instance when `model.azure` names a
deployment for that role.

AAD (Entra ID) token auth is the default for Azure: no API key is ever
generated, stored, or distributed. Every user authenticates with their own
`az login` session (or a managed identity in CI/production); Kaizen only
needs the "Cognitive Services OpenAI User" data-plane role, not the
(separately-gated) `listKeys` control-plane permission.
"""
from __future__ import annotations

from typing import Any

from kaizen.config import AzureModelConfig, ModelConfig


def build_azure_chat_model(azure: AzureModelConfig, deployment: str) -> Any:
    from langchain_openai import AzureChatOpenAI

    kwargs: dict[str, Any] = {
        "azure_endpoint": azure.endpoint,
        "api_version": azure.api_version,
        "azure_deployment": deployment,
    }

    if azure.auth_mode == "api_key":
        import os

        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "model.azure.auth_mode is 'api_key' but AZURE_OPENAI_API_KEY is not set."
            )
        kwargs["api_key"] = api_key
    else:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider

        kwargs["azure_ad_token_provider"] = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        )

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
