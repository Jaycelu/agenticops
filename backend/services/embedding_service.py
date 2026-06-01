"""
Phase 5 — 文本嵌入服务（可选）。

默认 NullEmbedder：不产生向量，零依赖。系统在它之下完全可用，记忆检索退化为
词法 + 元数据召回（仍优于原 naive 子串匹配）。

配置了 settings.llm_embedding_model 时启用 LLMEmbedder，走 OpenAI 兼容
embeddings 端点。任何失败一律降级为 None，绝不阻断主流程。
"""
from __future__ import annotations

import logging
import math
from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.types import JSON as SQLAlchemyJSON

from config.settings import settings

logger = logging.getLogger(__name__)


def cosine_similarity(a: Optional[List[float]], b: Optional[List[float]]) -> float:
    """余弦相似度。任一为空 / 维度不一致 / 零向量 -> 返回 0.0。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        try:
            fx = float(x)
            fy = float(y)
        except (TypeError, ValueError):
            return 0.0
        dot += fx * fy
        norm_a += fx * fx
        norm_b += fy * fy
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


class Embedder:
    """嵌入器基类。"""

    is_enabled: bool = False

    async def embed(self, text: str) -> Optional[List[float]]:  # noqa: D401
        raise NotImplementedError

    async def embed_many(self, texts: List[str]) -> List[Optional[List[float]]]:
        return [await self.embed(t) for t in texts]


class NullEmbedder(Embedder):
    """默认实现：不产生向量。语义检索关闭。"""

    is_enabled = False

    async def embed(self, text: str) -> Optional[List[float]]:
        return None


class LLMEmbedder(Embedder):
    """通过 OpenAI 兼容 embeddings 端点产生向量。失败降级为 None。"""

    is_enabled = True

    def __init__(self, model: str, api_url: str, api_key: str) -> None:
        self.model = model
        self.api_url = api_url
        self.api_key = api_key or "EMPTY"
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.api_url, timeout=30.0)
        return self._client

    async def embed(self, text: str) -> Optional[List[float]]:
        cleaned = (text or "").strip()
        if not cleaned:
            return None
        try:
            client = self._get_client()
            response = await client.embeddings.create(model=self.model, input=cleaned)
            vector = response.data[0].embedding
            return [float(x) for x in vector]
        except Exception as exc:  # noqa: BLE001
            logger.warning("embedding failed (model=%s): %s", self.model, exc)
            return None


def build_embedder() -> Embedder:
    """按 settings 决定启用哪种嵌入器。未配置嵌入模型 -> NullEmbedder。"""
    model = (settings.llm_embedding_model or "").strip()
    if not model:
        return NullEmbedder()
    api_url = (settings.llm_embedding_api_url or settings.llm_api_url or "").strip()
    if not api_url:
        logger.warning("llm_embedding_model set but no api_url resolved; semantic retrieval disabled")
        return NullEmbedder()
    return LLMEmbedder(model=model, api_url=api_url, api_key=settings.llm_api_key)


# Module-level singleton. Rebuild via build_embedder() if settings change at runtime.
embedding_service: Embedder = build_embedder()


async def backfill_memory_embeddings(db, *, limit: int = 500, recompute_all: bool = False) -> dict:
    """
    批量回填 MemoryEntry.embedding。db 由调用方负责创建/关闭。

    embedder 未启用时直接返回 skipped。把嵌入计算放在离线/调度，
    避开记忆写入路径的 sync/async 冲突与逐条打 LLM 的开销。
    """
    from models.agenticops import MemoryEntry  # 局部导入，保持模块加载轻量

    embedder = build_embedder()
    if not getattr(embedder, "is_enabled", False):
        return {"status": "skipped", "reason": "embedder_disabled"}

    query = db.query(MemoryEntry)
    if not recompute_all:
        query = query.filter(
            or_(
                MemoryEntry.embedding.is_(None),
                MemoryEntry.embedding == SQLAlchemyJSON.NULL,
            )
        )
    entries = query.order_by(MemoryEntry.created_at.desc()).limit(limit).all()

    processed = embedded = failed = 0
    for entry in entries:
        processed += 1
        text = " ".join(str(x or "") for x in [entry.title, entry.summary]).strip()
        if not text:
            continue
        vector = await embedder.embed(text)
        if vector:
            entry.embedding = vector
            embedded += 1
        else:
            failed += 1
        if processed % 25 == 0:
            db.commit()
    db.commit()
    return {
        "status": "ok",
        "processed": processed,
        "embedded": embedded,
        "failed": failed,
        "recompute_all": recompute_all,
    }
