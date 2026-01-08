"""
Session 管理模块
=================

基于 Redis 的会话状态管理
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from redis import Redis

from app.core.redis_client import get_redis
from app.schemas.session_schema import (
    AnalysisSession,
    SessionStatus,
    TimeSeriesPoint,
    NewsItem,
    ReportItem,
    EmotionAnalysis,
    StepDetail,
    RAGSource,
    IntentResult
)
from app.core.step_definitions import get_steps_for_intent, get_step_count


class Session:
    """分析会话管理器"""
    
    def __init__(self, session_id: str, redis_client: Optional[Redis] = None):
        self.session_id = session_id
        self.redis = redis_client or get_redis()
        self.key = f"session:{session_id}"
        self.ttl = 86400  # 24小时过期
    
    @classmethod
    def create(cls, context: str = "", model_name: str = "prophet") -> "Session":
        """
        创建新会话
        
        Args:
            context: 上下文
            model_name: 模型名称
            
        Returns:
            Session 实例
        """
        session_id = str(uuid.uuid4())
        session = cls(session_id)
        
        #初始化会话数据
        now = datetime.now().isoformat()
        initial_data = AnalysisSession(
            session_id=session_id,
            context=context,
            model_name=model_name,
            status=SessionStatus.PENDING,
            created_at=now,
            updated_at=now
        )
        
        session._save(initial_data)
        return session
    
    def get(self) -> Optional[AnalysisSession]:
        """获取会话数据"""
        data = self.redis.get(self.key)
        if not data:
            return None
        return AnalysisSession.model_validate_json(data)
    
    def _save(self, data: AnalysisSession):
        """保存会话数据"""
        data.updated_at = datetime.now().isoformat()
        json_data = data.model_dump_json()
        self.redis.setex(
            self.key,
            self.ttl,
            json_data
        )
        # 添加日志确认保存
        print(f"✅ Session {self.session_id} saved: status={data.status}, steps={data.steps}")
    
    def update_step(self, step: int):
        """更新当前步骤"""
        data = self.get()
        if data:
            data.steps = step
            data.status = SessionStatus.PROCESSING
            self._save(data)
            print(f"📊 Step {step}/7 updated")
    
    def save_time_series_original(self, points: List[TimeSeriesPoint]):
        """保存原始时序数据"""
        data = self.get()
        if data:
            data.time_series_original = points
            self._save(data)
            print(f"📈 Saved {len(points)} original data points")
    
    def save_time_series_full(self, points: List[TimeSeriesPoint], prediction_start: str):
        """保存完整时序数据（含预测）"""
        data = self.get()
        if data:
            data.time_series_full = points
            data.prediction_start_day = prediction_start
            data.prediction_done = True
            self._save(data)
            print(f"🔮 Saved {len(points)} full data points (with predictions)")
    
    def save_news(self, news: List[NewsItem]):
        """保存新闻列表"""
        data = self.get()
        if data:
            data.news_list = news
            self._save(data)
            print(f"📰 Saved {len(news)} news items")
    
    def save_emotion(self, emotion: EmotionAnalysis):
        """保存情绪分析"""
        data = self.get()
        if data:
            data.emotion = emotion.score
            data.emotion_des = emotion.description
            self._save(data)
            print(f"😊 Saved emotion: {emotion.score}")
    
    def save_conclusion(self, conclusion: str):
        """保存综合报告"""
        data = self.get()
        if data:
            data.conclusion = conclusion
            self._save(data)
            print(f"📝 Saved conclusion: {len(conclusion)} characters")
    
    def mark_completed(self):
        """标记为完成"""
        data = self.get()
        if data:
            data.status = SessionStatus.COMPLETED
            data.steps = 7  # 完成所有步骤
            self._save(data)
            print(f"✅✅✅ Session {self.session_id} MARKED AS COMPLETED ✅✅✅")
            
            # 验证保存
            verification = self.get()
            if verification and verification.status == SessionStatus.COMPLETED:
                print(f"✅ Verification SUCCESS: status={verification.status}, steps={verification.steps}")
            else:
                print(f"❌ Verification FAILED: status={verification.status if verification else 'None'}")
    
    def mark_error(self, error_message: str):
        """标记为错误"""
        data = self.get()
        if data:
            data.status = SessionStatus.ERROR
            data.error_message = error_message
            self._save(data)
            print(f"❌ Session marked as ERROR: {error_message}")
    
    def delete(self):
        """删除会话"""
        self.redis.delete(self.key)
        print(f"🗑️  Session {self.session_id} deleted")
    
    @classmethod
    def exists(cls, session_id: str) -> bool:
        """检查会话是否存在"""
        redis = get_redis()
        return redis.exists(f"session:{session_id}") > 0

    # ========== v2 新增方法 ==========

    def save_intent_result(self, intent: str, intent_result: dict):
        """
        保存意图识别结果并初始化步骤

        Args:
            intent: 意图类型 (forecast/rag/news/chat)
            intent_result: 意图识别结果字典
        """
        data = self.get()
        if data:
            data.intent = intent
            data.intent_result = IntentResult(
                intent=intent_result.get("intent", "analyze"),
                reason=intent_result.get("reason", ""),
                tools=intent_result.get("tools", {"forecast": True, "report_rag": False, "news_rag": False}),
                model=intent_result.get("model", "prophet"),
                params=intent_result.get("params", {"history_days": 365, "forecast_horizon": 30})
            )

            # 初始化步骤详情
            steps = get_steps_for_intent(intent)
            data.total_steps = len(steps)
            data.step_details = [
                StepDetail(id=s["id"], name=s["name"], status="pending", message="")
                for s in steps
            ]

            self._save(data)
            print(f"🎯 Intent saved: {intent}, total_steps={data.total_steps}")

    def update_step_detail(self, step: int, status: str, message: str = ""):
        """
        更新步骤详情

        Args:
            step: 步骤编号 (1-based)
            status: 状态 (pending/running/completed/error)
            message: 状态消息
        """
        data = self.get()
        if data and 0 < step <= len(data.step_details):
            data.steps = step  # 兼容旧字段
            data.status = SessionStatus.PROCESSING
            data.step_details[step - 1].status = status
            data.step_details[step - 1].message = message
            self._save(data)
            print(f"📊 Step {step}/{data.total_steps} [{status}]: {message}")

    def save_rag_sources(self, sources: List[RAGSource]):
        """保存 RAG 来源"""
        data = self.get()
        if data:
            data.rag_sources = sources
            self._save(data)
            print(f"📚 Saved {len(sources)} RAG sources")

    def get_conversation_history(self) -> List[dict]:
        """获取对话历史"""
        data = self.get()
        return data.conversation_history if data else []

    def add_conversation_message(self, role: str, content: str):
        """
        添加对话消息

        Args:
            role: 角色 (user/assistant)
            content: 消息内容
        """
        data = self.get()
        if data:
            data.conversation_history.append({"role": role, "content": content})
            # 保留最近10轮对话
            if len(data.conversation_history) > 20:
                data.conversation_history = data.conversation_history[-20:]
            self._save(data)
            print(f"💬 Added {role} message to history")

    def reset_for_new_query(self):
        """重置会话状态（用于多轮对话的新查询）"""
        data = self.get()
        if data:
            # 保留会话历史，重置其他状态
            data.status = SessionStatus.PENDING
            data.steps = 0
            data.intent = "pending"
            data.intent_result = None
            data.total_steps = 0
            data.step_details = []
            data.time_series_original = []
            data.time_series_full = []
            data.prediction_done = False
            data.prediction_start_day = None
            data.news_list = []
            data.rag_sources = []
            data.emotion = None
            data.emotion_des = None
            data.conclusion = ""
            data.error_message = None
            self._save(data)
            print(f"🔄 Session reset for new query")

    def mark_completed_v2(self):
        """标记为完成（v2 版本，使用动态步骤数）"""
        data = self.get()
        if data:
            data.status = SessionStatus.COMPLETED
            data.steps = data.total_steps  # 使用动态步骤数
            # 将所有步骤标记为完成
            for step in data.step_details:
                if step.status != "error":
                    step.status = "completed"
            self._save(data)
            print(f"✅✅✅ Session {self.session_id} COMPLETED ({data.total_steps} steps) ✅✅✅")
