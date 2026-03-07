"""初始化自动化数据库表。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db


def main():
    init_db()
    print("[OK] automation database initialized")


if __name__ == "__main__":
    main()
