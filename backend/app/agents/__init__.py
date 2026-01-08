"""
Agents Module
=============

AI Agent 层，负责业务逻辑编排
"""

from .nlp_agent import NLPAgent
from .report_agent import ReportAgent
from .finance_agent import FinanceChatAgent
from .intent_agent import IntentAgent
from .suggestion_agent import SuggestionAgent

# RAG Agent 可选导入（依赖 Qdrant 和 FlagEmbedding）
try:
    from .rag_agent import RAGAgent
    RAG_AVAILABLE = True
except ImportError as e:
    RAGAgent = None
    RAG_AVAILABLE = False
    print(f"[Warning] RAG Agent 不可用: {e}")

__all__ = ["NLPAgent", "ReportAgent", "FinanceChatAgent", "IntentAgent", "SuggestionAgent", "RAGAgent", "RAG_AVAILABLE"]
