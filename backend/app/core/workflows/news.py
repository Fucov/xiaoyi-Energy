"""
新闻获取模块
=============

纯功能模块：获取天气/电力相关新闻数据，不涉及 LLM 调用
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Tuple
import pandas as pd

from app.core.config import settings
from app.data import TavilyNewsClient, format_datetime, extract_domain
from app.schemas.session_schema import NewsItem


async def fetch_tavily_news(
    region_name: str, days: int = 30, max_results: int = 5
) -> List[NewsItem]:
    """
    获取 Tavily 天气/电力相关新闻搜索结果

    纯数据获取，不涉及 LLM

    Args:
        region_name: 区域名称（城市名称）
        days: 搜索时间范围（天数）
        max_results: 最大结果数

    Returns:
        新闻列表
    """
    if not region_name:
        return []

    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        client = TavilyNewsClient(settings.tavily_api_key)
        result = await asyncio.to_thread(
            client.search_weather_news,
            region_name=region_name,
            start_date=start_date,
            end_date=end_date,
            max_results=max_results,
        )

        return [
            NewsItem(
                title=item.get("title", ""),
                content=item.get("content", "")[:300],
                url=item.get("url", ""),
                published_date=format_datetime(item.get("published_date", "")),
                source_type="search",
                source_name=extract_domain(item.get("url", "")),
            )
            for item in result.get("results", [])
        ]
    except Exception as e:
        print(f"[News] Tavily 获取失败: {e}")
        return []


async def fetch_news_all(
    region_name: str, days: int = 30, tavily_limit: int = 10
) -> Tuple[List[NewsItem], dict]:
    """
    获取全部新闻（仅使用 Tavily，搜索天气/电力相关）

    纯数据获取，不涉及 LLM

    Args:
        region_name: 区域名称（城市名称）
        days: 搜索时间范围（天数）
        tavily_limit: Tavily 新闻数量

    Returns:
        (news_items, sentiment_data)
    """
    # 获取 Tavily 新闻
    tavily_task = _fetch_tavily_raw(region_name, days, tavily_limit)
    tavily_results = await tavily_task

    if isinstance(tavily_results, Exception):
        tavily_results = {"results": [], "count": 0}

    news_items = []

    # 转换 Tavily 新闻
    for item in tavily_results.get("results", [])[:tavily_limit]:
        url = item.get("url", "")
        pub_date = item.get("published_date") or ""
        news_items.append(
            NewsItem(
                title=item.get("title", ""),
                content=item.get("content", "")[:300],
                url=url,
                published_date=format_datetime(pub_date) if pub_date else "-",
                source_type="search",
                source_name=extract_domain(url),
            )
        )

    tavily_count = len(tavily_results.get("results", [])[:tavily_limit])
    print(f"[News] 获取新闻: Tavily {tavily_count} 条")

    # 构建情感分析数据
    sentiment_data = {"tavily_results": tavily_results, "news_count": len(news_items)}

    return news_items, sentiment_data


async def _fetch_tavily_raw(
    region_name: str, days: int = 30, max_results: int = 10
) -> dict:
    """
    获取 Tavily 原始数据（内部使用）

    返回原始 dict 供情感分析使用
    """
    if not region_name:
        return {"results": [], "count": 0}

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    client = TavilyNewsClient(settings.tavily_api_key)
    return await asyncio.to_thread(
        client.search_weather_news,
        region_name=region_name,
        start_date=start_date,
        end_date=end_date,
        max_results=max_results,
    )


async def search_web(
    keywords: List[str], days: int = 30, max_results: int = 10
) -> List[dict]:
    """
    通用网络搜索（非股票专用）

    返回原始 dict 格式，供聊天流程使用

    Args:
        keywords: 搜索关键词列表
        days: 搜索时间范围（天数）
        max_results: 最大结果数

    Returns:
        搜索结果列表
    """
    if not keywords:
        return []

    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        client = TavilyNewsClient(settings.tavily_api_key)
        query = " ".join(keywords[:3])

        result = await asyncio.to_thread(
            client.search,
            query=query,
            start_date=start_date,
            end_date=end_date,
            max_results=max_results,
            country="china",  # 限制为中国地区
        )
        print(f"[Search] 网络搜索时间范围: {start_date} ~ {end_date}")
        return result.get("results", [])
    except Exception as e:
        print(f"[Search] 搜索失败: {e}")
        return []


async def fetch_domain_news(region_name: str, keywords: List[str]) -> List[dict]:
    """
    获取领域新闻 (Tavily 天气/电力相关)

    返回原始 dict 格式，供聊天流程使用

    Args:
        region_name: 区域名称
        keywords: 关键词列表

    Returns:
        新闻列表
    """
    if not region_name and not keywords:
        return []

    try:
        # 构建搜索查询
        query_parts = [region_name] if region_name else []
        query_parts.extend(keywords[:2])  # 最多使用2个关键词
        query = " ".join(query_parts)

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        client = TavilyNewsClient(settings.tavily_api_key)
        result = await asyncio.to_thread(
            client.search_weather_news,
            region_name=region_name or "",
            start_date=start_date,
            end_date=end_date,
            max_results=10,
        )

        items = []
        for item in result.get("results", [])[:10]:
            items.append(
                {
                    "title": item.get("title", ""),
                    "content": item.get("content", "")[:200],
                    "url": item.get("url", ""),
                    "date": item.get("published_date", ""),
                }
            )
        return items
    except Exception as e:
        print(f"[Domain] 获取新闻失败: {e}")
        return []


async def search_news_around_date(
    keywords: List[str], target_date: str, days: int = 3, max_results: int = 3
) -> List[dict]:
    """
    Search for news around a specific historical date.

    Args:
        keywords: Search keywords
        target_date: Target date string (YYYY-MM-DD)
        days: Window size in days (target_date +/- days)
        max_results: Max results

    Returns:
        List of result dicts
    """
    if not keywords or not target_date:
        return []

    try:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
        start_date = (dt - timedelta(days=days)).strftime("%Y-%m-%d")
        end_date = (dt + timedelta(days=days)).strftime("%Y-%m-%d")

        client = TavilyNewsClient(settings.tavily_api_key)
        query = " ".join(keywords[:3])

        # Use simple search, not search_weather_news
        result = await asyncio.to_thread(
            client.search,
            query=query,
            start_date=start_date,
            end_date=end_date,
            max_results=max_results,
            country="china",  # 限制为中国地区
        )
        print(f"[Search] Historical search for {target_date} ({start_date}~{end_date})")
        return result.get("results", [])
    except Exception as e:
        print(f"[Search] Historical search failed: {e}")
        return []
