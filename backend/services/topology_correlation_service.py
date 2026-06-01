"""
Phase 4.B — 拓扑降噪 / 衍生告警归并。

问题：上游设备（核心/汇聚交换机）故障时，下游设备（接入交换机、AP、服务器）会各自
冒出告警/日志信号。原链路会为每个下游设备各建一个 Case。本服务在「建 Case 前」判断
新事件的设备是否在某个未关闭 Case 的拓扑下游——是则把它作为衍生证据归并进父 Case，
不再新建独立 Case。

设计要点：
- 方向由「角色层级」决定（core=0 < aggregation=1 < access=2 < ap/server=3）。
- 邻接由 NetBox topology（cable 连接）决定，不靠角色硬猜，避免过度归并。
- 用本地 AssetDevice 镜像解析 name/role/id，避免每次都打 NetBox。
- 任何异常一律 fail-open（返回 None）：宁可多建独立 Case，也不掩盖真实故障。
- 不静默丢弃：命中后以 EvidenceItem 形式挂到父 Case，全程可审计。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from config import pipeline_thresholds
from models.agenticops import (
    CaseRecord,
    CaseStatus,
    EvidenceItem,
    EvidenceType,
    SourceEvent,
    SourceEventStatus,
)
from models.automation import AssetDevice

logger = logging.getLogger(__name__)


# 角色关键词 -> 层级（数值越小越上游，越靠核心）。
_ROLE_TIERS: List[Tuple[int, Tuple[str, ...]]] = [
    (0, ("core", "spine", "border", "gateway", "backbone", "核心", "出口", "网关", "骨干")),
    (1, ("aggregation", "distribution", "agg", "dist", "汇聚", "分布")),
    (2, ("access", "tor", "leaf", "接入")),
    (3, ("ap", "wlan", "wireless", "endpoint", "server", "host", "无线", "终端", "服务器")),
]
# 未知角色默认按接入层处理（保守：不轻易把未知设备当成上游）。
_DEFAULT_TIER = 2


@dataclass
class CorrelationHit:
    parent_case_id: int
    parent_case_code: str
    anchor_device_name: Optional[str]
    anchor_netbox_device_id: Optional[int]
    candidate_device_name: Optional[str]
    candidate_netbox_device_id: Optional[int]
    hops: int
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parent_case_id": self.parent_case_id,
            "parent_case_code": self.parent_case_code,
            "anchor_device_name": self.anchor_device_name,
            "anchor_netbox_device_id": self.anchor_netbox_device_id,
            "candidate_device_name": self.candidate_device_name,
            "candidate_netbox_device_id": self.candidate_netbox_device_id,
            "hops": self.hops,
            "confidence": self.confidence,
            "reason": self.reason,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }


# 拓扑抓取函数签名：device_id -> {"success": bool, "data": {"links": [{"peer_device": name}, ...]}}
TopologyFetcher = Callable[[int], Awaitable[Dict[str, Any]]]


class TopologyCorrelationService:
    def __init__(self, topology_fetcher: Optional[TopologyFetcher] = None) -> None:
        self._topology_fetcher = topology_fetcher

    # ------------------------------------------------------------------
    # 角色层级
    # ------------------------------------------------------------------

    @staticmethod
    def role_tier(role: Optional[str]) -> int:
        if not role:
            return _DEFAULT_TIER
        low = str(role).lower()
        for tier, keywords in _ROLE_TIERS:
            if any(keyword in low for keyword in keywords):
                return tier
        return _DEFAULT_TIER

    # ------------------------------------------------------------------
    # 拓扑抓取（可注入，便于单测）
    # ------------------------------------------------------------------

    async def _fetch_topology(self, netbox_device_id: int) -> Dict[str, Any]:
        fetcher = self._topology_fetcher
        if fetcher is None:
            from adapters.netbox_adapter import netbox_adapter

            fetcher = netbox_adapter.get_topology
        try:
            result = await fetcher(netbox_device_id)
            return result if isinstance(result, dict) else {"success": False}
        except Exception as exc:  # noqa: BLE001
            logger.warning("topology fetch failed for device %s: %s", netbox_device_id, exc)
            return {"success": False}

    # ------------------------------------------------------------------
    # AssetDevice 本地镜像查询
    # ------------------------------------------------------------------

    @staticmethod
    def _device_by_id(db: Session, netbox_device_id: Optional[int]) -> Optional[AssetDevice]:
        if not netbox_device_id:
            return None
        return db.query(AssetDevice).filter(AssetDevice.netbox_device_id == netbox_device_id).first()

    @staticmethod
    def _device_by_name(db: Session, name: Optional[str]) -> Optional[AssetDevice]:
        if not name:
            return None
        return db.query(AssetDevice).filter(AssetDevice.name == name).first()

    # ------------------------------------------------------------------
    # 向上游有界 BFS
    # ------------------------------------------------------------------

    async def collect_upstream(
        self,
        db: Session,
        netbox_device_id: int,
        max_hops: int,
    ) -> Dict[str, int]:
        """
        从 candidate 设备出发，沿 cable 拓扑向「上游或同级」方向有界 BFS。

        返回 {device_name: hop_count}，只收录 tier <= 当前节点 tier 的邻居（即上游或同级）。
        """
        upstream: Dict[str, int] = {}
        start = self._device_by_id(db, netbox_device_id)
        if start is None or not start.name:
            return upstream

        visited: Set[str] = {start.name}
        # frontier: (netbox_device_id, tier, name)
        frontier: List[Tuple[int, int, str]] = [
            (netbox_device_id, self.role_tier(start.role), start.name)
        ]

        for hop in range(1, max(1, max_hops) + 1):
            next_frontier: List[Tuple[int, int, str]] = []
            for dev_id, dev_tier, _dev_name in frontier:
                topo = await self._fetch_topology(dev_id)
                if not topo.get("success"):
                    continue
                links = ((topo.get("data") or {}).get("links")) or []
                for link in links:
                    peer_name = link.get("peer_device")
                    if not peer_name or peer_name in visited:
                        continue
                    peer = self._device_by_name(db, peer_name)
                    peer_tier = self.role_tier(peer.role if peer else None)
                    # 只向上游（或同级）扩展：peer 的 tier 数值 <= 当前节点。
                    if peer_tier <= dev_tier:
                        visited.add(peer_name)
                        upstream[peer_name] = hop
                        if peer is not None and peer.netbox_device_id:
                            next_frontier.append((peer.netbox_device_id, peer_tier, peer_name))
            frontier = next_frontier
            if not frontier:
                break
        return upstream

    # ------------------------------------------------------------------
    # 主入口：找父 Case
    # ------------------------------------------------------------------

    async def find_parent_case(
        self,
        db: Session,
        *,
        site_id: Optional[int],
        netbox_device_id: Optional[int],
        device_ip: Optional[str] = None,
        host: Optional[str] = None,
        signal_family: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
        max_hops: Optional[int] = None,
    ) -> Optional[CorrelationHit]:
        """
        若 candidate 设备在某个未关闭 Case 的拓扑下游，返回 CorrelationHit；否则 None。

        没有 netbox_device_id（无法做拓扑判断）时直接返回 None —— fail-open。
        """
        if not netbox_device_id:
            return None

        max_hops = max_hops or pipeline_thresholds.TOPOLOGY_CORRELATION_MAX_HOPS
        window_minutes = pipeline_thresholds.TOPOLOGY_CORRELATION_WINDOW_MINUTES
        since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

        query = db.query(CaseRecord).filter(
            CaseRecord.status.not_in([CaseStatus.RESOLVED, CaseStatus.CLOSED]),
            CaseRecord.opened_at >= since,
            CaseRecord.netbox_device_id.isnot(None),
        )
        if site_id is not None:
            query = query.filter(CaseRecord.site_id == site_id)
        open_cases = [
            case
            for case in query.order_by(CaseRecord.opened_at.desc()).limit(50).all()
            if case.netbox_device_id != netbox_device_id
        ]
        if not open_cases:
            return None

        upstream = await self.collect_upstream(db, netbox_device_id, max_hops)
        if not upstream:
            return None

        candidate = self._device_by_id(db, netbox_device_id)
        candidate_name = candidate.name if candidate else (host or device_ip)

        best: Optional[CorrelationHit] = None
        for case in open_cases:
            anchor = self._device_by_id(db, case.netbox_device_id)
            anchor_name = anchor.name if anchor else None
            if not anchor_name or anchor_name not in upstream:
                continue
            hops = upstream[anchor_name]
            confidence = 0.85 if hops <= 1 else 0.68
            hit = CorrelationHit(
                parent_case_id=int(case.id),
                parent_case_code=case.case_code,
                anchor_device_name=anchor_name,
                anchor_netbox_device_id=case.netbox_device_id,
                candidate_device_name=candidate_name,
                candidate_netbox_device_id=netbox_device_id,
                hops=hops,
                confidence=confidence,
                reason=(
                    f"candidate device '{candidate_name}' is {hops}-hop downstream of "
                    f"open case anchor '{anchor_name}' ({case.case_code})"
                ),
            )
            # 取拓扑距离最近的父 Case（跳数最少）；同跳数取更早开的 Case。
            if best is None or hit.hops < best.hops:
                best = hit
        return best

    # ------------------------------------------------------------------
    # 把衍生信号挂到父 Case
    # ------------------------------------------------------------------

    def attach_derivative_evidence(
        self,
        db: Session,
        hit: CorrelationHit,
        *,
        derivative_dedup_key: Optional[str] = None,
        candidate_summary: Optional[str] = None,
        candidate_payload: Optional[Dict[str, Any]] = None,
    ) -> EvidenceItem:
        """
        在父 Case 上新增一条 EXTERNAL_CONTEXT 证据，记录这次拓扑归并；
        并把衍生 SourceEvent（若能按 dedup_key 找到）标记为 CORRELATED。
        """
        source_event: Optional[SourceEvent] = None
        if derivative_dedup_key:
            source_event = (
                db.query(SourceEvent)
                .filter(SourceEvent.dedup_key == derivative_dedup_key)
                .first()
            )

        summary = candidate_summary or (
            f"拓扑衍生信号：{hit.candidate_device_name} 为 {hit.anchor_device_name} 的下游设备"
            f"（{hit.hops} 跳），已归并至 {hit.parent_case_code}"
        )
        evidence = EvidenceItem(
            case_id=hit.parent_case_id,
            source_event_id=source_event.id if source_event is not None else None,
            evidence_type=EvidenceType.EXTERNAL_CONTEXT,
            source_system="topology_correlation",
            source_ref=f"derivative:{hit.candidate_device_name}",
            device_ip=None,
            host=hit.candidate_device_name,
            summary=summary,
            confidence=hit.confidence,
            payload={
                "correlation": hit.to_dict(),
                "candidate": candidate_payload or {},
            },
            occurred_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc),
        )
        db.add(evidence)
        if source_event is not None:
            source_event.status = SourceEventStatus.CORRELATED
        db.flush()
        return evidence


topology_correlation_service = TopologyCorrelationService()
