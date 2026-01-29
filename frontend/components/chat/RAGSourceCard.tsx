'use client'

import { FileText } from 'lucide-react'
import type { RAGSource } from '@/lib/api/analysis'

interface RAGSourceCardProps {
  sources: RAGSource[]
}

/**
 * RAG 研报来源卡片组件
 *
 * 直接展示 LLM 总结的研报摘要
 */
export function RAGSourceCard({ sources }: RAGSourceCardProps) {
  if (!sources || sources.length === 0) {
    return null
  }

  const getScoreColor = (score: number) => {
    if (score >= 0.8) return 'text-green-400'
    if (score >= 0.6) return 'text-blue-400'
    if (score >= 0.4) return 'text-yellow-400'
    return 'text-gray-400'
  }

  return (
    <div className="space-y-2.5">
      {sources.map((source, index) => (
        <div
          key={`${source.filename}-${source.page}-${index}`}
          className="relative rounded-lg bg-dark-700/40 border border-white/5 px-3.5 py-2.5"
        >
          {/* 标题行 */}
          <div className="flex items-center gap-2 mb-1.5">
            <FileText className={`w-3.5 h-3.5 flex-shrink-0 ${getScoreColor(source.score)}`} />
            <span className="text-xs text-gray-300 font-medium truncate flex-1">
              {source.filename}
            </span>
            <span className="text-[10px] text-gray-500 flex-shrink-0">p.{source.page}</span>
            <span className={`text-[10px] flex-shrink-0 ${getScoreColor(source.score)}`}>
              {(source.score * 100).toFixed(0)}%
            </span>
          </div>
          {/* 摘要 */}
          {source.content_snippet && (
            <p className="text-xs text-gray-400 leading-relaxed">
              {source.content_snippet}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}

/**
 * 紧凑版 RAG 来源展示（用于有限空间）
 */
export function RAGSourceCompact({ sources }: RAGSourceCardProps) {
  if (!sources || sources.length === 0) {
    return null
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {sources.slice(0, 3).map((source, index) => (
        <span
          key={`${source.filename}-${source.page}-${index}`}
          className="inline-flex items-center gap-1 text-[10px] text-violet-400 bg-violet-500/10 px-2 py-1 rounded-full border border-violet-500/20"
          title={`${source.filename} - 第${source.page}页 (${(source.score * 100).toFixed(0)}%)\n${source.content_snippet}`}
        >
          <FileText className="w-3 h-3" />
          <span className="truncate max-w-[120px]">{source.filename}</span>
          <span className="text-violet-300/60">p.{source.page}</span>
        </span>
      ))}
      {sources.length > 3 && (
        <span className="text-[10px] text-gray-500 px-2 py-1">
          +{sources.length - 3} 更多
        </span>
      )}
    </div>
  )
}
