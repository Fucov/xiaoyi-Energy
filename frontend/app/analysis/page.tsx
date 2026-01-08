'use client'

import { useState, useEffect, useRef } from 'react'
import Image from 'next/image'
import { Download, Share2, MoreVertical, Send, CheckCircle2, Loader2, TrendingUp, TrendingDown, Minus, AlertCircle, ExternalLink } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts'
import {
    createAnalysisTask,
    pollAnalysisStatus,
    AnalysisStatusResponse,
    AnalysisSessionData,
    TimeSeriesPoint,
    StepDetail,
    NewsItem,
    RAGSource,
    getStepsForIntent
} from '@/lib/api/analysis'

// 消息类型
interface Message {
    id: string
    role: 'user' | 'assistant'
    timestamp: string
    text?: string
    sessionId?: string
    status?: 'pending' | 'processing' | 'completed' | 'error'
    data?: AnalysisSessionData
}

export default function AnalysisPage() {
    const [messages, setMessages] = useState<Message[]>([])
    const [inputValue, setInputValue] = useState('')
    const [model, setModel] = useState<'prophet' | 'xgboost' | 'randomforest' | 'dlinear'>('prophet')
    const [isLoading, setIsLoading] = useState(false)
    const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)

    const chatContainerRef = useRef<HTMLDivElement>(null)

    // 自动滚动到底部
    const scrollToBottom = () => {
        if (chatContainerRef.current) {
            chatContainerRef.current.scrollTo({
                top: chatContainerRef.current.scrollHeight,
                behavior: 'smooth'
            })
        }
    }

    useEffect(() => {
        scrollToBottom()
    }, [messages])

    // 快速建议
    const quickSuggestions = [
        '分析贵州茅台未来一个月走势',
        '茅台最新的研报有什么观点？',
        '最近有哪些股市相关新闻？',
        '帮我分析一下宁德时代',
    ]

    const handleSend = async (messageOverride?: string) => {
        const messageToSend = messageOverride || inputValue
        if (!messageToSend.trim() || isLoading) return

        const userMessage: Message = {
            id: Date.now().toString(),
            role: 'user',
            text: messageToSend,
            timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        }

        const assistantMessageId = (Date.now() + 1).toString()
        const assistantMessage: Message = {
            id: assistantMessageId,
            role: 'assistant',
            timestamp: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
            status: 'pending',
        }

        setMessages(prev => [...prev, userMessage, assistantMessage])
        setInputValue('')
        setIsLoading(true)

        try {
            // 创建分析任务
            const result = await createAnalysisTask(
                messageToSend,
                model,
                '',
                currentSessionId || undefined
            )

            setCurrentSessionId(result.session_id)

            // 更新 assistant 消息的 sessionId
            setMessages(prev => prev.map(msg =>
                msg.id === assistantMessageId
                    ? { ...msg, sessionId: result.session_id, status: 'processing' as const }
                    : msg
            ))

            // 轮询状态
            await pollAnalysisStatus(result.session_id, (statusResp) => {
                setMessages(prev => prev.map(msg =>
                    msg.id === assistantMessageId
                        ? {
                            ...msg,
                            status: statusResp.status,
                            data: statusResp.data
                        }
                        : msg
                ))
            })

            setIsLoading(false)
        } catch (error: any) {
            console.error('分析失败:', error)
            setMessages(prev => prev.map(msg =>
                msg.id === assistantMessageId
                    ? {
                        ...msg,
                        status: 'error' as const,
                        data: {
                            ...msg.data,
                            error_message: error.message
                        } as AnalysisSessionData
                    }
                    : msg
            ))
            setIsLoading(false)
        }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
            handleSend()
        }
    }

    const isEmpty = messages.length === 0

    return (
        <main className="flex-1 flex flex-col min-w-0 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 min-h-screen">
            {/* 顶部栏 */}
            <header className="h-14 border-b border-white/5 flex items-center justify-between px-6 bg-slate-800/30">
                <div className="flex items-center gap-4">
                    <Image
                        src="/logo.svg"
                        alt="Logo"
                        width={28}
                        height={28}
                        className="flex-shrink-0"
                    />
                    <h2 className="text-base font-semibold text-white">
                        {isEmpty ? '智能金融分析' : '分析对话'}
                    </h2>
                    {!isEmpty && isLoading && (
                        <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded text-[10px] font-medium">
                            分析中
                        </span>
                    )}
                </div>
                {!isEmpty && (
                    <div className="flex items-center gap-2">
                        <button className="p-2 hover:bg-slate-700 rounded-lg transition-colors" title="导出">
                            <Download className="w-4 h-4 text-gray-400" />
                        </button>
                        <button className="p-2 hover:bg-slate-700 rounded-lg transition-colors" title="分享">
                            <Share2 className="w-4 h-4 text-gray-400" />
                        </button>
                        <button className="p-2 hover:bg-slate-700 rounded-lg transition-colors" title="更多">
                            <MoreVertical className="w-4 h-4 text-gray-400" />
                        </button>
                    </div>
                )}
            </header>

            {/* 对话区域 */}
            <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-6 space-y-6">
                {isEmpty ? (
                    /* 空状态 - 欢迎界面 */
                    <div className="flex flex-col items-center justify-center h-full -mt-20">
                        <div className="text-center max-w-lg">
                            <h3 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent mb-4">
                                智能金融分析平台
                            </h3>
                            <p className="text-gray-400 text-sm mb-8">
                                基于AI的时序预测与市场情绪分析，支持股票走势预测、研报检索、新闻分析
                            </p>
                            <div className="flex flex-col gap-3">
                                {quickSuggestions.map((suggestion, index) => (
                                    <button
                                        key={index}
                                        onClick={() => handleSend(suggestion)}
                                        className="px-4 py-3 bg-slate-700/50 hover:bg-slate-600/50 border border-white/5 hover:border-blue-500/30 rounded-xl text-left text-sm text-gray-300 hover:text-gray-100 transition-all"
                                    >
                                        {suggestion}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                ) : (
                    /* 消息列表 */
                    messages.map((message) => (
                        <div key={message.id} className="max-w-5xl mx-auto">
                            {message.role === 'user' ? (
                                <UserMessageBubble message={message} />
                            ) : (
                                <AssistantMessageBubble message={message} />
                            )}
                        </div>
                    ))
                )}
            </div>

            {/* 快捷建议 - 有消息时显示 */}
            {!isEmpty && !isLoading && (
                <div className="px-6 py-2 flex gap-2 flex-wrap justify-center">
                    {quickSuggestions.slice(0, 3).map((suggestion, index) => (
                        <button
                            key={index}
                            onClick={() => handleSend(suggestion)}
                            className="px-3 py-1.5 bg-slate-700/50 hover:bg-slate-600/50 border border-white/5 hover:border-blue-500/30 rounded-lg text-xs text-gray-400 hover:text-gray-200 transition-all"
                        >
                            {suggestion}
                        </button>
                    ))}
                </div>
            )}

            {/* 输入区域 */}
            <div className="px-3 py-3 border-t border-white/5 bg-slate-800/50">
                <div className="max-w-4xl mx-auto">
                    <div className="flex items-center gap-3">
                        {/* 模型选择 */}
                        <select
                            value={model}
                            onChange={(e) => setModel(e.target.value as any)}
                            className="px-3 py-2.5 bg-slate-700/50 border border-white/10 rounded-lg text-sm text-gray-300 focus:outline-none focus:border-blue-500/50"
                            disabled={isLoading}
                        >
                            <option value="prophet">Prophet</option>
                            <option value="xgboost">XGBoost</option>
                            <option value="randomforest">RandomForest</option>
                            <option value="dlinear">DLinear</option>
                        </select>

                        {/* 输入框 */}
                        <div className="flex-1 relative">
                            <div className="bg-slate-700/50 rounded-xl border border-white/10 focus-within:border-blue-500/50 transition-colors">
                                <textarea
                                    className="w-full bg-transparent px-4 py-2.5 text-sm text-gray-200 placeholder-gray-500 resize-none outline-none"
                                    rows={1}
                                    placeholder="输入分析问题，如：分析茅台未来走势..."
                                    value={inputValue}
                                    onChange={(e) => setInputValue(e.target.value)}
                                    onKeyDown={handleKeyDown}
                                    disabled={isLoading}
                                />
                            </div>
                        </div>

                        {/* 发送按钮 */}
                        <button
                            className="p-2.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 rounded-lg transition-all flex-shrink-0 disabled:opacity-50"
                            onClick={() => handleSend()}
                            disabled={!inputValue.trim() || isLoading}
                        >
                            <Send className="w-4 h-4 text-white" />
                        </button>
                    </div>

                    <div className="flex items-center justify-between mt-1.5 px-1">
                        <div className="flex items-center gap-2 text-[10px] text-gray-600">
                            <kbd className="px-1 py-0.5 bg-slate-700/50 rounded text-gray-500 text-[9px]">⌘↵</kbd>
                            <span>发送</span>
                        </div>
                        <div className="text-[10px] text-gray-600">
                            智能意图识别 · 异步分析
                        </div>
                    </div>
                </div>
            </div>
        </main>
    )
}

// 用户消息气泡
function UserMessageBubble({ message }: { message: Message }) {
    return (
        <div className="flex justify-end">
            <div className="bg-blue-600/20 border border-blue-500/30 rounded-2xl px-4 py-3 max-w-xl">
                <p className="text-gray-200 text-sm">{message.text}</p>
                <p className="text-[10px] text-gray-500 mt-1 text-right">{message.timestamp}</p>
            </div>
        </div>
    )
}

// 助手消息气泡 - 包含分析结果
function AssistantMessageBubble({ message }: { message: Message }) {
    const { status, data } = message

    // 错误状态
    if (status === 'error') {
        return (
            <div className="bg-red-900/20 border border-red-500/30 rounded-2xl p-4">
                <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                    <div>
                        <p className="text-red-300 font-medium">分析失败</p>
                        <p className="text-red-400/80 text-sm mt-1">{data?.error_message || '未知错误'}</p>
                    </div>
                </div>
            </div>
        )
    }

    // 加载/处理状态
    if (status === 'pending' || status === 'processing') {
        const intent = data?.intent || 'pending'
        const steps = intent !== 'pending' ? getStepsForIntent(intent) : []
        const stepDetails = data?.step_details || []

        return (
            <div className="space-y-4">
                {/* 意图显示 */}
                {data?.intent_result && (
                    <div className="bg-slate-700/30 border border-white/5 rounded-xl p-4">
                        <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs text-gray-400">识别意图：</span>
                            <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded text-xs font-medium">
                                {data.intent_result.intent}
                            </span>
                        </div>
                        <p className="text-gray-400 text-xs">{data.intent_result.reason}</p>
                    </div>
                )}

                {/* 步骤进度 */}
                <StepProgress steps={steps} stepDetails={stepDetails} />
            </div>
        )
    }

    // 完成状态 - 显示结果
    if (status === 'completed' && data) {
        return (
            <div className="space-y-6">
                {/* 根据意图显示不同内容 */}
                {data.intent === 'forecast' && (
                    <ForecastResult data={data} />
                )}
                {data.intent === 'rag' && (
                    <RAGResult data={data} />
                )}
                {data.intent === 'news' && (
                    <NewsResult data={data} />
                )}
                {data.intent === 'chat' && (
                    <ChatResult data={data} />
                )}
                {!data.intent && (
                    <ChatResult data={data} />
                )}
            </div>
        )
    }

    // 默认 - 加载中
    return (
        <div className="flex items-center gap-3 text-gray-400">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm">正在处理...</span>
        </div>
    )
}

// 步骤进度组件
function StepProgress({ steps, stepDetails }: { steps: { id: string; name: string; icon: string }[], stepDetails: StepDetail[] }) {
    if (steps.length === 0) {
        return (
            <div className="flex items-center gap-3 text-gray-400">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span className="text-sm">正在识别意图...</span>
            </div>
        )
    }

    return (
        <div className="bg-slate-700/30 border border-white/5 rounded-xl p-4">
            <div className="space-y-3">
                {steps.map((step) => {
                    const detail = stepDetails.find(d => d.id === step.id)
                    const stepStatus = detail?.status || 'pending'

                    return (
                        <div key={step.id} className="flex items-center gap-3">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm ${
                                stepStatus === 'completed'
                                    ? 'bg-green-500/20 text-green-400'
                                    : stepStatus === 'running'
                                        ? 'bg-blue-500/20 text-blue-400'
                                        : stepStatus === 'error'
                                            ? 'bg-red-500/20 text-red-400'
                                            : 'bg-slate-600/50 text-gray-500'
                            }`}>
                                {stepStatus === 'completed' ? (
                                    <CheckCircle2 className="w-4 h-4" />
                                ) : stepStatus === 'running' ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : stepStatus === 'error' ? (
                                    <AlertCircle className="w-4 h-4" />
                                ) : (
                                    step.icon
                                )}
                            </div>
                            <div className="flex-1">
                                <p className={`text-sm ${
                                    stepStatus === 'completed' || stepStatus === 'running'
                                        ? 'text-gray-200'
                                        : 'text-gray-500'
                                }`}>
                                    {step.name}
                                </p>
                                {detail?.message && (
                                    <p className="text-xs text-gray-500 mt-0.5">{detail.message}</p>
                                )}
                            </div>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}

// 预测结果组件
function ForecastResult({ data }: { data: AnalysisSessionData }) {
    return (
        <div className="space-y-6">
            {/* 上部：情绪仪表 + 新闻/研报 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <EmotionGauge emotion={data.emotion} description={data.emotion_des} />
                <div className="space-y-4">
                    <NewsSection news={data.news_list} />
                    <ReportsSection reports={data.report_list} />
                </div>
            </div>

            {/* 中部：价格图表 */}
            <PriceChart
                originalData={data.time_series_original}
                fullData={data.time_series_full}
                predictionDone={data.prediction_done}
            />

            {/* 底部：结论 */}
            <ConclusionSection conclusion={data.conclusion} />
        </div>
    )
}

// RAG 结果组件
function RAGResult({ data }: { data: AnalysisSessionData }) {
    return (
        <div className="space-y-4">
            {/* 回答 */}
            <div className="bg-slate-700/30 border border-white/5 rounded-xl p-6">
                <div className="prose prose-invert prose-sm max-w-none">
                    <ReactMarkdown>{data.conclusion}</ReactMarkdown>
                </div>
            </div>

            {/* 来源 */}
            {data.rag_sources && data.rag_sources.length > 0 && (
                <div className="bg-slate-700/30 border border-white/5 rounded-xl p-4">
                    <h4 className="text-sm font-medium text-gray-300 mb-3">📚 引用来源</h4>
                    <div className="space-y-2">
                        {data.rag_sources.map((source, idx) => (
                            <div key={idx} className="flex items-start gap-2 text-xs text-gray-400">
                                <span className="text-blue-400">[{idx + 1}]</span>
                                <div>
                                    <span className="text-gray-300">{source.file_name}</span>
                                    <span className="text-gray-500"> · 第{source.page_number}页 · 相关度 {(source.score * 100).toFixed(0)}%</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}

// 新闻结果组件
function NewsResult({ data }: { data: AnalysisSessionData }) {
    return (
        <div className="space-y-4">
            {/* 新闻总结 */}
            <div className="bg-slate-700/30 border border-white/5 rounded-xl p-6">
                <div className="prose prose-invert prose-sm max-w-none">
                    <ReactMarkdown>{data.conclusion}</ReactMarkdown>
                </div>
            </div>

            {/* 新闻列表 */}
            {data.news_list && data.news_list.length > 0 && (
                <div className="bg-slate-700/30 border border-white/5 rounded-xl p-4">
                    <h4 className="text-sm font-medium text-gray-300 mb-3">📰 相关新闻</h4>
                    <div className="space-y-3">
                        {data.news_list.map((news, idx) => (
                            <div key={idx} className="border-l-2 border-blue-500/50 pl-3 hover:bg-slate-600/30 py-2 rounded-r transition-colors">
                                <p className="text-sm text-gray-200 font-medium">{news.title}</p>
                                {news.summary && (
                                    <p className="text-xs text-gray-400 mt-1 line-clamp-2">{news.summary}</p>
                                )}
                                <div className="flex items-center gap-2 mt-1.5 text-[10px] text-gray-500">
                                    <span>{news.source}</span>
                                    <span>·</span>
                                    <span>{news.date}</span>
                                    {news.url && (
                                        <>
                                            <span>·</span>
                                            <a href={news.url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline flex items-center gap-0.5">
                                                查看原文 <ExternalLink className="w-3 h-3" />
                                            </a>
                                        </>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}

// 对话结果组件
function ChatResult({ data }: { data: AnalysisSessionData }) {
    return (
        <div className="bg-slate-700/30 border border-white/5 rounded-xl p-6">
            <div className="prose prose-invert prose-sm max-w-none">
                <ReactMarkdown>{data.conclusion}</ReactMarkdown>
            </div>
        </div>
    )
}

// 情绪仪表盘组件 - 暗色主题版
function EmotionGauge({ emotion, description }: { emotion: number | null, description: string | null }) {
    if (emotion === null) {
        return (
            <div className="bg-slate-700/30 border border-white/5 rounded-xl p-6 flex items-center justify-center h-80">
                <div className="text-center text-gray-400">
                    <Loader2 className="w-10 h-10 animate-spin mx-auto mb-3 text-blue-400" />
                    <p className="text-sm">正在分析市场情绪...</p>
                </div>
            </div>
        )
    }

    const rotation = emotion * 90
    const getEmotionColor = (score: number) => {
        if (score > 0.3) return 'text-green-400'
        if (score < -0.3) return 'text-red-400'
        return 'text-gray-400'
    }

    const getEmotionIcon = (score: number) => {
        if (score > 0.3) return <TrendingUp className="w-6 h-6" />
        if (score < -0.3) return <TrendingDown className="w-6 h-6" />
        return <Minus className="w-6 h-6" />
    }

    return (
        <div className="bg-slate-700/30 border border-white/5 rounded-xl p-6">
            <h3 className="text-lg font-semibold text-gray-200 mb-4">😊 市场情绪</h3>

            {/* 仪表盘 */}
            <div className="relative w-56 h-28 mx-auto mb-6">
                <svg className="w-full h-full" viewBox="0 0 200 100">
                    <defs>
                        <linearGradient id="gaugeRedDark" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="#ef4444" />
                            <stop offset="100%" stopColor="#f87171" />
                        </linearGradient>
                        <linearGradient id="gaugeGreenDark" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="#22c55e" />
                            <stop offset="100%" stopColor="#4ade80" />
                        </linearGradient>
                    </defs>

                    <path d="M 20 80 A 80 80 0 0 1 180 80" fill="none" stroke="#374151" strokeWidth="20" strokeLinecap="round" />
                    <path d="M 20 80 A 80 80 0 0 1 100 10" fill="none" stroke="url(#gaugeRedDark)" strokeWidth="20" strokeLinecap="round" opacity="0.5" />
                    <path d="M 100 10 A 80 80 0 0 1 180 80" fill="none" stroke="url(#gaugeGreenDark)" strokeWidth="20" strokeLinecap="round" opacity="0.5" />

                    <line x1="100" y1="80" x2="100" y2="30" stroke="#e5e7eb" strokeWidth="3" strokeLinecap="round"
                        transform={`rotate(${rotation} 100 80)`} className="transition-transform duration-1000" />
                    <circle cx="100" cy="80" r="8" fill="#e5e7eb" />
                </svg>

                <div className="absolute top-0 left-0 text-[10px] font-medium text-red-400">看跌</div>
                <div className="absolute top-0 right-0 text-[10px] font-medium text-green-400">看涨</div>
            </div>

            {/* 情绪值 */}
            <div className="text-center space-y-3">
                <div className={`flex items-center justify-center gap-2 ${getEmotionColor(emotion)}`}>
                    {getEmotionIcon(emotion)}
                    <span className="text-3xl font-bold">
                        {emotion > 0 ? '+' : ''}{emotion.toFixed(2)}
                    </span>
                </div>
                <div className="bg-slate-600/30 rounded-lg p-3">
                    <p className="text-gray-300 text-sm leading-relaxed">{description}</p>
                </div>
            </div>
        </div>
    )
}

// 新闻列表组件 - 暗色主题版
function NewsSection({ news }: { news: NewsItem[] }) {
    if (!news || news.length === 0) {
        return (
            <div className="bg-slate-700/30 border border-white/5 rounded-xl p-4 h-36 flex items-center justify-center">
                <div className="text-center text-gray-500">
                    <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2 text-blue-400" />
                    <p className="text-xs">获取新闻中...</p>
                </div>
            </div>
        )
    }

    return (
        <div className="bg-slate-700/30 border border-white/5 rounded-xl p-4">
            <h3 className="font-medium text-gray-200 mb-3 flex items-center text-sm">
                📰 相关新闻
                <span className="ml-2 text-[10px] bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full">{news.length}</span>
            </h3>
            <div className="space-y-2 max-h-32 overflow-y-auto">
                {news.map((item, idx) => (
                    <div key={idx} className="border-l-2 border-blue-500/50 pl-3 hover:bg-slate-600/30 py-1.5 rounded-r transition-colors">
                        <p className="text-xs text-gray-300 line-clamp-1">{item.title}</p>
                        <p className="text-[10px] text-gray-500 mt-0.5">
                            {item.source} · {item.date}
                        </p>
                    </div>
                ))}
            </div>
        </div>
    )
}

// 研报列表组件 - 暗色主题版
function ReportsSection({ reports }: { reports: any[] }) {
    if (!reports || reports.length === 0) {
        return (
            <div className="bg-slate-700/30 border border-white/5 rounded-xl p-4 h-28 flex items-center justify-center">
                <p className="text-xs text-gray-500">暂无研报数据</p>
            </div>
        )
    }

    return (
        <div className="bg-slate-700/30 border border-white/5 rounded-xl p-4">
            <h3 className="font-medium text-gray-200 mb-3 text-sm">📊 研究报告</h3>
            <div className="space-y-2">
                {reports.map((item, idx) => (
                    <div key={idx} className="border-l-2 border-purple-500/50 pl-3 hover:bg-slate-600/30 py-1.5 rounded-r transition-colors">
                        <p className="text-xs text-gray-300">{item.title}</p>
                    </div>
                ))}
            </div>
        </div>
    )
}

// 价格图表组件 - 暗色主题版
function PriceChart({ originalData, fullData, predictionDone }: {
    originalData: TimeSeriesPoint[]
    fullData: TimeSeriesPoint[]
    predictionDone: boolean
}) {
    if (!originalData || originalData.length === 0) {
        return (
            <div className="bg-slate-700/30 border border-white/5 rounded-xl p-6 h-80 flex items-center justify-center">
                <div className="text-center text-gray-400">
                    <Loader2 className="w-10 h-10 animate-spin mx-auto mb-3 text-blue-400" />
                    <p className="text-sm">加载数据中...</p>
                </div>
            </div>
        )
    }

    const dataToShow = predictionDone ? fullData : originalData
    const predictionStartIndex = originalData.length

    const chartData = dataToShow.map((point, index) => ({
        date: point.date,
        value: point.value,
        isPrediction: point.is_prediction,
        displayDate: index % Math.ceil(dataToShow.length / 10) === 0 ? point.date : ''
    }))

    return (
        <div className="bg-slate-700/30 border border-white/5 rounded-xl p-6">
            <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold text-gray-200">📈 价格走势</h3>
                <div className="flex gap-4 text-xs">
                    <div className="flex items-center gap-2">
                        <div className="w-3 h-3 bg-blue-500 rounded"></div>
                        <span className="text-gray-400">历史</span>
                    </div>
                    {predictionDone && (
                        <div className="flex items-center gap-2">
                            <div className="w-3 h-3 bg-green-500 rounded"></div>
                            <span className="text-gray-400">预测</span>
                        </div>
                    )}
                </div>
            </div>

            <ResponsiveContainer width="100%" height={300}>
                <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="displayDate" stroke="#6b7280" style={{ fontSize: '10px' }} />
                    <YAxis stroke="#6b7280" style={{ fontSize: '10px' }} domain={['auto', 'auto']} />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: 'rgba(30, 41, 59, 0.95)',
                            border: '1px solid rgba(255,255,255,0.1)',
                            borderRadius: '8px',
                            color: '#e5e7eb'
                        }}
                        formatter={(value: any) => [`¥${value.toFixed(2)}`, '价格']}
                    />

                    {predictionDone && (
                        <ReferenceLine
                            x={chartData[predictionStartIndex]?.date}
                            stroke="#6b7280"
                            strokeDasharray="5 5"
                            label={{ value: '预测起点', position: 'top', fill: '#9ca3af', fontSize: 10 }}
                        />
                    )}

                    <Line
                        type="monotone"
                        dataKey="value"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        dot={false}
                        name="价格"
                        connectNulls
                    />

                    {predictionDone && (
                        <Line
                            type="monotone"
                            dataKey={(entry) => entry.isPrediction ? entry.value : null}
                            stroke="#22c55e"
                            strokeWidth={2}
                            strokeDasharray="5 5"
                            dot={false}
                            name="预测"
                            connectNulls
                        />
                    )}
                </LineChart>
            </ResponsiveContainer>

            <div className="mt-3 flex justify-between text-xs text-gray-500 bg-slate-600/30 rounded-lg p-3">
                <span>历史数据: <strong className="text-blue-400">{originalData.length}</strong> 点</span>
                {predictionDone && (
                    <span>预测数据: <strong className="text-green-400">{fullData.length - originalData.length}</strong> 点</span>
                )}
            </div>
        </div>
    )
}

// 结论组件 - 暗色主题版
function ConclusionSection({ conclusion }: { conclusion: string }) {
    if (!conclusion) {
        return (
            <div className="bg-slate-700/30 border border-white/5 rounded-xl p-6 min-h-60 flex items-center justify-center">
                <div className="text-center text-gray-400">
                    <Loader2 className="w-10 h-10 animate-spin mx-auto mb-3 text-blue-400" />
                    <p className="text-sm">生成分析报告中...</p>
                </div>
            </div>
        )
    }

    return (
        <div className="bg-slate-700/30 border border-white/5 rounded-xl p-6">
            <h3 className="text-lg font-semibold text-gray-200 mb-4">📝 综合分析报告</h3>
            <div className="prose prose-invert prose-sm max-w-none">
                <ReactMarkdown>{conclusion}</ReactMarkdown>
            </div>
        </div>
    )
}
