"""
指纹生成服务
为日志生成唯一指纹，用于Raw Anomaly聚合和去重
"""
import re
import hashlib
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class FingerprintGenerator:
    """指纹生成器"""
    
    # 常见的日志facility映射
    FACILITY_MAP = {
        'kern': 'KERNEL',
        'user': 'USER',
        'mail': 'MAIL',
        'daemon': 'DAEMON',
        'auth': 'AUTH',
        'syslog': 'SYSLOG',
        'lpr': 'LPR',
        'news': 'NEWS',
        'uucp': 'UUCP',
        'cron': 'CRON',
        'authpriv': 'AUTHPRIV',
        'ftp': 'FTP',
        'ntp': 'NTP',
        'audit': 'AUDIT',
        'alert': 'ALERT',
        'clock': 'CLOCK',
        'local0': 'LOCAL0',
        'local1': 'LOCAL1',
        'local2': 'LOCAL2',
        'local3': 'LOCAL3',
        'local4': 'LOCAL4',
        'local5': 'LOCAL5',
        'local6': 'LOCAL6',
        'local7': 'LOCAL7'
    }
    
    # 设备厂商识别关键词
    VENDOR_KEYWORDS = {
        'huawei': ['HUAWEI', 'Huawei', 'huawei', 'CNSF', 'S5735', 'S6730', 'NE40E'],
        'cisco': ['Cisco', 'CISCO', 'cisco', 'Catalyst', 'Nexus', 'ASR', 'ISR'],
        'h3c': ['H3C', 'h3c', 'H3C', 'Comware'],
        'juniper': ['Juniper', 'juniper', 'JUNIPER', 'MX', 'EX', 'SRX'],
        'arista': ['Arista', 'arista', 'ARISTA', 'EOS'],
        'fortinet': ['Fortinet', 'fortinet', 'FORTINET', 'FortiGate'],
        'default': ['unknown']
    }
    
    @classmethod
    def generate_fingerprint(
        cls,
        log_message: str,
        vendor: Optional[str] = None
    ) -> str:
        """
        生成日志指纹
        
        Args:
            log_message: 日志消息
            vendor: 设备厂商（可选）
        
        Returns:
            指纹字符串（格式：<vendor>|<facility>|<normalized_message>的hash）
        """
        try:
            # 1. 提取facility
            facility = cls._extract_facility(log_message)
            
            # 2. 提取或推断vendor
            if not vendor:
                vendor = cls._extract_vendor(log_message)
            
            # 3. 标准化日志消息
            normalized_message = cls._normalize_message(log_message)
            
            # 4. 组合指纹字符串
            fingerprint_str = f"{vendor}|{facility}|{normalized_message}"
            
            # 5. 生成hash
            fingerprint_hash = hashlib.md5(fingerprint_str.encode()).hexdigest()
            
            return fingerprint_hash
            
        except Exception as e:
            logger.error(f"Error generating fingerprint: {e}", exc_info=True)
            # 返回默认指纹
            return hashlib.md5(log_message.encode()).hexdigest()
    
    @classmethod
    def _extract_facility(cls, log_message: str) -> str:
        """
        从日志中提取facility
        
        Args:
            log_message: 日志消息
        
        Returns:
            facility字符串
        """
        # 尝试从PRI字段提取facility
        pri_match = re.search(r'^<(\d+)>', log_message)
        if pri_match:
            pri = int(pri_match.group(1))
            facility_code = pri >> 3
            # facility_code到facility名称的映射
            facility_names = ['kern', 'user', 'mail', 'daemon', 'auth', 'syslog', 'lpr', 'news', 'uucp', 'cron', 'authpriv', 'ftp', 'ntp', 'audit', 'alert', 'clock', 'local0', 'local1', 'local2', 'local3', 'local4', 'local5', 'local6', 'local7']
            if 0 <= facility_code < len(facility_names):
                return facility_names[facility_code].upper()
        
        # 尝试从日志中识别facility
        for facility in cls.FACILITY_MAP.keys():
            if facility in log_message:
                return cls.FACILITY_MAP[facility]
        
        return 'UNKNOWN'
    
    @classmethod
    def _extract_vendor(cls, log_message: str) -> str:
        """
        从日志中提取设备厂商
        
        Args:
            log_message: 日志消息
        
        Returns:
            厂商名称
        """
        log_upper = log_message.upper()
        
        for vendor, keywords in cls.VENDOR_KEYWORDS.items():
            if vendor == 'default':
                continue
            for keyword in keywords:
                if keyword.upper() in log_upper:
                    return vendor.upper()
        
        return 'UNKNOWN'
    
    @classmethod
    def _normalize_message(cls, log_message: str) -> str:
        """
        标准化日志消息
        
        Args:
            log_message: 原始日志消息
        
        Returns:
            标准化后的消息
        """
        # 1. 移除PRI字段
        message = re.sub(r'^<\d+>', '', log_message)
        
        # 2. 移除时间戳
        message = re.sub(r'^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}', '', message)
        message = re.sub(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', '', message)
        message = re.sub(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', '', message)
        
        # 3. 移除主机名
        message = re.sub(r'^\S+\s+', '', message)
        
        # 4. 移除进程ID
        message = re.sub(r'\[\d+\]', '', message)
        
        # 5. 移除数字（替换为占位符）
        message = re.sub(r'\d+', 'N', message)
        
        # 6. 移除IP地址（替换为占位符）
        message = re.sub(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', 'IP', message)
        
        # 7. 移除MAC地址（替换为占位符）
        message = re.sub(r'[0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}', 'MAC', message)
        
        # 8. 移除OID（替换为占位符）
        message = re.sub(r'1\.3\.6\.1\.4\.1\.\d+(\.\d+)*', 'OID', message)
        
        # 9. 移除十六进制字符串
        message = re.sub(r'0x[0-9a-fA-F]+', 'HEX', message)
        
        # 10. 移除多余空格
        message = ' '.join(message.split())
        
        return message


# 全局指纹生成器实例
fingerprint_generator = FingerprintGenerator()