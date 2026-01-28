'use client'

import { useState } from 'react'
import { FileText, ChevronDown, ChevronUp, ExternalLink, Sparkles } from 'lucide-react'
import type { RAGSource } from '@/lib/api/analysis'

interface RAGSourceCardProps {
  sources: RAGSource[]
}

/**
 * RAG 研报来源卡片组件
 *
 * 展示 RAG 检索到的研报来源，包括：
 * - 文件名
 * - 页码定位
 * - 内容摘要
 * - 相关度分数
 */
export function RAGSourceCard({ sources }: RAGSourceCardProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null)

  if (!sources || sources.length === 0) {
    return null
  }

  const toggleExpand = (index: number) => {
    setExpandedIndex(expandedIndex === index ? null : index)
  }

  // 根据分数获取颜色
  const getScoreColor = (score: number) => {
    if (score >= 0.8) return {
      text: 'text-green-400',
      bg: 'bg-green-500/10',
      border: 'border-green-500/30',
      glow: 'shadow-green-500/20'
    }
    if (score >= 0.6) return {
      text: 'text-blue-400',
      bg: 'bg-blue-500/10',
      border: 'border-blue-500/30',
      glow: 'shadow-blue-500/20'
    }
    if (score >= 0.4) return {
      text: 'text-yellow-400',
      bg: 'bg-yellow-500/10',
      border: 'border-yellow-500/30',
      glow: 'shadow-yellow-500/20'
    }
    return {
      text: 'text-gray-400',
      bg: 'bg-gray-500/10',
      border: 'border-gray-500/30',
      glow: 'shadow-gray-500/20'
    }
  }

  // 根据分数获取相关度文字
  const getScoreLabel = (score: number) => {
    if (score >= 0.8) return '高度相关'
    if (score >= 0.6) return '较为相关'
    if (score >= 0.4) return '一般相关'
    return '参考价值'
  }

  return (
    <div className="space-y-3">
      {sources.map((source, index) => {
        const scoreStyle = getScoreColor(source.score)
        const isExpanded = expandedIndex === index
        
        return (
          <div
            key={`${source.filename}-${source.page}-${index}`}
            className={`group relative overflow-hidden rounded-xl bg-gradient-to-br from-dark-700/60 via-dark-800/40 to-dark-700/60 border transition-all duration-300 ${
              isExpanded 
                ? `${scoreStyle.border} shadow-lg ${scoreStyle.glow}` 
                : 'border-white/10 hover:border-violet-500/30'
            }`}
          >
            {/* 背景渐变 */}
            <div className={`absolute inset-0 bg-gradient-to-r transition-opacity duration-300 ${
              isExpanded ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
            } ${
              source.score >= 0.8 ? 'from-green-500/5 via-transparent to-transparent' :
              source.score >= 0.6 ? 'from-blue-500/5 via-transparent to-transparent' :
              source.score >= 0.4 ? 'from-yellow-500/5 via-transparent to-transparent' :
              'from-gray-500/5 via-transparent to-transparent'
            }`} />
            
            {/* 头部：文件名、页码、相关度 */}
            <button
              onClick={() => toggleExpand(index)}
              className="relative w-full flex items-center justify-between px-4 py-3 text-left hover:bg-dark-600/20 transition-all duration-200"
            >
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <div className={`p-1.5 rounded-lg bg-gradient-to-br ${
                  source.score >= 0.8 ? 'from-green-500/20 to-emerald-500/20 border border-green-500/30' :
                  source.score >= 0.6 ? 'from-blue-500/20 to-cyan-500/20 border border-blue-500/30' :
                  source.score >= 0.4 ? 'from-yellow-500/20 to-amber-500/20 border border-yellow-500/30' :
                  'from-gray-500/20 to-gray-500/20 border border-gray-500/30'
                }`}>
                  <FileText className={`w-4 h-4 ${scoreStyle.text}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm text-gray-200 truncate font-semibold group-hover:text-violet-300 transition-colors">
                      {source.filename}
                    </span>
                    <span className="text-xs text-gray-500 px-2 py-0.5 bg-dark-700/50 rounded border border-white/5 flex-shrink-0">
                      第 {source.page} 页
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                {/* 相关度标签 */}
                <span
                  className={`text-[10px] px-2.5 py-1 rounded-lg border font-semibold shadow-sm ${scoreStyle.text} ${scoreStyle.bg} ${scoreStyle.border}`}
                >
                  {getScoreLabel(source.score)} {(source.score * 100).toFixed(0)}%
                </span>
                <div className={`p-1 rounded transition-transform duration-200 ${
                  isExpanded ? 'rotate-180' : ''
                }`}>
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-gray-400" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-gray-400" />
                  )}
                </div>
              </div>
            </button>

            {/* 展开内容：摘要 */}
            {isExpanded && source.content_snippet && (
              <div className="px-4 pb-4 border-t border-white/10 animate-in slide-in-from-top-2 duration-200">
                <div className="mt-3 text-xs text-gray-400 leading-relaxed bg-dark-800/60 rounded-lg p-3 border border-white/5">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="w-3 h-3 text-violet-400" />
                    <span className="text-xs font-semibold text-violet-300 uppercase tracking-wide">内容摘要</span>
                  </div>
                  <p className="line-clamp-4 text-gray-300">{source.content_snippet}</p>
                </div>
                {/* 快捷操作 */}
                <div className="mt-3 flex items-center gap-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      // TODO: 实现研报预览功能
                      const ragUrl = `rag://${source.filename}#page=${source.page}`
                      alert(`研报来源: ${source.filename}\n页码: ${source.page}\n\n链接: ${ragUrl}`)
                    }}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-violet-400 hover:text-violet-300 bg-violet-500/10 hover:bg-violet-500/20 rounded-lg border border-violet-500/20 hover:border-violet-500/30 transition-all duration-200"
                  >
                    <ExternalLink className="w-3 h-3" />
                    查看原文
                  </button>
                </div>
              </div>
            )}
          </div>
        )
      })}
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
          className="inline-flex items-center gap-1 text-[10px] text-violet-400 bg-violet-500/10 px-2 py-1 rounded-full border border-violet-500/20 hover:bg-violet-500/20 cursor-pointer transition-colors"
          title={`${source.filename} - 第${source.page}页 (相关度: ${(source.score * 100).toFixed(0)}%)`}
          onClick={() => {
            alert(`研报来源: ${source.filename}\n页码: ${source.page}\n相关度: ${(source.score * 100).toFixed(0)}%\n\n摘要:\n${source.content_snippet}`)
          }}
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
