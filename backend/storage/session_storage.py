import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path


class SessionStorage:
    def __init__(self, storage_dir: str = "storage/chat_history"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, session_id: str) -> Path:
        return self.storage_dir / f"{session_id}.json"

    def save_session(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        """保存会话历史"""
        session_data = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "messages": messages
        }

        session_path = self._get_session_path(session_id)
        with open(session_path, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """加载会话历史"""
        session_path = self._get_session_path(session_id)
        if not session_path.exists():
            return None

        with open(session_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """获取所有会话列表"""
        sessions = []
        for session_file in self.storage_dir.glob("*.json"):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                    sessions.append({
                        "session_id": session_data["session_id"],
                        "created_at": session_data["created_at"],
                        "updated_at": session_data["updated_at"],
                        "message_count": len(session_data.get("messages", [])),
                        "title": self._generate_title(session_data.get("messages", []))
                    })
            except Exception as e:
                print(f"Error loading session {session_file}: {e}")
                continue

        # 按更新时间倒序排列
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        session_path = self._get_session_path(session_id)
        if session_path.exists():
            session_path.unlink()
            return True
        return False

    def _generate_title(self, messages: List[Dict[str, Any]]) -> str:
        """生成会话标题（使用第一条用户消息）"""
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                # 截取前30个字符作为标题
                return content[:30] + "..." if len(content) > 30 else content
        return "新会话"

    def add_message(self, session_id: str, message: Dict[str, Any]) -> None:
        """向会话添加消息"""
        session_data = self.load_session(session_id)
        if session_data is None:
            session_data = {
                "session_id": session_id,
                "created_at": datetime.now().isoformat(),
                "messages": []
            }

        session_data["messages"].append(message)
        session_data["updated_at"] = datetime.now().isoformat()
        self.save_session(session_id, session_data["messages"])


# 全局实例
session_storage = SessionStorage()