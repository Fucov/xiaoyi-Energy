"""
Chat API 新端点 - 异步任务版本
================================

创建分析任务和查询状态的API
"""

import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from app.core.config import settings

from app.schemas.session_schema import (
    CreateAnalysisRequest,
    AnalysisStatusResponse,
    SessionStatus
)
from app.core.session import Session
from app.core.tasks import get_task_processor

router = APIRouter()


@router.post("/create", response_model=dict)
async def create_analysis_task(
    request: CreateAnalysisRequest,
    background_tasks: BackgroundTasks
):
    """
    创建分析任务
    
    Request Body:
    {
        "message": "分析茅台未来一个月走势",
        "model": "prophet",
        "context": ""
    }
    
    Response:
    {
        "session_id": "uuid-xxxx",
        "status": "created"
    }
    """
    try:
        # 创建 session
        session = Session.create(
            context=request.context,
            model_name=request.model
        )
        
        # 在后台启动任务
        task_processor = get_task_processor(settings.DEEPSEEK_API_KEY)
        background_tasks.add_task(
            task_processor.execute,
            session.session_id,
            request.message,
            request.model
        )
        
        return {
            "session_id": session.session_id,
            "status": "created"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{session_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(session_id: str):
    """
    查询分析任务状态
    
    Response:
    {
        "session_id": "uuid",
        "status": "processing",
        "steps": 3,
        "data": {
            "session_id": "uuid",
            "context": "",
            "steps": 3,
            "status": "processing",
            ...
        }
    }
    """
    # 检查 session 是否存在
    if not Session.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 获取 session 数据
    session = Session(session_id)
    data = session.get()
    
    if not data:
        raise HTTPException(status_code=404, detail="Session data not found")
    
    return AnalysisStatusResponse(
        session_id=session_id,
        status=data.status,
        steps=data.steps,
        data=data
    )


@router.delete("/{session_id}")
async def delete_analysis_session(session_id: str):
    """
    删除分析会话
    
    Response:
    {
        "message": "Session deleted successfully"
    }
    """
    if not Session.exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = Session(session_id)
    session.delete()
    
    return {"message": "Session deleted successfully"}
