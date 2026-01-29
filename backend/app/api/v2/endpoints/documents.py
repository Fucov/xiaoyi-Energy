"""
RAG 文档代理 API
================

代理转发 RAG 服务的文档获取请求
"""

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List

from app.core.config import settings

router = APIRouter()

# RAG 服务地址
RAG_SERVICE_URL = settings.RAG_SERVICE_URL


class DocumentInfo(BaseModel):
    """文档详情"""
    doc_id: str
    file_name: str
    file_path: str
    title: Optional[str] = None
    author: Optional[str] = None
    publish_date: Optional[str] = None
    source: Optional[str] = None
    total_pages: int = 0
    total_chunks: int = 0
    file_size: int = 0
    industry: Optional[str] = None
    stock_codes: List[str] = []
    report_type: Optional[str] = None


@router.get("/documents/{doc_id}", response_model=DocumentInfo)
async def get_document_info(doc_id: str):
    """
    获取文档详情

    代理转发到 RAG 服务获取文档元信息
    """
    if not RAG_SERVICE_URL:
        raise HTTPException(status_code=503, detail="RAG 服务未配置")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{RAG_SERVICE_URL}/api/v1/documents/{doc_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="文档不存在")
            raise HTTPException(status_code=502, detail=f"RAG 服务错误: {e.response.status_code}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"无法连接 RAG 服务: {str(e)}")


@router.get("/documents/{doc_id}/pdf")
async def get_document_pdf(doc_id: str, page: Optional[int] = None):
    """
    获取文档 PDF 文件

    通过 RAG 服务获取 PDF 文件路径，然后返回文件流
    """
    if not RAG_SERVICE_URL:
        raise HTTPException(status_code=503, detail="RAG 服务未配置")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # 先获取文档详情以获得 file_path
            response = await client.get(f"{RAG_SERVICE_URL}/api/v1/documents/{doc_id}")
            response.raise_for_status()
            doc_info = response.json()
            file_path = doc_info.get("file_path")

            if not file_path:
                raise HTTPException(status_code=404, detail="文档路径不存在")

            # 尝试通过 RAG 服务下载 PDF
            # 假设 RAG 服务提供 /api/v1/documents/{doc_id}/download 端点
            try:
                pdf_response = await client.get(
                    f"{RAG_SERVICE_URL}/api/v1/documents/{doc_id}/download",
                    timeout=60.0
                )
                pdf_response.raise_for_status()

                # 返回 PDF 文件流
                return StreamingResponse(
                    iter([pdf_response.content]),
                    media_type="application/pdf",
                    headers={
                        "Content-Disposition": f'inline; filename="{doc_info.get("file_name", "document.pdf")}"',
                        "X-Page": str(page) if page else "1"
                    }
                )
            except httpx.HTTPStatusError:
                # 如果没有下载端点，返回文件路径让前端处理
                return {
                    "doc_id": doc_id,
                    "file_path": file_path,
                    "file_name": doc_info.get("file_name"),
                    "page": page or 1,
                    "message": "PDF 下载端点不可用，请使用 file_path 访问"
                }

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="文档不存在")
            raise HTTPException(status_code=502, detail=f"RAG 服务错误: {e.response.status_code}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"无法连接 RAG 服务: {str(e)}")
