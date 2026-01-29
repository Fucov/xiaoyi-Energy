"""
新闻获取模块
=============

纯功能模块：获取天气/电力相关新闻数据，不涉及 LLM 调用
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Tuple

from app.core.config import settings
from app.data import BochaNewsClient, format_datetime, extract_domain
from app.schemas.session_schema import NewsItem


async def fetch_power_news(
    region_name: str, days: int = 30, max_results: int = 5
) -> List[NewsItem]:
    """
    获取电力/天气相关新闻

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
        client = BochaNewsClient(settings.bocha_api_key)
        result = await asyncio.to_thread(
            client.search_power_news,
            region_name=region_name,
            days=days,
            max_results=max_results,
        )

        return [
            NewsItem(
                title=item.get("title", ""),
                content=item.get("content", "")[:300],
                url=item.get("url", ""),
                published_date=format_datetime(item.get("published_date", "")),
                source_type="search",
                source_name=item.get("site_name") or extract_domain(item.get("url", "")),
            )
            for item in result.get("results", [])
        ]
    except Exception as e:
        print(f"[News] 获取新闻失败: {e}")
        return []


async def fetch_news_all(
    region_name: str, days: int = 30, news_limit: int = 10
) -> Tuple[List[NewsItem], dict]:
    """
    获取全部新闻（搜索天气/电力相关）

    纯数据获取，不涉及 LLM

    Args:
        region_name: 区域名称（城市名称）
        days: 搜索时间范围（天数）
        news_limit: 新闻数量

    Returns:
        (news_items, sentiment_data)
    """
    raw_results = await _fetch_news_raw(region_name, days, news_limit)

    if isinstance(raw_results, Exception):
        raw_results = {"results": [], "count": 0}

    news_items = []

    for item in raw_results.get("results", [])[:news_limit]:
        url = item.get("url", "")
        pub_date = item.get("published_date") or ""
        news_items.append(
            NewsItem(
                title=item.get("title", ""),
                content=item.get("content", "")[:300],
                url=url,
                published_date=format_datetime(pub_date) if pub_date else "-",
                source_type="search",
                source_name=item.get("site_name") or extract_domain(url),
            )
        )

    news_count = len(raw_results.get("results", [])[:news_limit])
    print(f"[News] 获取新闻: {news_count} 条")

    sentiment_data = {"news_results": raw_results, "news_count": len(news_items)}

    return news_items, sentiment_data


async def _fetch_news_raw(
    region_name: str, days: int = 30, max_results: int = 10
) -> dict:
    """
    获取原始新闻数据（内部使用）

    返回原始 dict 供情感分析使用
    """
    if not region_name:
        return {"results": [], "count": 0}

    try:
        client = BochaNewsClient(settings.bocha_api_key)
        return await asyncio.to_thread(
            client.search_power_news,
            region_name=region_name,
            days=days,
            max_results=max_results,
        )
    except Exception as e:
        print(f"[News] _fetch_news_raw 失败: {e}")
        return {"results": [], "count": 0}


async def search_web(
    keywords: List[str], days: int = 30, max_results: int = 10
) -> List[dict]:
    """
    通用网络搜索

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
        client = BochaNewsClient(settings.bocha_api_key)
        query = " ".join(keywords[:3])

        result = await asyncio.to_thread(
            client.search,
            query=query,
            days=days,
            max_results=max_results,
        )
        print(f"[Search] 网络搜索关键词: {query}, 时间范围: {days}天")
        return result.get("results", [])
    except Exception as e:
        print(f"[Search] 搜索失败: {e}")
        return []


async def fetch_domain_news(region_name: str, keywords: List[str]) -> List[dict]:
    """
    获取领域新闻 (天气/电力相关)

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
        client = BochaNewsClient(settings.bocha_api_key)
        result = await asyncio.to_thread(
            client.search_power_news,
            region_name=region_name or "",
            days=30,
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
        days: Window size in days
        max_results: Max results

    Returns:
        List of result dicts
    """
    if not keywords or not target_date:
        return []

    try:
        client = BochaNewsClient(settings.bocha_api_key)
        query = " ".join(keywords[:3])

        result = await asyncio.to_thread(
            client.search,
            query=query,
            days=days * 2,  # 扩大搜索范围
            max_results=max_results,
        )
        print(f"[Search] Historical search for {target_date} (window: {days} days)")
        return result.get("results", [])
    except Exception as e:
        print(f"[Search] Historical search failed: {e}")
        return []
