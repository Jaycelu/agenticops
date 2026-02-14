"""
手动触发一次日志采样测试
"""
import asyncio
import sys
import os

# 添加项目路径到sys.path
sys.path.insert(0, '/opt/netops/backend')
os.chdir('/opt/netops/backend')

from services.log_sampler import log_sampler

async def test_sampling():
    """测试采样功能"""
    print("开始手动触发采样测试...")
    
    try:
        # 触发德阳基地的采样
        await log_sampler.sample_site_logs("DEYANG")
        print("✓ 采样测试完成")
    except Exception as e:
        print(f"✗ 采样测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_sampling())