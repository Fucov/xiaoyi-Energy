"""
步骤定义模块
=============

定义各意图对应的步骤列表
"""

from typing import List, Dict

# 预测分析流程（7步）
FORECAST_STEPS = [
    {"id": "1", "name": "数据获取与预处理"},
    {"id": "2", "name": "新闻获取与情绪分析"},
    {"id": "3", "name": "时序特征分析"},
    {"id": "4", "name": "参数智能推荐"},
    {"id": "5", "name": "模型训练与预测"},
    {"id": "6", "name": "结果可视化"},
    {"id": "7", "name": "报告生成"},
]

# RAG 研报检索流程（2步）
RAG_STEPS = [
    {"id": "1", "name": "研报检索"},
    {"id": "2", "name": "生成回答"},
]

# 新闻搜索流程（2步）
NEWS_STEPS = [
    {"id": "1", "name": "新闻搜索"},
    {"id": "2", "name": "新闻总结"},
]

# 纯对话流程（1步）
CHAT_STEPS = [
    {"id": "1", "name": "生成回答"},
]


def get_steps_for_intent(intent: str) -> List[Dict[str, str]]:
    """
    根据意图获取对应的步骤列表

    Args:
        intent: 意图类型 (forecast/rag/news/chat)

    Returns:
        步骤列表
    """
    mapping = {
        "forecast": FORECAST_STEPS,
        "rag": RAG_STEPS,
        "news": NEWS_STEPS,
        "chat": CHAT_STEPS,
    }
    return mapping.get(intent, CHAT_STEPS)


def get_step_count(intent: str) -> int:
    """
    获取意图对应的步骤数量

    Args:
        intent: 意图类型

    Returns:
        步骤数量
    """
    return len(get_steps_for_intent(intent))
