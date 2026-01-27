"""
Workflows 模块
===============

封装数据获取、分析、预测等流程
"""

# 数据获取
from .data_fetch import fetch_power_data, fetch_rag_reports
# fetch_stock_data 已废弃，如需兼容请从 data_fetch 直接导入

# 新闻获取
from .news import (
    fetch_tavily_news,
    fetch_news_all,
    search_web,
    fetch_domain_news,
)
# fetch_akshare_news 已移除，不再需要

# 分析
from .analysis import recommend_forecast_params

# 预测
from .forecast import run_forecast
from .model_selection import select_best_model

# 转换
from .converters import df_to_points


__all__ = [
    # data_fetch.py
    "fetch_power_data",
    "fetch_rag_reports",
    # news.py
    "fetch_tavily_news",
    "fetch_news_all",
    "search_web",
    "fetch_domain_news",
    # analysis.py
    "recommend_forecast_params",
    # forecast.py
    "run_forecast",
    # model_selection.py
    "select_best_model",
    # converters.py
    "df_to_points",
]
