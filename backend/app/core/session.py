"""
Session 管理模块
=================

基于 Redis 的会话状态管理
"""

import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict
from redis import Redis

from app.core.redis_client import get_redis
from app.schemas.session_schema import (
    SessionData,
    SessionStatus,
    StepStatus,
    StepDetail,
    UnifiedIntent,
    ResolvedKeywords,
    StockMatchResult,
    TimeSeriesPoint,
    RAGSource,
    SummarizedNewsItem,
    ReportItem,
)
from app.core.step_definitions import get_steps_for_intent


class Session:
    """
    会话管理器

    基于 Redis 存储会话状态，支持预测和非预测两种流程
    """

    def __init__(self, session_id: str, redis_client: Optional[Redis] = None):
        self.session_id = session_id
        self.redis = redis_client or get_redis()
        self.key = f"session:{session_id}"
        self.ttl = 86400  # 24小时过期

    @classmethod
    def create(cls, context: str = "", model_name: str = "prophet") -> "Session":
        """创建新会话"""
        session_id = str(uuid.uuid4())
        session = cls(session_id)

        now = datetime.now().isoformat()
        initial_data = SessionData(
            session_id=session_id,
            context=context,
            model_name=model_name,
            status=SessionStatus.PENDING,
            created_at=now,
            updated_at=now
        )

        session._save(initial_data)
        return session

    @classmethod
    def exists(cls, session_id: str) -> bool:
        """检查会话是否存在"""
        redis = get_redis()
        return redis.exists(f"session:{session_id}") > 0

    def get(self) -> Optional[SessionData]:
        """获取会话数据"""
        data = self.redis.get(self.key)
        if not data:
            return None
        return SessionData.model_validate_json(data)

    def _save(self, data: SessionData):
        """保存会话数据"""
        data.updated_at = datetime.now().isoformat()
        json_data = data.model_dump_json()
        self.redis.setex(self.key, self.ttl, json_data)

    def delete(self):
        """删除会话"""
        self.redis.delete(self.key)
        print(f"[Session] Deleted: {self.session_id}")

    # ========== 意图相关 ==========

    def save_unified_intent(self, intent: UnifiedIntent):
        """保存统一意图识别结果"""
        data = self.get()
        if data:
            data.unified_intent = intent
            data.is_forecast = intent.is_forecast

            # 设置 intent 字段
            if not intent.is_in_scope:
                data.intent = "out_of_scope"
            elif intent.is_forecast:
                data.intent = "forecast"
            elif intent.enable_rag:
                data.intent = "rag"
            elif intent.enable_search or intent.enable_domain_info:
                data.intent = "news"
            else:
                data.intent = "chat"

            # 初始化步骤
            steps = get_steps_for_intent(data.intent)
            data.total_steps = len(steps)
            data.step_details = [
                StepDetail(id=s["id"], name=s["name"], status=StepStatus.PENDING, message="")
                for s in steps
            ]

            self._save(data)
            print(f"[Session] Intent: {data.intent}, forecast={intent.is_forecast}")

    # ========== 股票相关 ==========

    def save_stock_match(self, result: StockMatchResult):
        """保存股票匹配结果"""
        data = self.get()
        if data:
            data.stock_match = result
            if result.success and result.stock_info:
                data.stock_code = result.stock_info.stock_code
            self._save(data)
            print(f"[Session] Stock match: {result.success}")

    def save_resolved_keywords(self, keywords: ResolvedKeywords):
        """保存最终关键词"""
        data = self.get()
        if data:
            data.resolved_keywords = keywords
            self._save(data)

    # ========== 步骤管理 ==========

    def update_step_detail(self, step: int, status: str, message: str = ""):
        """更新步骤详情"""
        data = self.get()
        if data and 0 < step <= len(data.step_details):
            data.steps = step
            data.status = SessionStatus.PROCESSING
            data.step_details[step - 1].status = StepStatus(status)
            data.step_details[step - 1].message = message
            self._save(data)
            print(f"[Session] Step {step}/{data.total_steps} [{status}]: {message}")

    # ========== 数据保存 ==========

    def save_time_series_original(self, points: List[TimeSeriesPoint]):
        """保存原始时序数据"""
        data = self.get()
        if data:
            data.time_series_original = points
            self._save(data)

    def save_time_series_full(self, points: List[TimeSeriesPoint], prediction_start: str):
        """保存完整时序数据（含预测）"""
        data = self.get()
        if data:
            data.time_series_full = points
            data.prediction_start_day = prediction_start
            data.prediction_done = True
            self._save(data)

    def save_news(self, news: List[SummarizedNewsItem]):
        """保存新闻列表"""
        data = self.get()
        if data:
            data.news_list = news
            self._save(data)

    def save_reports(self, reports: List[ReportItem]):
        """保存研报列表"""
        data = self.get()
        if data:
            data.report_list = reports
            self._save(data)

    def save_rag_sources(self, sources: List[RAGSource]):
        """保存 RAG 来源"""
        data = self.get()
        if data:
            data.rag_sources = sources
            self._save(data)

    def save_emotion(self, score: float, description: str):
        """保存情绪分析"""
        data = self.get()
        if data:
            data.emotion = score
            data.emotion_des = description
            self._save(data)

    def save_conclusion(self, conclusion: str):
        """保存综合报告"""
        data = self.get()
        if data:
            data.conclusion = conclusion
            self._save(data)

    # ========== 状态管理 ==========

    def mark_completed(self):
        """标记为完成"""
        data = self.get()
        if data:
            data.status = SessionStatus.COMPLETED
            data.steps = data.total_steps
            for step in data.step_details:
                if step.status != StepStatus.ERROR:
                    step.status = StepStatus.COMPLETED
            self._save(data)
            print(f"[Session] Completed: {self.session_id}")

    def mark_error(self, error_message: str):
        """标记为错误"""
        data = self.get()
        if data:
            data.status = SessionStatus.ERROR
            data.error_message = error_message
            self._save(data)
            print(f"[Session] Error: {error_message}")

    # ========== 对话历史 ==========

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        data = self.get()
        return data.conversation_history if data else []

    def add_conversation_message(self, role: str, content: str):
        """添加对话消息"""
        data = self.get()
        if data:
            data.conversation_history.append({"role": role, "content": content})
            if len(data.conversation_history) > 20:
                data.conversation_history = data.conversation_history[-20:]
            self._save(data)

    def reset_for_new_query(self):
        """重置会话状态（用于多轮对话的新查询）"""
        data = self.get()
        if data:
            data.status = SessionStatus.PENDING
            data.steps = 0
            data.intent = "pending"
            data.unified_intent = None
            data.stock_match = None
            data.resolved_keywords = None
            data.total_steps = 0
            data.step_details = []
            data.time_series_original = []
            data.time_series_full = []
            data.prediction_done = False
            data.prediction_start_day = None
            data.news_list = []
            data.report_list = []
            data.rag_sources = []
            data.emotion = None
            data.emotion_des = None
            data.conclusion = ""
            data.error_message = None
            data.is_forecast = False
            self._save(data)
            print(f"[Session] Reset for new query")
