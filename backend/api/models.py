"""
兼容导入入口。

历史上 settings 路由放在 `api.models` 中。当前已迁移到 `api.settings`，
但为避免旧调用点立刻失效，这里保留 re-export shim。
"""

from .settings import router
from services.model_registry import _models_store

__all__ = ["router", "_models_store"]
