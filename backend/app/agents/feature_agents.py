"""
新增功能 Agent 模块
===================

包含新闻、研报、情绪分析等功能的简单实现
"""

import random
from typing import List, Dict
from datetime import datetime, timedelta
from app.schemas.session_schema import NewsItem, EmotionAnalysis


class NewsAgent:
    """新闻获取和总结 Agent（Demo实现）"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
    
    def fetch_and_summarize(self, stock_code: str, limit: int = 5) -> List[NewsItem]:
        """
        获取并总结新闻（Demo版本）
        
        实际实现应该：
        1. 使用 akshare 获取新闻: ak.stock_news_em(symbol=stock_code)
        2. 使用 LLM 总结新闻内容
        
        Args:
            stock_code: 股票代码
            limit: 新闻数量限制
            
        Returns:
            新闻列表
        """
        # Demo: 返回模拟新闻
        demo_news = [
            NewsItem(
                title=f"{stock_code} 发布年度财报，营收大幅增长",
                summary="公司公布年度财报，显示营收同比增长25%，净利润增长18%，超出市场预期。",
                date=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
                source="财经日报"
            ),
            NewsItem(
                title=f"{stock_code} 获机构增持，市场看好后市",
                summary="多家机构近期增持该股，分析师给予买入评级，目标价上调10%。",
                date=(datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
                source="证券时报"
            ),
            NewsItem(
                title=f"行业政策利好，{stock_code} 有望受益",
                summary="相关政策出台支持行业发展，公司作为龙头企业预计将获得更多市场机会。",
                date=(datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
                source="经济观察报"
            )
        ]
        
        return demo_news[:limit]


class EmotionAnalyzer:
    """市场情绪分析 Agent（Demo实现）"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
    
    def analyze(self, news_list: List[NewsItem], features: Dict) -> EmotionAnalysis:
        """
        分析市场情绪（Demo版本）
        
        实际实现应该：
        1. 综合新闻内容和技术指标
        2. 使用 LLM 进行情绪分析
        3. 返回 -1到1 的情绪分数
        
        Args:
            news_list: 新闻列表
            features: 技术特征
            
        Returns:
            情绪分析结果
        """
        # Demo: 基于简单规则
        # 正面词汇权重
        positive_keywords = ['增长', '利好', '看好', '上调', '增持', '受益']
        negative_keywords = ['下跌', '风险', '减持', '下调', '亏损', '下滑']
        
        positive_count = 0
        negative_count = 0
        
        for news in news_list:
            text = news.title + news.summary
            positive_count += sum(1 for kw in positive_keywords if kw in text)
            negative_count += sum(1 for kw in negative_keywords if kw in text)
        
        # 计算情绪分数
        total = positive_count + negative_count
        if total == 0:
            score = 0.0
        else:
            score = (positive_count - negative_count) / total
        
        # 趋势也影响情绪
        trend = features.get('trend', 'neutral')
        if trend == 'rising':
            score += 0.2
        elif trend == 'falling':
            score -= 0.2
        
        # 限制在 -1 到 1
        score = max(-1.0, min(1.0, score))
        
        # 生成描述
        if score > 0.6:
            description = "市场情绪极度看涨，多方占据主导"
        elif score > 0.3:
            description = "市场情绪偏乐观，买盘较为积极"
        elif score > -0.3:
            description = "市场情绪中性，观望氛围浓厚"
        elif score > -0.6:
            description = "市场情绪偏悲观，抛压较重"
        else:
            description = "市场情绪极度看跌，恐慌情绪蔓延"
        
        return EmotionAnalysis(
            score=round(score, 2),
            description=description
        )


class ReportAgent:
    """研报获取和总结 Agent（预留接口）"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
    
    def search_and_summarize(self, stock_code: str, limit: int = 3):
        """
        搜索并总结研报（预留）
        
        实际实现应该：
        1. 从本地 RAG 向量库搜索相关研报
        2. 使用 LLM 总结研报内容
        
        Args:
            stock_code: 股票代码
            limit: 研报数量限制
            
        Returns:
            研报列表（当前返回空列表）
        """
        # 预留接口，返回空列表
        return []
