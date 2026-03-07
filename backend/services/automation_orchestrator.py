"""
旧自动化编排器兼容层。

主流程已迁移到 `log_sampler -> case_orchestrator -> agents/fabric`。
这里仅保留最小代理，避免历史调用点直接失效。
"""
import logging
from typing import Any, Dict, Optional

from services.log_sampler import log_sampler

logger = logging.getLogger(__name__)


class AutomationOrchestrator:
    """兼容层：将旧 sample 触发请求转发到新的 case pipeline。"""

    async def process_abnormal_sample(self, sample_id: int) -> Dict[str, Any]:
        logger.info("Legacy automation orchestrator forwarding sample %s to case pipeline", sample_id)
        return await log_sampler.create_case_for_sample(sample_id, rerun_pipeline=True)

    async def process_pending_tasks(self, site_id: Optional[int] = None) -> Dict[str, Any]:
        logger.info("Legacy pending task loop is disabled; site_id=%s", site_id)
        return {
            "processed": 0,
            "site_id": site_id,
            "mode": "disabled",
            "message": "Legacy automation task queue disabled; use Fabric pipeline",
        }


automation_orchestrator = AutomationOrchestrator()
