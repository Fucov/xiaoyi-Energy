"""
博查 AI 新闻搜索客户端
====================

使用 Bocha AI Web Search API 搜索新闻，支持时间过滤和中文搜索
API 文档: https://open.bochaai.com/
"""

import requests
from typing import List, Dict, Optional

# 中国新闻/天气/能源网站域名白名单
CN_NEWS_DOMAINS = [
    "sina.com.cn",       # 新浪
    "163.com",           # 网易
    "qq.com",            # 腾讯
    "sohu.com",          # 搜狐
    "people.com.cn",     # 人民网
    "xinhuanet.com",     # 新华网
    "chinanews.com.cn",  # 中国新闻网
    "bjnews.com.cn",     # 新京报
    "thepaper.cn",       # 澎湃新闻
    "cctv.com",          # 央视网
    "weather.com.cn",    # 中国天气网
    "weather.gov.cn",    # 中国气象局
    "nea.gov.cn",        # 国家能源局
    "sgcc.com.cn",       # 国家电网
    "csg.cn",            # 南方电网
    "in-en.com",         # 国际能源网
    "ne21.com",          # 北极星电力网
    "bjx.com.cn",        # 北极星电力网
    "cec.org.cn",        # 中国电力企业联合会
    "cet.com.cn",        # 中国电力新闻网
]


class BochaNewsClient:
    """博查 AI 新闻搜索客户端"""

    API_URL = "https://api.bochaai.com/v1/web-search"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def search(
        self,
        query: str,
        days: Optional[int] = None,
        max_results: int = 10,
        include_domains: Optional[List[str]] = None,
    ) -> Dict:
        """
        搜索新闻

        Args:
            query: 搜索关键词
            days: 时间范围（天数）
            max_results: 最大结果数 (1-50)
            include_domains: 域名白名单（在结果中过滤）

        Returns:
            搜索结果字典
        """
        # 时间范围映射
        if days is None or days > 365:
            freshness = "noLimit"
        elif days <= 1:
            freshness = "oneDay"
        elif days <= 7:
            freshness = "oneWeek"
        elif days <= 30:
            freshness = "oneMonth"
        else:
            freshness = "oneYear"

        payload = {
            "query": query,
            "freshness": freshness,
            "summary": True,
            "count": min(max_results * 2, 50),  # 请求更多以便过滤
        }

        try:
            response = requests.post(
                self.API_URL,
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            # 解析结果
            raw_results = data.get("data", {}).get("webPages", {}).get("value", [])

            results = []
            for item in raw_results:
                url = item.get("url", "")

                # 域名过滤
                if include_domains:
                    if not any(domain in url for domain in include_domains):
                        continue

                results.append({
                    "title": item.get("name", ""),
                    "url": url,
                    "content": item.get("summary", "") or item.get("snippet", ""),
                    "published_date": item.get("dateLastCrawled", ""),
                    "score": 1.0,
                    "site_name": item.get("siteName", ""),
                })

                if len(results) >= max_results:
                    break

            return {
                "results": results,
                "query": query,
                "count": len(results),
            }

        except Exception as e:
            print(f"[Bocha] 搜索失败: {e}")
            return {"results": [], "query": query, "count": 0, "error": str(e)}

    def search_power_news(
        self,
        region_name: str,
        days: int = 30,
        max_results: int = 10,
    ) -> Dict:
        """搜索电力/天气相关新闻"""
        query = f"{region_name} 电力 供电 天气"
        return self.search(
            query=query,
            days=days,
            max_results=max_results,
            include_domains=CN_NEWS_DOMAINS,
        )
