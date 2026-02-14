from typing import List, Optional
from agent.schemas import ChatRequest, ChatResponse, Intent, ExecutionPlan, ExecutionStep
from agent.intent import IntentAgent
from agent.planner import PlannerAgent
from agent.executor import ExecutorAgent
from agent.summarizer import SummarizerAgent
from models.llm_client import LLMClient
from utils.idgen import generate_id
from config.logging import logger
from config.settings import settings
from storage.session_storage import session_storage


class Orchestrator:
    def __init__(self):
        self.llm_client = LLMClient(
            model=settings.llm_model_name,
            api_key=settings.llm_api_key,
            base_url=settings.llm_api_url
        )
        self.intent_agent = IntentAgent(self.llm_client)
        self.planner_agent = PlannerAgent()
        self.executor_agent = ExecutorAgent()
        self.summarizer_agent = SummarizerAgent(self.llm_client)

    async def handle_chat(self, request: ChatRequest) -> ChatResponse:
        trace_id = generate_id("trace")
        session_id = request.session_id or "default"
        logger.info(f"[{trace_id}] Handling chat request: {request.message}")

        # 保存用户消息
        from datetime import datetime
        user_message = {
            "role": "user",
            "content": request.message,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
        session_storage.add_message(session_id, user_message)

        try:
            intent = await self.intent_agent.detect_intent(request.message)
            logger.info(f"[{trace_id}] Detected intent: {intent.intent}")

            # 低置信度或槽位缺失时，优先澄清，避免误调度
            if intent.needs_clarification or intent.confidence < 0.55:
                clarification = intent.clarification_question
                if not clarification:
                    missing = "、".join(intent.missing_slots) if intent.missing_slots else "关键信息"
                    clarification = f"为避免误操作，请补充{missing}后再执行。"

                assistant_message = {
                    "role": "assistant",
                    "content": clarification,
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "trace_id": trace_id
                }
                session_storage.add_message(session_id, assistant_message)
                return ChatResponse(
                    response=clarification,
                    trace_id=trace_id
                )

            if intent.intent == "other" or intent.intent == "technical_concept":
                # 对于技术概念性问题和其他问题，调用大模型进行回答
                messages = [
                    {"role": "system", "content": "你是一个专业的网络运维AI助手，精通网络技术，包括但不限于交换机堆叠、VRRP、OSPF、BGP、MPLS等网络协议和技术。请用专业但易懂的语言回答用户的技术问题。直接输出答案，不要包含思考过程（如\"thinking\"等标记）或多余的格式符号，保持回答简洁清晰。"},
                    {"role": "user", "content": request.message}
                ]
                
                summary = await self.llm_client.chat_completion(messages, temperature=0.3)
                
                assistant_message = {
                    "role": "assistant",
                    "content": summary,
                    "timestamp": int(datetime.now().timestamp() * 1000)
                }
                session_storage.add_message(session_id, assistant_message)

                return ChatResponse(
                    response=summary,
                    trace_id=trace_id
                )

            plan = await self.planner_agent.build_plan(intent)
            logger.info(f"[{trace_id}] Built execution plan with {len(plan.steps)} steps")

            execution_results = []
            for step in plan.steps:
                result_step = await self.executor_agent.execute_step(step)
                execution_results.append(result_step)

            summary = await self.summarizer_agent.summarize(request.message, execution_results)
            logger.info(f"[{trace_id}] Generated summary")

            # 保存AI回复消息
            assistant_message = {
                "role": "assistant",
                "content": summary,
                "timestamp": int(datetime.now().timestamp() * 1000),
                "execution_results": [
                    {
                        "step_id": step.step_id,
                        "tool": step.tool,
                        "action": step.action,
                        "status": step.status,
                        "result": step.result,
                        "error": step.error,
                        "start_time": step.start_time.isoformat() if step.start_time else None,
                        "end_time": step.end_time.isoformat() if step.end_time else None
                    }
                    for step in execution_results
                ],
                "trace_id": trace_id
            }
            session_storage.add_message(session_id, assistant_message)

            return ChatResponse(
                response=summary,
                execution_plan=plan,
                execution_results=execution_results,
                trace_id=trace_id
            )

        except Exception as e:
            logger.error(f"[{trace_id}] Error handling chat: {str(e)}")
            assistant_message = {
                "role": "assistant",
                "content": f"处理请求时出错: {str(e)}",
                "timestamp": int(datetime.now().timestamp() * 1000)
            }
            session_storage.add_message(session_id, assistant_message)

            return ChatResponse(
                response=assistant_message["content"],
                trace_id=trace_id
            )
