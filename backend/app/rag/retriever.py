"""
混合检索模块
============

结合稠密向量和稀疏向量的混合检索
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from qdrant_client import QdrantClient
from qdrant_client.models import (
    SparseVector,
    SearchRequest,
    NamedSparseVector,
    NamedVector,
    Prefetch,
    FusionQuery,
    Fusion,
)
from .embedding import EmbeddingService
from .config import RAGConfig


@dataclass
class RetrievalResult:
    """检索结果"""
    chunk_id: str
    doc_id: str
    content: str
    score: float
    page_number: int
    file_name: str
    file_path: str
    doc_title: str


class HybridRetriever:
    """混合检索器"""

    def __init__(self, config: RAGConfig):
        self.config = config
        self.client = QdrantClient(
            host=config.qdrant_host,
            port=config.qdrant_port
        )
        self.embedding_service = EmbeddingService(config.embedding_model)
        self.collection_name = config.collection_name

    def search(
        self,
        query: str,
        top_k: int = 5,
        use_hybrid: bool = True
    ) -> List[RetrievalResult]:
        """
        执行混合检索

        Args:
            query: 查询文本
            top_k: 返回数量
            use_hybrid: 是否使用混合检索

        Returns:
            检索结果列表
        """
        print(f"[Search] 查询: \"{query[:50]}{'...' if len(query) > 50 else ''}\"")

        # 编码查询
        query_embedding = self.embedding_service.encode_query(query)

        if use_hybrid:
            results = self._hybrid_search(query_embedding, top_k)
            print(f"[Search] RRF 混合检索完成: {len(results)} 条结果")
        else:
            results = self._dense_search(query_embedding["dense"], top_k)
            print(f"[Search] Dense 检索完成: {len(results)} 条结果")

        # 打印来源摘要
        if results:
            sources = [f"{r.file_name}:{r.page_number}" for r in results[:3]]
            print(f"[Search] 来源: {', '.join(sources)}...")

        return results

    def _hybrid_search(
        self,
        query_embedding: Dict,
        top_k: int
    ) -> List[RetrievalResult]:
        """RRF 混合检索"""
        # 使用 Qdrant 原生的 Query API 进行混合检索
        results = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                Prefetch(
                    query=query_embedding["dense"].tolist(),
                    using="dense",
                    limit=top_k * 2
                ),
                Prefetch(
                    query=SparseVector(
                        indices=query_embedding["sparse"]["indices"],
                        values=query_embedding["sparse"]["values"]
                    ),
                    using="sparse",
                    limit=top_k * 2
                )
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=top_k
        )

        return self._convert_results(results.points)

    def _dense_search(
        self,
        dense_vector: List[float],
        top_k: int
    ) -> List[RetrievalResult]:
        """仅稠密向量检索"""
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=("dense", dense_vector.tolist()),
            limit=top_k
        )

        return self._convert_results(results)

    def _convert_results(self, points) -> List[RetrievalResult]:
        """转换检索结果"""
        results = []
        for point in points:
            payload = point.payload
            results.append(RetrievalResult(
                chunk_id=str(point.id),
                doc_id=payload.get("doc_id", ""),
                content=payload.get("content", ""),
                score=point.score if hasattr(point, "score") else 0.0,
                page_number=payload.get("page_number", 0),
                file_name=payload.get("file_name", ""),
                file_path=payload.get("file_path", ""),
                doc_title=payload.get("doc_title", "")
            ))
        return results
