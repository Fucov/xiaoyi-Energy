'use client'

import { cn } from '@/lib/utils'
import { Copy, ThumbsUp, ThumbsDown, RotateCcw } from 'lucide-react'
import type { Message } from './ChatArea'

interface MessageBubbleProps {
  message: Message
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={cn(
      "flex gap-3 animate-slide-up",
      isUser ? "justify-end" : "justify-start"
    )}>
      {/* AI 头像 */}
      {!isUser && (
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center flex-shrink-0 shadow-lg">
          <span className="text-base">🔮</span>
        </div>
      )}

      <div className={cn(
        "max-w-[70%] group",
        isUser ? "order-first" : ""
      )}>
        {/* 消息内容 */}
        <div className={cn(
          "px-4 py-3 rounded-2xl text-[15px] leading-relaxed",
          isUser 
            ? "bg-gradient-to-r from-violet-600 to-purple-600 text-white rounded-br-md" 
            : "glass text-gray-200 rounded-bl-md"
        )}>
          {/* TODO: 支持 Markdown 渲染 - 可以让新手来实现 */}
          <MessageContent content={message.content} />
        </div>

        {/* 消息底部操作 */}
        <div className={cn(
          "flex items-center gap-2 mt-1.5 px-1",
          isUser ? "justify-end" : "justify-start"
        )}>
          <span className="text-[10px] text-gray-600">{message.timestamp}</span>
          
          {/* AI 消息的操作按钮 */}
          {!isUser && (
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <ActionButton icon={<Copy className="w-3 h-3" />} title="复制" />
              <ActionButton icon={<ThumbsUp className="w-3 h-3" />} title="有帮助" />
              <ActionButton icon={<ThumbsDown className="w-3 h-3" />} title="没帮助" />
              <ActionButton icon={<RotateCcw className="w-3 h-3" />} title="重新生成" />
            </div>
          )}
        </div>
      </div>

      {/* 用户头像 */}
      {isUser && (
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-orange-400 to-pink-500 flex items-center justify-center flex-shrink-0 text-sm font-bold">
          李
        </div>
      )}
    </div>
  )
}

// 消息内容渲染 - 简单版本，可以让新手扩展为完整 Markdown 支持
function MessageContent({ content }: { content: string }) {
  // 简单的加粗处理 **text**
  const parts = content.split(/(\*\*[^*]+\*\*)/g)
  
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={i} className="font-semibold text-violet-300">{part.slice(2, -2)}</strong>
        }
        return <span key={i}>{part}</span>
      })}
    </>
  )
}

// 操作按钮组件
function ActionButton({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <button 
      className="p-1 hover:bg-dark-600 rounded transition-colors text-gray-500 hover:text-gray-300"
      title={title}
    >
      {icon}
    </button>
  )
}
