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

    def analyze_prediction_zone(self, zone_info: Dict, region_name: str) -> str:
        """
        Analyze the cause of a predicted future trend (interval).

        Args:
            zone_info: Dictionary containing zone info (startDate, endDate, direction, avg_return).
            region_name: Name of the region.

        Returns:
            A short explanation of the likely cause (seasonality, holiday, etc.).
        """
        if not self.client:
            return "智能分析不可用 (未配置 API Key)"

        start_date = zone_info.get("startDate")
        end_date = zone_info.get("endDate")
        # direction = zone_info.get("direction", "unknown")  # Unused
        avg_return = zone_info.get("avg_return", 0) * 100  # Convert to percentage
        # summary = zone_info.get("summary", "")  # Unused

        prompt = f"""
        你是电力领域的专家分析师。
        针对 **{region_name}** 地区，模型预测在 **{start_date} 至 {end_date}** 期间，
        供电需求将呈现 **{"上升" if avg_return > 0 else "下降"}** 趋势，
        变化幅度约为 **{avg_return:+.1f}%**。
        
        请结合该地区的气候特征（{start_date}左右的季节性气温）、节假日安排（春节、国庆、暑期等）以及工业生产规律，
        分析导致这一预测趋势的主要原因。

        要求：
        1. **一句话解释**，简练专业（不超过50字）。
        2. 必须明确提及具体原因（如："受春节假期工厂停工影响" 或 "进入夏季高温期，制冷负荷增加"）。
        3. 严禁使用模棱两可的废话（如"受多种因素影响"）。
        4. 仅输出原因，不要重复描述趋势。
        5. 结合日期判断：
           - 1-2月：重点考虑春节、寒潮。
           - 6-8月：重点考虑夏季高温、制冷。
           - 10月：国庆假期。
           - 11-12月：冬季供暖（如果该地区有）。

        输出示例：
        - 受春节假期工厂大规模停工影响，工业负荷显著下降。
        - 进入夏季主汛期，高温天气导致居民制冷负荷大幅攀升。

        分析结果：
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
                max_tokens=100,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[PredictionAnalysisAgent] Error: {e}")
            return "无法生成分析"
