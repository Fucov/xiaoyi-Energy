#!/usr/bin/env python
"""
RAG 索引构建脚本
================

独立运行的索引构建脚本，用于预先构建 PDF 研报索引。

用法:
    cd backend
    python -m scripts.build_index [--recreate] [--directory PATH]

参数:
    --recreate      重建索引（删除旧数据）
    --directory     PDF 目录路径（默认: ./energy_reports_test）
"""

import sys
import os
import argparse
import time

# 添加 backend 目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 自动加载 .env 文件
from dotenv import load_dotenv
# 先尝试项目根目录的 .env，再尝试 backend 目录的 .env
root_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
backend_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(root_env) or load_dotenv(backend_env)

from app.rag import RAGService
from app.rag.config import get_rag_config


def main():
    parser = argparse.ArgumentParser(description="构建 RAG 索引")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="重建索引（删除旧数据）"
    )
    parser.add_argument(
        "--directory",
        type=str,
        default=None,
        help="PDF 目录路径（默认从配置获取，可通过 RAG_PDF_DIRECTORY 环境变量设置）"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("RAG 索引构建脚本")
    print("=" * 60)

    # 加载配置
    config = get_rag_config()
    directory = args.directory or config.pdf_directory

    print(f"\n[Config] Qdrant: {config.qdrant_host}:{config.qdrant_port}")
    print(f"[Config] Collection: {config.collection_name}")
    print(f"[Config] Embedding: {config.embedding_model}")
    print(f"[Config] PDF 目录: {directory}")
    print(f"[Config] Chunk 大小: {config.chunk_size}, 重叠: {config.chunk_overlap}")

    # 检查目录
    if not os.path.exists(directory):
        print(f"\n[Error] PDF 目录不存在: {directory}")
        sys.exit(1)

    pdf_files = [f for f in os.listdir(directory) if f.lower().endswith(".pdf")]
    print(f"\n[Info] 发现 {len(pdf_files)} 个 PDF 文件")

    if len(pdf_files) == 0:
        print("[Error] 目录中没有 PDF 文件")
        sys.exit(1)

    # 初始化服务
    print("\n[Init] 初始化 RAG 服务...")
    start_time = time.time()

    try:
        rag_service = RAGService(config)
        print(f"[Init] RAG 服务初始化完成 ({time.time() - start_time:.2f}s)")
    except Exception as e:
        print(f"[Error] RAG 服务初始化失败: {e}")
        sys.exit(1)

    # 检查 Qdrant 连接
    print("\n[Qdrant] 检查连接...")
    try:
        status = rag_service.get_status()
        if status:
            print(f"[Qdrant] 连接成功, 当前文档数: {status.get('points_count', 0)}")
        else:
            print("[Qdrant] Collection 不存在，将创建新的")
    except Exception as e:
        print(f"[Error] Qdrant 连接失败: {e}")
        print("\n请确保 Qdrant 已启动:")
        print("  docker run -p 6333:6333 qdrant/qdrant")
        sys.exit(1)

    # 重建索引
    if args.recreate:
        print("\n[Index] 重建索引（删除旧数据）...")
        rag_service.indexer.create_collection(recreate=True)
        print("[Index] Collection 已重建")
    else:
        # 确保 collection 存在
        rag_service.indexer.create_collection(recreate=False)

    # 开始索引
    print("\n" + "=" * 60)
    print("开始索引 PDF 文件...")
    print("=" * 60 + "\n")

    total_start = time.time()
    result = rag_service.index_directory(directory)

    # 输出结果
    print("\n" + "=" * 60)
    print("索引完成!")
    print("=" * 60)
    print(f"\n[Result] 总文件数: {result['total_files']}")
    print(f"[Result] 成功索引: {result['indexed_files']}")
    print(f"[Result] 总文本块: {result['total_chunks']}")
    print(f"[Result] 总耗时: {time.time() - total_start:.2f}s")

    if result['failed']:
        print(f"\n[Warning] 失败文件: {len(result['failed'])}")
        for f in result['failed']:
            print(f"  - {f['file']}: {f['error']}")

    # 验证索引
    print("\n[Verify] 验证索引...")
    final_status = rag_service.get_status()
    print(f"[Verify] Collection 文档总数: {final_status.get('points_count', 0)}")

    print("\n索引构建完成!")


if __name__ == "__main__":
    main()
