from __future__ import annotations

import argparse
import json
from pathlib import Path

from ingestion.replay import evaluate_replay
from ingestion.schemas import ELKDocument


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay a JSONL ELK dataset through noise-reduction rules")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--critical-truth", type=Path, help="optional file containing one critical document id per line")
    args = parser.parse_args()
    documents = [ELKDocument.model_validate(json.loads(line)) for line in args.dataset.read_text().splitlines() if line.strip()]
    truth = (
        {line.strip() for line in args.critical_truth.read_text().splitlines() if line.strip()}
        if args.critical_truth
        else set()
    )
    print(json.dumps(evaluate_replay(documents, truth), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
