#!/usr/bin/env python3
"""
手动触发日志采样任务
"""
import asyncio
import sys
import os

# 添加backend目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.log_sampler import log_sampler


async def main():
    """主函数"""
    print("[DEBUG] Starting manual trigger test...")

    # 启动日志采样服务
    await log_sampler.start()

    # 手动触发DEYANG基地的日志采样
    print("[DEBUG] Triggering manual sampling for DEYANG...")
    await log_sampler.sample_site_logs("DEYANG")

    print("[DEBUG] Manual trigger test completed")

    # 停止日志采样服务
    await log_sampler.stop()


if __name__ == "__main__":
    asyncio.run(main())