"""
Data Services
=============

数据获取与处理模块:
- DataFetcher: AkShare 股票/新闻数据获取（保留以兼容）
- PowerDataFetcher: 供电需求数据获取
- WeatherClient: 天气数据获取
- TavilyNewsClient: Tavily 新闻搜索
- format_datetime: 统一时间格式化（北京时间）
- extract_domain: 从 URL 提取域名
"""

from .fetcher import DataFetcher, format_datetime, extract_domain
from .power_data_fetcher import PowerDataFetcher
from .weather_client import WeatherClient, get_weather_client
from .tavily_client import TavilyNewsClient

__all__ = [
    "DataFetcher", 
    "PowerDataFetcher",
    "WeatherClient",
    "get_weather_client",
    "TavilyNewsClient", 
    "format_datetime", 
    "extract_domain"
]
