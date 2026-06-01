"""
Phase 5 — 批量回填 MemoryEntry.embedding（命令行入口）。

核心逻辑在 services.embedding_service.backfill_memory_embeddings；
本脚本与 main.py 的调度任务共用同一实现。

用法（在 backend/ 目录下）：
    python3 scripts/backfill_memory_embeddings.py [--limit N] [--all]

- 默认只处理 embedding 为空的条目；--all 重算全部。
- 未配置 settings.llm_embedding_model 时直接退出（语义检索关闭）。
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from services.embedding_service import backfill_memory_embeddings


async def _run(limit: int, recompute_all: bool) -> dict:
    db = SessionLocal()
    try:
        return await backfill_memory_embeddings(db, limit=limit, recompute_all=recompute_all)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill MemoryEntry embeddings")
    parser.add_argument("--limit", type=int, default=500, help="max entries to process this run")
    parser.add_argument("--all", action="store_true", help="recompute embeddings for all entries")
    args = parser.parse_args()
    result = asyncio.run(_run(limit=args.limit, recompute_all=args.all))
    print(result)


if __name__ == "__main__":
    main()
