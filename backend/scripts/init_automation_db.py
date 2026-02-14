"""初始化自动化数据库表和默认异常类型"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db
from database import SessionLocal
from services.abnormal_type_service import abnormal_type_service


def main():
    init_db()
    db = SessionLocal()
    try:
        abnormal_type_service.get_enabled_types(db)
        print("[OK] automation database initialized")
    finally:
        db.close()


if __name__ == "__main__":
    main()
