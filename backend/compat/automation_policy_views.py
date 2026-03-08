from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from models.automation import AutomationPolicy


def list_compat_policies(
    db: Session,
    *,
    site_id: Optional[int] = None,
    enabled: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    query = db.query(AutomationPolicy)

    if site_id:
        query = query.filter(AutomationPolicy.site_id == site_id)
    if enabled is not None:
        query = query.filter(AutomationPolicy.enabled == enabled)

    total = query.count()
    policies = query.order_by(AutomationPolicy.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "total": total,
        "policies": policies,
    }


def get_compat_policy(db: Session, policy_id: int) -> AutomationPolicy:
    policy = db.query(AutomationPolicy).filter(AutomationPolicy.id == policy_id).first()
    if policy is None:
        raise LookupError("Policy not found")
    return policy
