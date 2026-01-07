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
    EmotionAnalysis
)


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
