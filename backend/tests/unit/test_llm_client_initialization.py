from __future__ import annotations

from unittest.mock import AsyncMock

from models.llm_client import LLMClient


def test_llm_client_initialization_is_lazy_without_api_key(monkeypatch):
    created = []

    def fail_if_created(**kwargs):
        created.append(kwargs)
        raise AssertionError("SDK client must not be created during LLMClient initialization")

    monkeypatch.setattr("models.llm_client.AsyncOpenAI", fail_if_created)

    client = LLMClient(api_key="", base_url="http://localhost:8000/v1", model="test-model")

    assert client.api_key == "EMPTY"
    assert client.client is None
    assert created == []


def test_injected_llm_client_does_not_create_external_sdk_client():
    injected = AsyncMock()

    client = LLMClient(model="test-model", client=injected)

    assert client._get_client() is injected
