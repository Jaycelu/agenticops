from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.schemas.settings import (
    IntegrationConfigPayload,
    LogScopePayload,
    ModelUpdateRequest,
    ModelCreateRequest,
)
from database import get_db
from services.integration_config_service import integration_config_service
from services.log_scope_service import log_scope_service
from config.settings import settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


# 运行时模型配置存储（当前为内存态，后续可迁移到数据库）
_models_store = {
    "default": {
        "id": "default",
        "name": "默认模型",
        "provider": "vllm",
        "api_key": "",
        "api_url": settings.llm_api_url,
        "model": settings.llm_model_name,
        "is_active": True,
        "parameters": {
            "temperature": 0.7,
            "max_tokens": 4096
        }
    }
}


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
async def create_log_scope(payload: LogScopePayload, db: Session = Depends(get_db)):
    try:
        return {"success": True, "data": log_scope_service.create_scope(db, payload.model_dump())}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/log-scopes/{scope_id}")
async def update_log_scope(scope_id: int, payload: LogScopePayload, db: Session = Depends(get_db)):
    try:
        return {"success": True, "data": log_scope_service.update_scope(db, scope_id, payload.model_dump())}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/log-scopes/{scope_id}")
async def delete_log_scope(scope_id: int, db: Session = Depends(get_db)):
    try:
        log_scope_service.delete_scope(db, scope_id)
        return {"success": True, "message": "日志范围已删除"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/log-scopes/{scope_id}/test")
async def test_log_scope(scope_id: int, db: Session = Depends(get_db)):
    try:
        result = await log_scope_service.test_scope(db, scope_id)
        return result
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/models")
async def get_models():
    """获取所有模型配置"""
    return {
        "success": True,
        "data": list(_models_store.values())
    }


@router.get("/models/active")
async def get_active_model():
    """获取当前激活的模型"""
    for model in _models_store.values():
        if model["is_active"]:
            return {
                "success": True,
                "model": model
            }
    return {
        "success": True,
        "model": None
    }


@router.post("/models")
async def create_model(request: ModelCreateRequest):
    """创建新的模型配置"""
    # 生成唯一ID
    model_id = f"model_{len(_models_store) + 1}"
    
    new_model = {
        "id": model_id,
        "name": request.name,
        "provider": request.provider,
        "api_key": request.api_key,
        "api_url": request.api_url,
        "model": request.model,
        "is_active": False,
        "parameters": request.parameters or {}
    }
    
    # 如果是第一个模型，自动激活
    if len(_models_store) == 0:
        new_model["is_active"] = True
    
    _models_store[model_id] = new_model
    
    return {
        "success": True,
        "model": new_model
    }


@router.put("/models/{model_id}")
async def update_model(model_id: str, request: ModelUpdateRequest):
    """更新模型配置"""
    if model_id not in _models_store:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    model = _models_store[model_id]
    
    if request.name is not None:
        model["name"] = request.name
    if request.api_key is not None:
        model["api_key"] = request.api_key
    if request.api_url is not None:
        model["api_url"] = request.api_url
    if request.model is not None:
        model["model"] = request.model
    if request.parameters is not None:
        model["parameters"] = request.parameters
    
    return {
        "success": True,
        "model": model
    }


@router.delete("/models/{model_id}")
async def delete_model(model_id: str):
    """删除模型配置"""
    if model_id not in _models_store:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    # 不允许删除最后一个模型
    if len(_models_store) == 1:
        raise HTTPException(status_code=400, detail="不能删除最后一个模型")
    
    deleted_model = _models_store.pop(model_id)
    
    # 如果删除的是激活的模型，激活另一个模型
    if deleted_model["is_active"]:
        remaining_models = list(_models_store.values())
        if remaining_models:
            remaining_models[0]["is_active"] = True
    
    return {
        "success": True,
        "message": "模型已删除"
    }


@router.post("/models/{model_id}/activate")
async def activate_model(model_id: str):
    """激活指定的模型"""
    if model_id not in _models_store:
        raise HTTPException(status_code=404, detail="模型不存在")

    # 取消所有模型的激活状态
    for model in _models_store.values():
        model["is_active"] = False

    # 激活指定的模型
    _models_store[model_id]["is_active"] = True

    return {
        "success": True,
        "message": "模型已激活",
        "data": _models_store[model_id]
    }


@router.get("/models/providers")
async def get_providers():
    """获取支持的模型提供商"""
    return {
        "success": True,
        "providers": [
            {
                "id": "vllm",
                "name": "VLLM (本地)",
                "description": "本地部署的VLLM模型服务",
                "required_params": ["api_url", "model"],
                "optional_params": ["temperature", "max_tokens"]
            },
            {
                "id": "aihubmix",
                "name": "AIHubMix",
                "description": "AIHubMix API服务",
                "required_params": ["api_key", "api_url", "model"],
                "optional_params": ["temperature", "max_tokens"]
            },
            {
                "id": "openrouter",
                "name": "OpenRouter",
                "description": "OpenRouter API服务",
                "required_params": ["api_key", "api_url", "model"],
                "optional_params": ["temperature", "max_tokens"]
            }
        ]
    }


@router.get("/models/test/{model_id}")
async def test_model(model_id: str):
    """测试模型连接"""
    if model_id not in _models_store:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    model = _models_store[model_id]
    
    try:
        from models.llm_client import LLMClient
        
        # 创建临时客户端进行测试
        test_client = LLMClient(
            api_key=model["api_key"],
            base_url=model["api_url"],
            model=model["model"]
        )
        
        # 发送测试消息
        test_messages = [
            {
                "role": "system",
                "content": "你是一个测试助手。"
            },
            {
                "role": "user",
                "content": "请回复'测试成功'"
            }
        ]
        
        response = await test_client.chat_completion(
            messages=test_messages,
            temperature=0.3,
            max_tokens=100
        )

        return {
            "success": True,
            "message": "模型连接测试成功",
            "data": {
                "response": response
            }
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"模型连接测试失败：{str(e)}"
        }
