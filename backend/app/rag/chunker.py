"""
文本分块模块
============

语义感知的文本分块器
"""

from typing import List, Dict
from dataclasses import dataclass
import uuid


@dataclass
class Chunk:
    """文本块"""
    chunk_id: str
    doc_id: str
    content: str
    page_number: int
    chunk_index: int
    # 文档元信息（冗余存储便于检索）
    file_name: str
    file_path: str
    doc_title: str


class TextChunker:
    """文本分块器"""

    def __init__(
        self,
        chunk_size: int = 512,
        overlap: int = 50,
        min_chunk_size: int = 50
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_chunk_size = min_chunk_size

        # 分隔符优先级
        self.separators = [
            "\n\n",  # 段落
            "\n",    # 换行
            "。",    # 中文句号
            ".",     # 英文句号
            "；",    # 分号
            "，",    # 逗号
            " "      # 空格
        ]

    def chunk_document(
        self,
        doc_id: str,
        pages: List[Dict],  # [{page_number, text, ...}]
        doc_info: Dict
    ) -> List[Chunk]:
        """
        将文档分块

        Args:
            doc_id: 文档ID
            pages: 页面内容列表
            doc_info: 文档元信息

        Returns:
            Chunk 列表
        """
        chunks = []
        chunk_index = 0

        for page in pages:
            page_num = page.get("page_number", 1)
            text = page.get("text", "")

            if not text.strip():
                continue

            # 分块当前页面
            page_chunks = self._split_text(text)

            for chunk_text in page_chunks:
                if len(chunk_text.strip()) < self.min_chunk_size:
                    continue

                chunks.append(Chunk(
                    chunk_id=str(uuid.uuid4()),
                    doc_id=doc_id,
                    content=chunk_text.strip(),
                    page_number=page_num,
                    chunk_index=chunk_index,
                    file_name=doc_info.get("file_name", ""),
                    file_path=doc_info.get("file_path", ""),
                    doc_title=doc_info.get("title", "")
                ))
                chunk_index += 1

        print(f"[Chunk] 文档 {doc_info.get('file_name', 'unknown')} 分块: {len(chunks)} 个 chunks")
        return chunks

    def _split_text(self, text: str) -> List[str]:
        """智能分割文本"""
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            if end >= len(text):
                chunks.append(text[start:])
                break

            # 在分隔符处切分
            best_split = end
            for sep in self.separators:
                pos = text.rfind(sep, start + self.min_chunk_size, end)
                if pos > start:
                    best_split = pos + len(sep)
                    break

            chunks.append(text[start:best_split])
            start = max(start + 1, best_split - self.overlap)

        return [c for c in chunks if c.strip()]
