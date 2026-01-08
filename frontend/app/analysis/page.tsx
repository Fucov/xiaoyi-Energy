'use client'

import { useState } from 'react'
import {
    createAnalysisTask,
    pollAnalysisStatus,
    AnalysisStatusResponse,
    TimeSeriesPoint
} from '@/lib/api/analysis'
import { CheckCircle2, Loader2, TrendingUp, TrendingDown, Minus, AlertCircle } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts'

// 步骤定义
const ANALYSIS_STEPS = [
    { id: 1, name: '解析需求', icon: '🔍' },
    { id: 2, name: '获取数据', icon: '📊' },
    { id: 3, name: '特征分析', icon: '📈' },
    { id: 4, name: '获取新闻', icon: '📰' },
    { id: 5, name: '情绪分析', icon: '😊' },
    { id: 6, name: '模型预测', icon: '🔮' },
    { id: 7, name: '生成报告', icon: '📝' }
]

export default function AnalysisPage() {
    const [message, setMessage] = useState('分析贵州茅台未来一个月走势')
    const [model, setModel] = useState<'prophet' | 'xgboost' | 'randomforest' | 'dlinear'>('prophet')
    const [sessionId, setSessionId] = useState<string | null>(null)
    const [status, setStatus] = useState<AnalysisStatusResponse | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const handleSubmit = async () => {
        try {
            setLoading(true)
            setError(null)
            setStatus(null)
            setSessionId(null)

            const result = await createAnalysisTask(message, model)
            setSessionId(result.session_id)

            await pollAnalysisStatus(result.session_id, (newStatus) => {
                setStatus(newStatus)
            })

            setLoading(false)
        } catch (err: any) {
            setError(err.message)
            setLoading(false)
        }
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100">
            <div className="max-w-7xl mx-auto p-6 space-y-6">
                {/* Header */}
                <div className="text-center py-8">
                    <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-3">
                        智能金融分析平台
                    </h1>
                    <p className="text-gray-600 text-lg">基于AI的时序预测与市场情绪分析</p>
                </div>

                {/* Input Section */}
                <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
                    <div className="flex gap-4">
                        <input
                            type="text"
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                            placeholder="请输入分析问题，例如：分析茅台未来走势"
                            className="flex-1 px-5 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-blue-500 transition-colors"
                            disabled={loading}
                        />
                        <select
                            value={model}
                            onChange={(e) => setModel(e.target.value as any)}
                            className="px-5 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:border-blue-500 bg-white"
                            disabled={loading}
                        >
                            <option value="prophet">Prophet</option>
                            <option value="xgboost">XGBoost</option>
                            <option value="randomforest">RandomForest</option>
                            <option value="dlinear">DLinear</option>
                        </select>
                        <button
                            onClick={handleSubmit}
                            disabled={loading}
                            className="px-8 py-3 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-xl font-semibold hover:from-blue-700 hover:to-blue-800 disabled:from-gray-400 disabled:to-gray-500 transition-all shadow-lg hover:shadow-xl transform hover:scale-105 disabled:transform-none"
                        >
                            {loading ? (
                                <span className="flex items-center gap-2">
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                    分析中...
                                </span>
                            ) : (
                                '开始分析'
                            )}
                        </button>
                    </div>
                </div>

                {/* Error Display */}
                {error && (
                    <div className="bg-red-50 border-2 border-red-200 rounded-xl p-4 flex items-start gap-3">
                        <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5" />
                        <div>
                            <p className="text-red-800 font-semibold">分析失败</p>
                            <p className="text-red-600 text-sm mt-1">{error}</p>
                        </div>
                    </div>
                )}

                {/* Analysis Results */}
                {status && (
                    <>
                        {/* Step Timeline */}
                        <StepTimeline currentStep={status.steps} isCompleted={status.status === 'completed'} />

                        {/* Main Content */}
                        <div className="space-y-6">
                            {/* Top Section: Emotion + News/Reports */}
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                <EmotionGauge
                                    emotion={status.data.emotion}
                                    description={status.data.emotion_des}
                                />
                                <div className="space-y-4">
                                    <NewsSection news={status.data.news_list} />
                                    <ReportsSection reports={status.data.report_list} />
                                </div>
                            </div>

                            {/* Middle: Price Chart */}
                            <PriceChart
                                originalData={status.data.time_series_original}
                                fullData={status.data.time_series_full}
                                predictionDone={status.data.prediction_done}
                            />

                            {/* Bottom: Conclusion */}
                            <ConclusionSection conclusion={status.data.conclusion} />
                        </div>
                    </>
                )}
            </div>
        </div>
    )
}

// 1. 更新 StepTimeline 组件定义，接收 isCompleted 参数
function StepTimeline({
    currentStep,
    isCompleted
}: {
    currentStep: number,
    isCompleted: boolean
}) {
    return (
        <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
            <div className="flex items-center justify-between">
                {ANALYSIS_STEPS.map((step, index) => {
                    // 判断逻辑：
                    // 1. 是否已完成：步骤 ID 小于当前步骤，或者整体任务已完成
                    const isFinished = step.id < currentStep || isCompleted;
                    // 2. 是否正在处理：当前步骤等于 ID，且整体任务尚未完成
                    const isProcessing = step.id === currentStep && !isCompleted;

                    return (
                        <div key={step.id} className="flex items-center flex-1">
                            <div className="flex flex-col items-center">
                                <div className={`relative w-14 h-14 rounded-full flex items-center justify-center font-bold text-lg transition-all ${isFinished
                                        ? 'bg-gradient-to-br from-green-400 to-green-600 text-white shadow-lg scale-110' :
                                        isProcessing
                                            ? 'bg-gradient-to-br from-blue-500 to-blue-700 text-white animate-pulse shadow-xl scale-125' :
                                            'bg-gray-100 text-gray-400'
                                    }`}>
                                    {isFinished ? (
                                        <CheckCircle2 className="w-7 h-7" />
                                    ) : isProcessing ? (
                                        <Loader2 className="w-7 h-7 animate-spin" />
                                    ) : (
                                        step.icon
                                    )}
                                </div>
                                <p className={`mt-3 text-sm font-semibold text-center transition-colors ${isFinished || isProcessing ? 'text-gray-900' : 'text-gray-400'
                                    }`}>
                                    {step.name}
                                </p>
                            </div>

                            {/* 连接线逻辑 */}
                            {index < ANALYSIS_STEPS.length - 1 && (
                                <div className={`flex-1 h-2 mx-3 rounded-full transition-all ${
                                    // 如果下一步已经开始或当前步已完成，线变绿
                                    step.id < currentStep || (step.id === currentStep && isCompleted)
                                        ? 'bg-gradient-to-r from-green-400 to-green-600'
                                        : 'bg-gray-200'
                                    }`} />
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    )
}

// 情绪仪表盘组件
function EmotionGauge({ emotion, description }: { emotion: number | null, description: string | null }) {
    if (emotion === null) {
        return (
            <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100 flex items-center justify-center h-96">
                <div className="text-center text-gray-400">
                    <Loader2 className="w-14 h-14 animate-spin mx-auto mb-4 text-blue-500" />
                    <p className="text-lg font-medium">正在分析市场情绪...</p>
                </div>
            </div>
        )
    }

    const rotation = emotion * 90
    const getEmotionColor = (score: number) => {
        if (score > 0.3) return 'text-green-600'
        if (score < -0.3) return 'text-red-600'
        return 'text-gray-600'
    }

    const getEmotionIcon = (score: number) => {
        if (score > 0.3) return <TrendingUp className="w-8 h-8" />
        if (score < -0.3) return <TrendingDown className="w-8 h-8" />
        return <Minus className="w-8 h-8" />
    }

    return (
        <div className="bg-gradient-to-br from-white to-gray-50 rounded-2xl shadow-xl p-8 border border-gray-100">
            <h3 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                😊 市场情绪
            </h3>

            {/* 仪表盘 */}
            <div className="relative w-72 h-36 mx-auto mb-8">
                <svg className="w-full h-full" viewBox="0 0 200 100">
                    <defs>
                        <linearGradient id="gaugeRed" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="#dc2626" />
                            <stop offset="100%" stopColor="#f87171" />
                        </linearGradient>
                        <linearGradient id="gaugeGreen" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="#10b981" />
                            <stop offset="100%" stopColor="#34d399" />
                        </linearGradient>
                    </defs>

                    <path d="M 20 80 A 80 80 0 0 1 180 80" fill="none" stroke="#e5e7eb" strokeWidth="24" strokeLinecap="round" />
                    <path d="M 20 80 A 80 80 0 0 1 100 10" fill="none" stroke="url(#gaugeRed)" strokeWidth="24" strokeLinecap="round" opacity="0.4" />
                    <path d="M 100 10 A 80 80 0 0 1 180 80" fill="none" stroke="url(#gaugeGreen)" strokeWidth="24" strokeLinecap="round" opacity="0.4" />

                    <line x1="100" y1="80" x2="100" y2="25" stroke="#1f2937" strokeWidth="4" strokeLinecap="round"
                        transform={`rotate(${rotation} 100 80)`} className="transition-transform duration-1000" />
                    <circle cx="100" cy="80" r="10" fill="#1f2937" />
                </svg>

                <div className="absolute top-0 left-0 text-xs font-bold text-red-600">极度看跌</div>
                <div className="absolute top-0 right-0 text-xs font-bold text-green-600">极度看涨</div>
            </div>

            {/* 情绪值 */}
            <div className="text-center space-y-4">
                <div className={`flex items-center justify-center gap-3 ${getEmotionColor(emotion)}`}>
                    {getEmotionIcon(emotion)}
                    <span className="text-5xl font-bold">
                        {emotion > 0 ? '+' : ''}{emotion.toFixed(2)}
                    </span>
                </div>
                <div className="bg-gray-50 rounded-xl p-4">
                    <p className="text-gray-700 font-medium leading-relaxed">{description}</p>
                </div>
            </div>
        </div>
    )
}

// 新闻列表组件
function NewsSection({ news }: { news: any[] }) {
    if (!news || news.length === 0) {
        return (
            <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-100 h-44 flex items-center justify-center">
                <div className="text-center text-gray-400">
                    <Loader2 className="w-10 h-10 animate-spin mx-auto mb-3 text-blue-500" />
                    <p className="text-sm font-medium">正在获取新闻...</p>
                </div>
            </div>
        )
    }

    return (
        <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-100">
            <h3 className="font-bold text-gray-900 mb-4 flex items-center text-lg">
                📰 相关新闻
                <span className="ml-2 text-xs bg-blue-100 text-blue-700 px-3 py-1 rounded-full font-semibold">{news.length}</span>
            </h3>
            <div className="space-y-3 max-h-44 overflow-y-auto custom-scrollbar">
                {news.map((item, idx) => (
                    <div key={idx} className="border-l-4 border-blue-500 pl-4 hover:bg-blue-50 p-3 rounded-r transition-colors cursor-pointer">
                        <p className="text-sm font-semibold text-gray-900 line-clamp-2">{item.title}</p>
                        <p className="text-xs text-gray-500 mt-2 flex items-center gap-2">
                            <span>{item.source}</span>
                            <span>·</span>
                            <span>{item.date}</span>
                        </p>
                    </div>
                ))}
            </div>
        </div>
    )
}

// 研报列表组件
function ReportsSection({ reports }: { reports: any[] }) {
    if (!reports || reports.length === 0) {
        return (
            <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-100 h-36 flex items-center justify-center">
                <p className="text-sm text-gray-400 font-medium">暂无研报数据</p>
            </div>
        )
    }

    return (
        <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-100">
            <h3 className="font-bold text-gray-900 mb-4 text-lg">📊 研究报告</h3>
            <div className="space-y-3">
                {reports.map((item, idx) => (
                    <div key={idx} className="border-l-4 border-purple-500 pl-4 hover:bg-purple-50 p-3 rounded-r transition-colors cursor-pointer">
                        <p className="text-sm font-semibold text-gray-900">{item.title}</p>
                    </div>
                ))}
            </div>
        </div>
    )
}

// 价格图表组件 (使用 Recharts)
function PriceChart({ originalData, fullData, predictionDone }: {
    originalData: TimeSeriesPoint[]
    fullData: TimeSeriesPoint[]
    predictionDone: boolean
}) {
    if (!originalData || originalData.length === 0) {
        return (
            <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100 h-96 flex items-center justify-center">
                <div className="text-center text-gray-400">
                    <Loader2 className="w-14 h-14 animate-spin mx-auto mb-4 text-blue-500" />
                    <p className="text-lg font-medium">正在加载数据...</p>
                </div>
            </div>
        )
    }

    const dataToShow = predictionDone ? fullData : originalData
    const predictionStartIndex = originalData.length

    // 转换数据格式
    const chartData = dataToShow.map((point, index) => ({
        date: point.date,
        value: point.value,
        isPrediction: point.is_prediction,
        displayDate: index % Math.ceil(dataToShow.length / 10) === 0 ? point.date : ''
    }))

    return (
        <div className="bg-gradient-to-br from-white to-gray-50 rounded-2xl shadow-xl p-8 border border-gray-100">
            <div className="flex justify-between items-center mb-6">
                <h3 className="text-2xl font-bold text-gray-900">📈 价格走势分析</h3>
                <div className="flex gap-6 text-sm font-medium">
                    <div className="flex items-center gap-2">
                        <div className="w-4 h-4 bg-blue-500 rounded"></div>
                        <span>历史数据</span>
                    </div>
                    {predictionDone && (
                        <div className="flex items-center gap-2">
                            <div className="w-4 h-4 bg-green-500 rounded"></div>
                            <span>预测数据</span>
                        </div>
                    )}
                </div>
            </div>

            <ResponsiveContainer width="100%" height={400}>
                <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis
                        dataKey="displayDate"
                        stroke="#888"
                        style={{ fontSize: '12px' }}
                    />
                    <YAxis
                        stroke="#888"
                        style={{ fontSize: '12px' }}
                        domain={['auto', 'auto']}
                    />
                    <Tooltip
                        contentStyle={{
                            backgroundColor: 'rgba(255, 255, 255, 0.95)',
                            border: '1px solid #e5e7eb',
                            borderRadius: '8px',
                            boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
                        }}
                        formatter={(value: any) => [`¥${value.toFixed(2)}`, '价格']}
                    />
                    <Legend />

                    {predictionDone && (
                        <ReferenceLine
                            x={chartData[predictionStartIndex]?.date}
                            stroke="#666"
                            strokeDasharray="5 5"
                            label={{ value: '预测起点', position: 'top', fill: '#666', fontSize: 12 }}
                        />
                    )}

                    <Line
                        type="monotone"
                        dataKey="value"
                        stroke="#3b82f6"
                        strokeWidth={3}
                        dot={false}
                        name="价格"
                        connectNulls
                    />

                    {predictionDone && (
                        <Line
                            type="monotone"
                            dataKey={(entry) => entry.isPrediction ? entry.value : null}
                            stroke="#22c55e"
                            strokeWidth={3}
                            strokeDasharray="5 5"
                            dot={false}
                            name="预测"
                            connectNulls
                        />
                    )}
                </LineChart>
            </ResponsiveContainer>

            <div className="mt-4 flex justify-between text-sm text-gray-600 bg-gray-50 rounded-lg p-4">
                <span>历史数据: <strong className="text-blue-600">{originalData.length}</strong> 个数据点</span>
                {predictionDone && (
                    <span>预测数据: <strong className="text-green-600">{fullData.length - originalData.length}</strong> 个预测点</span>
                )}
            </div>
        </div>
    )
}

// 结论组件 (使用 ReactMarkdown)
function ConclusionSection({ conclusion }: { conclusion: string }) {
    if (!conclusion) {
        return (
            <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100 min-h-96 flex items-center justify-center">
                <div className="text-center text-gray-400">
                    <Loader2 className="w-14 h-14 animate-spin mx-auto mb-4 text-blue-500" />
                    <p className="text-lg font-medium">正在生成分析报告...</p>
                </div>
            </div>
        )
    }

    return (
        <div className="bg-gradient-to-br from-white to-gray-50 rounded-2xl shadow-xl p-10 border border-gray-100">
            <h3 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                📝 综合分析报告
            </h3>
            <div className="prose prose-lg max-w-none 
                    text-black 
                    prose-headings:text-black 
                    prose-p:text-black 
                    prose-strong:text-black 
                    prose-ul:text-black 
                    prose-li:text-black 
                    prose-code:text-black 
                    prose-blockquote:text-black">
                <ReactMarkdown>{conclusion}</ReactMarkdown>
            </div>
        </div>
    )
}
