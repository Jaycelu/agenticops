"""
Phase 5 — 记忆检索器。

替换 case_orchestrator 里 naive 的「子串命中」召回（_find_memory_hits）。
打分维度：词法重叠 + tag 命中 + 站点匹配 + signal_family 匹配 + 新近度 +
confidence/success_score + memory_type 任务偏好 + 可选语义 cosine。

retrieve() 是纯同步打分：query_embedding 作为入参传入，不在内部调 LLM
（嵌入计算由调用方在异步上下文里完成，或离线回填）。embedder 关闭时
query_embedding 为 None，cosine 维度权重自然为 0，退化为词法 + 元数据召回。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from models.agenticops import MemoryEntry
from services.embedding_service import cosine_similarity


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: Optional[str]) -> Set[str]:
    if not text:
        return set()
    return {tok for tok in _TOKEN_RE.findall(str(text).lower()) if len(tok) >= 2}


# 任务档：每个维度的权重 + memory_type 偏好加成。
_DEFAULT_WEIGHTS = {
    "lexical": 1.0,
    "tag": 0.8,
    "site": 0.5,
    "family": 0.9,
    "recency": 0.4,
    "success": 0.3,
    "confidence": 0.3,
    "cosine": 1.3,
}

TASK_PROFILES: Dict[str, Dict[str, Any]] = {
    "default": {"weights": dict(_DEFAULT_WEIGHTS), "type_pref": {}},
    "triage": {
        "weights": {**_DEFAULT_WEIGHTS, "recency": 0.8, "family": 1.0, "success": 0.2, "cosine": 1.0},
        "type_pref": {"episode": 0.4},
    },
    "rca": {
        "weights": {**_DEFAULT_WEIGHTS, "tag": 0.9, "family": 1.1, "recency": 0.3, "success": 0.4, "cosine": 1.5},
        "type_pref": {"pattern": 0.5},
    },
    "remediation": {
        "weights": {**_DEFAULT_WEIGHTS, "lexical": 0.8, "success": 1.0, "recency": 0.3, "cosine": 1.1},
        "type_pref": {"outcome": 0.6, "feedback": 0.4},
    },
}


@dataclass
class ScoredMemory:
    id: Optional[int]
    memory_type: str
    memory_key: Optional[str]
    title: Optional[str]
    summary: Optional[str]
    confidence: float
    success_score: float
    content: Dict[str, Any]
    case_id: Optional[int]
    score: float
    components: Dict[str, float] = field(default_factory=dict)

    def to_hit_dict(self) -> Dict[str, Any]:
        """复刻 case_orchestrator._find_memory_hits 旧返回结构 + 附检索透明度字段。"""
        return {
            "id": self.id,
            "memory_type": self.memory_type,
            "title": self.title,
            "summary": self.summary,
            "confidence": self.confidence,
            "success_score": self.success_score,
            "content": self.content or {},
            "case_id": self.case_id,
            "retrieval_score": round(self.score, 4),
            "retrieval_components": {k: round(v, 4) for k, v in self.components.items()},
        }


class MemoryRetriever:
    def retrieve(
        self,
        db: Session,
        *,
        task_type: str = "default",
        query_text: str = "",
        query_tokens: Optional[Set[str]] = None,
        tags: Optional[List[str]] = None,
        site_id: Optional[int] = None,
        signal_family: Optional[str] = None,
        exclude_case_id: Optional[int] = None,
        query_embedding: Optional[List[float]] = None,
        candidate_limit: int = 80,
        limit: int = 5,
    ) -> List[ScoredMemory]:
        profile = TASK_PROFILES.get(task_type) or TASK_PROFILES["default"]
        weights: Dict[str, float] = profile["weights"]
        type_pref: Dict[str, float] = profile["type_pref"]

        q_tokens = set(query_tokens) if query_tokens is not None else tokenize(query_text)
        tag_set = {str(t).lower() for t in (tags or []) if t}
        family = (signal_family or "").lower().strip()

        query = db.query(MemoryEntry)
        if exclude_case_id is not None:
            query = query.filter(
                (MemoryEntry.case_id.is_(None)) | (MemoryEntry.case_id != exclude_case_id)
            )
        candidates = (
            query.order_by(MemoryEntry.confidence.desc(), MemoryEntry.created_at.desc())
            .limit(candidate_limit)
            .all()
        )

        scored: List[ScoredMemory] = []
        now = datetime.now(timezone.utc)
        for entry in candidates:
            components = self._score_entry(
                entry,
                q_tokens=q_tokens,
                tag_set=tag_set,
                family=family,
                site_id=site_id,
                query_embedding=query_embedding,
                type_pref=type_pref,
                now=now,
            )
            total = sum(weights.get(name, 0.0) * value for name, value in components.items() if name != "type_pref")
            total += components.get("type_pref", 0.0)  # type_pref is already an absolute bonus
            mem_type = entry.memory_type.value if hasattr(entry.memory_type, "value") else str(entry.memory_type)
            scored.append(
                ScoredMemory(
                    id=entry.id,
                    memory_type=mem_type,
                    memory_key=entry.memory_key,
                    title=entry.title,
                    summary=entry.summary,
                    confidence=float(entry.confidence or 0.0),
                    success_score=float(entry.success_score or 0.0),
                    content=entry.content or {},
                    case_id=entry.case_id,
                    score=total,
                    components=components,
                )
            )

        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:limit]

    # ------------------------------------------------------------------

    def _score_entry(
        self,
        entry: MemoryEntry,
        *,
        q_tokens: Set[str],
        tag_set: Set[str],
        family: str,
        site_id: Optional[int],
        query_embedding: Optional[List[float]],
        type_pref: Dict[str, float],
        now: datetime,
    ) -> Dict[str, float]:
        text_blob = " ".join(
            str(x or "")
            for x in [entry.memory_key, entry.title, entry.summary, " ".join(entry.tags or [])]
        )
        mem_tokens = tokenize(text_blob)

        # lexical: fraction of query tokens present in the memory text
        lexical = (len(q_tokens & mem_tokens) / len(q_tokens)) if q_tokens else 0.0

        # tag: fraction of query tags present in memory tags
        mem_tags = {str(t).lower() for t in (entry.tags or []) if t}
        tag = (len(tag_set & mem_tags) / len(tag_set)) if tag_set else 0.0

        # site: 1.0 match, 0.5 unknown, 0.0 mismatch
        content = entry.content or {}
        mem_site = content.get("site_id")
        if mem_site is None or site_id is None:
            site = 0.5
        else:
            try:
                site = 1.0 if int(mem_site) == int(site_id) else 0.0
            except (TypeError, ValueError):
                site = 0.5

        # family: 1.0 if signal family token appears in the memory text
        family_score = 1.0 if (family and family in text_blob.lower()) else 0.0

        # recency: decays with age in days
        recency = 0.5
        created = getattr(entry, "created_at", None)
        if isinstance(created, datetime):
            created_aware = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (now - created_aware).total_seconds() / 86400.0)
            recency = 1.0 / (1.0 + age_days / 7.0)  # half-ish weight after a week

        success = max(0.0, min(1.0, float(entry.success_score or 0.0)))
        confidence = max(0.0, min(1.0, float(entry.confidence or 0.0)))

        cosine = 0.0
        if query_embedding and entry.embedding:
            cosine = max(0.0, cosine_similarity(query_embedding, entry.embedding))

        mem_type = entry.memory_type.value if hasattr(entry.memory_type, "value") else str(entry.memory_type)
        type_bonus = float(type_pref.get(mem_type, 0.0))

        return {
            "lexical": lexical,
            "tag": tag,
            "site": site,
            "family": family_score,
            "recency": recency,
            "success": success,
            "confidence": confidence,
            "cosine": cosine,
            "type_pref": type_bonus,
        }

    # ------------------------------------------------------------------

    def case_memory_hits(
        self,
        db: Session,
        *,
        case: Any,
        runtime: Optional[Dict[str, Any]] = None,
        signal_family: Optional[str] = None,
        query_embedding: Optional[List[float]] = None,
        task_type: str = "rca",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        case_orchestrator 用的便捷入口：从 CaseRecord + runtime 组装查询，
        返回与旧 _find_memory_hits 一致的 dict 列表（附 retrieval_score）。
        """
        runtime = runtime or {}
        query_text = " ".join(str(x or "") for x in [case.title, getattr(case, "summary", "")])
        tags: List[str] = [t for t in [getattr(case, "device_ip", None), getattr(case, "host", None)] if t]
        log_devices = (runtime.get("log_summary") or {}).get("devices") or []
        if log_devices:
            dev_ip = log_devices[0].get("device_ip")
            if dev_ip:
                tags.append(dev_ip)
        scored = self.retrieve(
            db,
            task_type=task_type,
            query_text=query_text,
            tags=tags,
            site_id=getattr(case, "site_id", None),
            signal_family=signal_family,
            exclude_case_id=getattr(case, "id", None),
            query_embedding=query_embedding,
            limit=limit,
        )
        return [s.to_hit_dict() for s in scored]

    def build_query_text(self, *, case: Any, signal_family: Optional[str] = None) -> str:
        """供调用方拿去算 query embedding 的文本。"""
        parts = [getattr(case, "title", ""), getattr(case, "summary", "")]
        if signal_family:
            parts.append(str(signal_family))
        return " ".join(str(p) for p in parts if p).strip()


memory_retriever = MemoryRetriever()
