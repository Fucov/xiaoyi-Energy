"""
PDF 解析模块
============

使用 PyMuPDF 提取文本和位置信息
"""

import fitz  # PyMuPDF
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import os


@dataclass
class PageContent:
    """页面内容"""
    page_number: int
    text: str
    blocks: List[Dict]


@dataclass
class DocumentInfo:
    """文档信息"""
    file_path: str
    file_name: str
    title: str
    total_pages: int
    file_size: int


class PDFParser:
    """PDF 解析器"""

    def parse(self, file_path: str) -> Tuple[List[PageContent], DocumentInfo]:
        """
        解析 PDF 文件

        Args:
            file_path: PDF 文件路径

        Returns:
            (页面内容列表, 文档信息)
        """
        file_name = os.path.basename(file_path)
        print(f"[PDF] 解析: {file_name}")

        doc = fitz.open(file_path)
        pages = []
        total_chars = 0

        for page_num in range(len(doc)):
            page = doc[page_num]
            blocks = page.get_text("dict")["blocks"]
            text_blocks = []
            full_text = ""

            for block in blocks:
                if block.get("type") == 0:  # 文本块
                    block_text = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            block_text += span.get("text", "")
                        block_text += "\n"

                    if block_text.strip():
                        text_blocks.append({
                            "text": block_text.strip(),
                            "bbox": block.get("bbox"),
                            "type": "text"
                        })
                        full_text += block_text

            pages.append(PageContent(
                page_number=page_num + 1,  # 1-indexed
                text=full_text.strip(),
                blocks=text_blocks
            ))
            total_chars += len(full_text)

        # 提取文档信息
        metadata = doc.metadata
        title = metadata.get("title") or file_name.replace(".pdf", "")

        doc_info = DocumentInfo(
            file_path=file_path,
            file_name=file_name,
            title=title,
            total_pages=len(doc),
            file_size=os.path.getsize(file_path)
        )

        doc.close()
        print(f"[PDF] 页数: {len(pages)}, 提取文本: {total_chars} 字符")
        return pages, doc_info

    def extract_text_with_positions(self, file_path: str) -> List[Dict]:
        """
        提取文本及其位置信息

        Returns:
            [{page_number, text, bbox}, ...]
        """
        pages, _ = self.parse(file_path)
        results = []

        for page in pages:
            for block in page.blocks:
                if block["text"]:
                    results.append({
                        "page_number": page.page_number,
                        "text": block["text"],
                        "bbox": block["bbox"]
                    })

        return results
