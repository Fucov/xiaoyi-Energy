"""
RAG 服务入口
============

统一的 RAG 服务接口
"""

from typing import List, Dict, Optional
import os
import uuid

from .config import RAGConfig, get_rag_config
from .pdf_parser import PDFParser, PageContent, DocumentInfo
from .chunker import TextChunker, Chunk
from .indexer import QdrantIndexer
from .retriever import HybridRetriever, RetrievalResult


class RAGService:
    """RAG 服务"""

    _instance: Optional["RAGService"] = None

    def __new__(cls, config: Optional[RAGConfig] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[RAGConfig] = None):
        if self._initialized:
            return

        self.config = config or get_rag_config()
        self.pdf_parser = PDFParser()
        self.chunker = TextChunker(
            chunk_size=self.config.chunk_size,
            overlap=self.config.chunk_overlap
        )
        self.indexer = QdrantIndexer(self.config)
        self.retriever = HybridRetriever(self.config)
        self._initialized = True

    def index_pdf(self, file_path: str) -> Dict:
        """
        索引单个 PDF 文件

        Returns:
            {"doc_id": str, "chunks_count": int}
        """
        # 解析 PDF
        pages, doc_info = self.pdf_parser.parse(file_path)

        # 生成文档 ID
        doc_id = str(uuid.uuid4())

        # 转换为 chunker 需要的格式
        pages_dict = [
            {"page_number": p.page_number, "text": p.text}
            for p in pages
        ]
        doc_info_dict = {
            "file_name": doc_info.file_name,
            "file_path": doc_info.file_path,
            "title": doc_info.title
        }

        # 分块
        chunks = self.chunker.chunk_document(doc_id, pages_dict, doc_info_dict)

        # 索引
        indexed_count = self.indexer.index_chunks(chunks)

        return {
            "doc_id": doc_id,
            "file_name": doc_info.file_name,
            "total_pages": doc_info.total_pages,
            "chunks_count": indexed_count
        }

    def index_directory(self, directory: Optional[str] = None) -> Dict:
        """
        索引目录下所有 PDF

        Returns:
            {"total_files": int, "total_chunks": int, "failed": [...]}
        """
        directory = directory or self.config.pdf_directory

        # 确保 collection 存在
        self.indexer.create_collection(recreate=False)

        pdf_files = [
            f for f in os.listdir(directory)
            if f.lower().endswith(".pdf")
        ]

        total_chunks = 0
        failed = []

        for i, pdf_file in enumerate(pdf_files):
            file_path = os.path.join(directory, pdf_file)
            try:
                result = self.index_pdf(file_path)
                total_chunks += result["chunks_count"]
                print(f"[{i+1}/{len(pdf_files)}] Indexed: {pdf_file} ({result['chunks_count']} chunks)")
            except Exception as e:
                print(f"[{i+1}/{len(pdf_files)}] Failed: {pdf_file} - {e}")
                failed.append({"file": pdf_file, "error": str(e)})

        return {
            "total_files": len(pdf_files),
            "indexed_files": len(pdf_files) - len(failed),
            "total_chunks": total_chunks,
            "failed": failed
        }

    def search(
        self,
        query: str,
        top_k: int = 5,
        use_hybrid: bool = True
    ) -> List[RetrievalResult]:
        """
        执行检索

        Args:
            query: 查询文本
            top_k: 返回数量
            use_hybrid: 是否使用混合检索

        Returns:
            检索结果列表
        """
        return self.retriever.search(query, top_k, use_hybrid)

    def get_status(self) -> Dict:
        """获取 RAG 服务状态"""
        return self.indexer.get_collection_info()


def get_rag_service() -> RAGService:
    """获取 RAG 服务单例"""
    return RAGService()
