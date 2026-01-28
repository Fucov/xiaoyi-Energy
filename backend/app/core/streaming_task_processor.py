"""
流式任务处理器
===============

完全流式架构 - 所有步骤的输出都通过 SSE 实时返回
支持断点续传：流式数据同时存入 Redis
"""

import asyncio
import os  # 用于读取环境变量
import json
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict, Any, Callable, Awaitable
import pandas as pd
import numpy as np

from app.core.session import Session, Message
from app.core.redis_client import get_redis
from app.schemas.session_schema import (
    TimeSeriesPoint,
    UnifiedIntent,
    ResolvedKeywords,
    StockMatchResult,  # 保留以兼容
    RegionMatchResult,
    SummarizedNewsItem,
)

# Services
from app.services.stock_matcher import get_stock_matcher  # 保留以兼容
from app.services.region_matcher import get_region_matcher
from app.services.rag_client import check_rag_availability
from app.services.influence_analyzer import InfluenceAnalyzer
from app.data.industry_structure_client import get_industry_structure_client
from app.services.stock_signal_service import StockSignalService

# Agents
from app.agents import (
    IntentAgent,
    ReportAgent,
    ErrorExplainerAgent,
    SentimentAgent,
    NewsSummaryAgent,
    PredictionAnalysisAgent,
)
from app.services.trend_service import TrendService

# Data clients
from app.data.rag_searcher import RAGSearcher

# Data & Models
from app.data import extract_domain
from app.data.fetcher import DataFetchError
from app.models import TimeSeriesAnalyzer

# Workflows
from app.core.workflows import (
    fetch_power_data,
    fetch_news_all,
    fetch_rag_reports,
    search_web,
    search_news_around_date,
    fetch_domain_news,
    run_forecast,
    df_to_points,
    recommend_forecast_params,
    select_best_model,
)


class StreamingTaskProcessor:
    """
    流式任务处理器

    核心流程（全程流式）:
    1. 意图识别 - 流式返回思考过程
    2. 股票验证 - 返回匹配结果
    3. 数据获取 - 返回历史数据和新闻
    4. 分析处理 - 返回特征和情绪
    5. 模型预测 - 返回预测结果
    6. 报告生成 - 流式返回报告内容
    """

    # Baseline 惩罚机制开关
    # True: 启用惩罚机制，用户指定模型不如 baseline 时降级为 baseline
    # False: 禁用惩罚机制，即使最佳模型不如 baseline 也使用最佳模型
    ENABLE_BASELINE_PENALTY = False

    def __init__(self):
        self.intent_agent = IntentAgent()
        self.rag_searcher = RAGSearcher()
        self.report_agent = ReportAgent()
        self.error_explainer = ErrorExplainerAgent()
        self.sentiment_agent = SentimentAgent()
        self.news_summary_agent = NewsSummaryAgent()
        self.stock_matcher = get_stock_matcher()  # 保留以兼容
        self.region_matcher = get_region_matcher()
        self.prediction_analysis_agent = PredictionAnalysisAgent()
        self.redis = get_redis()

    async def execute_streaming(
        self,
        session_id: str,
        message_id: str,
        user_input: str,
        event_queue: asyncio.Queue | None,
        model_name: Optional[str] = None,
    ):
        """
        执行完全流式任务

        Args:
            session_id: 会话 ID
            message_id: 消息 ID
            user_input: 用户输入
            event_queue: 事件队列（发送到 SSE，后台任务时为 None）
            model_name: 预测模型名称
        """
        session = Session(session_id)
        message = Message(message_id, session_id)

        # 设置流式状态
        self._update_stream_status(message, "streaming")

        try:
            conversation_history = session.get_conversation_history()

            # === Step 1: 意图识别（流式） ===
            await self._emit_event(
                event_queue,
                message,
                {"type": "step_start", "step": 1, "step_name": "意图识别"},
            )

            message.update_step_detail(1, "running", "分析用户意图...")

            intent, thinking_content = await self._step_intent_streaming(
                user_input, conversation_history, event_queue, message
            )

            if not intent:
                await self._emit_error(event_queue, message, "意图识别失败")
                return

            # 如果用户通过 API 指定了模型，覆盖意图识别的结果
            # print(f"[ModelSelection] API 传入的 model_name: {model_name}")
            # print(f"[ModelSelection] 意图识别返回的 forecast_model: {intent.forecast_model}")
            if model_name is not None:
                intent.forecast_model = model_name
                # print(f"[ModelSelection] 使用 API 指定的模型: {model_name}")
            else:
                # 如果用户没有通过 API 指定模型，且 LLM 返回的是 "prophet"（可能是默认值），
                # 则将其设为 None，触发自动模型选择
                intent.forecast_model = None

            # 保存意图
            message.save_unified_intent(intent)
            message.append_thinking_log("intent", "意图识别", thinking_content)

            # 发送意图结果
            await self._emit_event(
                event_queue,
                message,
                {
                    "type": "intent",
                    "intent": "forecast" if intent.is_forecast else "chat",
                    "is_forecast": intent.is_forecast,
                    "reason": intent.reason,
                },
            )

            # 处理超出范围
            if not intent.is_in_scope:
                reply = (
                    intent.out_of_scope_reply
                    or "抱歉，我是金融时序分析助手，暂不支持此类问题。"
                )
                message.save_conclusion(reply)
                message.update_step_detail(1, "completed", "超出服务范围")
                message.mark_completed()
                self._update_stream_status(message, "completed")
                await self._emit_event(
                    event_queue,
                    message,
                    {"type": "chat_chunk", "content": reply, "is_complete": True},
                )
                await self._emit_done(event_queue, message)
                return

            await self._emit_event(
                event_queue,
                message,
                {
                    "type": "step_complete",
                    "step": 1,
                    "data": {"intent": "forecast" if intent.is_forecast else "chat"},
                },
            )
            message.update_step_detail(
                1, "completed", f"意图: {'预测' if intent.is_forecast else '对话'}"
            )

            # === Step 2: 区域验证 ===
            region_match_result = None
            stock_match_result = None  # 保留以兼容
            resolved_keywords = None

            # 优先使用region_mention，如果没有则使用stock_mention（兼容旧数据）
            region_mention = intent.region_mention or intent.stock_mention

            if region_mention:
                await self._emit_event(
                    event_queue,
                    message,
                    {"type": "step_start", "step": 2, "step_name": "区域验证"},
                )

                query_name = (
                    intent.region_name or intent.stock_full_name or region_mention
                )
                message.update_step_detail(2, "running", f"验证区域: {query_name}")

                region_match_result = await asyncio.to_thread(
                    self.region_matcher.match, query_name
                )

                if not region_match_result or not region_match_result.matched:
                    error_msg = f"未找到区域「{query_name}」，请检查区域名称是否正确。支持的区域: 北京、上海、广州、深圳、杭州、成都、武汉、西安、南京、天津"
                    message.save_conclusion(error_msg)
                    message.update_step_detail(2, "error", error_msg)
                    message.mark_completed()
                    self._update_stream_status(message, "error")
                    await self._emit_error(event_queue, message, error_msg)
                    return

                region_info = region_match_result.region_info
                resolved_keywords = self.intent_agent.resolve_keywords(
                    intent,
                    region_name=region_info.region_name if region_info else None,
                    region_code=region_info.region_code if region_info else None,
                )
                message.save_resolved_keywords(resolved_keywords)

                await self._emit_event(
                    event_queue,
                    message,
                    {
                        "type": "step_complete",
                        "step": 2,
                        "data": {
                            "region_code": region_info.region_code
                            if region_info
                            else "",
                            "region_name": region_info.region_name
                            if region_info
                            else "",
                        },
                    },
                )
                message.update_step_detail(
                    2,
                    "completed",
                    f"匹配: {region_info.region_name}({region_info.region_code})"
                    if region_info
                    else "无匹配",
                )
            else:
                resolved_keywords = ResolvedKeywords(
                    search_keywords=intent.raw_search_keywords,
                    rag_keywords=intent.raw_rag_keywords,
                    domain_keywords=intent.raw_domain_keywords,
                )

            # === 根据意图执行不同流程 ===
            if intent.is_forecast:
                await self._execute_forecast_streaming(
                    message,
                    session,
                    user_input,
                    intent,
                    region_match_result,  # 使用region_match_result
                    resolved_keywords,
                    conversation_history,
                    event_queue,
                )
            else:
                await self._execute_chat_streaming(
                    message,
                    session,
                    user_input,
                    intent,
                    region_match_result,  # 使用region_match_result
                    resolved_keywords,
                    conversation_history,
                    event_queue,
                )

            # 标记完成
            message.mark_completed()
            self._update_stream_status(message, "completed")

            # 添加助手回复到对话历史
            data = message.get()
            if data and data.conclusion:
                session.add_conversation_message("assistant", data.conclusion)

            await self._emit_done(event_queue, message)

        except Exception as e:
            print(f"❌ Streaming task error: {traceback.format_exc()}")
            message.mark_error(str(e))
            self._update_stream_status(message, "error")
            await self._emit_error(event_queue, message, str(e))

    # ========== 流式意图识别 ==========

    async def _step_intent_streaming(
        self,
        user_input: str,
        conversation_history: List[dict],
        event_queue: asyncio.Queue | None,
        message: Message,
    ) -> tuple:
        """流式意图识别"""
        import queue as thread_queue

        chunk_queue: thread_queue.Queue = thread_queue.Queue()

        def on_chunk(chunk: str):
            """同步回调 - 放入线程安全队列"""
            chunk_queue.put(chunk)

        def run_intent():
            """在线程中运行意图识别"""
            result = self.intent_agent.recognize_intent_streaming(
                user_input, conversation_history, on_chunk
            )
            chunk_queue.put(None)  # 结束标记
            return result

        # 启动线程任务
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(None, run_intent)

        # 轮询队列，通过 _emit_event 发送事件
        thinking_content = ""
        while True:
            try:
                chunk = chunk_queue.get_nowait()
                if chunk is None:
                    break
                thinking_content += chunk
                await self._emit_event(
                    event_queue,
                    message,
                    {"type": "thinking", "content": thinking_content},
                )
            except thread_queue.Empty:
                if future.done():
                    # 处理剩余的 chunks
                    while not chunk_queue.empty():
                        chunk = chunk_queue.get_nowait()
                        if chunk is not None:
                            thinking_content += chunk
                            await self._emit_event(
                                event_queue,
                                message,
                                {"type": "thinking", "content": thinking_content},
                            )
                    break
                await asyncio.sleep(0.01)

        intent, final_thinking = await future
        return intent, final_thinking or thinking_content

    # ========== 预测流程（流式） ==========

    async def _execute_forecast_streaming(
        self,
        message: Message,
        session: Session,
        user_input: str,
        intent: UnifiedIntent,
        region_match: Optional[RegionMatchResult],
        keywords: ResolvedKeywords,
        conversation_history: List[dict],
        event_queue: asyncio.Queue | None,
    ):
        """流式预测流程"""
        region_info = region_match.region_info if region_match else None
        region_name = region_info.region_name if region_info else user_input
        region_code = region_info.region_code if region_info else ""

        # === Step 3: 数据获取 ===
        await self._emit_event(
            event_queue,
            message,
            {"type": "step_start", "step": 3, "step_name": "数据获取"},
        )
        message.update_step_detail(3, "running", "获取历史数据和新闻...")

        # 限制历史天数，确保不超过Open-Meteo API限制（92天）
        # 同时确保有足够的数据用于模型训练
        effective_history_days = min(intent.history_days, 92)
        effective_history_days = max(effective_history_days, 30)  # 至少30天用于训练

        # 使用北京时区确保一致性
        BEIJING_TZ = ZoneInfo("Asia/Shanghai")
        now = datetime.now(BEIJING_TZ)
        end_date = now.strftime("%Y%m%d")
        start_date = (now - timedelta(days=effective_history_days)).strftime("%Y%m%d")

        # 并行获取数据
        power_data_task = asyncio.create_task(
            fetch_power_data(region_name, start_date, end_date, effective_history_days)
        )
        news_task = asyncio.create_task(
            fetch_news_all(region_name, intent.history_days)
        )
        rag_available = await check_rag_availability() if intent.enable_rag else False
        rag_task = (
            asyncio.create_task(
                fetch_rag_reports(self.rag_searcher, keywords.rag_keywords)
            )
            if intent.enable_rag and rag_available
            else None
        )

        # 优先获取供电需求数据和天气数据
        try:
            power_result = await power_data_task
        except Exception as e:
            power_result = e

        # 处理供电需求数据
        df = None
        weather_df = None
        if isinstance(power_result, DataFetchError):
            error_explanation = await asyncio.to_thread(
                self.error_explainer.explain_data_fetch_error, power_result, user_input
            )
            message.save_conclusion(error_explanation)
            message.update_step_detail(3, "error", "数据获取失败")
            news_task.cancel()
            if rag_task:
                rag_task.cancel()
            await self._emit_error(event_queue, message, error_explanation)
            return
        elif isinstance(power_result, Exception):
            error_msg = f"获取数据时发生错误: {str(power_result)}"
            message.save_conclusion(error_msg)
            message.update_step_detail(3, "error", "数据获取失败")
            news_task.cancel()
            if rag_task:
                rag_task.cancel()
            await self._emit_error(event_queue, message, error_msg)
            return
        else:
            # 处理返回的元组 (供电数据, 天气数据)
            if isinstance(power_result, tuple):
                df, weather_df = power_result
            else:
                df = power_result
                weather_df = None

        if df is None or df.empty:
            error_msg = (
                f"无法获取 {region_name} 的历史供电需求数据，请检查区域名称是否正确。"
            )
            message.save_conclusion(error_msg)
            message.update_step_detail(3, "error", "数据获取失败")
            news_task.cancel()
            if rag_task:
                rag_task.cancel()
            await self._emit_error(event_queue, message, error_msg)
            return

        # 立即保存并发送供电需求数据
        original_points = df_to_points(df, is_prediction=False)
        message.save_time_series_original(original_points)

        await self._emit_event(
            event_queue,
            message,
            {
                "type": "data",
                "data_type": "time_series_original",
                "data": [p.model_dump() for p in original_points],
            },
        )

        # 等待新闻和 RAG
        pending_tasks = [news_task]
        if rag_task:
            pending_tasks.append(rag_task)

        other_results = await asyncio.gather(*pending_tasks, return_exceptions=True)

        news_result = (
            other_results[0]
            if not isinstance(other_results[0], Exception)
            else ([], {})
        )
        rag_sources = (
            other_results[1]
            if len(other_results) > 1
            and not isinstance(other_results[1], Exception)
            and intent.enable_rag
            else []
        )

        news_items, sentiment_result = news_result

        # 总结新闻 - 直接调用 Agent
        if news_items:
            summarized_news, _ = await asyncio.to_thread(
                self.news_summary_agent.summarize, news_items
            )
        else:
            summarized_news = []

        message.save_news(summarized_news)

        # 发送新闻数据
        if summarized_news:
            await self._emit_event(
                event_queue,
                message,
                {
                    "type": "data",
                    "data_type": "news",
                    "data": [n.model_dump() for n in summarized_news],
                },
            )

        if rag_sources:
            message.save_rag_sources(rag_sources)

        # === 计算异常区域（在Step 3完成前，确保resume时能获取到）===
        print(
            f"[AnomalyZones] Starting dynamic clustering for message {message.message_id}"
        )
        try:
            import pandas as pd
            from app.services.stock_signal_service import StockSignalService
            from app.agents.event_summary_agent import EventSummaryAgent

            # 从 df 提取日期、收盘价、成交量
            sig_df = pd.DataFrame(
                {
                    "date": df["ds"].dt.strftime("%Y-%m-%d"),
                    "close": df["y"],
                    "volume": df.get("volume", [1] * len(df)),
                }
            )

            # === 改动：不依赖新闻接口 ===
            # 构建新闻计数字典（强制为空，不使用 summarise_news）
            # The user requested to remove news interface dependency for detection.
            news_counts = {}
            # for news_item in summarized_news or []: ... (Removed)

            # === Redis 全局缓存检查 ===
            redis_client = get_redis()
            cache_key = f"power_zones_v3:{region_code}"
            cached_zones_json = None

            try:
                cached_zones_json = redis_client.get(cache_key)
                if cached_zones_json:
                    import json

                    anomaly_zones = json.loads(cached_zones_json)
                    print(
                        f"[AnomalyZones] ✓ Using Redis cached {len(anomaly_zones)} zones for {region_code}"
                    )
            except Exception as e:
                print(f"[AnomalyZones] Failed to get Redis client or cache: {e}")

            # 如果缓存不存在，计算并保存
            if not cached_zones_json:
                # 1. Trend Analysis (Regime Segmentation)
                trend_service = TrendService()
                # Use all methods but prefer PLR for visual zones
                trend_results = trend_service.analyze_trend(sig_df, method="plr")

                # Debug Prints for Trend Algorithms
                print("\n" + "=" * 50)
                plr_list = trend_results.get("plr", [])
                print(
                    f"\n📈 [ALGO 3/6] Bottom-Up PLR: Found {len(plr_list)} segments. Verifying Continuity:"
                )
                for i, seg in enumerate(plr_list):
                    print(
                        f"   [{i}] {seg['startDate']} -> {seg['endDate']} ({seg['direction']})"
                    )
                print("=" * 50 + "\n")

                # Map PLR segments to anomaly_zones format expected by frontend
                plr_segments = trend_results.get("plr", [])

                # Combine all segments for frontend selection
                all_segments = []
                all_segments.extend(plr_segments)

                # NEW: Generate Semantic Broad Regimes (Merged PLR)
                # This creates broad "Event Flow" phases
                semantic_raw = trend_service.process_semantic_regimes(
                    plr_segments, min_duration_days=7
                )

                # Process semantic zones
                semantic_zones = []
                for seg in semantic_raw:
                    # Determine sentiment/color
                    sentiment = "neutral"
                    direction = seg.get("direction", "").lower()
                    seg_type = seg.get("type", "").lower()

                    if direction == "up" or seg_type == "bull":
                        sentiment = "positive"
                    elif direction == "down" or seg_type == "bear":
                        sentiment = "negative"

                    # Calculate return
                    try:
                        start_p = float(seg.get("startPrice", 0))
                        end_p = float(seg.get("endPrice", 0))
                        change_pct = (end_p - start_p) / start_p if start_p else 0
                    except:
                        change_pct = 0

                    semantic_zones.append(
                        {
                            "startDate": seg["startDate"],
                            "endDate": seg["endDate"],
                            "avg_return": change_pct,
                            "avg_score": abs(change_pct) * 10,
                            "zone_type": "semantic_regime",
                            "method": "plr_merged",
                            "sentiment": sentiment,
                            "summary": f"{seg.get('direction', seg.get('type', 'Phase')).title()} ({change_pct * 100:.1f}%)",
                            "description": f"Phase from {seg['startDate']} to {seg['endDate']}. Return: {change_pct * 100:.1f}%",
                            "type": seg_type,
                            "normalizedType": seg_type,
                            "direction": direction,
                            "events": [],  # Placeholder for events
                        }
                    )

                # Process raw segments (anomaly_zones)
                anomaly_zones = []
                for seg in all_segments:
                    # Determine sentiment/color
                    sentiment = "neutral"
                    direction = seg.get("direction", "").lower()
                    seg_type = seg.get("type", "").lower()

                    if direction == "up" or seg_type == "bull":
                        sentiment = "positive"
                    elif direction == "down" or seg_type == "bear":
                        sentiment = "negative"

                    # Calculate simple impact/score
                    start_p = seg.get("startPrice", seg.get("avgPrice", 1.0))
                    end_p = seg.get("endPrice", seg.get("avgPrice", 1.0))
                    change_pct = (end_p - start_p) / start_p if start_p else 0

                    anomaly_zones.append(
                        {
                            "startDate": seg["startDate"],
                            "endDate": seg["endDate"],
                            "avg_return": change_pct,
                            "avg_score": abs(change_pct) * 10,
                            "zone_type": "trend_segment",
                            "method": seg.get("method", "plr"),
                            "sentiment": sentiment,
                            "summary": f"{seg.get('direction', seg.get('type', 'Trend')).title()} ({change_pct * 100:.1f}%)",
                            "description": f"Trend detected from {seg['startDate']} to {seg['endDate']}. Return: {change_pct * 100:.1f}%",
                            "type": seg_type,
                            "normalizedType": seg_type,
                            "direction": direction,
                        }
                    )

                # Merge semantic zones into anomaly_zones
                anomaly_zones.extend(semantic_zones)

                # Also keep StockSignalService for consistency if needed, but for now we replace the main logic
                # or we can append significant points differently.
                # For this task, we focus on TrendService, but let's keep the existing generated zones logic as specific method 'clustering'?
                # Actually, the user wants to REPLACE/MIGRATE features.
                # Let's keep the old one as "clustering" method if desired, but here we just use TrendService results.
                # However, to avoid losing functionality, we might want to run ClusteringService too?
                # The Plan says "Combine these with existing StockSignalService results or structure them".

                # Let's run StockSignalService as well for 'clustering' method
                clustering_service = StockSignalService(lookback=60, max_zone_days=10)
                clustering_zones = clustering_service.generate_zones(
                    sig_df, news_counts
                )
                for z in clustering_zones:
                    z["method"] = "clustering"

                anomaly_zones.extend(clustering_zones)

                print(
                    f"[AnomalyZones] ⚙️ Generated {len(anomaly_zones)} zones (PLR + Semantic + Clustering)"
                )

            # 为每个区域生成事件摘要（即使是从缓存读取的也可以重新生成，或者仅当未缓存时生成）
            if anomaly_zones and not cached_zones_json:
                try:
                    event_agent = EventSummaryAgent()

                    # 并发处理每个Zone的搜索总结 (Search REMOVED as per user request)
                    async def process_zone(zone):
                        start = zone["startDate"]
                        end = zone["endDate"]

                        zone_dates = []
                        curr = datetime.strptime(start, "%Y-%m-%d")
                        while curr <= datetime.strptime(end, "%Y-%m-%d"):
                            zone_dates.append(curr.strftime("%Y-%m-%d"))
                            curr += timedelta(days=1)

                        # 改动：不再调用 Tavily 搜索新闻供摘要使用

                        # 生成摘要
                        event_summary = event_agent.summarize_zone(
                            zone_dates=zone_dates,
                            price_change=zone.get("avg_return", 0) * 100,
                            news_items=[],  # EMPTY
                            region_name=region_name,
                        )

                        zone["event_summary"] = event_summary
                        # 改动：不在 anomaly zones 中保存 url，因为不获取新闻了
                        zone["news_links"] = []

                        print(
                            f"[AnomalyZones] Zone {start}-{end} (Internal Analysis): {event_summary}"
                        )
                        return zone

                    # 并发执行
                    tasks = [process_zone(z) for z in anomaly_zones]
                    anomaly_zones = await asyncio.gather(*tasks)

                except Exception as e:
                    import traceback

                    print(f"[AnomalyZones] Error generating event summaries: {e}")
                    print(traceback.format_exc())
                    # Fallback
                    for zone in anomaly_zones:
                        if "event_summary" not in zone:
                            zone["event_summary"] = (
                                f"供电量波动{zone.get('avg_return', 0) * 100:+.1f}%"
                            )

            # ⚠️ 不再过滤无新闻的 zones，保留所有检测到的异常区间
            anomaly_zones_with_news = anomaly_zones
            print(f"[AnomalyZones] Final zones: {len(anomaly_zones)}")

            # === 保存到Redis全局缓存 ===
            if anomaly_zones:
                try:
                    import json

                    zones_json = json.dumps(anomaly_zones, ensure_ascii=False)
                    redis_client.setex(
                        cache_key,
                        12 * 60 * 60,  # 12小时TTL
                        zones_json,
                    )
                    print(
                        f"[AnomalyZones] 💾 Saved {len(anomaly_zones)} zones to Redis cache (12 hours)"
                    )
                except Exception as e:
                    print(f"[AnomalyZones] Redis cache save error: {e}")

            # 保存并发送异常区域数据
            if anomaly_zones:
                message.save_anomaly_zones(anomaly_zones, region_code)

                await self._emit_event(
                    event_queue,
                    message,
                    {
                        "type": "data",
                        "data_type": "anomaly_zones",
                        "data": {"zones": anomaly_zones, "ticker": region_code},
                    },
                )
                print(f"[AnomalyZones] Successfully saved and emitted")

        except Exception as e:
            import traceback

            print(f"[AnomalyZones] Error: {e}")
            print(f"[AnomalyZones] Traceback:\n{traceback.format_exc()}")

        await self._emit_event(
            event_queue,
            message,
            {
                "type": "step_complete",
                "step": 3,
                "data": {"data_points": len(df), "news_count": len(news_items)},
            },
        )
        message.update_step_detail(
            3, "completed", f"历史数据 {len(df)} 天, 新闻 {len(news_items)} 条"
        )

        # === Step 4: 分析处理（多因素影响力分析）===
        await self._emit_event(
            event_queue,
            message,
            {"type": "step_start", "step": 4, "step_name": "分析处理"},
        )
        message.update_step_detail(4, "running", "分析时序特征和多因素影响力...")

        # 时序特征分析
        features = await asyncio.to_thread(TimeSeriesAnalyzer.analyze_features, df)

        # 多因素影响力分析（替代情绪分析）
        print(
            f"[Influence] 准备分析影响因子，供电数据: {len(df) if df is not None else 0} 条，天气数据: {len(weather_df) if weather_df is not None else 0} 条"
        )
        influence_result = await self._step_influence_analysis(
            df,
            weather_df,
            event_queue,
            message,
            region_match.region_info if region_match else None,
        )
        # print(f"[Influence] 影响因子分析完成，结果: {influence_result}")

        # 保存影响因子数据（兼容原有emotion字段）
        message.save_emotion(
            influence_result.get("overall_score", 0),
            influence_result.get("summary")
            or influence_result.get("description", "影响因素分析"),
        )

        await self._emit_event(
            event_queue,
            message,
            {
                "type": "step_complete",
                "step": 4,
                "data": {
                    "trend": features.get("trend", "N/A"),
                    "influence": influence_result.get("summary", "影响因素分析"),
                },
            },
        )
        message.update_step_detail(
            4,
            "completed",
            f"趋势: {features.get('trend', 'N/A')}, 影响因素: {influence_result.get('summary', '分析完成')}",
        )

        # === Step 5: 模型预测 ===
        await self._emit_event(
            event_queue,
            message,
            {"type": "step_start", "step": 5, "step_name": "模型预测"},
        )
        message.update_step_detail(5, "running", f"训练模型...")

        prophet_params = await recommend_forecast_params(
            self.sentiment_agent, influence_result or {}, features
        )

        # 使用意图中的预测天数（默认30天）
        forecast_horizon = max(intent.forecast_horizon, 1)

        # 模型选择：默认使用基于历史同期数据的预测方法
        # 该方法基于近2年同期数据平均，并根据天气差异调整
        user_specified_model = intent.forecast_model

        # 默认使用历史同期预测方法
        if not user_specified_model or user_specified_model == "auto":
            final_model = "historical_average"
            model_selection_reason = "基于近2年历史同期数据平均预测，并根据天气差异调整"
        else:
            # 用户指定了模型，使用用户指定的模型
            final_model = user_specified_model
            model_selection_reason = (
                f"使用用户指定的 {user_specified_model.upper()} 模型"
            )

        # 发送模型选择事件（简化版）
        await self._emit_event(
            event_queue,
            message,
            {
                "type": "model_selection",
                "selected_model": final_model,
                "best_model": final_model,
                "baseline": "seasonal_naive",
                "model_comparison": {},
                "is_better_than_baseline": False,
                "user_specified_model": user_specified_model,
                "model_selection_reason": model_selection_reason,
            },
        )

        # 保存模型选择信息到 Message
        message.save_model_selection(final_model, {}, False)

        # 保存模型选择原因
        message.save_model_selection_reason(model_selection_reason)

        message.update_step_detail(5, "running", f"训练 {final_model.upper()} 模型...")

        prophet_params = await recommend_forecast_params(
            self.sentiment_agent, influence_result or {}, features
        )

        # 只对最终选定的模型调用一次 run_forecast
        forecast_result = await run_forecast(
            df, final_model, max(forecast_horizon, 1), prophet_params, weather_df, region_name
        )

        # 保存并发送预测结果（forecast_result 是 ForecastResult 对象）
        full_points = original_points + forecast_result.points
        prediction_start = (
            forecast_result.points[0].date if forecast_result.points else ""
        )
        message.save_time_series_full(full_points, prediction_start)

        await self._emit_event(
            event_queue,
            message,
            {
                "type": "data",
                "data_type": "time_series_full",
                "data": [p.model_dump() for p in full_points],
                "prediction_start_day": prediction_start,
            },
        )

        metrics = forecast_result.metrics
        metrics_dict = {"mae": metrics.mae}
        if metrics.rmse:
            metrics_dict["rmse"] = metrics.rmse
        metrics_info = f"MAE: {metrics.mae}" + (
            f", RMSE: {metrics.rmse}" if metrics.rmse else ""
        )
        await self._emit_event(
            event_queue,
            message,
            {"type": "step_complete", "step": 5, "data": {"metrics": metrics_dict}},
        )
        message.update_step_detail(5, "completed", f"预测完成 ({metrics_info})")

        # 保存模型名称到 MessageData（使用最终选定的模型）
        message.save_model_name(final_model)

        # === Change Point Detection & Analysis (Separated History / Forecast) ===
        try:
            # 1. 准备数据：分离历史和预测
            hist_points = [p for p in full_points if not p.is_prediction]
            pred_points = [p for p in full_points if p.is_prediction]

            # 如果预测点不足，可能是纯历史分析或预测未开始
            if not pred_points and len(hist_points) > 0:
                # 假设最后一部分是其实是未来预测（针对某些特殊case），或者干脆不检测未来
                pass

            import pandas as pd

            # 定义检测函数，方便复用
            def run_detection(points, label, threshold):
                if not points:
                    return []
                df = pd.DataFrame(
                    [
                        {"date": p.date, "y": p.value, "is_prediction": p.is_prediction}
                        for p in points
                    ]
                )
                print(
                    f"[ChangePoints] Starting detection for {region_name} on {label} data ({len(df)} rows)"
                )
                # 必须重新索引，否则索引会不连续影响检测逻辑（如果detect内部依赖索引连续性）
                df = df.reset_index(drop=True)

                srv = StockSignalService()
                return srv.detect_change_points(df, threshold=threshold)

            # 分别检测
            # 历史数据通常噪声较大，可以使用稍高阈值；或者保持一致
            hist_cps = run_detection(hist_points, "HISTORY", threshold=1.3)
            for cp in hist_cps:
                cp["is_prediction"] = False

            # 预测数据通常较平滑，阈值可低一点以敏感捕捉
            pred_cps = run_detection(pred_points, "FORECAST", threshold=1.2)
            for cp in pred_cps:
                cp["is_prediction"] = True

            all_change_points = hist_cps + pred_cps
            print(
                f"[ChangePoints] Total detected: {len(all_change_points)} (Hist: {len(hist_cps)}, Pred: {len(pred_cps)})"
            )

            if all_change_points:
                analyzed_points = []

                # 预处理天气数据查找表
                weather_lookup = {}
                if weather_df is not None and not weather_df.empty:
                    try:
                        weather_df["date_str"] = (
                            weather_df["date"].astype(str).str.slice(0, 10)
                        )
                        for _, row in weather_df.iterrows():
                            temp = f"{row.get('temperature', 'N/A')}°C"
                            hum = f"湿度{row.get('humidity', 'N/A')}%"
                            weather_lookup[row["date_str"]] = f"{temp}, {hum}"
                    except Exception as e:
                        print(f"[ChangePoints] Weather lookup build error: {e}")

                # 异步搜索工具函数
                async def enrich_point(cp):
                    cp_date = cp.get("date")
                    is_pred = cp.get("is_prediction", False)

                    # 2. 上下文构建
                    context_info = []
                    w_info = weather_lookup.get(cp_date)
                    if w_info:
                        context_info.append(f"天气: {w_info}")

                    if is_pred:
                        context_info.append("(未来预测)")
                    else:
                        context_info.append("(历史数据)")

                    weather_info_str = " ".join(context_info)

                    # 3. 并行执行：LLM分析 + Tavily搜索

                    # LLM 分析任务
                    llm_task = asyncio.to_thread(
                        self.prediction_analysis_agent.analyze_change_point,
                        cp,
                        region_name,
                        weather_info_str,
                    )

                    # Tavily 搜索任务 (仅对历史点或近期未来点更有意义)
                    search_task = None
                    if not is_pred:  # 历史数据才搜索新闻
                        keywords = [region_name, "供电", "天气", "工业"]
                        # 使用特定日期的搜索
                        search_task = search_news_around_date(
                            keywords, target_date=cp_date, days=3, max_results=3
                        )

                    # 执行任务
                    analysis_res, search_res = await asyncio.gather(
                        llm_task,
                        search_task if search_task else asyncio.sleep(0),
                        return_exceptions=True,
                    )

                    # 处理结果
                    cp["reason"] = (
                        analysis_res if isinstance(analysis_res, str) else "分析失败"
                    )

                    # 处理搜索结果
                    news_links = []
                    if isinstance(search_res, list):
                        for item in search_res:
                            news_links.append(
                                {
                                    "title": item.get("title", f"相关新闻 ({cp_date})"),
                                    "url": item.get("url", "#"),
                                    "source": extract_domain(item.get("url", "")),
                                }
                            )
                    cp["news_links"] = news_links

                    # 构建天气链接 (通用搜索链接)
                    weather_query = f"{region_name} {cp_date} 天气"
                    cp["weather_link"] = (
                        f"https://www.bing.com/search?q={weather_query}"
                    )

                    return cp

                    cp["is_prediction"] = is_pred

                    return cp

                # 并发处理所有点
                # 限制并发数以防触发API速率限制
                limit = asyncio.Semaphore(5)

                async def sem_task(cp):
                    async with limit:
                        return await enrich_point(cp)

                tasks = [sem_task(cp) for cp in all_change_points]
                analyzed_points = await asyncio.gather(*tasks)

                # Emit event
                await self._emit_event(
                    event_queue,
                    message,
                    {
                        "type": "data",
                        "data_type": "change_points",
                        "data": analyzed_points,
                    },
                )
                message.save_change_points(analyzed_points)

        except Exception as e:
            print(f"❌ Change Point Analysis Error: {e}")
            import traceback

            print(traceback.format_exc())

        # === Step 6: 报告生成（流式） ===
        await self._emit_event(
            event_queue,
            message,
            {"type": "step_start", "step": 6, "step_name": "报告生成"},
        )
        message.update_step_detail(6, "running", "生成分析报告...")

        # 将 ForecastResult 转换为字典格式供报告生成使用
        forecast_dict = {
            "forecast": [
                {"date": p.date, "value": p.value} for p in forecast_result.points
            ],
            "metrics": metrics_dict,
            "model": forecast_result.model,
        }

        report_content = await self._step_report_streaming(
            user_input,
            features,
            forecast_dict,
            influence_result or {},  # 使用影响因子结果替代情绪结果
            conversation_history,
            event_queue,
            message,
        )

        message.save_conclusion(report_content)
        await self._emit_event(
            event_queue, message, {"type": "step_complete", "step": 6, "data": {}}
        )
        message.update_step_detail(6, "completed", "报告生成完成")

    # ========== 聊天流程（流式） ==========

    async def _execute_chat_streaming(
        self,
        message: Message,
        _session: Session,  # 保留参数以保持接口一致性
        user_input: str,
        intent: UnifiedIntent,
        region_match: Optional[RegionMatchResult],
        keywords: ResolvedKeywords,
        conversation_history: List[dict],
        event_queue: asyncio.Queue | None,
    ):
        """流式聊天流程"""
        # 优先使用region_mention，如果没有则使用stock_mention（兼容）
        region_mention = intent.region_mention or intent.stock_mention
        step_num = 3 if region_mention else 2

        # === 数据获取 ===
        await self._emit_event(
            event_queue,
            message,
            {"type": "step_start", "step": step_num, "step_name": "信息获取"},
        )
        message.update_step_detail(step_num, "running", "获取相关信息...")

        tasks = []
        task_names = []

        if intent.enable_rag:
            rag_available = await check_rag_availability()
            if rag_available:
                tasks.append(
                    fetch_rag_reports(self.rag_searcher, keywords.rag_keywords)
                )
                task_names.append("rag")

        if intent.enable_search:
            tasks.append(search_web(keywords.search_keywords, intent.history_days))
            task_names.append("search")

        if intent.enable_domain_info:
            region_name = (
                region_match.region_info.region_name
                if region_match and region_match.region_info
                else ""
            )
            tasks.append(fetch_domain_news(region_name, keywords.domain_keywords))
            task_names.append("domain")

        results = {}
        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            for name, result in zip(task_names, task_results):
                if not isinstance(result, Exception):
                    results[name] = result

        await self._emit_event(
            event_queue,
            message,
            {
                "type": "step_complete",
                "step": step_num,
                "data": {"sources": list(results.keys())},
            },
        )
        message.update_step_detail(
            step_num, "completed", f"获取完成: {list(results.keys())}"
        )

        # === 生成回答（流式） ===
        step_num += 1
        await self._emit_event(
            event_queue,
            message,
            {"type": "step_start", "step": step_num, "step_name": "生成回答"},
        )
        message.update_step_detail(step_num, "running", "生成回答...")

        # 构建上下文
        context_parts = []

        if "rag" in results and results["rag"]:
            context_parts.append("=== 研报内容 ===")
            for source in results["rag"][:5]:
                context_parts.append(
                    f"[{source.filename} 第{source.page}页]: {source.content_snippet}"
                )

        if "search" in results and results["search"]:
            context_parts.append("\n=== 网络搜索 ===")
            for item in results["search"][:5]:
                context_parts.append(
                    f"[{item.get('title', '')}]({item.get('url', '')}): {item.get('content', '')[:100]}"
                )

        if "domain" in results and results["domain"]:
            context_parts.append("\n=== 即时新闻 ===")
            for item in results["domain"][:5]:
                title = item.get("title", "")
                url = item.get("url", "")
                content = item.get("content", "")[:100]
                if url:
                    context_parts.append(f"[{title}]({url}): {content}")
                else:
                    context_parts.append(f"- {title}: {content}")

        context = "\n".join(context_parts) if context_parts else ""

        # 流式生成回答
        answer = await self._step_chat_streaming(
            user_input, conversation_history, context, event_queue, message
        )

        message.save_conclusion(answer)

        if "rag" in results:
            message.save_rag_sources(results["rag"])

        await self._emit_event(
            event_queue,
            message,
            {"type": "step_complete", "step": step_num, "data": {}},
        )
        message.update_step_detail(step_num, "completed", "回答完成")

    # ========== 流式报告生成 ==========

    async def _step_report_streaming(
        self,
        user_input: str,
        features: Dict,
        forecast_result: Dict,
        emotion_result: Dict,
        conversation_history: List[dict],
        event_queue: asyncio.Queue | None,
        message: Message,
    ) -> str:
        """流式报告生成"""
        loop = asyncio.get_running_loop()
        content_queue: asyncio.Queue = asyncio.Queue()

        def run_in_thread():
            def on_chunk(chunk: str):
                loop.call_soon_threadsafe(content_queue.put_nowait, ("chunk", chunk))

            content = self.report_agent.generate_streaming(
                user_input,
                features,
                forecast_result,
                emotion_result,
                conversation_history,
                on_chunk,
            )
            loop.call_soon_threadsafe(content_queue.put_nowait, ("done", content))

        future = loop.run_in_executor(None, run_in_thread)

        full_content = ""
        while True:
            try:
                event_type, data = await asyncio.wait_for(
                    content_queue.get(), timeout=120.0
                )

                if event_type == "chunk":
                    full_content += data
                    await self._emit_event(
                        event_queue,
                        message,
                        {"type": "report_chunk", "content": full_content},
                    )
                elif event_type == "done":
                    full_content = data
                    break
            except asyncio.TimeoutError:
                break

        await future

        return full_content

    # ========== 多因素影响力分析 ==========

    async def _step_influence_analysis(
        self,
        power_df: pd.DataFrame,
        weather_df: Optional[pd.DataFrame],
        event_queue: asyncio.Queue | None,
        message: Message,
        region_info: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """多因素影响力分析（替代情绪分析）"""

        # 如果没有供电数据或天气数据，返回默认值
        if power_df is None or power_df.empty or weather_df is None or weather_df.empty:
            default_result = InfluenceAnalyzer._get_default_result()
            default_result["overall_score"] = 0.0
            print(f"[Influence] 数据不足，发送默认影响因子")
            await self._emit_event(
                event_queue,
                message,
                {
                    "type": "data",
                    "data_type": "influence",
                    "data": default_result,
                },
            )
            return default_result

        # 获取日期范围
        start_date = power_df["ds"].min()
        end_date = power_df["ds"].max()

        # 标准化日期格式（移除时区）
        if hasattr(start_date, "tz") and start_date.tz is not None:
            start_date = start_date.tz_localize(None)
        if hasattr(end_date, "tz") and end_date.tz is not None:
            end_date = end_date.tz_localize(None)

        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        # 创建空的节假日数据（已废弃，保留以兼容接口）
        holiday_df = pd.DataFrame(columns=["date", "is_holiday", "holiday_score"])

        # 获取城市工业结构数据
        industry_structure_ratio = 0.3  # 默认值（全国平均工业结构比例约30%）
        if region_info and region_info.region_name:
            industry_structure_client = get_industry_structure_client()
            try:
                # 调用LLM获取城市工业结构数据（非async函数，使用线程执行）
                structure_data = await asyncio.to_thread(
                    industry_structure_client.fetch_industry_structure_data,
                    region_info.region_name,
                )
                industry_structure_ratio = structure_data.get(
                    "second_industry_ratio", 0.3
                )
                print(
                    f"[Influence] 获取城市工业结构数据: {region_info.region_name}, 比例={industry_structure_ratio:.2%}"
                )
            except Exception as e:
                print(f"[Influence] 获取城市工业结构数据失败: {e}，使用默认值0.3")
        else:
            print(f"[Influence] 未提供城市名称，使用默认工业结构比例0.3")

        # 计算影响因子（使用新方法）
        influence_result = await asyncio.to_thread(
            InfluenceAnalyzer.analyze_factors_influence,
            power_df,
            weather_df,
            holiday_df,
            industry_structure_ratio,
        )

        # 计算总体得分（各因素影响力得分的平均值，过滤NaN值）
        if influence_result.get("ranking"):
            valid_scores = [
                factor["influence_score"]
                for factor in influence_result["ranking"]
                if not (
                    np.isnan(factor.get("influence_score", np.nan))
                    or np.isinf(factor.get("influence_score", np.nan))
                )
            ]
            overall_score = np.mean(valid_scores) if valid_scores else 0.0
        else:
            overall_score = 0.0

        # 确保overall_score不是NaN
        if np.isnan(overall_score) or np.isinf(overall_score):
            overall_score = 0.0

        influence_result["overall_score"] = round(float(overall_score), 4)

        # 保存影响因子数据到 Redis
        message.save_influence_analysis(influence_result)

        print(
            f"[Influence] 发送影响因子数据: {len(influence_result.get('ranking', []))} 个因子"
        )
        await self._emit_event(
            event_queue,
            message,
            {
                "type": "data",
                "data_type": "influence",
                "data": influence_result,
            },
        )
        print(f"[Influence] 影响因子数据已发送并保存到Redis")

        return influence_result

    # ========== 流式情绪分析（保留以兼容）==========

    async def _step_sentiment_streaming(
        self,
        news_items: List[SummarizedNewsItem],
        event_queue: asyncio.Queue | None,
        message: Message,
    ) -> Dict[str, Any]:
        """流式情绪分析"""
        # 转换为字典列表
        news_list = (
            [
                {
                    "title": n.summarized_title,
                    "content": n.summarized_content,
                    "source_name": n.source_name,
                    "source_type": n.source_type,
                }
                for n in news_items
            ]
            if news_items
            else []
        )

        if not news_list:
            # 无新闻数据，返回默认值
            default_desc = "无新闻数据，默认中性情绪"
            await self._emit_event(
                event_queue,
                message,
                {
                    "type": "data",
                    "data_type": "emotion",
                    "data": {"score": 0.0, "description": default_desc},
                },
            )
            return {"score": 0.0, "description": default_desc}

        loop = asyncio.get_running_loop()
        content_queue: asyncio.Queue = asyncio.Queue()
        result_holder = {"result": None}

        def run_in_thread():
            def on_chunk(chunk: str):
                loop.call_soon_threadsafe(content_queue.put_nowait, ("chunk", chunk))

            result = self.sentiment_agent.analyze_streaming(news_list, on_chunk)
            result_holder["result"] = result
            loop.call_soon_threadsafe(content_queue.put_nowait, ("done", None))

        future = loop.run_in_executor(None, run_in_thread)

        # 实时发送情绪描述
        description_buffer = ""
        score_sent = False

        while True:
            try:
                event_type, data = await asyncio.wait_for(
                    content_queue.get(), timeout=60.0
                )

                if event_type == "chunk":
                    description_buffer += data
                    # 流式发送（score 先设为 0，等完成后更新）
                    if not score_sent:
                        score_sent = True
                    await self._emit_event(
                        event_queue,
                        message,
                        {"type": "emotion_chunk", "content": description_buffer},
                    )
                elif event_type == "done":
                    break
            except asyncio.TimeoutError:
                break

        await future

        # 获取最终结果
        result = result_holder["result"] or {
            "score": 0.0,
            "description": description_buffer or "中性情绪",
        }

        # 发送最终情绪数据
        await self._emit_event(
            event_queue,
            message,
            {
                "type": "data",
                "data_type": "emotion",
                "data": {
                    "score": result["score"],
                    "description": result["description"],
                },
            },
        )

        return result

    # ========== 流式聊天生成 ==========

    async def _step_chat_streaming(
        self,
        user_input: str,
        conversation_history: List[dict],
        context: str,
        event_queue: asyncio.Queue | None,
        message: Message,
    ) -> str:
        """流式聊天生成"""
        loop = asyncio.get_running_loop()
        content_queue: asyncio.Queue = asyncio.Queue()

        def run_in_thread():
            gen = self.intent_agent.generate_chat_response(
                user_input, conversation_history, context, stream=True
            )
            full = ""
            for chunk in gen:
                full += chunk
                loop.call_soon_threadsafe(content_queue.put_nowait, ("chunk", full))
            loop.call_soon_threadsafe(content_queue.put_nowait, ("done", full))

        future = loop.run_in_executor(None, run_in_thread)

        full_content = ""
        while True:
            try:
                event_type, data = await asyncio.wait_for(
                    content_queue.get(), timeout=120.0
                )

                if event_type == "chunk":
                    full_content = data
                    await self._emit_event(
                        event_queue,
                        message,
                        {"type": "chat_chunk", "content": full_content},
                    )
                elif event_type == "done":
                    full_content = data
                    break
            except asyncio.TimeoutError:
                break

        await future
        return full_content

    # ========== 辅助方法 ==========

    def _update_stream_status(self, message: Message, status: str):
        """更新流式状态"""
        data = message.get()
        if data:
            data.stream_status = status
            message._save(data)

    def _clean_nan_values(self, obj):
        """递归清理字典和列表中的NaN值，转换为None"""
        if isinstance(obj, dict):
            return {k: self._clean_nan_values(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._clean_nan_values(item) for item in obj]
        elif isinstance(obj, float):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return obj
        elif isinstance(obj, np.floating):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return float(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        else:
            return obj

    async def _emit_event(
        self, event_queue: asyncio.Queue | None, message: Message, event: Dict
    ):
        """发送事件到队列、PubSub 和 Stream"""

        # 清理NaN值以便JSON序列化
        event_clean = self._clean_nan_values(event)

        # 1. 发送到本地队列（如果存在）
        if event_queue:
            await event_queue.put(event_clean)

        try:
            # 2. 即时发布到 PubSub
            channel = f"stream:{message.message_id}"
            json_payload = json.dumps(event_clean, ensure_ascii=False)
            self.redis.publish(channel, json_payload)

            # 3. 持久化到 Stream（供断点续传使用）
            stream_key = f"stream-events:{message.message_id}"
            self.redis.xadd(
                stream_key, {"data": json_payload}, maxlen=1000, approximate=True
            )
            self.redis.expire(stream_key, 86400)  # 24小时 TTL

        except Exception as e:
            print(f"[StreamingTask] Event storage error: {e}")

    async def _emit_error(
        self, event_queue: asyncio.Queue | None, message: Message, error_msg: str
    ):
        """发送错误事件"""
        await self._emit_event(
            event_queue, message, {"type": "error", "message": error_msg}
        )

    async def _emit_done(self, event_queue: asyncio.Queue | None, message: Message):
        """发送完成事件"""
        await self._emit_event(
            event_queue, message, {"type": "done", "completed": True}
        )


# 单例
_streaming_processor: Optional[StreamingTaskProcessor] = None


def get_streaming_processor() -> StreamingTaskProcessor:
    """获取流式任务处理器单例"""
    global _streaming_processor
    if _streaming_processor is None:
        _streaming_processor = StreamingTaskProcessor()
    return _streaming_processor
