from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from config.settings import settings
from models.llm_client import LLMClient


def _default_model_config() -> Dict[str, Any]:
    return {
        "id": "default",
        "name": "默认模型",
        "provider": "vllm",
        "api_key": settings.llm_api_key,
        "api_url": settings.llm_api_url,
        "model": settings.llm_model_name,
        "is_active": True,
        "parameters": {
            "temperature": 0.7,
            "max_tokens": 4096,
        },
    }


# 当前仍为进程内注册表，但统一由此模块管理，避免多处各自维护。
_models_store: Dict[str, Dict[str, Any]] = {
    "default": _default_model_config(),
}


def list_models() -> list[Dict[str, Any]]:
    return [deepcopy(item) for item in _models_store.values()]


def get_model(model_id: str) -> Dict[str, Any] | None:
    model = _models_store.get(model_id)
    return deepcopy(model) if model else None


def get_active_model() -> Dict[str, Any] | None:
    for model in _models_store.values():
        if model.get("is_active"):
            return deepcopy(model)
    return None


def ensure_active_model() -> Dict[str, Any]:
    active = get_active_model()
    if active:
        return active
    fallback = _default_model_config()
    _models_store[fallback["id"]] = fallback
    return deepcopy(fallback)


def create_model(data: Dict[str, Any]) -> Dict[str, Any]:
    model_id = f"model_{len(_models_store) + 1}"
    new_model = {
        "id": model_id,
        "name": data["name"],
        "provider": data["provider"],
        "api_key": data.get("api_key", ""),
        "api_url": data["api_url"],
        "model": data["model"],
        "is_active": False,
        "parameters": data.get("parameters") or {},
    }
    if not _models_store:
        new_model["is_active"] = True
    _models_store[model_id] = new_model
    return deepcopy(new_model)


def update_model(model_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
    model = _models_store[model_id]
    for field in ("name", "api_key", "api_url", "model", "parameters"):
        if field in changes and changes[field] is not None:
            model[field] = changes[field]
    return deepcopy(model)


def delete_model(model_id: str) -> Dict[str, Any]:
    deleted = _models_store.pop(model_id)
    if deleted.get("is_active") and _models_store:
        first_key = next(iter(_models_store.keys()))
        _models_store[first_key]["is_active"] = True
    return deepcopy(deleted)


def activate_model(model_id: str) -> Dict[str, Any]:
    for model in _models_store.values():
        model["is_active"] = False
    _models_store[model_id]["is_active"] = True
    return deepcopy(_models_store[model_id])


def build_client(model: Dict[str, Any] | None = None) -> LLMClient:
    current = model or ensure_active_model()
    return LLMClient(
        api_key=current.get("api_key", "") or settings.llm_api_key,
        base_url=current.get("api_url", "") or settings.llm_api_url,
        model=current.get("model", "") or settings.llm_model_name,
    )
