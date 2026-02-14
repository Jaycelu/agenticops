"""
自动批量获取所有设备配置
确保每个设备都获取到完整配置
"""
import asyncio
import aiohttp
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

# 认证凭据
CREDENTIALS = {
    "username": "admin",
    "password": "Tianhe@123",
    "port": 22
}

# 配置完整性阈值（字符数）
MIN_CONFIG_LENGTH = 5000


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
            json=CREDENTIALS
        ) as response:
            if response.status == 200:
                result = await response.json()
                return {
                    "device_id": device_id,
                    "device_name": device_name,
                    "device_ip": device_ip,
                    "success": True,
                    "config_length": result.get("config_length", 0),
                    "is_complete": result.get("config_length", 0) >= MIN_CONFIG_LENGTH,
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


async def check_device_config(session, device_id):
    """检查设备配置是否完整"""
    try:
        async with session.get(f"{BASE_URL}/api/assets/devices/{device_id}/config") as response:
            if response.status == 200:
                data = await response.json()
                config_context = data.get("config_context", {})
                running_config = config_context.get("running_config", "")
                config_length = len(running_config)
                return {
                    "has_config": bool(running_config),
                    "config_length": config_length,
                    "is_complete": config_length >= MIN_CONFIG_LENGTH
                }
    except:
        pass
    
    return {
        "has_config": False,
        "config_length": 0,
        "is_complete": False
    }


async def process_batch(session, devices, batch_num, total_batches):
    """处理一批设备"""
    print(f"\n{'='*60}")
    print(f"批次 {batch_num}/{total_batches}")
    print(f"{'='*60}")
    
    results = []
    
    for i, device in enumerate(devices, 1):
        print(f"[{batch_num}-{i}/{len(devices)}] 正在获取 {device['name']} ({device['primary_ip']}) 的配置...")
        
        # 先检查是否已有完整配置
        check_result = await check_device_config(session, device["id"])
        
        if check_result["has_config"] and check_result["is_complete"]:
            print(f"  ✓ 已有完整配置 ({check_result['config_length']} 字符)，跳过")
            results.append({
                "device_id": device["id"],
                "device_name": device["name"],
                "success": True,
                "skipped": True,
                "config_length": check_result['config_length']
            })
            continue
        
        # 获取配置
        result = await fetch_device_config(session, device)
        results.append(result)
        
        if result["success"]:
            if result.get("is_complete"):
                print(f"  ✓ 成功 - 配置长度: {result['config_length']} 字符（完整）")
            else:
                print(f"  ✓ 成功 - 配置长度: {result['config_length']} 字符（可能不完整）")
        else:
            print(f"  ✗ 失败 - {result['error']}")
        
        # 添加延迟
        await asyncio.sleep(2)
    
    return results


async def main():
    """主函数"""
    print(f"{'='*60}")
    print(f"自动批量获取所有设备配置")
    print(f"配置完整性阈值: {MIN_CONFIG_LENGTH} 字符")
    print(f"开始时间: {datetime.now()}")
    print(f"{'='*60}")
    
    async with aiohttp.ClientSession() as session:
        # 获取所有有IP的设备
        print("\n正在获取设备列表...")
        devices = await fetch_devices_with_ip(session)
        print(f"找到 {len(devices)} 个有IP的设备")
        
        # 分批处理
        BATCH_SIZE = 20
        total_batches = (len(devices) + BATCH_SIZE - 1) // BATCH_SIZE
        
        all_results = []
        
        for batch_num in range(1, total_batches + 1):
            start_idx = (batch_num - 1) * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, len(devices))
            batch_devices = devices[start_idx:end_idx]
            
            # 处理批次
            batch_results = await process_batch(session, batch_devices, batch_num, total_batches)
            all_results.extend(batch_results)
            
            # 批次间休息
            if batch_num < total_batches:
                print(f"\n批次 {batch_num} 完成，等待10秒后继续...")
                await asyncio.sleep(10)
        
        # 统计结果
        success_count = sum(1 for r in all_results if r["success"])
        skipped_count = sum(1 for r in all_results if r.get("skipped", False))
        fetched_count = success_count - skipped_count
        failed_count = len(all_results) - success_count
        
        # 检查完整性
        complete_count = sum(1 for r in all_results if r.get("is_complete", False))
        incomplete_count = success_count - complete_count
        
        print(f"\n{'='*60}")
        print(f"批量获取完成 - {datetime.now()}")
        print(f"{'='*60}")
        print(f"总计: {len(all_results)} 个设备")
        print(f"成功: {success_count} 个")
        print(f"  - 已有完整配置（跳过）: {skipped_count} 个")
        print(f"  - 本次获取: {fetched_count} 个")
        print(f"    - 完整配置: {complete_count} 个")
        print(f"    - 可能不完整: {incomplete_count} 个")
        print(f"失败: {failed_count} 个")
        
        # 保存结果
        with open("/opt/netops/storage/auto_fetch_all_results.json", "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total": len(all_results),
                "success": success_count,
                "skipped": skipped_count,
                "fetched": fetched_count,
                "complete": complete_count,
                "incomplete": incomplete_count,
                "failed": failed_count,
                "results": all_results
            }, f, indent=2, ensure_ascii=False)
        print(f"\n结果已保存到: /opt/netops/storage/auto_fetch_all_results.json")
        
        # 保存不完整的设备列表
        if incomplete_count > 0:
            incomplete_devices = [r for r in all_results if r.get("success") and not r.get("is_complete", False)]
            print(f"\n配置可能不完整的设备 ({incomplete_count} 个):")
            for device in incomplete_devices:
                print(f"  - {device['device_name']} ({device.get('device_ip', 'N/A')}): {device.get('config_length', 0)} 字符")
            
            with open("/opt/netops/storage/incomplete_device_configs.json", "w") as f:
                json.dump(incomplete_devices, f, indent=2, ensure_ascii=False)
            print(f"不完整列表已保存到: /opt/netops/storage/incomplete_device_configs.json")
        
        # 保存失败列表
        if failed_count > 0:
            failed_devices = [r for r in all_results if not r.get("success")]
            print(f"\n获取失败的设备 ({failed_count} 个):")
            for device in failed_devices:
                print(f"  - {device['device_name']} ({device.get('device_ip', 'N/A')}): {device['error']}")
            
            with open("/opt/netops/storage/failed_device_configs.json", "w") as f:
                json.dump(failed_devices, f, indent=2, ensure_ascii=False)
            print(f"失败列表已保存到: /opt/netops/storage/failed_device_configs.json")
        
        # 总结
        if incomplete_count == 0 and failed_count == 0:
            print(f"\n✓ 所有设备配置获取完成，所有配置都是完整的！")
        else:
            print(f"\n⚠  还有 {incomplete_count} 个设备配置可能不完整，{failed_count} 个设备获取失败")
            print(f"建议检查不完整的设备并重新获取")


if __name__ == "__main__":
    asyncio.run(main())
