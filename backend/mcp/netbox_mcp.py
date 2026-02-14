import pynetbox
from typing import Dict, Any, Optional
from datetime import datetime
from config.settings import settings
from .base import BaseMCP, MCPResult


class NetBoxMCP(BaseMCP):
    name = "netbox"
    description = "NetBox integration for asset and topology management"

    def __init__(self):
        super().__init__()
        self.nb = pynetbox.api(settings.netbox_url, token=settings.netbox_api_token)

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": [
                "query_devices",
                "query_ips",
                "query_sites",
                "query_device_types",
                "query_racks",
                "query_vlans",
                "query_prefixes",
                "query_manufacturers",
                "get_device_config",
                "get_device_config_by_id"
            ]
        }

    async def execute(self, params: Dict[str, Any]) -> MCPResult:
        action = params.get("action")

        try:
            if action == "query_devices":
                return await self._query_devices(params)
            elif action == "query_ips":
                return await self._query_ips(params)
            elif action == "query_sites":
                return await self._query_sites(params)
            elif action == "query_device_types":
                return await self._query_device_types(params)
            elif action == "query_racks":
                return await self._query_racks(params)
            elif action == "query_vlans":
                return await self._query_vlans(params)
            elif action == "query_prefixes":
                return await self._query_prefixes(params)
            elif action == "get_device_config":
                return await self._get_device_config(params)
            elif action == "get_device_config_by_id":
                return await self._get_device_config_by_id(params)
            elif action == "fetch_and_save_device_config":
                return await self._fetch_and_save_device_config(params)
            else:
                return self._error(f"Unknown action: {action}")
        except Exception as e:
            return self._error(f"NetBox error: {str(e)}")

    async def _query_devices(self, params: Dict[str, Any]) -> MCPResult:
        filters = {}
        if "name" in params:
            # 使用 q 参数进行模糊搜索
            filters["q"] = params["name"]
        if "site" in params:
            filters["site"] = params["site"]
        if "status" in params:
            filters["status"] = params["status"]
        if "rack_id" in params:
            filters["rack_id"] = params["rack_id"]

        # 先获取设备列表
        devices = self.nb.dcim.devices.filter(**filters)

        # 如果有role参数，在内存中过滤
        if "role" in params and params["role"]:
            role_filter = params["role"]
            devices = [d for d in devices if d.role and role_filter in str(d.role.name)]

        result = {
            "count": len(devices),
            "devices": [
                {
                    "id": device.id,
                    "name": device.name,
                    "device_type": device.device_type.display if device.device_type else None,
                    "site": device.site.name if device.site else None,
                    "role": device.role.name if device.role else None,
                    "status": device.status.label if device.status else None,
                    "serial": device.serial,
                    "primary_ip": str(device.primary_ip) if device.primary_ip else None,
                    "rack": device.rack.name if device.rack else None,
                    "position": device.position,
                    "face": device.face.label if device.face else None,
                    "tags": [tag.name for tag in device.tags] if device.tags else []
                }
                for device in devices
            ]
        }

        return self._success(result, {"action": "query_devices", "filters": filters})

    async def _query_ips(self, params: Dict[str, Any]) -> MCPResult:
        filters = {}
        if "address" in params:
            filters["address"] = params["address"]
        if "device_id" in params:
            filters["device_id"] = params["device_id"]
        if "assigned" in params:
            filters["assigned"] = params["assigned"]

        # 如果指定了parent_prefix_id，先获取前缀信息
        if "parent_prefix_id" in params and params["parent_prefix_id"]:
            prefix_id = params["parent_prefix_id"]
            prefix = self.nb.ipam.prefixes.get(prefix_id)
            if prefix:
                filters["parent"] = prefix.prefix

        # 先获取IP列表
        ips = self.nb.ipam.ip_addresses.filter(**filters)

        # 如果有status参数，在内存中过滤
        if "status" in params and params["status"]:
            status_filter = params["status"]
            ips = [ip for ip in ips if ip.status and status_filter in str(ip.status.label)]

        result = {
            "count": len(ips),
            "ips": [
                {
                    "id": ip.id,
                    "address": ip.address,
                    "description": ip.description,
                    "status": ip.status.label if ip.status else None,
                    "assigned_object_type": ip.assigned_object_type,
                    "assigned_object_id": ip.assigned_object_id,
                    "dns_name": ip.dns_name
                }
                for ip in ips
            ]
        }

        return self._success(result, {"action": "query_ips", "filters": filters})

    async def _query_sites(self, params: Dict[str, Any]) -> MCPResult:
        sites = self.nb.dcim.sites.all()

        result = {
            "count": len(sites),
            "sites": [
                {
                    "id": site.id,
                    "name": site.name,
                    "slug": site.slug,
                    "description": site.description,
                    "status": site.status.label if site.status else None
                }
                for site in sites
            ]
        }

        return self._success(result, {"action": "query_sites"})

    async def _query_device_types(self, params: Dict[str, Any]) -> MCPResult:
        filters = {}
        if "manufacturer" in params:
            filters["manufacturer"] = params["manufacturer"]
        if "model" in params:
            filters["model"] = params["model"]

        device_types = self.nb.dcim.device_types.filter(**filters)

        result = {
            "count": len(device_types),
            "device_types": [
                {
                    "id": dt.id,
                    "model": dt.model,
                    "manufacturer": dt.manufacturer.name if dt.manufacturer else None,
                    "slug": dt.slug,
                    "is_full_depth": dt.is_full_depth,
                    "u_height": dt.u_height
                }
                for dt in device_types
            ]
        }

        return self._success(result, {"action": "query_device_types", "filters": filters})

    async def _query_racks(self, params: Dict[str, Any]) -> MCPResult:
        filters = {}
        if "name" in params:
            # 使用 q 参数进行模糊搜索
            filters["q"] = params["name"]
        if "status" in params:
            filters["status"] = params["status"]

        # 先获取机柜列表
        racks = self.nb.dcim.racks.filter(**filters)

        # 如果有site参数，在内存中过滤
        if "site" in params and params["site"]:
            site_filter = params["site"]
            racks = [r for r in racks if r.site and site_filter in str(r.site.name)]

        result = {
            "count": len(racks),
            "racks": [
                {
                    "id": rack.id,
                    "name": rack.name,
                    "site": rack.site.name if rack.site else None,
                    "location": rack.location.name if rack.location else None,
                    "status": rack.status.label if rack.status else None,
                    "u_height": rack.u_height,
                    "width": rack.width,
                    "role": rack.role.name if rack.role else None,
                    "serial": rack.serial,
                    "asset_tag": rack.asset_tag
                }
                for rack in racks
            ]
        }

        return self._success(result, {"action": "query_racks", "filters": filters})

    async def _query_vlans(self, params: Dict[str, Any]) -> MCPResult:
        """查询VLAN"""
        filters = {}
        if "site" in params and params["site"]:
            filters["site"] = params["site"]
        if "vid" in params and params["vid"]:
            filters["vid"] = params["vid"]
        if "name" in params and params["name"]:
            # 使用 q 参数进行模糊搜索
            filters["q"] = params["name"]
        if "status" in params and params["status"]:
            filters["status"] = params["status"]
        if "q" in params and params["q"]:
            filters["q"] = params["q"]

        vlans = self.nb.ipam.vlans.filter(**filters)

        result = {
            "count": len(vlans),
            "vlans": [
                {
                    "id": vlan.id,
                    "vid": vlan.vid,
                    "name": vlan.name,
                    "site": vlan.site.name if vlan.site else None,
                    "status": vlan.status.label if vlan.status else None,
                    "description": vlan.description,
                    "tenant": vlan.tenant.name if vlan.tenant else None,
                    "role": vlan.role.name if vlan.role else None
                }
                for vlan in vlans
            ]
        }

        return self._success(result, {"action": "query_vlans", "filters": filters})

    async def _query_prefixes(self, params: Dict[str, Any]) -> MCPResult:
        """查询前缀"""
        try:
            # 如果指定了prefix_id，查询单个前缀并计算利用率
            if "prefix_id" in params and params["prefix_id"]:
                prefix = self.nb.ipam.prefixes.get(params["prefix_id"])
                if not prefix:
                    return self._error(f"Prefix not found: {params['prefix_id']}")

                # 计算总IP数量
                try:
                    import ipaddress
                    network = ipaddress.ip_network(prefix.prefix)
                    total_ips = network.num_addresses
                except:
                    total_ips = 0

                # 获取已使用的IP数量
                used_ips = len(list(self.nb.ipam.ip_addresses.filter(parent=prefix.prefix)))

                # 计算利用率
                utilization = round((used_ips / total_ips) * 100, 2) if total_ips > 0 else 0

                return self._success({
                    "count": 1,
                    "prefixes": [{
                        "id": prefix.id,
                        "prefix": prefix.prefix,
                        "site": prefix.scope.site.name if prefix.scope and hasattr(prefix.scope, 'site') and prefix.scope.site else None,
                        "status": prefix.status.label if hasattr(prefix.status, 'label') else str(prefix.status) if prefix.status else None,
                        "description": prefix.description,
                        "tenant": prefix.tenant.name if prefix.tenant else None,
                        "family": prefix.family.label if hasattr(prefix.family, 'label') else str(prefix.family) if prefix.family else None,
                        "vlan": prefix.vlan.name if prefix.vlan else None,
                        "vlan_vid": prefix.vlan.vid if prefix.vlan else None,
                        "total_ips": total_ips,
                        "used_ips": used_ips,
                        "utilization": utilization
                    }]
                }, {"action": "query_prefixes", "filters": params})

            # 普通查询，计算利用率
            filters = {}
            if "site" in params and params["site"]:
                filters["site"] = params["site"]
            if "family" in params and params["family"]:
                filters["family"] = params["family"]
            if "status" in params and params["status"]:
                filters["status"] = params["status"]
            if "prefix" in params and params["prefix"]:
                # 使用 q 参数进行模糊搜索
                filters["q"] = params["prefix"]
            if "q" in params and params["q"]:
                filters["q"] = params["q"]

            # 添加限制，避免查询过多数据
            limit = params.get("limit", 1000)
            prefixes = self.nb.ipam.prefixes.filter(**filters)
            prefixes = list(prefixes)[:limit]  # 转换为列表再切片

            result = {
                "count": len(prefixes),
                "prefixes": []
            }

            for prefix in prefixes:
                # 计算总IP数量
                try:
                    import ipaddress
                    network = ipaddress.ip_network(prefix.prefix)
                    total_ips = network.num_addresses
                except:
                    total_ips = 0

                # 获取已使用的IP数量
                try:
                    used_ips = len(list(self.nb.ipam.ip_addresses.filter(parent=prefix.prefix)))
                except:
                    used_ips = 0

                # 计算利用率
                utilization = round((used_ips / total_ips) * 100, 2) if total_ips > 0 else 0

                result["prefixes"].append({
                    "id": prefix.id,
                    "prefix": prefix.prefix,
                    "site": prefix.scope.site.name if prefix.scope and hasattr(prefix.scope, 'site') and prefix.scope.site else None,
                    "status": prefix.status.label if hasattr(prefix.status, 'label') else str(prefix.status) if prefix.status else None,
                    "description": prefix.description,
                    "tenant": prefix.tenant.name if prefix.tenant else None,
                    "family": prefix.family.label if hasattr(prefix.family, 'label') else str(prefix.family) if prefix.family else None,
                    "vlan": prefix.vlan.name if prefix.vlan else None,
                    "vlan_vid": prefix.vlan.vid if prefix.vlan else None,
                    "total_ips": total_ips,
                    "used_ips": used_ips,
                    "utilization": utilization
                })

            return self._success(result, {"action": "query_prefixes", "filters": filters})
        except Exception as e:
            import traceback
            return self._error(f"Error in _query_prefixes: {str(e)}\n{traceback.format_exc()}")

    async def _get_device_config(self, params: Dict[str, Any]) -> MCPResult:
        """获取设备配置信息"""
        device_id = params.get("device_id")
        if not device_id:
            return self._error("device_id is required")

        device = self.nb.dcim.devices.get(device_id)
        if not device:
            return self._error(f"Device not found: {device_id}")

        # 从local_context_data中获取配置
        local_context_data = device.local_context_data if hasattr(device, 'local_context_data') and device.local_context_data else {}
        
        # 获取设备的自定义字段
        custom_fields = device.custom_fields if hasattr(device, 'custom_fields') else {}

        result = {
            "device_id": device_id,
            "device_name": device.name,
            "config_context": local_context_data,  # 为了兼容前端，仍然使用config_context字段名
            "custom_fields": custom_fields,
            "has_config": bool(local_context_data or custom_fields)
        }

        return self._success(result, {"action": "get_device_config", "device_id": device_id})

    async def _fetch_and_save_device_config(self, params: Dict[str, Any]) -> MCPResult:
        """从设备获取配置并写入NetBox"""
        import paramiko
        import asyncio
        
        device_id = params.get("device_id")
        username = params.get("username")
        password = params.get("password")
        port = params.get("port", 22)
        
        if not device_id or not username or not password:
            return self._error("device_id, username and password are required")
        
        # 获取设备信息
        device = self.nb.dcim.devices.get(device_id)
        if not device:
            return self._error(f"Device not found: {device_id}")
        
        # 获取设备IP
        device_ip = str(device.primary_ip) if device.primary_ip else None
        if not device_ip:
            return self._error(f"Device {device.name} has no IP address")
        
        # 移除IP地址中的掩码
        if "/" in device_ip:
            device_ip = device_ip.split("/")[0]
        
        print(f"[DEBUG] Fetching config for device {device.name} (ID: {device_id}) at IP: {device_ip}")
        
        try:
            # 在线程池中执行SSH连接（因为paramiko是同步的）
            loop = asyncio.get_event_loop()
            config_text = await loop.run_in_executor(
                None,
                self._fetch_config_via_ssh,
                device_ip,
                username,
                password,
                port
            )
            
            # 保存配置到NetBox的local_context_data
            local_context_data = device.local_context_data if hasattr(device, 'local_context_data') and device.local_context_data else {}
            local_context_data["running_config"] = config_text
            local_context_data["config_fetched_at"] = str(datetime.now())
            
            # 更新设备
            device.local_context_data = local_context_data
            device.save()
            
            result = {
                "device_id": device_id,
                "device_name": device.name,
                "device_ip": device_ip,
                "config_length": len(config_text),
                "config_preview": config_text[:200] + "..." if len(config_text) > 200 else config_text,
                "fetched_at": local_context_data["config_fetched_at"]
            }
            
            return self._success(result, {"action": "fetch_and_save_device_config", "device_id": device_id})
            
        except Exception as e:
            return self._error(f"Failed to fetch config: {str(e)}")
    
    def _fetch_config_via_ssh(self, ip: str, username: str, password: str, port: int) -> str:
        """通过SSH获取设备配置"""
        import paramiko
        from datetime import datetime
        import time
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            # 连接设备
            ssh.connect(ip, port=port, username=username, password=password, timeout=30, banner_timeout=30)
            
            # 使用invoke_shell执行命令
            shell = ssh.invoke_shell()
            time.sleep(1)  # 等待shell准备好
            
            # 禁用分页（华为设备）
            shell.send("screen-length 0 temporary\n")
            time.sleep(1)
            
            # 再次尝试禁用分页（确保生效）
            shell.send("\n")
            time.sleep(0.5)
            
            # 发送命令获取配置（华为设备）
            shell.send("display current-configuration\n")
            time.sleep(15)  # 等待命令执行（配置可能很大，需要更长时间）
            
            # 读取所有输出
            config_text = ""
            timeout_counter = 0
            max_timeout = 30  # 最多等待30秒
            
            while timeout_counter < max_timeout:
                if shell.recv_ready():
                    chunk = shell.recv(4096).decode('utf-8', errors='ignore')
                    config_text += chunk
                    
                    # 检查是否还有分页提示
                    if "--More--" in chunk or "-more-" in chunk:
                        # 发送空格继续
                        shell.send(" ")
                        time.sleep(0.5)
                        continue
                else:
                    time.sleep(0.5)
                    timeout_counter += 1
            
            # 如果没有获取到配置或配置太短，尝试思科命令
            if not config_text or len(config_text) < 100:
                # 禁用分页（思科设备）
                shell.send("terminal length 0\n")
                time.sleep(1)
                
                shell.send("show running-config\n")
                time.sleep(15)
                
                # 读取所有输出
                config_text = ""
                timeout_counter = 0
                
                while timeout_counter < max_timeout:
                    if shell.recv_ready():
                        chunk = shell.recv(4096).decode('utf-8', errors='ignore')
                        config_text += chunk
                        
                        # 检查是否还有分页提示
                        if "--More--" in chunk or "-more-" in chunk:
                            # 发送空格继续
                            shell.send(" ")
                            time.sleep(0.5)
                            continue
                    else:
                        time.sleep(0.5)
                        timeout_counter += 1
            
            return config_text
            
        except Exception as e:
            raise Exception(f"SSH connection or command execution failed: {str(e)}")
        finally:
            try:
                ssh.close()
            except:
                pass