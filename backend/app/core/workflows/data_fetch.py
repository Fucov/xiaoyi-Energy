"""
数据获取模块
=============

供电需求数据和 RAG 研报获取
"""

import asyncio
from typing import List
import pandas as pd

from app.data.power_data_fetcher import PowerDataFetcher
from app.data.rag_searcher import RAGSearcher
from app.schemas.session_schema import RAGSource


async def fetch_power_data(region_name: str, start_date: str, end_date: str, historical_days: int = None):
    """
    获取供电需求数据和天气数据

    Args:
        region_name: 区域名称（城市名称）
        start_date: 开始日期 (YYYYMMDD 或 YYYY-MM-DD)
        end_date: 结束日期 (YYYYMMDD 或 YYYY-MM-DD)
        historical_days: 历史天数（可选，用于获取更多训练数据）

    Returns:
        (供电数据DataFrame, 天气数据DataFrame)
        供电数据包含 ds 和 y 列
        天气数据包含 date, temperature, humidity 等列
    """
    fetcher = PowerDataFetcher()
    result = await fetcher.fetch_power_data(region_name, start_date, end_date, historical_days)
    # 返回元组 (供电数据, 天气数据)
    if isinstance(result, tuple):
        return result
    # 兼容旧代码：如果没有天气数据，返回空DataFrame
    import pandas as pd
    return result, pd.DataFrame()


async def fetch_stock_data(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    获取股票历史数据（已废弃，保留以兼容）
    
    注意：此函数已废弃，请使用 fetch_power_data 替代
    
    Args:
        stock_code: 股票代码（已废弃）
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
    
    Returns:
        处理后的 DataFrame
    """
    # 为了兼容性，返回一个空DataFrame或抛出错误
    raise NotImplementedError(
        "fetch_stock_data 已废弃，请使用 fetch_power_data 替代。"
        "此平台已转换为电力需求预测平台。"
    )


async def fetch_rag_reports(rag_searcher: RAGSearcher, keywords: List[str]) -> List[RAGSource]:
    """
    检索研报

    Args:
        rag_searcher: RAG 搜索器实例
        keywords: 关键词列表

    Returns:
        研报来源列表
    """
    if not keywords:
        return []

    try:
        query = " ".join(keywords[:3])
        docs = await asyncio.to_thread(
            rag_searcher.search_reports,
            query,
            5
        )

        return [
            RAGSource(
                filename=doc["file_name"],
                page=doc["page_number"],
                content_snippet=doc.get("content", "")[:200],
                score=doc["score"],
                doc_id=doc.get("doc_id", "")
            )
            for doc in docs
        ]
    except Exception as e:
        print(f"[RAG] 研报检索失败: {e}")
        return []
