"""检查自动化中心核心表结构是否与代码模型一致。"""
import os
import sys
from typing import Dict, List

from sqlalchemy import inspect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine  # noqa: E402
from models.automation import (  # noqa: E402
    Site,
    SiteAutomationSwitch,
    LogSample,
    LogAnalysisResult,
    AutomationTask,
    AutomationPolicy,
    AutomationTaskFeedback,
)


def _model_columns(model) -> List[str]:
    return [c.name for c in model.__table__.columns]


def main() -> int:
    insp = inspect(engine)
    targets: Dict[str, List[str]] = {
        Site.__tablename__: _model_columns(Site),
        SiteAutomationSwitch.__tablename__: _model_columns(SiteAutomationSwitch),
        LogSample.__tablename__: _model_columns(LogSample),
        LogAnalysisResult.__tablename__: _model_columns(LogAnalysisResult),
        AutomationTask.__tablename__: _model_columns(AutomationTask),
        AutomationPolicy.__tablename__: _model_columns(AutomationPolicy),
        AutomationTaskFeedback.__tablename__: _model_columns(AutomationTaskFeedback),
    }

    has_error = False
    print("=== Automation Schema Check ===")
    for table_name, model_cols in targets.items():
        if not insp.has_table(table_name):
            has_error = True
            print(f"[MISSING TABLE] {table_name}")
            continue

        db_cols = [c["name"] for c in insp.get_columns(table_name)]
        missing_cols = [c for c in model_cols if c not in db_cols]
        extra_cols = [c for c in db_cols if c not in model_cols]

        if missing_cols:
            has_error = True
            print(f"[MISSING COLUMNS] {table_name}: {missing_cols}")
        else:
            print(f"[OK] {table_name}")

        if extra_cols:
            print(f"  [INFO] extra columns in DB: {extra_cols}")

    print("=== Done ===")
    return 1 if has_error else 0


if __name__ == "__main__":
    raise SystemExit(main())

