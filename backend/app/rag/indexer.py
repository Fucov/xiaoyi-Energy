"""
Qdrant 索引模块
===============

将文档块索引到 Qdrant 向量数据库
"""

from typing import List, Dict, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    PointStruct,
    SparseVector,
)
from .chunker import Chunk
from .embedding import EmbeddingService
from .config import RAGConfig
import uuid


class QdrantIndexer:
    """Qdrant 索引器"""

    def __init__(self, config: RAGConfig):
        self.config = config
        self.client = QdrantClient(
            host=config.qdrant_host,
            port=config.qdrant_port
        )
        self.embedding_service = EmbeddingService(config.embedding_model)
        self.collection_name = config.collection_name

    def create_collection(self, recreate: bool = False) -> None:
        """
        创建 Qdrant collection

        Args:
            recreate: 是否重新创建（删除已有）
        """
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if exists and recreate:
            self.client.delete_collection(self.collection_name)
            exists = False

        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": VectorParams(
                        size=self.config.embedding_dimension,
                        distance=Distance.COSINE
                    )
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(
                        index=SparseIndexParams(on_disk=False)
                    )
                }
            )
            print(f"[Index] 创建 Collection: {self.collection_name}")
        else:
            print(f"[Index] Collection 已存在: {self.collection_name}")

    def index_chunks(self, chunks: List[Chunk], batch_size: int = 32) -> int:
        """
        批量索引文档块

        Args:
            chunks: 文档块列表
            batch_size: 批大小

        Returns:
            索引的块数量
        """
        if not chunks:
            return 0

        total_indexed = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c.content for c in batch]

            # 生成 embedding
            embeddings = self.embedding_service.encode(texts)

            # 构建 points
            points = []
            for j, chunk in enumerate(batch):
                # 稀疏向量
                sparse = embeddings["sparse"][j]
                sparse_vector = SparseVector(
                    indices=sparse["indices"],
                    values=sparse["values"]
                )

                points.append(PointStruct(
                    id=chunk.chunk_id,
                    vector={
                        "dense": embeddings["dense"][j].tolist(),
                        "sparse": sparse_vector
                    },
                    payload={
                        "doc_id": chunk.doc_id,
                        "content": chunk.content,
                        "page_number": chunk.page_number,
                        "chunk_index": chunk.chunk_index,
                        "file_name": chunk.file_name,
                        "file_path": chunk.file_path,
                        "doc_title": chunk.doc_title
                    }
                ))

            # 上传到 Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            total_indexed += len(batch)
            print(f"[Index] 批量写入: {len(batch)} 个向量 ({total_indexed}/{len(chunks)})")

        # 获取文档名用于日志
        doc_name = chunks[0].file_name if chunks else "unknown"
        print(f"[Index] 文档 {doc_name} 索引完成: {total_indexed} chunks")
        return total_indexed

    def get_collection_info(self) -> Dict:
        """获取 collection 信息"""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "points_count": info.points_count,
                "status": info.status
            }
        except Exception as e:
            return {"error": str(e)}
