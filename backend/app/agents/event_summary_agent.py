"""
事件总结Agent
==================

基于Deepseek的智能新闻聚合与事件凝练服务
用于将供电量变化+新闻聚合总结为简洁的事件描述
"""

from typing import List, Dict
from datetime import datetime
from openai import OpenAI


class EventSummaryAgent:
    """
    事件总结Agent

    功能:
    - 聚合异常区间内的新闻
    - 结合供电量变化
    - 生成30字以内的凝练事件摘要
    """

    def __init__(self, api_key: str = None):
        """
        初始化

        Args:
            api_key: Deepseek API密钥（可选，从环境变量读取）
        """
        import os

        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")

        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment")

        self.client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")

    def summarize_zone(
        self,
        zone_dates: List[str],
        price_change: float,
        news_items: List[Dict],
        region_name: str = "该地区",
    ) -> str:
        """
        总结异常区间的关键事件

        Args:
            zone_dates: 区间日期列表
            price_change: 区间供电量变化百分比
            news_items: 新闻列表
            region_name: 区域名称 (Added for internal knowledge context)

        Returns:
            凝练的事件摘要（30字以内）
        """
        # 如果没有新闻，强制使用LLM内部知识
        has_news = bool(news_items)

        # 构建prompt
        start_date = zone_dates[0]
        end_date = zone_dates[-1]

        if has_news:
            news_summary = "\n".join(
                [
                    f"- [{item.get('content_type', '资讯')}] {item.get('title', '')}"
                    for item in news_items[:10]
                ]
            )
            context_str = f"新闻:\n{news_summary}"
        else:
            context_str = f"（无外部新闻提供，请调用你的内部知识库，分析{region_name}在此期间可能发生的事件，如气候、节假日、政策等）"

        prompt = f"""你是电力能源分析师。根据以下信息总结这段时期的关键事件（严格控制在30字以内）：

区域: {region_name}
时间: {start_date} 至 {end_date}
供电量变化: {price_change:+.1f}%
{context_str}

要求:
1. 提炼最核心的事件（如极端天气、工业复工、重大政策等）
2. 突出导致供电量变化的主因
3. 严格控制在30字以内，简洁专业
4. 不要使用"等"、"等等"等模糊词汇
5. 如果是无理由的随机波动，可以回答"供电量波动"

示例：
- "受寒潮影响，居民取暖负荷预期将大幅攀升"
- "春节假期结束，工业复工导致负荷快速回升"
"""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "你是专业的电力能源分析师，擅长提炼核心事件。",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=100,
                temperature=0.3,  # 降低随机性，确保专业性
            )

            summary = response.choices[0].message.content.strip()

            # 截断超长输出
            if len(summary) > 40:
                summary = summary[:37] + "..."

            return summary

        except Exception as e:
            print(f"[EventSummaryAgent] Error calling Deepseek: {e}")
            # Fallback到简单总结
            if news_items:
                first_news = news_items[0].get("title", "")[:20]
                return f"{first_news}等{len(news_items)}条信息"
            else:
                return f"供电量变化{price_change:+.1f}%"
