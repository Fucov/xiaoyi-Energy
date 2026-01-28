"""
Prediction Analysis Agent
=========================

Agent for analyzing change points in power supply prediction data.
Uses Deepseek to interpret the causes of significant changes (e.g., weather, holidays, events).
"""

from typing import Dict, Optional
import os
from openai import OpenAI


class PredictionAnalysisAgent:
    """
    Agent for analyzing change points in prediction data.

    Capabilities:
    1. Analyze the cause of a detected change point (sudden rise/drop).
    2. Context-aware analysis (considering weather, date, holidays).
    """

    def __init__(self, api_key: str = None):
        """
        Initialize the agent.

        Args:
            api_key: Deepseek API key (optional, reads from env)
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            # It's better to log a warning rather than crash if key is missing,
            # as the app might run with reduced functionality.
            print("Warning: DEEPSEEK_API_KEY not found in environment.")

        self.client = (
            OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")
            if self.api_key
            else None
        )

    def analyze_change_point(
        self, change_point: Dict, region_name: str, weather_info: Optional[str] = None
    ) -> str:
        """
        Analyze a specific change point to determine potential causes.

        Args:
            change_point: Dictionary containing change point info
                          (date, type, magnitude, confidence).
            region_name: Name of the region (e.g., "Beijing").
            weather_info: Optional string describing weather context.

        Returns:
            A short, single-sentence explanation of the cause.
        """
        if not self.client:
            return "Analysis unavailable (API key missing)."

        date = change_point.get("date", "Unknown date")
        change_type = change_point.get("type", "change")  # 'rise' or 'drop'
        magnitude = change_point.get("magnitude", 0)

        prompt = f"""
        你是电力领域的专家分析师。
        检测到了以下用电负荷的{"预测" if "未来" in (weather_info or "") else "历史"}突变点：
        
        日期: {date}
        类型: {"上升" if change_type == "rise" else "下降"}
        幅度 (Z-score): {magnitude:.2f}
        区域: {region_name}
        环境信息: {weather_info or "数据缺失"}
        
        请结合日期、区域、环境信息（气温、湿度等），分析可能导致该突变的原因。
        重点考虑以下因素：
        1. 气候因素：气温骤变（寒潮/高温）、湿度变化、极端天气。
        2. 节假日因素：是否为节假日（春节、国庆等）、调休、周末效应。
        3. 社会活动：大型活动、工业复工/停工。
        
        请用一句话总结最可能的原因。
        
        要求：
        1. 绝对禁止使用金融术语（如"股价"、"市场"、"交易量"等）。
        2. 必须用中文回答。
        3. 如果是节假日，请明确指出是哪个节日。
        4. 结合气温分析（如："气温高达35度，导致空调用电增加"）。
        5. 语气客观专业。
        6. 严禁提及与该区域无关的其他城市或地区。
        7. 分析必须完全基于{region_name}本地特征。
        8. 不需要依赖外部新闻，请调用你的内部知识库，检索该日期{region_name}发生的真实核心事件（如气候、政策、工业大事件）。
        
        分析结果（仅输出一句话原因）：
        """
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert power grid analyst.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=60,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[PredictionAnalysisAgent] Error: {e}")
            return "Analysis failed due to service error."
