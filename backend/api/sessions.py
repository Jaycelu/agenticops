from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from storage.session_storage import session_storage

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class Message(BaseModel):
    role: str
    content: str
    timestamp: Optional[int] = None
    execution_results: Optional[List[dict]] = None
    trace_id: Optional[str] = None


class SessionCreate(BaseModel):
    session_id: Optional[str] = None
    name: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    created_at: str
    updated_at: str
    message_count: int
    title: str


class SessionDetailResponse(BaseModel):
    session_id: str
    created_at: str
    updated_at: str
    messages: List[Message]


@router.get("/", response_model=List[SessionResponse])
async def list_sessions():
    """获取所有会话列表"""
    sessions = session_storage.list_sessions()
    return sessions


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str):
    """获取会话详情"""
    session_data = session_storage.load_session(session_id)
    if session_data is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionDetailResponse(**session_data)


@router.post("/", response_model=SessionResponse)
async def create_session(session: SessionCreate):
    """创建新会话"""
    import uuid
    from datetime import datetime

    # 如果没有提供 session_id，则生成一个新的
    session_id = session.session_id or str(uuid.uuid4())

    # 检查会话是否已存在
    existing = session_storage.load_session(session_id)
    if existing:
        # 返回现有会话
        sessions = session_storage.list_sessions()
        for s in sessions:
            if s["session_id"] == session_id:
                return SessionResponse(**s)

    # 创建新会话
    session_storage.save_session(session_id, [])

    sessions = session_storage.list_sessions()
    for s in sessions:
        if s["session_id"] == session_id:
            return SessionResponse(**s)

    raise HTTPException(status_code=500, detail="Failed to create session")


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    success = session_storage.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"message": "Session deleted successfully"}


@router.post("/{session_id}/messages")
async def add_message(session_id: str, message: Message):
    """向会话添加消息"""
    session_data = session_storage.load_session(session_id)
    if session_data is None:
        raise HTTPException(status_code=404, detail="Session not found")

    message_dict = message.model_dump()
    if message_dict.get("timestamp") is None:
        from datetime import datetime
        message_dict["timestamp"] = int(datetime.now().timestamp() * 1000)

    session_storage.add_message(session_id, message_dict)

    return {"message": "Message added successfully"}