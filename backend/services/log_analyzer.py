import json
from datetime import datetime
from typing import List, Dict, Any
from models.llm_client import LLMClient
from api.models import _models_store


class LogAnalyzer:
    def __init__(self, llm_client: LLMClient = None):
        self.llm_client = llm_client or self._get_active_model_client()

    def _get_active_model_client(self) -> LLMClient:
        """获取当前激活的模型客户端"""
        for model in _models_store.values():
            if model["is_active"]:
                return LLMClient(
                    api_key=model["api_key"],
                    base_url=model["api_url"],
                    model=model["model"]
                )
        # 如果没有激活的模型，使用默认配置
        return LLMClient()

    def format_logs_for_analysis(self, logs: List[Dict[str, Any]], base_name: str) -> str:
        """将日志数据格式化为适合 LLM 分析的格式"""
        if not logs:
            return "[提示] 未找到日志记录"

        formatted_logs = []
        for log in logs:
            # 优先使用 device_ip，如果不存在则从 hostname 提取
            device_ip = log.get("device_ip")
            if not device_ip:
                hostname = log.get("hostname", "")
                # 尝试从 hostname 中提取 IP（如果 hostname 是 IP 地址格式）
                import re
                ip_match = re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', hostname)
                if ip_match:
                    device_ip = hostname
                else:
                    device_ip = ""
            
            formatted_log = {
                "hostname": log.get("hostname", "Unknown"),
                "device_ip": device_ip,
                "log_time": self._format_timestamp(log.get("timestamp")),
                "log_type": log.get("level", "unknown"),
                "raw_message": log.get("message", ""),
                "summary": "",
                "analysis_hint": "请分析此条日志的异常、告警、或性能问题，如无异常请说明。"
            }
            formatted_logs.append(formatted_log)

        result_str = json.dumps(formatted_logs, ensure_ascii=False)
        
        # 限制长度，避免超出 LLM 上下文
        if len(result_str) > 80000:
            result_str = result_str[:80000]
            
        return result_str

    def _format_timestamp(self, timestamp: str) -> str:
        """格式化时间戳"""
        if not timestamp:
            return ""
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return timestamp

    def extract_analysis_result(self, llm_response: str) -> str:
        """从 LLM 响应中提取分析结果"""
        try:
            result_content = llm_response
            
            # 删除"思考字符："等前缀
            prefixes_to_remove = ["思考字符：", "思考过程：", "分析过程：", "推理过程：", "思考：", "分析：", "推理："]
            for prefix in prefixes_to_remove:
                if result_content.startswith(prefix):
                    result_content = result_content[len(prefix):].strip()
                    break
            
            # 如果结果以换行符开始，删除前面的换行符
            result_content = result_content.lstrip('\n\r')
            
            # 尝试解析 JSON 格式的响应
            if result_content.strip().startswith('{'):
                response_dict = json.loads(result_content)
                result_content = response_dict.get("result", result_content)

            # 提取报告内容（从基地名称开始）
            if "日志分析报告" in result_content:
                parts = result_content.split("日志分析报告", 1)
                if len(parts) >= 2:
                    return "日志分析报告\n" + parts[1].strip()
            
            return result_content.strip()
        except Exception as e:
            return f"[错误] 分析结果提取失败：{str(e)}"

    async def analyze_logs(
        self, 
        logs: List[Dict[str, Any]], 
        base_name: str,
        base_name_cn: str = ""
    ) -> Dict[str, Any]:
        """使用 LLM 分析日志"""
        try:
            # 每次调用时重新获取激活的模型客户端
            llm_client = self._get_active_model_client()
            
            # 格式化日志数据
            formatted_logs = self.format_logs_for_analysis(logs, base_name_cn or base_name)
            
            # 加载 prompt 模板
            from pathlib import Path
            prompt_path = Path(__file__).parent.parent / "models" / "prompts" / "log_analysis.txt"
            
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()

            # 构建 prompt
            prompt = prompt_template.replace(
                "{{#context#}}", 
                formatted_logs
            ).replace(
                "{base_name}", 
                base_name_cn or base_name
            ).replace(
                "{elk_url}", 
                "日志系统"
            )

            messages = [
                {
                    "role": "system", 
                    "content": "你是一名网络日志分析专家，只输出分析结果，不输出任何解释或思考过程。"
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ]

            # 调用 LLM
            analysis_result = await llm_client.chat_completion(
                messages=messages,
                temperature=0.6
            )

            # 提取分析结果
            extracted_result = self.extract_analysis_result(analysis_result)

            return {
                "success": True,
                "result": extracted_result,
                "log_count": len(logs),
                "base_name": base_name,
                "base_name_cn": base_name_cn
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"日志分析失败：{str(e)}",
                "log_count": len(logs),
                "base_name": base_name
            }
