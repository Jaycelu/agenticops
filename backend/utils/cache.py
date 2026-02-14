import time
from typing import Any, Optional, Dict
import hashlib
import json


class SimpleCache:
    """简单的内存缓存实现"""

    def __init__(self, default_ttl: int = 300):
        """
        初始化缓存
        :param default_ttl: 默认过期时间（秒），默认5分钟
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl

    def _generate_key(self, prefix: str, params: Dict[str, Any]) -> str:
        """生成缓存键"""
        # 将参数转换为字符串并排序，确保相同的参数生成相同的键
        params_str = json.dumps(params, sort_keys=True)
        hash_obj = hashlib.md5(params_str.encode())
        return f"{prefix}:{hash_obj.hexdigest()}"

    def get(self, prefix: str, params: Dict[str, Any]) -> Optional[Any]:
        """
        获取缓存
        :param prefix: 缓存前缀（如 'devices', 'sites'）
        :param params: 查询参数
        :return: 缓存的数据，如果不存在或已过期返回None
        """
        key = self._generate_key(prefix, params)

        if key not in self.cache:
            return None

        cache_item = self.cache[key]
        # 检查是否过期
        if time.time() > cache_item['expires']:
            del self.cache[key]
            return None

        return cache_item['data']

    def set(self, prefix: str, params: Dict[str, Any], data: Any, ttl: Optional[int] = None) -> None:
        """
        设置缓存
        :param prefix: 缓存前缀
        :param params: 查询参数
        :param data: 要缓存的数据
        :param ttl: 过期时间（秒），如果为None使用默认值
        """
        key = self._generate_key(prefix, params)
        expires = time.time() + (ttl if ttl is not None else self.default_ttl)

        self.cache[key] = {
            'data': data,
            'expires': expires
        }

    def clear(self, prefix: Optional[str] = None) -> None:
        """
        清除缓存
        :param prefix: 如果指定，只清除该前缀的缓存；否则清除所有缓存
        """
        if prefix is None:
            self.cache.clear()
        else:
            # 清除指定前缀的所有缓存
            keys_to_delete = [key for key in self.cache if key.startswith(prefix + ':')]
            for key in keys_to_delete:
                del self.cache[key]

    def cleanup_expired(self) -> None:
        """清理所有过期的缓存"""
        current_time = time.time()
        keys_to_delete = [
            key for key, item in self.cache.items()
            if current_time > item['expires']
        ]
        for key in keys_to_delete:
            del self.cache[key]


# 创建全局缓存实例
# NetBox数据更新频率不高，使用5分钟缓存
netbox_cache = SimpleCache(default_ttl=300)