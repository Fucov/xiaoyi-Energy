"""
统一分析 API 端点 (v2)
======================

提供统一的异步分析接口，支持 forecast/rag/news/chat 四种意图
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.core.config import settings
from app.core.session import Session
from app.core.unified_tasks import get_task_processor
from app.schemas.session_schema import (
    CreateAnalysisRequest,
    AnalysisStatusResponse,
    SessionStatus
)

router = APIRouter()


@router.post("/create", response_model=dict)
async def create_analysis_task(
    request: CreateAnalysisRequest,
    background_tasks: BackgroundTasks
):
    """
    创建分析任务（统一入口）

    支持四种意图：
    - forecast: 完整预测分析（7步）
    - rag: 研报检索（2步）
    - news: 新闻搜索（2步）
    - chat: 纯对话（1步）

    Args:
        request: 请求体
            - message: 用户问题
            - session_id: 会话ID（可选，用于多轮对话）
            - model: 预测模型（prophet/xgboost/randomforest/dlinear）
            - context: 上下文
            - force_intent: 强制指定意图

    Returns:
        {
            "session_id": "uuid-xxx",
            "status": "created"
        }
    """
    try:
        api_key = settings.api_key
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 获取或创建 session
    if request.session_id and Session.exists(request.session_id):
        session = Session(request.session_id)
        # 复用现有会话，重置状态
        session.reset_for_new_query()
    else:
        session = Session.create(
            context=request.context,
            model_name=request.model
        )

    # 添加用户消息到历史
    session.add_conversation_message("user", request.message)

    # 在后台启动任务
    task_processor = get_task_processor(api_key)
    background_tasks.add_task(
        task_processor.execute,
        session.session_id,
        request.message,
        request.model,
        request.force_intent
    )

    return {
        "session_id": session.session_id,
        "status": "created"
    }


@router.get("/status/{session_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(session_id: str):
    """
    查询分析任务状态

    Args:
        session_id: 会话 ID

    Returns:
        AnalysisStatusResponse: 包含完整会话数据
    """
    session = Session(session_id)
    data = session.get()

    if not data:
        raise HTTPException(status_code=404, detail="会话不存在")

    return AnalysisStatusResponse(
        session_id=data.session_id,
        status=data.status,
        steps=data.steps,
        data=data
    )


@router.delete("/{session_id}")
async def delete_analysis_session(session_id: str):
    """
    删除分析会话

    Args:
        session_id: 会话 ID

    Returns:
        {"message": "会话已删除"}
    """
    if not Session.exists(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    session = Session(session_id)
    session.delete()

    return {"message": "会话已删除"}
