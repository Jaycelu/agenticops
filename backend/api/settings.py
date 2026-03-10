from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas.settings import (
    IntegrationConfigPayload,
    LogScopePayload,
    ModelCreateRequest,
    ModelUpdateRequest,
)
from config.settings import settings
from database import get_db
from services.integration_config_service import integration_config_service
from services.log_scope_service import log_scope_service
from services.model_registry import (
    activate_model,
    build_client,
    create_model,
    delete_model,
    ensure_active_model,
    get_model,
    list_models,
    update_model,
)
from services.automation_settings_service import automation_settings_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/integrations")
async def list_integrations(db: Session = Depends(get_db)):
    return {
        "success": True,
        "data": integration_config_service.list_public_configs(db),
    }


@router.get("/integrations/{integration_type}")
async def get_integration(integration_type: str, db: Session = Depends(get_db)):
    try:
        return {
            "success": True,
            "data": integration_config_service.get_public_config(db, integration_type),
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put("/integrations/{integration_type}")
async def upsert_integration(
    integration_type: str,
    payload: IntegrationConfigPayload,
    db: Session = Depends(get_db),
):
    try:
        return {
            "success": True,
            "data": integration_config_service.upsert_config(db, integration_type, payload.model_dump()),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/integrations/{integration_type}/test")
async def test_integration(integration_type: str, db: Session = Depends(get_db)):
    try:
        result = await integration_config_service.test_config(integration_type, db=db)
        return {
            "success": result["success"],
            "message": result["message"],
            "details": result["details"],
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/ssh-security")
async def get_ssh_security_status():
    return {
        "success": True,
        "data": {
            "app_secret_key_configured": bool((settings.app_secret_key or "").strip()),
            "message": "SSH 凭据与集成密钥使用 APP_SECRET_KEY 加密，明文不会通过设置接口回显。",
        },
    }


@router.get("/log-scopes")
async def list_log_scopes(db: Session = Depends(get_db)):
    return {"success": True, "data": log_scope_service.list_scopes(db)}


@router.post("/log-scopes")
async def create_log_scope_entry(payload: LogScopePayload, db: Session = Depends(get_db)):
    try:
        return {"success": True, "data": log_scope_service.create_scope(db, payload.model_dump())}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/log-scopes/{scope_id}")
async def update_log_scope_entry(scope_id: int, payload: LogScopePayload, db: Session = Depends(get_db)):
    try:
        return {"success": True, "data": log_scope_service.update_scope(db, scope_id, payload.model_dump())}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/log-scopes/{scope_id}")
async def delete_log_scope_entry(scope_id: int, db: Session = Depends(get_db)):
    try:
        log_scope_service.delete_scope(db, scope_id)
        return {"success": True, "message": "日志范围已删除"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/log-scopes/{scope_id}/test")
async def test_log_scope(scope_id: int, db: Session = Depends(get_db)):
    try:
        return await log_scope_service.test_scope(db, scope_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/models")
async def get_models():
    return {
        "success": True,
        "data": list_models(),
    }


@router.get("/models/providers")
async def get_model_providers():
    return {
        "success": True,
        "providers": [
            {
                "id": "vllm",
                "name": "VLLM",
                "description": "开源 VLLM 推理服务，支持本地部署的大模型",
                "required_params": ["api_url", "model"],
                "optional_params": ["api_key"],
            },
            {
                "id": "openai",
                "name": "OpenAI",
                "description": "OpenAI 官方 API，支持 GPT-4、GPT-3.5 等模型",
                "required_params": ["api_key"],
                "optional_params": ["api_url"],
            },
            {
                "id": "aihubmix",
                "name": "AIHubMix",
                "description": "AIHubMix 聚合平台，支持多种大模型",
                "required_params": ["api_key"],
                "optional_params": ["api_url"],
            },
            {
                "id": "openrouter",
                "name": "OpenRouter",
                "description": "OpenRouter 聚合平台，支持多种大模型",
                "required_params": ["api_key"],
                "optional_params": [],
            },
        ],
    }


@router.get("/models/active")
async def get_active_model():
    return {
        "success": True,
        "model": ensure_active_model(),
    }


@router.post("/models")
async def create_model_entry(request: ModelCreateRequest):
    return {
        "success": True,
        "model": create_model(request.model_dump()),
    }


@router.put("/models/{model_id}")
async def update_model_entry(model_id: str, request: ModelUpdateRequest):
    if get_model(model_id) is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    return {
        "success": True,
        "model": update_model(model_id, request.model_dump()),
    }


@router.delete("/models/{model_id}")
async def delete_model_entry(model_id: str):
    if get_model(model_id) is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    if len(list_models()) == 1:
        raise HTTPException(status_code=400, detail="不能删除最后一个模型")
    delete_model(model_id)
    return {
        "success": True,
        "message": "模型已删除",
    }


@router.post("/models/{model_id}/activate")
async def activate_model_entry(model_id: str):
    if get_model(model_id) is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    return {
        "success": True,
        "data": activate_model(model_id),
    }


@router.post("/models/{model_id}/test")
async def test_model_entry(model_id: str):
    model = get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="模型不存在")
    try:
        client = build_client(model)
        result = await client.chat_completion(
            messages=[
                {"role": "system", "content": "你是一个连通性测试助手，只返回 ok。"},
                {"role": "user", "content": "ping"},
            ],
            temperature=0.0,
        )
        return {
            "success": True,
            "message": "模型连通性测试通过",
            "details": {
                "model_id": model_id,
                "provider": model.get("provider"),
                "result_preview": str(result)[:120],
            },
        }
    except Exception as exc:  # noqa: BLE001
        return {
                    "success": False,
                    "message": f"模型连通性测试失败：{exc}",
                    "details": {
                        "model_id": model_id,
                        "provider": model.get("provider"),
                    },
                }

@router.get("/automation-mode")
async def get_automation_mode(db: Session = Depends(get_db)):
    """获取当前自动化模式"""
    try:
        mode_data = automation_settings_service.get_automation_mode(db)
        return {
            "success": True,
            "data": mode_data,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "message": f"获取自动化模式失败：{exc}",
        }


@router.put("/automation-mode")
async def set_automation_mode(mode: str, db: Session = Depends(get_db)):
    """设置自动化模式"""
    try:
        mode_data = automation_settings_service.set_automation_mode(db, mode)
        mode_name = "观察模式" if mode_data["is_observe_only"] else "自动模式"
        return {
            "success": True,
            "message": f"已切换到{mode_name}",
            "data": mode_data,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "message": f"设置自动化模式失败：{exc}",
        }


@router.post("/automation-mode/toggle")
async def toggle_automation_mode(db: Session = Depends(get_db)):
    """切换自动化模式"""
    try:
        mode_data = automation_settings_service.toggle_automation_mode(db)
        mode_name = "观察模式" if mode_data["is_observe_only"] else "自动模式"
        return {
            "success": True,
            "message": f"已切换到{mode_name}",
            "data": mode_data,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "message": f"切换自动化模式失败：{exc}",
        }
