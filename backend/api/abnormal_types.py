"""
异常类型管理API
提供异常类型的CRUD操作和状态管理
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from database import get_db
from models.automation import AbnormalType, AbnormalTypeStatus
from services.abnormal_type_service import abnormal_type_service

router = APIRouter(prefix="/api/abnormal-types", tags=["异常类型管理"])


# ============ 异常类型列表 ============

@router.get("/")
async def get_abnormal_types(
    status: Optional[str] = Query(None, description="状态筛选：DRAFT/OBSERVED/ENABLED"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取异常类型列表"""
    query = db.query(AbnormalType)

    if status:
        query = query.filter(AbnormalType.status == status)

    total = query.count()
    types = query.order_by(AbnormalType.created_at.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "types": types
    }


@router.get("/{type_id}")
async def get_abnormal_type(type_id: int, db: Session = Depends(get_db)):
    """获取异常类型详情"""
    abnormal_type = db.query(AbnormalType).filter(AbnormalType.id == type_id).first()
    if not abnormal_type:
        raise HTTPException(status_code=404, detail="Abnormal type not found")
    return abnormal_type


# ============ 创建异常类型 ============

@router.post("/")
async def create_abnormal_type(
    type_data: dict,
    db: Session = Depends(get_db)
):
    """创建新的异常类型"""
    try:
        # 检查类型代码是否已存在
        existing = db.query(AbnormalType).filter(
            AbnormalType.type_code == type_data.get("type_code")
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Type code already exists")

        # 创建异常类型
        abnormal_type = AbnormalType(
            type_code=type_data.get("type_code"),
            type_name=type_data.get("type_name"),
            description=type_data.get("description"),
            status=AbnormalTypeStatus.DRAFT,
            fingerprint_pattern=type_data.get("fingerprint_pattern"),
            keywords=type_data.get("keywords", []),
            threshold_config=type_data.get("threshold_config", {}),
            risk_level=type_data.get("risk_level", "medium"),
            enable_tracking=type_data.get("enable_tracking", True),
            tracking_config=type_data.get("tracking_config", {}),
            created_by=type_data.get("created_by", "system")
        )

        db.add(abnormal_type)
        db.commit()
        db.refresh(abnormal_type)

        return {
            "success": True,
            "message": "Abnormal type created successfully",
            "type": abnormal_type
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============ 更新异常类型 ============

@router.put("/{type_id}")
async def update_abnormal_type(
    type_id: int,
    type_data: dict,
    db: Session = Depends(get_db)
):
    """更新异常类型"""
    abnormal_type = db.query(AbnormalType).filter(AbnormalType.id == type_id).first()
    if not abnormal_type:
        raise HTTPException(status_code=404, detail="Abnormal type not found")

    try:
        # 更新字段
        if "type_name" in type_data:
            abnormal_type.type_name = type_data["type_name"]
        if "description" in type_data:
            abnormal_type.description = type_data["description"]
        if "status" in type_data:
            abnormal_type.status = type_data["status"]
        if "keywords" in type_data:
            abnormal_type.keywords = type_data["keywords"]
        if "threshold_config" in type_data:
            abnormal_type.threshold_config = type_data["threshold_config"]
        if "risk_level" in type_data:
            abnormal_type.risk_level = type_data["risk_level"]
        if "enable_tracking" in type_data:
            abnormal_type.enable_tracking = type_data["enable_tracking"]
        if "tracking_config" in type_data:
            abnormal_type.tracking_config = type_data["tracking_config"]

        abnormal_type.updated_by = type_data.get("updated_by", "system")
        abnormal_type.updated_at = datetime.now()

        db.commit()
        db.refresh(abnormal_type)

        return {
            "success": True,
            "message": "Abnormal type updated successfully",
            "type": abnormal_type
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============ 更新状态 ============

@router.patch("/{type_id}/status")
async def update_abnormal_type_status(
    type_id: int,
    status_data: dict,
    db: Session = Depends(get_db)
):
    """更新异常类型状态"""
    abnormal_type = db.query(AbnormalType).filter(AbnormalType.id == type_id).first()
    if not abnormal_type:
        raise HTTPException(status_code=404, detail="Abnormal type not found")

    try:
        new_status = status_data.get("status")
        if new_status not in [s.value for s in AbnormalTypeStatus]:
            raise HTTPException(status_code=400, detail="Invalid status")

        abnormal_type.status = new_status
        abnormal_type.updated_by = status_data.get("updated_by", "system")
        abnormal_type.updated_at = datetime.now()

        db.commit()
        db.refresh(abnormal_type)

        return {
            "success": True,
            "message": f"Abnormal type status updated to {new_status}",
            "type": abnormal_type
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============ 删除异常类型 ============

@router.delete("/{type_id}")
async def delete_abnormal_type(
    type_id: int,
    db: Session = Depends(get_db)
):
    """删除异常类型"""
    abnormal_type = db.query(AbnormalType).filter(AbnormalType.id == type_id).first()
    if not abnormal_type:
        raise HTTPException(status_code=404, detail="Abnormal type not found")

    try:
        # 只能删除DRAFT状态的异常类型
        if abnormal_type.status != AbnormalTypeStatus.DRAFT:
            raise HTTPException(
                status_code=400,
                detail="Can only delete abnormal types with DRAFT status"
            )

        db.delete(abnormal_type)
        db.commit()

        return {
            "success": True,
            "message": "Abnormal type deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============ 批量更新阈值 ============

@router.post("/batch-update-thresholds")
async def batch_update_thresholds(
    update_data: dict,
    db: Session = Depends(get_db)
):
    """批量更新异常类型阈值"""
    try:
        threshold_updates = update_data.get("updates", [])
        updated_count = 0

        for update in threshold_updates:
            type_code = update.get("type_code")
            threshold_config = update.get("threshold_config")

            if not type_code or not threshold_config:
                continue

            abnormal_type = db.query(AbnormalType).filter(
                AbnormalType.type_code == type_code
            ).first()

            if abnormal_type:
                abnormal_type.threshold_config = threshold_config
                abnormal_type.updated_by = update_data.get("updated_by", "system")
                abnormal_type.updated_at = datetime.now()
                updated_count += 1

        db.commit()

        return {
            "success": True,
            "message": f"Updated {updated_count} abnormal types",
            "updated_count": updated_count
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============ 获取统计信息 ============

@router.get("/stats/summary")
async def get_abnormal_types_stats(db: Session = Depends(get_db)):
    """获取异常类型统计信息"""
    total = db.query(AbnormalType).count()
    draft_count = db.query(AbnormalType).filter(
        AbnormalType.status == AbnormalTypeStatus.DRAFT
    ).count()
    observed_count = db.query(AbnormalType).filter(
        AbnormalType.status == AbnormalTypeStatus.OBSERVED
    ).count()
    enabled_count = db.query(AbnormalType).filter(
        AbnormalType.status == AbnormalTypeStatus.ENABLED
    ).count()

    # 获取出现次数最多的异常类型
    top_types = db.query(AbnormalType).order_by(
        AbnormalType.occurrence_count.desc()
    ).limit(10).all()

    return {
        "total": total,
        "by_status": {
            "draft": draft_count,
            "observed": observed_count,
            "enabled": enabled_count
        },
        "top_occurrences": [
            {
                "type_code": t.type_code,
                "type_name": t.type_name,
                "occurrence_count": t.occurrence_count,
                "last_occurred_at": t.last_occurred_at
            }
            for t in top_types
        ]
    }