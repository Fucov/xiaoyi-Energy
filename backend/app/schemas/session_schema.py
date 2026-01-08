"""
Session 数据模型
================

定义分析会话的数据结构
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    """会话状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class TimeSeriesPoint(BaseModel):
    """时序数据点"""
    date: str
    value: float
    is_prediction: bool = False


class NewsItem(BaseModel):
    """新闻条目"""
    title: str
    summary: str
    date: str
    source: str
    url: str = ""  # 新闻链接（Tavily 新闻有 URL）


class ReportItem(BaseModel):
    """研报条目"""
    title: str
    summary: str
    pdf_path: str


class EmotionAnalysis(BaseModel):
    """情绪分析结果"""
    score: float = Field(..., ge=-1, le=1, description="情绪分数 -1到1")
    description: str = Field(..., description="情绪描述")


class StepDetail(BaseModel):
    """步骤详情"""
    id: str
    name: str
    status: str = "pending"  # pending/running/completed/error
    message: str = ""


class RAGSource(BaseModel):
    """RAG 来源"""
    file_name: str
    page_number: int
    score: float
    content: str = ""  # 检索到的内容片段


class IntentResult(BaseModel):
    """意图识别结果"""
    intent: str  # analyze/answer
    reason: str = ""
    tools: Dict[str, bool] = {"forecast": True, "report_rag": False, "news_rag": False}
    model: str = "prophet"
    params: Dict[str, int] = {"history_days": 365, "forecast_horizon": 30}


class AnalysisSession(BaseModel):
    """分析会话完整数据模型"""

    # 基础信息
    session_id: str
    context: str = ""
    steps: int = 0  # 兼容旧字段，当前步骤编号
    status: SessionStatus = SessionStatus.PENDING
    is_time_series: bool = True

    # 意图相关（v2 新增）
    intent: str = "pending"  # pending/forecast/rag/news/chat
    intent_result: Optional[IntentResult] = None

    # 动态步骤（v2 新增）
    total_steps: int = 0  # 根据意图动态设置
    step_details: List[StepDetail] = []  # 详细步骤状态

    # 时序数据
    time_series_original: List[TimeSeriesPoint] = []
    time_series_full: List[TimeSeriesPoint] = []
    prediction_done: bool = False
    prediction_start_day: Optional[str] = None

    # 新闻和研报
    news_list: List[NewsItem] = []
    report_list: List[ReportItem] = []
    rag_sources: List[RAGSource] = []  # v2 新增：RAG 来源
    emotion: Optional[float] = None
    emotion_des: Optional[str] = None

    # 综合报告
    conclusion: str = ""

    # 对话历史（v2 新增）
    conversation_history: List[Dict[str, str]] = []

    # 元数据
    created_at: str
    updated_at: str
    error_message: Optional[str] = None

    # 额外配置
    stock_code: Optional[str] = None
    model_name: str = "prophet"


class CreateAnalysisRequest(BaseModel):
    """创建分析任务请求（v2 统一入口）"""
    message: str = Field(..., description="用户问题")
    session_id: Optional[str] = Field(default=None, description="会话ID，多轮对话时复用")
    model: str = Field(default="prophet", description="预测模型")
    context: str = Field(default="", description="上下文")
    force_intent: Optional[str] = Field(default=None, description="强制指定意图: forecast/rag/news/chat")


class AnalysisStatusResponse(BaseModel):
    """分析状态响应"""
    session_id: str
    status: SessionStatus
    steps: int
    data: AnalysisSession
