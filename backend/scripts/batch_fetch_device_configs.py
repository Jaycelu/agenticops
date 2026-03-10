"""
批量获取所有有IP设备的配置
"""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import aiohttp

BASE_URL = os.getenv("NETOPS_API_BASE_URL", "http://localhost:8000").rstrip("/")
ROOT_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = ROOT_DIR / "storage"


def build_credentials() -> dict:
    """从环境变量构造凭据，避免硬编码敏感信息。"""
    username = os.getenv("NETOPS_SSH_USERNAME", "").strip()
    password = os.getenv("NETOPS_SSH_PASSWORD", "").strip()
    port = int(os.getenv("NETOPS_SSH_PORT", "22"))
    if not username or not password:
        raise RuntimeError(
            "请先设置 NETOPS_SSH_USERNAME 和 NETOPS_SSH_PASSWORD 环境变量，再运行批量抓取脚本。"
        )
    return {
        "username": username,
        "password": password,
        "port": port,
    }


async def fetch_devices_with_ip(session):
    """获取所有有IP的设备"""
    async with session.get(f"{BASE_URL}/api/assets/devices/with-ip") as response:
        data = await response.json()
        return data.get("devices", [])


async def fetch_device_config(session, device):
    """获取单个设备的配置"""
    device_id = device["id"]
    device_name = device["name"]
    device_ip = device["primary_ip"].split("/")[0] if device["primary_ip"] else None
    
    if not device_ip:
        return {
            "device_id": device_id,
            "device_name": device_name,
            "success": False,
            "error": "No IP address"
        }
    
    try:
        async with session.post(
            f"{BASE_URL}/api/assets/devices/{device_id}/fetch-config",
            json=build_credentials()
        ) as response:
            if response.status == 200:
                result = await response.json()
                return {
                    "device_id": device_id,
                    "device_name": device_name,
                    "device_ip": device_ip,
                    "success": True,
                    "config_length": result.get("config_length", 0),
                    "fetched_at": result.get("fetched_at")
                }
            else:
                error_text = await response.text()
                return {
                    "device_id": device_id,
                    "device_name": device_name,
                    "device_ip": device_ip,
                    "success": False,
                    "error": f"HTTP {response.status}: {error_text}"
                }
    except Exception as e:
        return {
            "device_id": device_id,
            "device_name": device_name,
            "device_ip": device_ip,
            "success": False,
            "error": str(e)
        }


async def main():
    """主函数"""
    print(f"开始批量获取设备配置 - {datetime.now()}")
    
    async with aiohttp.ClientSession() as session:
        # 获取所有有IP的设备
        print("正在获取设备列表...")
        devices = await fetch_devices_with_ip(session)
        print(f"找到 {len(devices)} 个有IP的设备")
        
        # 限制每次只获取20个设备（避免太长时间）
        MAX_DEVICES = 20
        devices_to_fetch = devices[:MAX_DEVICES]
        
        print(f"本次将获取前 {len(devices_to_fetch)} 个设备的配置")
        
        # 批量获取配置
        print("开始获取设备配置...")
        results = []
        
        for i, device in enumerate(devices_to_fetch, 1):
            print(f"[{i}/{len(devices_to_fetch)}] 正在获取 {device['name']} ({device['primary_ip']}) 的配置...")
            
            result = await fetch_device_config(session, device)
            results.append(result)
            
            if result["success"]:
                print(f"  ✓ 成功 - 配置长度: {result['config_length']} 字符")
            else:
                print(f"  ✗ 失败 - {result['error']}")
            
            # 添加延迟，避免过快请求
            if i < len(devices_to_fetch):
                await asyncio.sleep(2)
        
        # 统计结果
        success_count = sum(1 for r in results if r["success"])
        failed_count = len(results) - success_count
        
        print(f"\n批量获取完成 - {datetime.now()}")
        print(f"总计: {len(results)} 个设备")
        print(f"成功: {success_count} 个")
        print(f"失败: {failed_count} 个")
        
        # 保存结果
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        output_path = STORAGE_DIR / "batch_fetch_results.json"
        with output_path.open("w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total": len(results),
                "success": success_count,
                "failed": failed_count,
                "results": results
            }, f, indent=2, ensure_ascii=False)
        print(f"\n结果已保存到: {output_path}")
        
        # 保存失败列表
        if failed_count > 0:
            failed_devices = [r for r in results if not r["success"]]
            print(f"\n失败的设备:")
            for device in failed_devices:
                print(f"  - {device['device_name']} ({device.get('device_ip', 'N/A')}): {device['error']}")
            
            # 保存到文件
            failed_path = STORAGE_DIR / "failed_device_configs.json"
            with failed_path.open("w", encoding="utf-8") as f:
                json.dump(failed_devices, f, indent=2, ensure_ascii=False)
            print(f"\n失败列表已保存到: {failed_path}")
        
        # 如果还有设备未获取，提示用户
        if len(devices) > MAX_DEVICES:
            print(f"\n还有 {len(devices) - MAX_DEVICES} 个设备未获取配置")
            print(f"请再次运行脚本继续获取剩余设备的配置")


if __name__ == "__main__":
    asyncio.run(main())
