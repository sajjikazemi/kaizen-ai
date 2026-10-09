from unittest.mock import MagicMock, patch

import pytest

from kaizen.azure_model import build_azure_chat_model, resolve_model
from kaizen.config import AzureModelConfig, ModelConfig


def test_resolve_model_returns_plain_string_without_azure():
    config = ModelConfig(runner_model="anthropic:claude-haiku-4-5", fixer_model="anthropic:claude-sonnet-4-5")
    assert resolve_model(config, "runner") == "anthropic:claude-haiku-4-5"
    assert resolve_model(config, "fixer") == "anthropic:claude-sonnet-4-5"


def test_resolve_model_falls_back_to_string_when_role_has_no_deployment():
    config = ModelConfig(
        runner_model="anthropic:claude-haiku-4-5",
        azure=AzureModelConfig(endpoint="https://x.openai.azure.com/", fixer_deployment="gpt-4o-reasoning"),
    )
    # No runner_deployment set -> falls back to the plain string for "runner".
    assert resolve_model(config, "runner") == "anthropic:claude-haiku-4-5"


def test_resolve_model_builds_azure_model_when_deployment_set():
    config = ModelConfig(
        azure=AzureModelConfig(
            endpoint="https://contoso-openai.openai.azure.com/",
            runner_deployment="gpt-4o-mini",
            fixer_deployment="gpt-4o-reasoning",
        )
    )
    fake_model = MagicMock(name="AzureChatOpenAI-instance")
    with patch("kaizen.azure_model.build_azure_chat_model", return_value=fake_model) as mocked:
        result = resolve_model(config, "fixer")
    assert result is fake_model
    mocked.assert_called_once()
    args, _ = mocked.call_args
    assert args[1] == "gpt-4o-reasoning"


def test_build_azure_chat_model_uses_aad_by_default():
    azure = AzureModelConfig(endpoint="https://x.openai.azure.com/", runner_deployment="gpt-4o-mini")
    fake_credential = MagicMock()
    fake_token_provider = MagicMock()
    with patch("azure.identity.DefaultAzureCredential", return_value=fake_credential) as cred, patch(
        "azure.identity.get_bearer_token_provider", return_value=fake_token_provider
    ) as provider, patch("langchain_openai.AzureChatOpenAI") as azure_chat:
        build_azure_chat_model(azure, "gpt-4o-mini")
        cred.assert_called_once()
        provider.assert_called_once_with(fake_credential, "https://cognitiveservices.azure.com/.default")
        azure_chat.assert_called_once_with(
            azure_endpoint="https://x.openai.azure.com/",
            api_version="2024-10-21",
            azure_deployment="gpt-4o-mini",
            azure_ad_token_provider=fake_token_provider,
        )


def test_build_azure_chat_model_api_key_mode_requires_env_var(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    azure = AzureModelConfig(
        endpoint="https://x.openai.azure.com/", auth_mode="api_key", runner_deployment="gpt-4o-mini"
    )
    with pytest.raises(ValueError, match="AZURE_OPENAI_API_KEY"):
        build_azure_chat_model(azure, "gpt-4o-mini")


def test_build_azure_chat_model_api_key_mode_uses_env_var(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "secret-123")
    azure = AzureModelConfig(
        endpoint="https://x.openai.azure.com/", auth_mode="api_key", runner_deployment="gpt-4o-mini"
    )
    with patch("langchain_openai.AzureChatOpenAI") as azure_chat:
        build_azure_chat_model(azure, "gpt-4o-mini")
        azure_chat.assert_called_once_with(
            azure_endpoint="https://x.openai.azure.com/",
            api_version="2024-10-21",
            azure_deployment="gpt-4o-mini",
            api_key="secret-123",
        )
