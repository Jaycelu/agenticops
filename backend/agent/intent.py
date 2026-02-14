from models.llm_client import LLMClient
from agent.schemas import Intent
import os


class IntentAgent:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client
        self.prompt_template = self._load_prompt("intent.txt")

    def _load_prompt(self, filename: str) -> str:
        prompt_path = os.path.join(os.path.dirname(__file__), "../models/prompts", filename)
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    async def detect_intent(self, user_input: str) -> Intent:
        try:
            prompt = self.prompt_template.format(user_input=user_input)
            messages = [
                {"role": "system", "content": "你是一个专业的网络运维AI助手。"},
                {"role": "user", "content": prompt}
            ]

            result = await self.llm_client.chat_completion_with_json(messages, temperature=0.3)
            if "confidence" not in result:
                result["confidence"] = 0.5
            if "needs_clarification" not in result:
                result["needs_clarification"] = False
            if "missing_slots" not in result:
                result["missing_slots"] = []
            if "clarification_question" not in result:
                result["clarification_question"] = None

            return Intent(**result)
        except Exception as e:
            return Intent(
                intent="other",
                targets=[],
                time_range=None,
                tools=[],
                risk_level="read_only",
                confidence=0.0,
                needs_clarification=False,
                missing_slots=[]
            )
