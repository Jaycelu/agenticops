"""按保留策略清理自动化历史数据"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.data_retention_service import data_retention_service


if __name__ == "__main__":
    result = data_retention_service.cleanup()
    print(result)
