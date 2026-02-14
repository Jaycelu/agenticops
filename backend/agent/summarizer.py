from typing import List
from models.llm_client import LLMClient
from agent.schemas import ExecutionStep
import json
import os


class SummarizerAgent:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.prompt_template = self._load_prompt("summary.txt")

    def _load_prompt(self, filename: str) -> str:
        prompt_path = os.path.join(os.path.dirname(__file__), "../models/prompts", filename)
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    async def summarize(self, user_question: str, execution_steps: List[ExecutionStep]) -> str:
        try:
            steps_summary = []
            for step in execution_steps:
                step_info = {
                    "tool": step.tool,
                    "action": step.action,
                    "status": step.status,
                    "result": step.result if step.result else step.error
                }
                steps_summary.append(step_info)

            prompt = self.prompt_template.format(
                user_question=user_question,
                execution_steps=json.dumps(steps_summary, ensure_ascii=False, indent=2)
            )

            messages = [
                {"role": "system", "content": "你是一个专业的网络运维AI助手，只输出最终结果，不输出思考过程。"},
                {"role": "user", "content": prompt}
            ]

            result = await self.llm_client.chat_completion(messages, temperature=0.3)
            return result

        except Exception as e:
            return f"执行总结时出错: {str(e)}"