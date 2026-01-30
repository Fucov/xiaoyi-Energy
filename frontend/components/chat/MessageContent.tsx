'use client'

import React, { useState, useMemo, useRef, useCallback, useEffect, Fragment } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { LineChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine, ReferenceArea, Label, ReferenceDot } from 'recharts'
import { RotateCcw, Move } from 'lucide-react'
import type { TextContent, ChartContent, TableContent, StockContent } from './ChatArea'
import { useBacktestSimulation } from '@/hooks/useBacktestSimulation'
import { BacktestControls } from './BacktestControls'
import type { TimeSeriesPoint } from '@/lib/api/analysis'
import rehypeRaw from 'rehype-raw'
import { StockWidget } from '@/components/stock/StockWidget'
import { ChartNewsSidebar } from './ChartNewsSidebar'


interface MessageContentProps {
  content: TextContent | ChartContent | TableContent | StockContent
}

// 预处理 markdown 文本，确保带正负号的数字加粗能正确解析
function preprocessMarkdown(text: string): string {
  let processed = text

  // 全角归一化
  processed = processed.replace(/＋/g, '+').replace(/－/g, '-')

  // 处理带正负号的数字加粗，包括复杂格式如 **-0.09元(-0.82%)**
  // 匹配格式：**+/-数字(单位)(括号内容)**
  // 例如：**-0.09元(-0.82%)** 或 **+0.52元(+4.73%)** 或 **+3.70%**
  // 使用更通用的匹配：匹配 ** 之间以 + 或 - 开头的所有内容（直到下一个 **）
  processed = processed.replace(
    /\*\*\s*([+-][^*]+?)\s*\*\*/g,
    '<strong>$1</strong>'
  )

  // 处理 markdown 链接中 URL 含有特殊字符的情况
  // 匹配 [text](url) 格式，对 URL 中的特殊字符进行编码
  processed = processed.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    (match, linkText, url) => {
      // 如果 URL 已经是正常的 http/https 链接，保持不变
      if (/^https?:\/\/[^\s\u4e00-\u9fa5()]+$/.test(url)) {
        return match
      }
      // 对含有中文或特殊字符的 URL 进行编码处理
      try {
        // 分离协议和路径
        const protocolMatch = url.match(/^(https?:\/\/|rag:\/\/)(.*)$/)
        if (protocolMatch) {
          const [, protocol, path] = protocolMatch
          // 对路径部分进行编码，但保留常用字符
          const encodedPath = path
            .split('/')
            .map((segment: string) => {
              // 如果包含特殊字符，进行编码
              if (/[\u4e00-\u9fa5()（）#=]/.test(segment)) {
                return encodeURIComponent(segment)
              }
              return segment
            })
            .join('/')
          return `[${linkText}](${protocol}${encodedPath})`
        }
      } catch (e) {
        // 编码失败，返回原文
      }
      return match
    }
  )

  return processed
}




export function MessageContent({ content }: MessageContentProps) {
  if (content.type === 'text') {
    // 预处理文本，确保加粗格式正确
    const processedText = preprocessMarkdown(content.text)

    return (
      <div className="prose prose-invert max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw]}
          components={{
            strong: ({ children }) => (
              <strong className="font-semibold text-violet-300">
                {children}
              </strong>
            ),
            // 标题
            h1: ({ children }) => <h1 className="text-2xl font-bold text-gray-200 mb-3 mt-4 first:mt-0">{children}</h1>,
            h2: ({ children }) => <h2 className="text-xl font-bold text-gray-200 mb-2 mt-4 first:mt-0">{children}</h2>,
            h3: ({ children }) => <h3 className="text-lg font-semibold text-gray-200 mb-2 mt-3 first:mt-0">{children}</h3>,
            h4: ({ children }) => <h4 className="text-base font-semibold text-gray-200 mb-2 mt-3 first:mt-0">{children}</h4>,
            h5: ({ children }) => <h5 className="text-sm font-semibold text-gray-200 mb-1 mt-2 first:mt-0">{children}</h5>,
            h6: ({ children }) => <h6 className="text-sm font-medium text-gray-300 mb-1 mt-2 first:mt-0">{children}</h6>,
            // 段落
            p: ({ children }) => <p className="mb-2 last:mb-0 text-gray-300 leading-relaxed">{children}</p>,
            em: ({ children }) => <em className="italic text-gray-200">{children}</em>,
            // 列表
            ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1 text-gray-300">{children}</ul>,
            ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1 text-gray-300">{children}</ol>,
            li: ({ children }) => <li className="text-gray-300">{children}</li>,
            // 代码
            code: ({ className, children, ...props }: any) => {
              const isInline = !className
              return isInline ? (
                <code className="px-1.5 py-0.5 bg-dark-600 rounded text-sm text-violet-300 font-mono" {...props}>
                  {children}
                </code>
              ) : (
                <code className="block p-3 bg-dark-700 rounded-lg text-sm text-gray-300 font-mono overflow-x-auto mb-2" {...props}>
                  {children}
                </code>
              )
            },
            pre: ({ children }) => (
              <pre className="bg-dark-700 rounded-lg p-3 overflow-x-auto mb-2">{children}</pre>
            ),
            // 表格
            table: ({ children }) => (
              <div className="overflow-x-auto my-3 rounded-lg border border-white/10 bg-dark-800/30 shadow-sm">
                <table className="w-full border-collapse">
                  {children}
                </table>
              </div>
            ),
            thead: ({ children }) => (
              <thead className="bg-gradient-to-r from-dark-700/50 to-dark-800/50 border-b border-white/10">{children}</thead>
            ),
            tbody: ({ children }) => (
              <tbody>{children}</tbody>
            ),
            tr: ({ children }) => (
              <tr className="border-b border-white/5 hover:bg-gradient-to-r hover:from-dark-700/30 hover:to-dark-800/30 transition-all duration-150 group">{children}</tr>
            ),
            th: ({ children }) => (
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="px-4 py-3 text-sm text-gray-300 group-hover:text-gray-200 transition-colors">
                {children}
              </td>
            ),
            // 链接
            a: ({ href, children }) => {
              // 处理 rag:// 协议（研报链接）
              if (href?.startsWith('rag://')) {
                // 解析 rag://文件名.pdf#page=页码 格式，支持 URL 编码
                let decodedHref = href
                try {
                  decodedHref = decodeURIComponent(href)
                } catch (e) {
                  // 解码失败，使用原始值
                }
                const match = decodedHref.match(/^rag:\/\/(.+?)(?:#page=(\d+))?$/)
                const filename = match?.[1] || decodedHref.replace('rag://', '')
                const page = match?.[2] || '1'
                // 清理文件名，去除 .pdf 后缀
                const displayName = filename.replace(/\.pdf$/i, '')
                return (
                  <span
                    className="text-violet-400 hover:text-violet-300 cursor-pointer"
                    title={`研报: ${displayName} 第${page}页`}
                  >
                    {children}
                  </span>
                )
              }
              // 普通链接
              return (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-violet-400 hover:text-violet-300 underline"
                >
                  {children}
                </a>
              )
            },
            // 引用
            blockquote: ({ children }) => (
              <blockquote className="border-l-4 border-violet-500/50 pl-4 py-2 my-2 bg-dark-700/30 italic text-gray-300">
                {children}
              </blockquote>
            ),
            // 水平线
            hr: () => <hr className="my-4 border-white/10" />,
            // 换行
            br: () => <br />,
          }}
        >
          {processedText}
        </ReactMarkdown>
      </div>
    )
  }

  if (content.type === 'chart') {
    return <InteractiveChart content={content} />
  }

  if (content.type === 'table') {
    const { title, headers, rows } = content

    // 解析 markdown 链接格式 [text](url)
    // 使用更健壮的解析方式，处理标题中含有 [ 或 ] 的情况
    const parseMarkdownLink = (text: string): { text: string; url?: string } => {
      // 查找最后一个 ]( 来分割标题和URL
      const lastBracket = text.lastIndexOf('](')
      if (text.startsWith('[') && lastBracket > 0 && text.endsWith(')')) {
        const title = text.slice(1, lastBracket)
        const url = text.slice(lastBracket + 2, -1)
        if (url && url.startsWith('http')) {
          return { text: title, url }
        }
      }
      return { text }
    }

    // 渲染单元格内容（支持链接）
    const renderCell = (cell: string | number, cellIndex: number) => {
      if (typeof cell === 'number') {
        return cell.toLocaleString()
      }

      // 检查是否是 markdown 链接格式
      const parsed = parseMarkdownLink(cell)

      if (parsed.url) {
        // 有链接，渲染为可点击的链接
        const displayText = parsed.text.length > 25
          ? parsed.text.substring(0, 25) + '...'
          : parsed.text
        return (
          <a
            href={parsed.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-violet-400 hover:text-violet-300 hover:underline transition-colors"
            title={parsed.text} // 鼠标悬停显示完整标题
          >
            {displayText}
          </a>
        )
      }

      // 第一列是标题，如果超过25个字则截断
      if (cellIndex === 0 && cell.length > 25) {
        return (
          <span title={cell}>
            {cell.substring(0, 25)}...
          </span>
        )
      }

      return cell
    }

    return (
      <div className="mt-2 overflow-x-auto rounded-lg border border-white/10 bg-dark-800/30">
        {title && (
          <div className="px-4 pt-3 pb-2 border-b border-white/10">
            <h4 className="text-sm font-semibold text-gray-200">{title}</h4>
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-gradient-to-r from-dark-700/50 to-dark-800/50 border-b border-white/10">
                {headers.map((header, index) => (
                  <th
                    key={index}
                    className="px-4 py-3 text-left text-xs font-semibold text-gray-300 uppercase tracking-wider"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr
                  key={rowIndex}
                  className="border-b border-white/5 hover:bg-gradient-to-r hover:from-dark-700/30 hover:to-dark-800/30 transition-all duration-150 group"
                >
                  {row.map((cell, cellIndex) => (
                    <td
                      key={cellIndex}
                      className="px-4 py-3 text-sm text-gray-300 group-hover:text-gray-200 transition-colors"
                    >
                      {renderCell(cell, cellIndex)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  if (content.type === 'stock') {
    return <StockWidget ticker={content.ticker} title={content.title} />;
  }

  return null
}

// 交互式图表组件，支持鼠标拖拽平移、滚轮缩放、异常区高亮、新闻侧边栏
function InteractiveChart({ content }: { content: ChartContent }) {
  const { title, data, chartType = 'line', sessionId, messageId, originalData, anomalyZones = [], ticker, changePoints = [], semanticZones = [], predictionSemanticZones = [] } = content

  // Aliases for compatibility with existing code
  const semantic_zones = semanticZones
  const prediction_semantic_zones = predictionSemanticZones
  const anomalies = anomalyZones

  // 新闻侧边栏状态
  const [newsSidebarOpen, setNewsSidebarOpen] = useState(false)
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [newsData, setNewsData] = useState<any[]>([])
  const [newsLoading, setNewsLoading] = useState(false)

  // 异常区悬浮状态
  const [activeZone, setActiveZone] = useState<any>(null)

  // 变点悬浮状态
  const [activeChangePoint, setActiveChangePoint] = useState<any>(null)

  // Trend Algorithm State
  const [trendAlgo, setTrendAlgo] = useState('semantic')
  const useSemanticRegimes = trendAlgo === 'semantic'



  // 从URL恢复新闻侧栏状态（仅在ticker可用时）
  useEffect(() => {
    if (!ticker) return;

    const urlParams = new URLSearchParams(window.location.search);
    const savedDate = urlParams.get('selectedDate');
    const savedSidebarOpen = urlParams.get('sidebarOpen') === 'true';

    if (savedDate) {
      setSelectedDate(savedDate);
      setNewsSidebarOpen(savedSidebarOpen);
      // console.log('[MessageContent] Restored from URL - date:', savedDate, 'sidebar:', savedSidebarOpen);
    }
  }, [ticker]); // 只在ticker变化时执行

  // 获取新闻数据 - 只要有ticker就自动加载（确保刷新后能恢复）
  useEffect(() => {
    const fetchNews = async () => {
      if (!selectedDate || !ticker) return;
      setNewsLoading(true);
      try {
        const response = await fetch(`/api/news?ticker=${ticker}&date=${selectedDate}&range=2`);
        if (!response.ok) throw new Error('Failed to fetch news');
        const data = await response.json();
        setNewsData(data.news || []);
      } catch (error) {
        console.error('Failed to load news:', error);
        setNewsData([]);
      } finally {
        setNewsLoading(false);
      }
    };
    fetchNews();
  }, [selectedDate, ticker]);  // 移除newsSidebarOpen依赖，确保刷新后自动加载

  // 图表点击处理
  const handleChartClick = useCallback((e: any) => {
    if (e && e.activeLabel && ticker) {
      const date = e.activeLabel as string;
      setSelectedDate(date);
      setNewsSidebarOpen(true);

      // 持久化到URL
      const params = new URLSearchParams(window.location.search);
      params.set('selectedDate', date);
      params.set('sidebarOpen', 'true');
      window.history.replaceState({}, '', `${window.location.pathname}?${params}`);
    }
  }, [ticker]);

  // 新闻侧栏关闭处理
  const handleCloseSidebar = useCallback(() => {
    setNewsSidebarOpen(false);

    // 更新URL参数
    const params = new URLSearchParams(window.location.search);
    params.set('sidebarOpen', 'false');
    window.history.replaceState({}, '', `${window.location.pathname}?${params}`);
  }, []);

  // 回测功能hook
  const backtest = useBacktestSimulation({
    sessionId: sessionId || '',
    messageId: messageId || '',
    originalData: originalData || []
  })

  const hasBacktestSupport = Boolean(sessionId && messageId && originalData && originalData.length >= 60)

  // 周末过滤函数
  const isWeekday = (dateStr: string): boolean => {
    try {
      const date = new Date(dateStr)
      const day = date.getDay() // 0=Sunday, 6=Saturday
      return day !== 0 && day !== 6 // 过滤掉周日和周六
    } catch {
      return true // 解析失败则保留
    }
  }
  // 转换数据格式为 Recharts 格式
  const chartData = useMemo(() => {
    // 如果在回测模式，使用回测数据
    if (backtest.chartData) {
      const { history, groundTruth, prediction } = backtest.chartData

      // 合并所有数据点
      const allDates = new Set<string>()
      history.forEach(p => allDates.add(p.date))
      groundTruth.forEach(p => allDates.add(p.date))
      prediction.forEach(p => allDates.add(p.date))

      const sortedDates = Array.from(allDates).sort()

      return sortedDates
        // .filter(date => isWeekday(date)) // User Request: Show ALL days for power data
        .map(date => {
          const histPoint = history.find(p => p.date === date)
          const truthPoint = groundTruth.find(p => p.date === date)
          const predPoint = prediction.find(p => p.date === date)

          return {
            name: date,
            历史供电量: histPoint?.value ?? null,
            实际值: truthPoint?.value ?? null,
            回测预测: predPoint?.value ?? null
          }
        })
    }

    // 正常模式
    return data.labels.map((label, index) => {
      const item: Record<string, string | number | null> = { name: label }
      data.datasets.forEach((dataset) => {
        item[dataset.label] = dataset.data[index]
      })
      return item
    })//.filter(item => isWeekday(item.name as string)) // User Request: Show ALL days
  }, [data, backtest.chartData])

  // 计算Y轴范围（自适应）- 基于所有数据，保持一致性
  const yAxisDomain = useMemo(() => {
    // 收集所有非null的数值
    const allValues: number[] = []
    chartData.forEach((item) => {
      data.datasets.forEach((dataset) => {
        const value = item[dataset.label]
        if (value !== null && value !== undefined && typeof value === 'number' && !isNaN(value)) {
          allValues.push(value)
        }
      })
    })

    if (allValues.length === 0) {
      return [0, 100] // 默认范围
    }

    const minValue = Math.min(...allValues)
    const maxValue = Math.max(...allValues)

    // 如果所有值相同，添加一些范围
    if (minValue === maxValue) {
      const padding = Math.abs(minValue) * 0.1 || 10
      return [minValue - padding, maxValue + padding]
    }

    // 计算范围，留出10%的边距
    const range = maxValue - minValue
    const padding = range * 0.1

    // 确保最小值不为负数（如果所有值都为正）
    const adjustedMin = minValue >= 0
      ? Math.max(0, minValue - padding)
      : minValue - padding

    const adjustedMax = maxValue + padding

    // 确保返回的是数字数组，保留合理精度
    return [Math.round(adjustedMin * 100) / 100, Math.round(adjustedMax * 100) / 100]
  }, [chartData, data.datasets])

  const colors = ['#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']

  // 状态管理：视图范围（显示的数据索引范围）
  const [viewStartIndex, setViewStartIndex] = useState(0)
  const [viewEndIndex, setViewEndIndex] = useState(() => chartData.length - 1)

  // 拖拽状态
  const [isDragging, setIsDragging] = useState(false)
  const [dragStartX, setDragStartX] = useState(0)
  const [dragStartIndex, setDragStartIndex] = useState(0)

  // 图表容器引用
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const [mouseY, setMouseY] = useState<number | null>(null) // 鼠标相对于绘图区域的Y坐标（像素）
  const [plotAreaBounds, setPlotAreaBounds] = useState<{ top: number; height: number } | null>(null) // 绘图区域边界

  // Use refs to avoid closure staleness issues in event listeners (Fixes Freeze)
  const viewStateRef = useRef({ startIndex: viewStartIndex, endIndex: viewEndIndex, chartLen: chartData.length });
  // Drag state ref to avoid re-binding mousemove listeners
  const dragStateRef = useRef({ isDragging: false, dragStartX: 0, dragStartIndex: 0 });

  useEffect(() => {
    viewStateRef.current = { startIndex: viewStartIndex, endIndex: viewEndIndex, chartLen: chartData.length };
  }, [viewStartIndex, viewEndIndex, chartData.length]);

  // 滑块拖拽状态
  const [isDraggingSlider, setIsDraggingSlider] = useState(false)
  const [tempSplitDate, setTempSplitDate] = useState<string | null>(null) // 拖拽时的临时分割日期

  // 计算当前显示的数据
  const displayData = useMemo(() => {
    return chartData.slice(viewStartIndex, viewEndIndex + 1)
  }, [chartData, viewStartIndex, viewEndIndex])

  // DIAGNOSTIC: Check if zone dates exist in chartData AND their positions
  useEffect(() => {
    if (anomalyZones && anomalyZones.length > 0 && chartData.length > 0) {
      const chartDates = new Set(chartData.map(d => d.name))
      console.log('[DIAGNOSTIC] chartData range:', chartData[0]?.name, 'to', chartData[chartData.length - 1]?.name, `(${chartData.length} points)`)
      console.log('[DIAGNOSTIC] viewStartIndex:', viewStartIndex, 'viewEndIndex:', viewEndIndex, 'visible:', viewEndIndex - viewStartIndex + 1, 'points')

      anomalyZones.forEach((zone, idx) => {
        const startIndex = chartData.findIndex(d => d.name === zone.startDate)
        const endIndex = chartData.findIndex(d => d.name === zone.endDate)
        const isInViewport = startIndex >= viewStartIndex && endIndex <= viewEndIndex
        const hasStart = chartDates.has(zone.startDate)
        const hasEnd = chartDates.has(zone.endDate)

        console.log(`[DIAGNOSTIC] Zone ${idx} (${zone.startDate}-${zone.endDate}): start=${hasStart}(idx=${startIndex}), end=${hasEnd}(idx=${endIndex}), inViewport=${isInViewport}`)
      })
    }
  }, [anomalyZones, chartData, viewStartIndex, viewEndIndex])

  // Debug: Log anomaly data when received
  useEffect(() => {
    if (anomalies && anomalies.length > 0) {
      // console.log(`[Anomaly Rendering] Received ${anomalies.length} anomalies:`, anomalies);
      // console.log('[Anomaly Rendering] Chart Y-axis domain:', yAxisDomain);
      // console.log('[Anomaly Rendering] Chart date range:', chartData[0]?.name, 'to', chartData[chartData.length - 1]?.name);

      // Check which anomalies are in valid date range
      const chartDates = new Set(chartData.map((d: any) => d.name));
      anomalies.forEach((anom: any, idx: number) => {
        const inDateRange = chartDates.has(anom.date);
        const inYRange = anom.price >= yAxisDomain[0] && anom.price <= yAxisDomain[1];
        // console.log(`[Anomaly ${idx}] ${anom.method} at ${anom.date}: price=${anom.price}, inDateRange=${inDateRange}, inYRange=${inYRange}`);
      });
    }
  }, [anomalies, chartData, yAxisDomain]);

  // --- Semantic Regimes Logic ---
  const semanticRegimes = useMemo(() => {
    // --- Helper Functions (Hoisted for reuse) ---

    const aggregateRawZones = (semanticZone: any, isPrediction: boolean) => {
      if (!anomalyZones || anomalyZones.length === 0) return semanticZone;

      // Find all raw zones that overlap with this semantic zone
      const overlappingRawZones = anomalyZones.filter((rawZone: any) => {
        const zoneMethod = rawZone.method || 'plr';
        // Basic match: Time overlap
        let matches = false;
        if (isPrediction) {
          matches = (zoneMethod === 'plr_prediction' || rawZone.is_prediction);
        } else {
          matches = (zoneMethod === 'plr' || !rawZone.is_prediction) && rawZone.startDate >= semanticZone.startDate && rawZone.endDate <= semanticZone.endDate;
        }

        // FIX: Direction Consistency Check
        if (matches) {
          const semanticSign = (semanticZone.avg_return || 0) >= 0;
          const rawSign = (rawZone.avg_return || 0) >= 0;
          // If Semantic is significant (>1%), prefer consistent events.
          // This removes contradictory "noise" events (like heavy rain during a heatwave trend)
          if (Math.abs(semanticZone.avg_return || 0) > 0.01) {
            return semanticSign === rawSign;
          }
        }
        return matches;
      });

      // Convert raw zones to event format for tooltip display
      const events = overlappingRawZones.map((rawZone: any) => ({
        startDate: rawZone.startDate,
        endDate: rawZone.endDate,
        // FIX: Prioritize event_summary (rich text) over summary (generic text)
        summary: rawZone.event_summary || rawZone.summary || 'Raw Zone Event',
        event_summary: rawZone.event_summary || rawZone.summary,
        avg_return: rawZone.avg_return, // Will recalculate in tooltip
        startPrice: rawZone.startPrice,
        endPrice: rawZone.endPrice,
        type: rawZone.type || rawZone.displayType || 'raw',
        sentiment: rawZone.sentiment
      }));

      return {
        ...semanticZone,
        events: events.length > 0 ? events : (semanticZone.events || [])
      };
    };

    // Helper: Merge events uniquely by Date + Summary (Robust Dedup)
    const mergeUniqueEvents = (eventsA: any[], eventsB: any[]) => {
      const merged = [...(eventsA || [])];
      // Create a set of signatures: Date + Summary (First 20 chars)
      // FIX: Remove avg_return from key to prevent duplicates with floating point differences
      const seen = new Set(merged.map(e => {
        const summary = (e.event_summary || e.summary || '').trim();
        return `${e.startDate}-${summary.substring(0, 20)}`;
      }));

      (eventsB || []).forEach(e => {
        const summary = (e.event_summary || e.summary || '').trim();
        const key = `${e.startDate}-${summary.substring(0, 20)}`;
        if (!seen.has(key)) {
          seen.add(key);
          merged.push(e);
        }
      });
      return merged;
    };

    // Merge logic: Merge adjacent zones with same sentiment
    const mergeSemanticZones = (zones: any[]) => {
      if (!zones || zones.length === 0) return [];
      const sorted = [...zones].sort((a, b) => new Date(a.startDate).getTime() - new Date(b.startDate).getTime());
      const merged: any[] = [];
      let current = sorted[0];

      for (let i = 1; i < sorted.length; i++) {
        const next = sorted[i];
        // FIX: Strict Sign Check and Continuity Check
        // 1. Check Direction Strictness: Positive must match Positive, Negative matches Negative
        const returnA = current.avg_return || 0;
        const returnB = next.avg_return || 0;
        const sameDirection = (returnA > 0 && returnB > 0) || (returnA < 0 && returnB < 0) || (returnA === 0 && returnB === 0);

        // 2. Continuity Check: Gap <= 5 days
        const currentEnd = new Date(current.endDate).getTime();
        const nextStart = new Date(next.startDate).getTime();
        const diffDays = (nextStart - currentEnd) / (1000 * 60 * 60 * 24);
        const isContiguous = diffDays <= 5;

        if (sameDirection && isContiguous) {
          // Validate continuity: if gap is small enough? For now assume strict or close enough
          // Extend current
          // FIX: Strict Growth Rate Calculation: (End - Start) / Start
          // preserve startPrice from 'current' (first block) and take endPrice from 'next' (last block)
          // Note: we assume curr.startPrice is valid. If not, fallback to curr.avg_return accumulation (but we try strict first)
          const newEnd = next.endDate;
          const mergedEndPrice = next.endPrice || next.close; // Ensure backend sends endPrice
          const mergedStartPrice = current.startPrice;

          let newAvgReturn = 0;
          if (mergedStartPrice && mergedEndPrice) {
            newAvgReturn = (mergedEndPrice - mergedStartPrice) / mergedStartPrice;
          } else {
            // Fallback to weighted average if prices missing (should not happen with new backend)
            const currentDur = (new Date(current.endDate).getTime() - new Date(current.startDate).getTime());
            const nextDur = (new Date(next.endDate).getTime() - new Date(next.startDate).getTime());
            const totalDur = currentDur + nextDur;
            newAvgReturn = ((current.avg_return * currentDur) + (next.avg_return * nextDur)) / (totalDur || 1);
          }

          current = {
            ...current,
            endDate: newEnd,
            avg_return: newAvgReturn,
            endPrice: mergedEndPrice, // Update end price
            // events: merge unique
            events: mergeUniqueEvents(current.events, next.events),
            sentiment: newAvgReturn >= 0 ? 'positive' : 'negative'
          };
        } else {
          merged.push(current);
          current = next;
        }
      }
      merged.push(current);
      return merged;
    };

    // Smoothing Logic: Absorb small "noise" zones into surrounding trends (Sandwich Logic)
    // e.g. UP (Long) -> DOWN (Short) -> UP (Long)  => Merge all to UP
    const smoothSemanticZones = (zones: any[]) => {
      if (!zones || zones.length < 3) return zones;

      let smoothed = [...zones];
      let changed = true;

      // Multi-pass to handle cascading merges
      while (changed) {
        changed = false;
        const result = [];
        let i = 0;

        while (i < smoothed.length) {
          const prev: any = result.length > 0 ? result[result.length - 1] : null;
          const curr = smoothed[i];
          const next = i + 1 < smoothed.length ? smoothed[i + 1] : null;

          let merged = false;

          // Check Sandwich: Prev and Next matched direction, Curr is opposite but "Small"
          if (prev && next) {
            const prevDir = (prev.avg_return || 0) > 0 ? 1 : -1;
            const nextDir = (next.avg_return || 0) > 0 ? 1 : -1;
            const currDir = (curr.avg_return || 0) > 0 ? 1 : -1;

            if (prevDir === nextDir && currDir !== prevDir) {
              // Check if Curr is "Small/Noise"
              // New Logic: Hybrid Thresholds
              // 1. Noise: < 2.5% (Always merge)
              // 2. Weak Short Trend: < 5.0% AND < 10 days (Merge)
              // 3. Real Trend: >= 5.0% OR (>= 2.5% AND >= 10 days) (Keep)
              const absReturn = Math.abs(curr.avg_return || 0);
              const d1 = new Date(curr.startDate).getTime();
              const d2 = new Date(curr.endDate).getTime();
              const days = (d2 - d1) / (1000 * 3600 * 24);

              const isNoise = absReturn < 0.025; // 2.5% Noise
              const isWeakShort = absReturn < 0.05 && days < 10; // 5% & < 10 days

              const isWeak = isNoise || isWeakShort;

              if (isWeak) {
                // MERGE ALL THREE into Prev
                // FIX: Strict Growth Rate Calculation
                const newStartP = prev.startPrice;
                const newEndP = next.endPrice;
                let weightedReturn = 0;

                if (newStartP && newEndP) {
                  weightedReturn = (newEndP - newStartP) / newStartP;
                } else {
                  const prevDur = (new Date(prev.endDate).getTime() - new Date(prev.startDate).getTime());
                  const currDur = (new Date(curr.endDate).getTime() - new Date(curr.startDate).getTime());
                  const nextDur = (new Date(next.endDate).getTime() - new Date(next.startDate).getTime());
                  const totalDur = prevDur + currDur + nextDur;
                  weightedReturn = ((prev.avg_return * prevDur) + (curr.avg_return * currDur) + (next.avg_return * nextDur)) / totalDur;
                }

                result[result.length - 1] = {
                  ...prev,
                  endDate: next.endDate,
                  endPrice: newEndP, // CRITICAL FIX: Update endPrice to ensure correct return calculation
                  events: mergeUniqueEvents(prev.events, mergeUniqueEvents(curr.events, next.events)),
                  avg_return: weightedReturn,
                  // CRITICAL FIX: Update sentiment to match the new return!
                  sentiment: weightedReturn >= 0 ? 'positive' : 'negative'
                };
                i += 2; // Skip curr and next
                merged = true;
                changed = true;
              }
            }
          }

          if (!merged) {
            result.push(curr);
            i++;
          }
        }
        smoothed = result;
      }
      return smoothed;
    };

    // 1. If Backend already provided Semantic Zones, use them directly!
    // This supports "Event Flow" feature and robust backend merging
    // FIX: Also enter this block if we have anomalyZones and useSemanticRegimes is true,
    // so we can utilize the "Convert raw to semantic" logic inside.
    if (semantic_zones.length > 0 || (prediction_semantic_zones && prediction_semantic_zones.length > 0) || (useSemanticRegimes && anomalyZones && anomalyZones.length > 0)) {
      // 1. Raw zones
      let historicalZones = semantic_zones.map((z: any) => ({ ...z, isPrediction: false }));

      // CRITICAL FIX: If backend did NOT provide historical semantic_zones (empty), 
      // but provided prediction zones, we must NOT leave historicalZones empty.
      // We must generate them from raw 'plr' zones (without merging, or with separate merging).
      // User said "History regions ... impossible to merge", so we preserve raw distinctness for history if backend is empty.
      if (historicalZones.length === 0 && anomalyZones && anomalyZones.length > 0) {
        const rawHistory = anomalyZones.filter((z: any) => (z.method || 'plr') === 'plr' && !z.is_prediction && z.method !== 'plr_prediction');
        // Convert raw to semantic format (1:1 mapping, no merging to avoid "impossible merge")
        historicalZones = rawHistory.map((z: any) => ({
          ...z,
          isPrediction: false,
          events: [{
            startDate: z.startDate,
            endDate: z.endDate,
            summary: z.event_summary || z.summary || 'Raw Zone Event',
            event_summary: z.event_summary || z.summary,
            avg_return: z.avg_return,
            startPrice: z.startPrice,
            endPrice: z.endPrice,
            type: z.type || z.displayType || 'raw',
            sentiment: z.sentiment
          }]
        }));
      }

      // FIX: Derive predictionZones from anomalyZones (backend unifies them) instead of relying on separate prop
      // Use existing 'rawPrediction' if available or filter here
      let predictionZones = (anomalyZones || [])
        .filter((z: any) => z.method === 'plr_prediction' || z.is_prediction);

      predictionZones = predictionZones.map((z: any) => ({ ...z, isPrediction: true }));

      // Apply aggregation to both historical and prediction zones
      // Apply aggregation to both historical and prediction zones
      // Apply aggregation to both historical and prediction zones
      if (historicalZones && historicalZones.length > 0) {
        historicalZones = historicalZones.map(z => aggregateRawZones(z, false));
        // FIX: If generated from raw (backend semantic_zones empty), we MUST Merge and Smooth to create solid blocks
        if (semantic_zones.length === 0) {
          historicalZones = mergeSemanticZones(historicalZones);
          historicalZones = smoothSemanticZones(historicalZones);
        }
      }

      if (predictionZones && predictionZones.length > 0) {
        // predictionZones: First aggregate events, THEN merge adjacent zones to form larger blocks
        predictionZones = predictionZones.map(z => aggregateRawZones(z, true));
        predictionZones = mergeSemanticZones(predictionZones);
        predictionZones = smoothSemanticZones(predictionZones);
      }

      // Merge history and prediction zones
      return [
        ...(historicalZones || []),
        ...(predictionZones || [])
      ];
    }

    // 2. Fallback: Frontend Calculation (for legacy cache or other algos)
    if (!anomalyZones || anomalyZones.length === 0) return [];
    if (chartData.length === 0) return [];

    // Filter and Sort zones
    const sortedZones = [...anomalyZones]
      .filter(z => {
        if (trendAlgo === 'all') return true;
        if (trendAlgo === 'plr' && z.method === 'plr_prediction') return true;
        // FIX: If mode is 'semantic' and we are in fallback, we operate on ALL 'plr' zones (history + prediction)
        if (trendAlgo === 'semantic') {
          return (z.method || 'plr') === 'plr' || z.method === 'plr_prediction';
        }
        return (z.method || 'plr') === trendAlgo;
      })
      .sort((a, b) => new Date(a.startDate).getTime() - new Date(b.startDate).getTime());

    // FIX: If in Semantic Mode Fallback, we MUST convert raw zones to Event format and MERGE them!
    // AND we must STRICTLY separate History and Prediction to avoid merging them together!
    if (trendAlgo === 'semantic') {
      // 1. Separate History and Prediction from available raw zones
      const rawHistory = sortedZones.filter(z => (z.method || 'plr') === 'plr' && !z.is_prediction && z.method !== 'plr_prediction');
      const rawPrediction = sortedZones.filter(z => z.method === 'plr_prediction' || z.is_prediction);

      // 2. Convert and Merge History
      let semanticHistory = mergeSemanticZones(rawHistory.map(z => ({
        ...z,
        isPrediction: false,
        events: [{
          startDate: z.startDate,
          endDate: z.endDate,
          summary: z.event_summary || z.summary || 'Raw Zone Event',
          event_summary: z.event_summary || z.summary,
          avg_return: z.avg_return,
          startPrice: z.startPrice,
          endPrice: z.endPrice,
          type: z.type || z.displayType || 'raw',
          sentiment: z.sentiment
        }]
      })));

      // Apply Smoothing to History as well to ensure visual and value consistency
      semanticHistory = smoothSemanticZones(semanticHistory);

      // 3. Convert and Merge Prediction
      // Apply: Strict Merge -> Smooth Noise -> Strict Merge (Cleanup)
      let semanticPrediction = mergeSemanticZones(rawPrediction.map(z => ({
        ...z,
        isPrediction: true,
        events: [{
          startDate: z.startDate,
          endDate: z.endDate,
          summary: z.event_summary || z.summary || 'Raw Zone Event',
          event_summary: z.event_summary || z.summary,
          avg_return: z.avg_return,
          startPrice: z.startPrice,
          endPrice: z.endPrice,
          type: z.type || z.displayType || 'raw',
          sentiment: z.sentiment
        }]
      })));

      // Apply Smoothing to Prediction to fix fragmentation
      semanticPrediction = smoothSemanticZones(semanticPrediction);

      return [...semanticHistory, ...semanticPrediction];
    }

    return sortedZones;

    if (sortedZones.length === 0) return [];

    // Helper to get price from chartData
    const getPrice = (date: string): number | null => {
      const point = chartData.find((d: any) => d.name === date);
      if (!point) return null;
      // Assume first dataset is the main price
      const label = data.datasets[0]?.label;
      return ((point as any)[label] as number) || null;
    };

    // 2. Merge Logic
    const merged: any[] = [];
    if (sortedZones.length === 0) return [];

    // let current removed to avoid redeclaration

    // Normalize type for comparison (up/down/sideways)
    const normalizeType = (type: string) => {
      const t = type?.toLowerCase() || '';
      if (t.includes('bull') || t.includes('up')) return 'up';
      if (t.includes('bear') || t.includes('down')) return 'down';
      return 'sideways';
    };

    // [New] Smooth out noise (Sandwich Logic): A(Up) -> B(Down) -> C(Up) => Merge B into Up
    // Fix: PLR returns 'direction', HMM returns 'type'. Map both to 'type'.
    const smoothedZones = (sortedZones as any[]).map(z => ({
      ...z,
      type: z.type || (z as any).direction || 'sideways'
    }));

    // 1-pass smoothing with Duration Check to avoid swallowing real corrections
    for (let pass = 0; pass < 1; pass++) {
      for (let i = 1; i < smoothedZones.length - 1; i++) {
        const prev: any = smoothedZones[i - 1];
        const curr: any = smoothedZones[i];
        const next: any = smoothedZones[i + 1];

        const prevType = normalizeType(prev.type);
        const currType = normalizeType(curr.type);
        const nextType = normalizeType(next.type);

        // If sandwiched between same types, flip current type IF it is short (noise)
        if (prevType === nextType && currType !== prevType) {
          const d1 = new Date(curr.startDate).getTime();
          const d2 = new Date(curr.endDate).getTime();
          const days = (d2 - d1) / (1000 * 3600 * 24);

          // Only treat as noise if < 7 days (1 week)
          if (days < 7) {
            curr.type = prev.type;
          }
        }
      }
    }

    if (smoothedZones.length === 0) return [];

    let current: any = { ...smoothedZones[0] };
    current.normalizedType = normalizeType(current.type);

    for (let i = 1; i < smoothedZones.length; i++) {
      const next: any = smoothedZones[i];
      const nextType = normalizeType(next.type);

      // Merge if same type and contiguous (or overlap/close)
      // Simple check: same type
      if (current.normalizedType === nextType) {
        // Extend current
        current.endDate = next.endDate;
        // Accumulate other props if needed
      } else {
        merged.push(current);
        current = { ...next, normalizedType: nextType };
      }
    }
    merged.push(current);

    // 3. Volatility / Efficiency Ratio Check & Final Enrichment
    return merged.map(regime => {
      const startPrice = getPrice(regime.startDate);
      const endPrice = getPrice(regime.endDate);

      let type = regime.normalizedType;
      let efficiencyRatio = 1.0;

      // Calculate Efficiency Ratio over the regime range
      if (startPrice !== null && endPrice !== null) {
        const startIndex = chartData.findIndex((d: any) => d.name === regime.startDate);
        const endIndex = chartData.findIndex((d: any) => d.name === regime.endDate);

        if (startIndex !== -1 && endIndex !== -1 && endIndex > startIndex) {
          const slice = chartData.slice(startIndex, endIndex + 1);
          const firstLabel = data.datasets[0]?.label;
          const prices = slice.map((d: any) => (d as any)[firstLabel] as number).filter((p: any) => p !== null);

          if (prices.length > 1) {
            const netChange = Math.abs(prices[prices.length - 1] - prices[0]);
            let sumAbsChange = 0;
            for (let k = 1; k < prices.length; k++) {
              sumAbsChange += Math.abs(prices[k] - prices[k - 1]);
            }
            efficiencyRatio = sumAbsChange === 0 ? 0 : netChange / sumAbsChange;

            // Identify anomalies/events within this regime
            const regimeEvents = (anomalies || []).filter((a: any) => {
              return a.date >= regime.startDate && a.date <= regime.endDate;
            });

            // Calculate total change
            const totalChange = (startPrice && endPrice)
              ? ((endPrice - startPrice) / startPrice * 100).toFixed(2) + '%'
              : 'N/A';

            // FIX: Preserve existing events (Deepseek analysis) and merge with anomalies
            const existingEvents = regime.events || [];
            const mergedEvents = [...existingEvents];

            // Avoid duplicates if anomalies are already in existingEvents? 
            // Usually existingEvents are Area events (Analysis), regimeEvents are Points.
            // Just append is fine.
            regimeEvents.forEach((ev: any) => {
              // simple check to avoid exact dup by object ref or content
              const isDup = existingEvents.some((e: any) => e.date === ev.date && e.price === ev.price);
              if (!isDup) mergedEvents.push(ev);
            });

            return {
              ...regime,
              displayType: type,
              efficiencyRatio,
              totalChange,
              events: mergedEvents,
              startPrice,
              endPrice
            };
          }
        }
      }
      // If ER < 0.3, force sideways
      // DISABLED: PLR is volatile, this makes everything grey. Let original type stand.
      // if (efficiencyRatio < 0.3) {
      //   type = 'sideways';
      // }
      // Identify anomalies/events within this regime
      const regimeEvents = (anomalies || []).filter((a: any) => {
        return a.date >= regime.startDate && a.date <= regime.endDate;
      });

      // Calculate total change
      const totalChange = (startPrice && endPrice)
        ? ((endPrice - startPrice) / startPrice * 100).toFixed(2) + '%'
        : 'N/A';

      // FIX: Preserve existing events (Deepseek analysis) and merge with anomalies
      const existingEvents = regime.events || [];
      const mergedEvents = [...existingEvents];
      regimeEvents.forEach((ev: any) => {
        const isDup = existingEvents.some((e: any) => e.date === ev.date && e.price === ev.price);
        if (!isDup) mergedEvents.push(ev);
      });

      return {
        ...regime,
        displayType: type,
        efficiencyRatio,
        totalChange,
        events: mergedEvents,
        startPrice,
        endPrice
      };
    });
  }, [anomalyZones, chartData, trendAlgo, anomalies, data.datasets, semantic_zones, prediction_semantic_zones]);

  // --- End Semantic Regimes ---

  // Filter Logic
  // @ts-ignore
  const visibleZones = (anomalyZones || []).filter((z: any) => {
    if (trendAlgo === 'all') return true;
    // Allow 'plr_prediction' when 'plr' is selected
    if (trendAlgo === 'plr' && z.method === 'plr_prediction') return true;
    return (z.method || 'plr') === trendAlgo;
  });

  // === Optimized Zone Lookup ===
  // Create a map of date -> zone for O(1) lookup to prevent lag
  // === Optimized Zone Lookup ===
  // Create a map of date -> zone for O(1) lookup
  const zoneMap = useMemo(() => {
    const map = new Map();
    const zones = useSemanticRegimes ? semanticRegimes : visibleZones;
    if (!zones || !chartData) return map;

    // Iterate chartData to ensure keys match exactly what Recharts uses for tooltips
    chartData.forEach((d: any) => {
      const dateStr = d.name; // This is the label Recharts passes to CustomTooltip

      // Find zone covering this date
      // Note: zones are sorted, we can optimize, but simple find is fine for N=800
      const coveringZone = zones.find((z: any) => {
        return dateStr >= z.startDate && dateStr <= z.endDate;
      });

      if (coveringZone) {
        map.set(dateStr, coveringZone);
      }
    });

    return map;
  }, [useSemanticRegimes, semanticRegimes, visibleZones, chartData]);


  // === Custom Tooltip for Event Flow ===
  const CustomTooltip = ({ active, payload, label }: any) => {
    // If not active or no payload, don't render anything
    if (!active || !payload || !payload.length) return null;

    // Use memoized map for O(1) lookup
    const date = label;
    let currentZone = zoneMap.get(date);

    // Fallback: if map failed (e.g. date string format mismatch), try find() but ONLY if map is empty?
    // No, keep it fast. If map missing, maybe no zone.

    if (!currentZone) {
      const activeZoneId = activeZone?.startDate + activeZone?.endDate; // From hover state
      if (activeZone && activeZoneId) {
        // Check if activeZone actually covers this date?
        // Or just trust the hover.
        // Let's trust hover if date lookup failed.
        currentZone = activeZone;
      }
    }


    if (!currentZone) {
      // Fallback to simple point tooltip
      const point = payload[0].payload;
      return (
        <div className="bg-gray-900/95 border border-white/10 rounded-lg p-3 shadow-xl backdrop-blur-md min-w-[200px]">
          <div className="text-gray-400 text-xs mb-1">{date}</div>
          <div className="flex justify-between items-center">
            <span className="text-gray-200">价格</span>
            <span className="font-mono text-white font-bold">{Number(point.y || point.close).toFixed(2)}</span>
          </div>
        </div>
      );
    }

    // Zone Tooltip
    // Fix: Revert colors to A-share style (Red=Up, Green=Down)
    // FIX: Calculate growth rate from Semantic Start/End Price if available
    let displayReturn = currentZone.avg_return || 0;
    if (currentZone.startPrice && currentZone.endPrice) {
      displayReturn = (currentZone.endPrice - currentZone.startPrice) / currentZone.startPrice;
    }

    const isPositive = displayReturn >= 0;
    const color = isPositive ? '#ef4444' : '#10b981';
    const bgColor = isPositive ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)';
    const borderColor = isPositive ? 'rgba(239, 68, 68, 0.3)' : 'rgba(16, 185, 129, 0.3)';

    // Filter and Deduplicate Events
    const rawEvents = currentZone.events || [];
    const validEvents = rawEvents.filter((evt: any) => {
      // Strict containment check
      return evt.startDate >= currentZone.startDate && evt.endDate <= currentZone.endDate;
    });

    // Deduplicate by summary and date
    const uniqueEvents: any[] = [];
    const seenEvents = new Set();
    validEvents.forEach((evt: any) => {
      // FIX: Strict deduplication by Date + Summary
      // We normalize summary to catch duplicates with minor spacing differences
      const summary = (evt.event_summary || evt.summary || '').trim();
      const key = `${evt.startDate}-${summary}`;
      if (!seenEvents.has(key)) {
        seenEvents.add(key);
        uniqueEvents.push(evt);
      }
    });

    // Sort by date
    uniqueEvents.sort((a, b) => new Date(a.startDate).getTime() - new Date(b.startDate).getTime());

    return (
      <div className="bg-gray-900/95 border border-white/10 rounded-lg shadow-xl backdrop-blur-md max-w-sm overflow-hidden text-sm">
        {/* Header */}
        <div
          className="flex justify-between items-center px-3 py-2 border-b"
          style={{
            backgroundColor: bgColor,
            borderColor: borderColor
          }}
        >
          <div className="flex items-center gap-2">
            <span className={`font-bold font-mono ${isPositive ? 'text-red-400' : 'text-green-400'}`}>
              {(displayReturn * 100).toFixed(1)}%
            </span>
            <span className="text-xs text-white/50">
              {currentZone.startDate} ~ {currentZone.endDate}
            </span>
          </div>
        </div>

        {/* Current Data points (Y-axis values) */}
        <div className="px-3 py-2 bg-black/20 border-b border-white/5 space-y-1">
          {payload.map((entry: any, index: number) => (
            <div key={index} className="flex justify-between items-center text-xs">
              <span style={{ color: entry.color }} className="font-medium">
                {entry.name}
              </span>
              <span className="font-mono text-gray-200">
                {typeof entry.value === 'number' ? entry.value.toFixed(2) : entry.value}
                <span className="ml-1 text-gray-500 scale-90 inline-block">MW</span>
              </span>
            </div>
          ))}
        </div>

        {/* Event List */}
        <div className="p-3">
          <div className="text-xs font-bold text-gray-500 mb-2 flex items-center gap-1">
            <div className="w-1 h-1 rounded-full bg-purple-500"></div>
            EVENT FLOW
          </div>

          <div className="space-y-3">
            {/* If we have specific sub-events in 'events' field */}
            {uniqueEvents.length > 0 ? (
              uniqueEvents.map((evt: any, idx: number) => {
                // FIX: Sub-event value must be (End - Start) / Start
                let evtReturn = evt.avg_return || 0;
                if (evt.startPrice && evt.endPrice) {
                  evtReturn = (evt.endPrice - evt.startPrice) / evt.startPrice;
                } else if (evt.price && currentZone.startPrice) {
                  // If it's a point event with a price, calculate return relative to zone start
                  evtReturn = (evt.price - currentZone.startPrice) / currentZone.startPrice;
                }


                const isEvtPos = evtReturn >= 0;
                return (
                  <div key={idx} className="relative pl-3 border-l border-gray-700">
                    <div className="absolute -left-[3px] top-1.5 w-1.5 h-1.5 rounded-full bg-gray-600"></div>
                    <div className="flex justify-between items-start">
                      <div className="text-gray-400 text-xs mb-0.5">{evt.startDate}</div>
                      <span className={`text-[10px] px-1 rounded ${isEvtPos ? 'bg-red-500/10 text-red-500' : 'bg-green-500/10 text-green-500'}`}>
                        {(evtReturn * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="text-gray-300 text-xs leading-relaxed">
                      {evt.event_summary || evt.summary || evt.description || "区间波动"}
                    </div>
                  </div>
                )
              })
            ) : (
              <div className="text-gray-400 text-xs">
                {currentZone.event_summary || currentZone.summary || currentZone.description || "无详细事件数据"}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  // --- End Semantic Regimes ---


  // 检查是否处于缩放状态
  const isZoomed = (viewEndIndex - viewStartIndex + 1) < chartData.length

  // 鼠标按下开始拖拽
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0) { // 左键
      setIsDragging(true)
      setDragStartX(e.clientX)
      setDragStartIndex(viewStartIndex)
      dragStateRef.current = { isDragging: true, dragStartX: e.clientX, dragStartIndex: viewStartIndex };
      e.preventDefault()
    }
  }, [viewStartIndex])

  // 鼠标移动拖拽 - Optimized with Refs + requestAnimationFrame
  const requestRef = useRef<number>();

  const handleMouseMove = useCallback((e: MouseEvent) => {
    // Access latest state from refs
    const { isDragging, dragStartX, dragStartIndex } = dragStateRef.current;

    if (!isDragging || !chartContainerRef.current) return

    // Use rAF to throttle updates properly
    if (requestRef.current) return; // Skip if frame pending

    requestRef.current = requestAnimationFrame(() => {
      // We also need latest view state to calculate bounds
      const { chartLen } = viewStateRef.current;
      const { startIndex: currentViewStart, endIndex: currentViewEnd } = viewStateRef.current;

      const container = chartContainerRef.current
      if (!container) return; // Safety check inside rAF

      const containerWidth = container.clientWidth
      const deltaX = dragStartX - e.clientX // 反转方向：向左拖拽显示更早的数据
      const dataRange = currentViewEnd - currentViewStart + 1
      const pixelsPerDataPoint = containerWidth / dataRange

      // 计算应该移动的数据点数量
      const dataPointsToMove = Math.round(deltaX / pixelsPerDataPoint)
      const newStartIndex = dragStartIndex + dataPointsToMove

      // 限制在有效范围内
      const minStart = 0
      const maxStart = Math.max(0, chartLen - dataRange)

      const clampedStart = Math.max(minStart, Math.min(maxStart, newStartIndex))
      const clampedEnd = clampedStart + dataRange - 1

      if (clampedStart !== currentViewStart) {
        setViewStartIndex(clampedStart)
        setViewEndIndex(clampedEnd)
      }
      requestRef.current = undefined; // Reset
    });
  }, []) // Empty dependency array = Stable listener!


  // 鼠标释放结束拖拽
  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
    dragStateRef.current = { ...dragStateRef.current, isDragging: false };
  }, [])

  // 绑定拖拽相关的全局鼠标事件
  useEffect(() => {
    if (isDragging) {
      // 拖拽时绑定到 window，确保鼠标移出容器外也能继续拖拽
      window.addEventListener('mousemove', handleMouseMove)
      window.addEventListener('mouseup', handleMouseUp)

      return () => {
        window.removeEventListener('mousemove', handleMouseMove)
        window.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [isDragging, handleMouseMove, handleMouseUp])

  // 滚轮缩放处理函数 - Optimized with Refs
  const handleWheel = useCallback((e: WheelEvent) => {
    if (!chartContainerRef.current) return

    const container = chartContainerRef.current
    const rect = container.getBoundingClientRect()
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top

    // 检查鼠标是否在图表容器内
    if (mouseX < 0 || mouseX > rect.width || mouseY < 0 || mouseY > rect.height) {
      return
    }

    // 阻止默认滚动行为
    e.preventDefault()
    e.stopPropagation()

    // Access state from Ref to ensure we have latest values without re-binding listener
    const { startIndex, endIndex, chartLen } = viewStateRef.current;
    if (chartLen === 0) return;

    const containerWidth = rect.width
    const currentRange = endIndex - startIndex + 1
    const mousePositionRatio = mouseX / containerWidth
    const focusIndex = Math.round(startIndex + mousePositionRatio * currentRange)

    // 缩放因子（向上滚动放大，向下滚动缩小）
    const zoomFactor = e.deltaY > 0 ? 1.15 : 0.85
    const newRange = Math.round(currentRange * zoomFactor)

    // 限制缩放范围
    const minRange = 5 // 最少显示5个数据点
    const maxRange = chartLen // 最多显示全部数据

    const clampedRange = Math.max(minRange, Math.min(maxRange, newRange))

    // 以鼠标位置为中心进行缩放
    const newStartIndex = Math.max(0, Math.min(
      chartLen - clampedRange,
      Math.round(focusIndex - mousePositionRatio * clampedRange)
    ))
    const newEndIndex = newStartIndex + clampedRange - 1

    setViewStartIndex(newStartIndex)
    setViewEndIndex(newEndIndex)
  }, []) // Empty dependency array ensures listener is stable!

  // 当数据变化时重置视图
  useEffect(() => {
    setViewStartIndex(0)
    setViewEndIndex(chartData.length - 1)
  }, [chartData.length])

  // 添加滚轮事件监听（使用原生事件以正确阻止默认行为）
  useEffect(() => {
    const container = chartContainerRef.current
    if (!container) return

    // 使用 { passive: false } 确保可以调用 preventDefault
    container.addEventListener('wheel', handleWheel, { passive: false })

    return () => {
      container.removeEventListener('wheel', handleWheel)
    }
  }, [handleWheel]) // handleWheel is now stable

  // 获取绘图区域边界（排除图例和边距）
  useEffect(() => {
    const container = chartContainerRef.current
    if (!container) return

    const updatePlotAreaBounds = () => {
      // 查找 SVG 元素（Recharts 会在容器内创建 SVG）
      const svg = container.querySelector('svg')
      if (!svg) return

      const containerRect = container.getBoundingClientRect()
      const svgRect = svg.getBoundingClientRect()

      // 查找 X 轴和 Y 轴的实际位置来确定绘图区域
      const xAxis = svg.querySelector('.recharts-cartesian-axis.xAxis')
      const yAxis = svg.querySelector('.recharts-cartesian-axis.yAxis')

      // 如果找不到坐标轴，使用 margin 计算
      if (!xAxis || !yAxis) {
        const marginTop = 5
        const marginBottom = 20
        const legend = svg.querySelector('.recharts-legend-wrapper')
        const legendHeight = legend ? legend.getBoundingClientRect().height : 0

        const plotTop = marginTop
        const plotHeight = containerRect.height - marginTop - marginBottom - legendHeight
        setPlotAreaBounds({ top: plotTop, height: plotHeight })
        return
      }

      // 获取坐标轴的实际位置
      const xAxisRect = xAxis.getBoundingClientRect()
      const yAxisRect = yAxis.getBoundingClientRect()

      // 绘图区域从 Y 轴顶部开始，到 X 轴顶部结束
      // 计算相对于容器顶部的偏移
      const plotTop = yAxisRect.top - containerRect.top
      const plotBottom = xAxisRect.top - containerRect.top
      const plotHeight = plotBottom - plotTop

      if (plotHeight > 0) {
        setPlotAreaBounds({ top: plotTop, height: plotHeight })
      }
    }

    // 初始化时获取边界
    const timer = setTimeout(updatePlotAreaBounds, 100)

    // 监听窗口大小变化
    window.addEventListener('resize', updatePlotAreaBounds)

    // 使用 MutationObserver 监听 DOM 变化（图表渲染完成）
    const observer = new MutationObserver(updatePlotAreaBounds)
    observer.observe(container, { childList: true, subtree: true })

    return () => {
      clearTimeout(timer)
      window.removeEventListener('resize', updatePlotAreaBounds)
      observer.disconnect()
    }
  }, [chartData, viewStartIndex, viewEndIndex, isZoomed])

  // 原生鼠标跟踪获取真实Y坐标（仅在绘图区域内）
  useEffect(() => {
    const container = chartContainerRef.current
    if (!container || !plotAreaBounds) return

    const handleMouseMove = (e: MouseEvent) => {
      const containerRect = container.getBoundingClientRect()
      const mouseYRelativeToContainer = e.clientY - containerRect.top

      // 检查鼠标是否在绘图区域内
      const plotAreaTop = plotAreaBounds.top
      const plotAreaBottom = plotAreaTop + plotAreaBounds.height

      if (mouseYRelativeToContainer >= plotAreaTop && mouseYRelativeToContainer <= plotAreaBottom) {
        // 计算相对于绘图区域顶部的坐标
        const yInPlotArea = mouseYRelativeToContainer - plotAreaTop
        setMouseY(yInPlotArea)
      } else {
        // 鼠标不在绘图区域内，不显示虚线
        setMouseY(null)
      }
    }

    const handleMouseLeave = () => setMouseY(null)

    container.addEventListener('mousemove', handleMouseMove)
    container.addEventListener('mouseleave', handleMouseLeave)

    return () => {
      container.removeEventListener('mousemove', handleMouseMove)
      container.removeEventListener('mouseleave', handleMouseLeave)
    }
  }, [plotAreaBounds])

  // 重置视图
  const handleReset = useCallback(() => {
    setViewStartIndex(0)
    setViewEndIndex(chartData.length - 1)
  }, [chartData.length])



  // Filter Anomalies
  // @ts-ignore
  // Filter Anomalies - Memoized to prevent re-renders
  // @ts-ignore
  const visibleAnomalies = useMemo(() => {
    return (anomalies || []).filter((a: any) => {
      if (trendAlgo === 'all') return true;
      return (a.method || 'bcpd') === trendAlgo;
    });
  }, [anomalies, trendAlgo]);

  // 如果标题包含"预测"，则不显示（因为外层已有"价格走势分析"标题）
  const shouldShowTitle = title && !title.includes('预测')

  // Memoize Ticks to avoid re-calculating on every drag frame
  const MemoizedTicks = useMemo(() => {
    if (!anomalyZones || anomalyZones.length === 0) return null;

    // Filter to raw 'plr' zones only
    return (anomalyZones || [])
      .filter((z: any) => (z.method || 'plr') === 'plr')
      .map((zone: any, idx: number) => (
        <ReferenceLine
          key={`tick-${idx}`}
          x={zone.startDate}
          stroke="rgba(255, 255, 255, 0.1)"
          strokeDasharray="3 3"
          label={{ position: 'top', value: '', fill: 'gray', fontSize: 10 }}
        />
      ));
  }, [anomalyZones]);

  // === Performance Optimization: Pre-calculate Snapped Zones ===
  // Snap semantic regimes to closest valid dates in chartData ONCE.
  // This solves 2 issues:
  // 1. Lag: Expensive scanning removed from render loop.
  // 2. Visibility: Zones on weekends/gaps are now snapped to valid chart dates, so Recharts can render them.
  const snappedSemanticRegimes = useMemo(() => {
    if (!useSemanticRegimes || !semanticRegimes || semanticRegimes.length === 0 || !chartData || chartData.length === 0) {
      return [];
    }

    // Helper: Binary search for closest date

    const validDates = (chartData.map(d => d.name).filter((n: any) => n) as string[]).sort();
    const findClosest = (target: string) => {
      if (!target || validDates.length === 0) return target;
      let low = 0, high = validDates.length - 1;
      while (low <= high) {
        const mid = Math.floor((low + high) / 2);
        const midVal = validDates[mid];
        if (midVal === target) return target;
        if (midVal < target) low = mid + 1;
        else high = mid - 1;
      }
      if (high < 0) return validDates[0];
      if (low >= validDates.length) return validDates[validDates.length - 1];
      const d1 = validDates[high];
      const d2 = validDates[low];
      // FIX: Ensure non-null before Date conversion
      const t = new Date(target || '').getTime();
      const t1 = new Date(d1 || '').getTime();
      const t2 = new Date(d2 || '').getTime();
      return (Math.abs(t - t1) < Math.abs(t - t2)) ? d1 : d2;
    };

    return semanticRegimes.map(regime => ({
      ...regime,
      // Snap start/end to valid dates
      snappedStart: findClosest(regime.startDate),
      snappedEnd: findClosest(regime.endDate)
    }));
  }, [useSemanticRegimes, semanticRegimes, chartData]);

  return (
    <div className="mt-2 relative">
      {/* 回测控制UI */}
      {hasBacktestSupport && (
        <BacktestControls
          isLoading={backtest.isLoading}
          mae={backtest.metrics?.mape ?? null}
          onReset={backtest.resetBacktest}
        />
      )}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {shouldShowTitle && (
            <h4 className="text-sm font-medium text-gray-300">{title}</h4>
          )}
          {/* Trend Algo Selector Removed - Default to Semantic */}
        </div>
        <div className="flex items-center gap-2">
          {isZoomed && (
            <>
              <button
                onClick={handleReset}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-gray-400 hover:text-gray-200 bg-dark-600/50 hover:bg-dark-600 rounded-lg transition-colors"
                title="重置视图"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>重置</span>
              </button>
              <div className="flex items-center gap-1 text-xs text-gray-500">
                <Move className="w-3.5 h-3.5" />
                <span>拖拽平移 | 滚轮缩放</span>
              </div>
            </>
          )}
          {!isZoomed && (
            <div className="flex items-center gap-1 text-xs text-gray-500">
              <Move className="w-3.5 h-3.5" />
              <span>点击图表后：拖拽平移 | 滚轮缩放</span>
            </div>
          )}
        </div>
      </div>
      {/* Zone计数器 - debug */}
      {anomalyZones && anomalyZones.length > 0 && (
        <div className="absolute top-2 right-2 bg-black/70 px-2 py-1 rounded text-xs text-white/70 z-10">
          {anomalyZones.length} 个重点区域
        </div>
      )}
      {/* Zone Detail Tooltip (Overlay) REMOVED - using Hover Tooltip instead */}

      {/* 变点详情提示 */}
      {
        activeChangePoint && (
          <div className="absolute top-10 right-2 bg-gray-900/90 border border-amber-500/30 p-2 rounded shadow-lg max-w-xs z-20 backdrop-blur-sm pointer-events-none">
            <div className="text-amber-400 text-xs font-bold mb-1 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
              突变点分析 ({activeChangePoint.date})
            </div>
            <div className="text-gray-200 text-xs leading-relaxed">
              {activeChangePoint.reason}
            </div>
            <div className="mt-1 text-gray-500 text-[10px] flex justify-between gap-4">
              <span>幅度: {activeChangePoint.magnitude ? Number(activeChangePoint.magnitude).toFixed(2) : '-'}</span>
              <span>类型: {activeChangePoint.type === 'shift' ? '水平偏移' : '趋势变化'}</span>
            </div>
          </div>
        )
      }
      <div
        ref={chartContainerRef}
        className="w-full h-[512px] relative"
        onMouseDown={handleMouseDown}
        style={{
          cursor: isDragging ? 'grabbing' : 'grab',
          userSelect: 'none'
        }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={displayData}
            margin={{ top: 5, right: 10, left: 0, bottom: 20 }}
            onClick={handleChartClick}
            onMouseMove={(e: any) => {
              // Update mouse Y for horizontal crosshair
              if (e && e.activeCoordinate) {
                setMouseY(e.activeCoordinate.y);
              }
            }}
            onMouseLeave={() => {
              setMouseY(null);
            }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#3a3a4a" vertical={false} />
            <XAxis
              dataKey="name"
              stroke="#6b7280"
              style={{ fontSize: '12px' }}
              angle={isZoomed ? -45 : 0}
              textAnchor={isZoomed ? "end" : "middle"}
              height={isZoomed ? 60 : 30}
            />
            <YAxis
              stroke="#6b7280"
              style={{ fontSize: '12px' }}
              domain={yAxisDomain}
              allowDataOverflow={false}
              label={{ value: '供电量(MW)', angle: -90, position: 'insideLeft' }}
              tickFormatter={(value) => {
                // 格式化 Y 轴刻度标签，处理大数值
                if (isNaN(value) || !isFinite(value)) {
                  return ''
                }

                // 如果数值很大，使用科学计数法或简化显示
                if (Math.abs(value) >= 100000000) {
                  return (value / 100000000).toFixed(1) + '亿'
                } else if (Math.abs(value) >= 10000) {
                  return (value / 10000).toFixed(1) + '万'
                } else if (Math.abs(value) >= 1000) {
                  return (value / 1000).toFixed(1) + 'k'
                } else if (Math.abs(value) >= 1) {
                  return value.toFixed(0)
                } else {
                  return value.toFixed(2)
                }
              }}
              width={60}
            />
            <Tooltip
              content={<CustomTooltip />}
              offset={20}
              cursor={{ stroke: 'rgba(255, 255, 255, 0.2)', strokeWidth: 1, strokeDasharray: '5 5' }}
              contentStyle={{
                backgroundColor: '#1a1a24',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '8px',
              }}
              labelStyle={{ color: '#9ca3af' }}
            />
            <Legend
              wrapperStyle={{ fontSize: '12px' }}
            />
            {/* Ticks for Raw Intervals (Vertical Lines) - Rendered only in Semantic Mode (Memoized) */}
            {trendAlgo === 'semantic' && MemoizedTicks}
            {/* RAW Interval Ticks (Start/End Markers) - User Request: "Larger ticks on horizontal axis" */}
            {trendAlgo === 'semantic' && anomalyZones && anomalyZones.length > 0 && (
              (() => {
                // Filter for raw zones (method='plr')
                const rawZones = anomalyZones.filter((z: any) => (z.method || 'plr') === 'plr');
                return rawZones.map((z: any, i: number) => {
                  // Ensure visible
                  if (!displayData || displayData.length === 0) return null;
                  const viewStart = displayData[0]?.name;
                  const viewEnd = displayData[displayData.length - 1]?.name;

                  if (!viewStart || !viewEnd) return null;
                  const validViewStart = viewStart; // Ensure non-null for closure
                  const validViewEnd = viewEnd;

                  // Helper to render a tick if inside view
                  const renderTick = (date: string, type: 'start' | 'end') => {
                    // Check visibility
                    if (date < validViewStart || date > validViewEnd) return null;

                    // Calculate tick height (at bottom)
                    // yAxisDomain is available from scope
                    const [yMin, yMax] = yAxisDomain;
                    // Ensure yMin/yMax are numbers. If auto/dataMin, this might fail, but yAxisDomain is calculated in this component.
                    const min = typeof yMin === 'number' ? yMin : 0;
                    const max = typeof yMax === 'number' ? yMax : 1000; // Fallback
                    const tickHeight = (max - min) * 0.03;

                    return (
                      <ReferenceLine
                        key={`raw-tick-${i}-${type}`}
                        segment={[
                          { x: date, y: min },
                          { x: date, y: min + tickHeight }
                        ]}
                        stroke="rgba(255, 255, 255, 0.6)"
                        strokeWidth={2}
                      // Solid line for tick
                      />
                    )
                  };

                  return (
                    <React.Fragment key={`raw-group-${i}`}>
                      {renderTick(z.startDate, 'start')}
                      {renderTick(z.endDate, 'end')}
                    </React.Fragment>
                  );
                });
              })()
            )}
            {/* 异常区域与悬浮提示 - Bloomberg风格 */}
            {/* 区域渲染逻辑：语义合并 vs 原始分段 */}
            {/* 1. Semantic Regimes: Areas */}
            {/* 2. Anomalies: Points of Interest - Rendered before zones to sit behind/above? No, dots on top usually. */}
            {/* But we keep order: Zones first, then Dots? Recharts renders in order. */}
            {/* Let's render Zones first. */}

            {useSemanticRegimes && snappedSemanticRegimes.map((regime: any, idx: number) => {
              // CRITICAL FIX: Use sentiment field (from backend) instead of displayType
              // AND PRIORITIZE avg_return for color determination to ensure visual accuracy!
              const returnVal = regime.avg_return !== undefined ? regime.avg_return : 0;
              const hasReturn = regime.avg_return !== undefined;

              const sentiment = regime.sentiment || regime.displayType;
              // If we have a numeric return, use it! Otherwise fall back to sentiment string.
              const isPositive = hasReturn ? returnVal >= 0 : (sentiment === 'positive' || sentiment === 'up');
              const isNegative = hasReturn ? returnVal < 0 : (sentiment === 'negative' || sentiment === 'down');

              // const isSideways = sentiment === 'sideways' || sentiment === 'neutral'; // Not strictly used for fill color logic below

              // A-share colors: Red for Up/Positive, Green for Down/Negative, Gray for Sideways
              const fill = isPositive ? '#ef4444' : (isNegative ? '#10b981' : '#6b7280');

              // Prediction Styling - User wants "Semantic Version" (solid block), not dashed "Raw" look
              const isPrediction = regime.is_prediction;
              // Opacity: History=0.15 (Fainted as requested), Prediction=0.15 (Consistent)
              // User Request: "Too intense! Lower slightly" -> Reduced from 0.3 to 0.15
              const baseOpacity = 0.15; // Unified opacity (Fainted)

              const uniqueKey = `regime-area-${regime.startDate}-${idx}`;

              // Optmization: Use PRE-CALCULATED snapped dates
              let validStart = regime.snappedStart || regime.startDate;
              let validEnd = regime.snappedEnd || regime.endDate;

              return (
                <ReferenceArea
                  key={uniqueKey}
                  x1={validStart}
                  x2={validEnd}
                  fill={fill}
                  fillOpacity={baseOpacity}
                  stroke={isPrediction ? fill : "none"}
                  strokeWidth={isPrediction ? 1 : 0}
                  // REMOVED dashes to look like standard Semantic Zone
                  className="cursor-pointer hover:opacity-80 transition-opacity"
                  onMouseEnter={() => {
                    setActiveZone(regime);
                  }}
                  onMouseLeave={() => setActiveZone(null)}
                  onClick={(e) => { e.stopPropagation(); setActiveZone(regime); }}
                >
                  <Label
                    value={`${((() => {
                      // FIX: Calculate return strictly: (End - Start) / Start
                      if (regime.startPrice && regime.endPrice) {
                        return (regime.endPrice - regime.startPrice) / regime.startPrice * 100;
                      }
                      return (regime.avg_return || regime.change_pct || 0) * 100;
                    })()).toFixed(2)}%`}
                    position="top"
                    fill={isPositive ? '#ef4444' : '#22c55e'}
                    fontSize={12}
                    fontWeight="bold"
                  />
                </ReferenceArea>
              );
            })}

            {/* 2. Anomalies: Points of Interest */}
            {visibleAnomalies.map((anom: any, idx: number) => {
              // Ensure anomaly is within view
              const isInView = true;

              if (!isInView) return null;

              const uniqueKey = `anomaly-${anom.date}-${idx}`;

              return (
                <ReferenceDot
                  key={uniqueKey}
                  x={anom.date}
                  y={anom.price}
                  r={5}
                  fill="#FBBF24"  // Yellow-400
                  stroke="#ffffff"
                  strokeWidth={2}
                  isFront={false}
                  className="cursor-pointer"
                >
                  <Label
                    value="" // No text inside dot
                    position="top"
                  />
                </ReferenceDot>
              );
            })}

            {!useSemanticRegimes && visibleZones.map((zone: any, idx: number) => {
              // A股配色：红涨绿跌
              const isPositive = (zone.avg_return || 0) >= 0
              const isRaw = trendAlgo === 'plr'
              const zoneColor = isPositive
                // User Request: Raw zones should be "transparent color" (fill='transparent')
                ? { fill: isRaw ? 'transparent' : 'rgba(239, 68, 68, 0.15)', stroke: '#ef4444' }  // 红色=上涨
                : { fill: isRaw ? 'transparent' : 'rgba(34, 197, 94, 0.15)', stroke: '#22c55e' }   // 绿色=下跌

              const impact = zone.impact || 0.5
              const isCalm = zone.zone_type === 'calm'

              // 使用唯一key：startDate-endDate组合
              const uniqueKey = `zone-${zone.startDate}-${zone.endDate}-${idx}`

              // FIX: 单日zones需要扩展宽度，否则ReferenceArea不显示
              // FIX: Use findClosestDate logic to prevent gaps in raw zones too
              const findClosestDateRaw = (targetDate: string) => {
                const chartDates = chartData.map((d: any) => d.name).sort();
                if (chartData.find((d: any) => d.name === targetDate)) return targetDate;
                if (chartDates.length === 0) return targetDate;
                if (targetDate < chartDates[0]) return chartDates[0];
                if (targetDate > chartDates[chartDates.length - 1]) return chartDates[chartDates.length - 1];
                let closest = chartDates[0];
                let minDiff = Math.abs(new Date(targetDate).getTime() - new Date(closest).getTime());
                for (let i = 1; i < chartDates.length; i++) {
                  const diff = Math.abs(new Date(targetDate).getTime() - new Date(chartDates[i]).getTime());
                  if (diff < minDiff) {
                    minDiff = diff;
                    closest = chartDates[i];
                  }
                }
                return closest;
              };

              let displayStartDate = findClosestDateRaw(zone.startDate);
              let displayEndDate = findClosestDateRaw(zone.endDate);

              if (displayStartDate === displayEndDate) {
                const startIdx = chartData.findIndex((d: any) => d.name === displayStartDate)
                if (startIdx > 0) {
                  displayStartDate = chartData[startIdx - 1].name
                }
              }


              // Prediction Logic
              const isPrediction = zone.is_prediction || zone.zone_type === 'prediction_regime';

              // Styling Logic
              // If it's prediction, use fill even in raw mode (User request: "Prediction area only has semantic intervals... canceling, only historical points are covered")
              // Actually, user wants prediction area to exist.
              // So for prediction zones, we ALWAYS use fill (maybe lighter) and dashed stroke

              let fill = zoneColor.fill;
              let stroke = zoneColor.stroke;
              let fillOpacity = impact * 0.8;
              let strokeDasharray = isCalm ? '5 5' : undefined;

              if (isPrediction) {
                // User request: "Cancel (Raw Mode), then only historical points be covered by raw intervals"
                // So we do NOT show prediction zones in Raw Mode.
                return null;
              }

              // Normal Raw styling (no fill but capture events)
              fill = 'transparent';

              return (
                <ReferenceArea
                  key={uniqueKey}
                  x1={displayStartDate}
                  x2={displayEndDate}
                  fill={fill || undefined} // use undefined instead of null
                  fillOpacity={fillOpacity}
                  stroke={stroke || undefined}
                  strokeOpacity={impact}
                  strokeDasharray={strokeDasharray}
                  onMouseEnter={() => {
                    console.log('Hover Raw Zone:', zone)
                    // Construct a rich object for the tooltip
                    // Ensure event_summary is prioritized
                    setActiveZone({
                      ...zone,
                      // If raw zone, we want the event_summary as the main description
                      summary: zone.event_summary || zone.summary || 'No details available',
                      // Clear events if it's a raw zone (since it IS the event)
                      events: []
                    })
                  }}
                  onMouseLeave={() => setActiveZone(null)}
                  className="cursor-pointer transition-all duration-300"
                />
              )
            })}
            {/* 变点检测标记 */}

            {/* 鼠标跟随的水平参考线 */}
            {mouseY !== null && plotAreaBounds && (() => {
              // mouseY 已经是相对于绘图区域顶部的坐标
              const effectiveHeight = plotAreaBounds.height

              // 计算对应的数据值
              const dataValue = yAxisDomain[1] - (mouseY / effectiveHeight) * (yAxisDomain[1] - yAxisDomain[0])

              return (
                <ReferenceLine
                  y={dataValue}
                  stroke="#60a5fa"
                  strokeWidth={1}
                  strokeDasharray="3 3"
                  label={{
                    value: dataValue.toFixed(2),
                    position: 'right',
                    fill: '#60a5fa',
                    fontSize: 10
                  }}
                />
              )
            })()}
            {/* 回测分割线 - 垂直参考线 */}
            {((hasBacktestSupport && backtest.splitDate) || (isDraggingSlider && tempSplitDate)) && (() => {
              // 拖拽时使用临时日期，否则使用回测分割日期
              const splitDate = (isDraggingSlider && tempSplitDate) ? tempSplitDate : backtest.splitDate
              if (!splitDate) return null

              // 检查分割日期是否在当前显示的数据中
              const splitDataPoint = displayData.find(item => item.name === splitDate)
              if (splitDataPoint) {
                return (
                  <ReferenceLine
                    x={splitDate}
                    stroke="#f97316"
                    strokeWidth={2}
                    strokeDasharray="4 2"
                  />
                )
              }
              return null
            })()}
            {/* 回测模式：3条线 */}
            {backtest.chartData ? (
              <>
                <Line
                  type="monotone"
                  dataKey="历史供电量"
                  stroke="#a855f7"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                  isAnimationActive={false}
                  name="历史供电量(MW)"
                />
                <Line
                  type="monotone"
                  dataKey="实际值"
                  stroke="#6b7280"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                  activeDot={{ r: 4 }}
                  connectNulls={false}
                  isAnimationActive={false}
                  name="实际供电量(MW)"
                />
                <Line
                  type="monotone"
                  dataKey="回测预测"
                  stroke="#06b6d4"
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                  isAnimationActive={false}
                  name="回测预测(MW)"
                />
              </>
            ) : (
              /* 正常模式：原有数据集 */
              data.datasets.map((dataset, index) => (
                <Line
                  key={dataset.label}
                  type="monotone"
                  dataKey={dataset.label}
                  stroke={dataset.color || colors[index % colors.length]}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 5 }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              ))
            )}

            {/* 2. Semantic Regimes: Event Dots (Moved to Top Layer) */}
            {useSemanticRegimes && semanticRegimes.flatMap((regime: any, idx: any) =>
              regime.events.map((ev: any, evIdx: any) => {
                const dotColor = ev.method === 'bcpd' ? '#fbbf24' : (ev.method === 'matrix_profile' ? '#c084fc' : '#f87171');
                const yPos = yAxisDomain[0] + (yAxisDomain[1] - yAxisDomain[0]) * 0.05;

                return (
                  <ReferenceDot
                    key={`regime-event-${idx}-${evIdx}`}
                    x={ev.date}
                    y={yPos}
                    r={4}
                    fill={dotColor}
                    stroke="#fff"
                    strokeWidth={1}
                    className="cursor-pointer hover:r-6 transition-all"
                    isFront={true}
                  >
                    <Label value="" />
                  </ReferenceDot>
                );
              })
            )}

            {/* 异常点调试日志 (控制台可见) */}
            {(() => {
              // console.log("[MessageContent] Anomalies Prop:", anomalies?.length || 0);
              // console.log("[MessageContent] Visible Anomalies:", visibleAnomalies.length);
              // console.log("[MessageContent] Prediction Zones (Prop):", prediction_semantic_zones?.length || 0);
              // console.log("[MessageContent] Semantic Regimes (Calculated):", semanticRegimes?.length || 0);
              if (anomalies && anomalies.length > 0 && visibleAnomalies.length === 0) {
                // console.warn("[MessageContent] WARNING: Anomalies exist but none are visible!");
              }
              return null;
            })()}

            {/* 异常点 - ReferenceDot (Visible in ALL modes, styled as Signal Points) */}
            {visibleAnomalies.map((anomaly: any, idx: number) => {
              // Validate anomaly has required fields
              if (!anomaly.date || anomaly.price === undefined) {
                // console.warn(`[Anomaly Rendering] Skipping anomaly ${idx}: missing date or price`, anomaly);
                return null;
              }

              // Check if date exists in FULL chartData (not just displayData which is zoom-filtered)
              const dateExists = chartData.some((d: any) => d.name === anomaly.date);
              if (!dateExists) {
                // Date not in dataset at all (weekends or missing data)
                return null;
              }

              // Color Mapping: Use Yellow/Amber for Signal Service (New Standard)
              // method 'signal_service' -> #FBBF24 (Amber-400) or #F59E0B (Amber-500)
              // Keep legacy colors just in case
              const colorMap: Record<string, string> = {
                'signal_service': '#FBBF24', // Bright Amber (Eye-catching)
                'bcpd': '#F59E0B',
                'stl_cusum': '#EF4444',
                'matrix_profile': '#8B5CF6'
              };
              const dotColor = colorMap[anomaly.method] || '#FBBF24';

              // Size: Magnified for Signal Service
              const dotSize = anomaly.method === 'signal_service' ? 6 : 5;
              const hoverSize = anomaly.method === 'signal_service' ? 9 : 7;

              if (anomaly.method === 'signal_service') {
                return (
                  <ReferenceDot
                    key={`anomaly-${anomaly.method}-${idx}`}
                    x={anomaly.date}
                    y={anomaly.price}
                    r={6}
                    fill={dotColor}
                    stroke="#fff"
                    strokeWidth={2}
                    className="cursor-pointer transition-all duration-300 animate-pulse hover:scale-150 z-50"
                    isFront={true}
                    onMouseEnter={() => {
                      const mockZone = {
                        type: 'anomaly',
                        displayType: 'anomaly',
                        startDate: anomaly.date,
                        endDate: anomaly.date,
                        summary: anomaly.description || '异常波动点',
                        event_summary: anomaly.description,
                        isAnomaly: true,
                        data: anomaly
                      }
                      setActiveZone(mockZone);
                    }}
                    onMouseLeave={() => setActiveZone(null)}
                  >
                    <Label value="" />
                  </ReferenceDot>
                );
              }

              return (
                <ReferenceDot
                  key={`anomaly-${anomaly.method}-${idx}`}
                  x={anomaly.date}
                  y={anomaly.price}
                  r={5}
                  fill={dotColor}
                  stroke="#fff"
                  strokeWidth={2}
                  className={`cursor-pointer transition-all duration-300 animate-in zoom-in-50`}
                  isFront={true}
                  onMouseEnter={() => {
                    const mockZone = {
                      type: 'anomaly',
                      displayType: 'anomaly',
                      startDate: anomaly.date,
                      endDate: anomaly.date,
                      summary: anomaly.description || '异常波动点',
                      event_summary: anomaly.description,
                      isAnomaly: true,
                      data: anomaly
                    }
                    setActiveZone(mockZone);
                  }}
                  onMouseLeave={() => setActiveZone(null)}
                >
                  <Label value="" />
                </ReferenceDot>
              );
            })}
          </LineChart>
        </ResponsiveContainer>

        {/* X 轴滑块 - 明显的滑块圆点 */}
        {((hasBacktestSupport && originalData && originalData.length > 60) || (data.datasets.some(d => d.label === '历史供电量') && data.datasets.some(d => d.label === '预测供电量'))) && plotAreaBounds && (() => {
          // 计算分割点：拖拽时使用临时日期，否则使用回测分割点或历史供电量和预测供电量的分界点
          let splitDate = isDraggingSlider && tempSplitDate ? tempSplitDate : backtest.splitDate
          let splitIndexInChart = -1

          if (splitDate) {
            // 回测模式：使用指定的分割点
            splitIndexInChart = chartData.findIndex(item => item.name === splitDate)
          } else {
            // 正常模式：查找历史供电量和预测供电量的分界点
            // 找到最后一个有历史供电量值的点，下一个点就是预测供电量的起点
            for (let i = chartData.length - 1; i >= 0; i--) {
              const item = chartData[i]
              const historicalPower = (item as any)['历史供电量']
              if (historicalPower !== null && historicalPower !== undefined) {
                // 找到下一个有预测供电量的点作为分界点
                if (i + 1 < chartData.length) {
                  const nextItem = chartData[i + 1]
                  const predictedPower = (nextItem as any)['预测供电量']
                  if (predictedPower !== null && predictedPower !== undefined) {
                    splitIndexInChart = i + 1
                    splitDate = nextItem.name as string
                    break
                  }
                }
                // 如果没有找到预测供电量，使用当前点
                if (splitIndexInChart < 0) {
                  splitIndexInChart = i
                  splitDate = item.name as string
                  break
                }
              }
            }
          }

          if (!splitDate || splitIndexInChart < 0) return null

          // 检查是否在当前显示范围内
          const isInView = splitIndexInChart >= viewStartIndex && splitIndexInChart <= viewEndIndex

          // 计算位置比例（相对于当前显示的 displayData）
          // 需要找到分割日期在 displayData 中的索引，而不是在 chartData 中的索引
          let positionRatio = 0
          const splitIndexInDisplayData = displayData.findIndex(item => item.name === splitDate)

          if (splitIndexInDisplayData >= 0) {
            // 在显示数据中找到，计算位置比例
            const displayDataLength = displayData.length
            // Recharts 的 X 轴是均匀分布的，所以位置比例就是索引比例
            // 但需要考虑第一个和最后一个点的位置（它们不在边缘，而是在中间）
            if (displayDataLength > 1) {
              positionRatio = splitIndexInDisplayData / (displayDataLength - 1)
            } else {
              positionRatio = 0
            }
          } else if (isDraggingSlider) {
            // 拖拽时，即使不在显示数据中，也根据位置计算显示
            if (splitIndexInChart < viewStartIndex) {
              positionRatio = 0 // 在视图左侧
            } else {
              positionRatio = 1 // 在视图右侧
            }
          } else {
            // 不在显示数据中且不在拖拽，不显示
            return null
          }

          // X 轴位置
          // plotAreaBounds.top + plotAreaBounds.height 是绘图区域的底部，也就是 X 轴线的位置
          // 滑块圆点应该直接显示在 X 轴线上
          const xAxisLineTop = plotAreaBounds.top + plotAreaBounds.height
          // 滑块圆点在 X 轴线上，所以顶部位置是 X 轴线位置减去圆点半径（8px）以居中
          const sliderTop = xAxisLineTop - 8

          return (
            <>
              {/* 滑块圆点容器 - 覆盖绘图区域 */}
              <div
                className="absolute pointer-events-none z-30"
                style={{
                  left: '60px', // Y 轴宽度
                  right: '10px', // 右侧边距
                  top: `${sliderTop}px`, // X 轴线位置（减去圆点半径以居中）
                  height: '16px'
                }}
              >
                {/* 滑块圆点 - 在 X 轴上明显显示，支持拖拽 */}
                <div
                  className="absolute pointer-events-auto group"
                  style={{
                    left: `${positionRatio * 100}%`, // 在绘图区域内的位置比例
                    transform: 'translateX(-50%)', // 居中对齐
                    width: '16px',
                    height: '16px'
                  }}
                  onMouseDown={(e) => {
                    e.stopPropagation() // 阻止触发图表拖拽
                    e.preventDefault()
                    const container = chartContainerRef.current
                    if (!container) return

                    // 开始拖拽
                    setIsDraggingSlider(true)

                    const updateSplitPoint = (clientX: number, isFinal: boolean = false) => {
                      const svg = container.querySelector('svg')
                      if (!svg) return

                      const svgRect = svg.getBoundingClientRect()
                      const plotLeft = svgRect.left
                      const plotWidth = svgRect.width

                      // 计算鼠标在绘图区域内的位置比例
                      const mouseX = clientX - plotLeft
                      const positionRatio = Math.max(0, Math.min(1, mouseX / plotWidth))

                      // 计算对应的数据点索引
                      const viewRange = viewEndIndex - viewStartIndex + 1
                      const relativeIndex = Math.round(positionRatio * viewRange)
                      const targetIndex = viewStartIndex + relativeIndex

                      // 找到对应的日期
                      if (targetIndex >= 0 && targetIndex < chartData.length && originalData) {
                        const targetDate = chartData[targetIndex].name
                        if (typeof targetDate === 'string') {
                          const originalIndex = originalData.findIndex(p => p.date === targetDate)
                          if (originalIndex >= 60 && originalIndex < originalData.length) {
                            if (isFinal) {
                              // 释放鼠标时才触发回测更新
                              backtest.triggerBacktest(targetDate)
                              setIsDraggingSlider(false)
                              setTempSplitDate(null)
                            } else {
                              // 拖拽过程中只更新临时日期，用于显示滑块位置
                              setTempSplitDate(targetDate)
                            }
                          }
                        }
                      }
                    }

                    const handleMouseMove = (e: MouseEvent) => {
                      updateSplitPoint(e.clientX, false) // 拖拽中，不触发回测
                    }

                    const handleMouseUp = (e: MouseEvent) => {
                      updateSplitPoint(e.clientX, true) // 释放时，触发回测
                      window.removeEventListener('mousemove', handleMouseMove)
                      window.removeEventListener('mouseup', handleMouseUp)
                    }

                    // 立即更新一次（拖拽开始）
                    updateSplitPoint(e.clientX, false)

                    // 绑定全局事件以支持拖拽
                    window.addEventListener('mousemove', handleMouseMove)
                    window.addEventListener('mouseup', handleMouseUp)
                  }}
                >
                  {/* 滑块圆点 - 大而明显 */}
                  <div className="w-full h-full bg-orange-400 rounded-full shadow-xl shadow-orange-400/50 border-2 border-orange-300 cursor-grab active:cursor-grabbing hover:scale-125 hover:shadow-orange-400/70 transition-all duration-200 flex items-center justify-center">
                    {/* 内部白点 */}
                    <div className="w-2 h-2 bg-white/90 rounded-full" />
                  </div>

                  {/* 日期标签 - 悬停时显示 */}
                  <div className="absolute top-full left-1/2 transform -translate-x-1/2 mt-2 px-2 py-1 text-xs text-orange-300 bg-dark-800/95 backdrop-blur-sm rounded-md border border-orange-400/40 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none shadow-lg">
                    {splitDate}
                  </div>
                </div>
              </div>

              {/* 滑块交互区域 - 覆盖 X 轴区域，支持拖拽 */}
              <div
                className="absolute cursor-pointer z-20"
                style={{
                  left: '60px', // Y 轴宽度
                  right: '10px', // 右侧边距
                  top: `${xAxisLineTop - 10}px`, // X 轴线上方一点，方便交互
                  height: `20px` // 交互区域高度，覆盖 X 轴线及其附近区域
                }}
                onMouseDown={(e) => {
                  e.stopPropagation()
                  const container = chartContainerRef.current
                  if (!container) return

                  // 开始拖拽
                  setIsDraggingSlider(true)

                  const updateSplitPoint = (clientX: number, isFinal: boolean = false) => {
                    const svg = container.querySelector('svg')
                    if (!svg) return

                    const svgRect = svg.getBoundingClientRect()
                    const plotLeft = svgRect.left
                    const plotWidth = svgRect.width

                    // 计算鼠标在绘图区域内的位置比例
                    const mouseX = clientX - plotLeft
                    const positionRatio = Math.max(0, Math.min(1, mouseX / plotWidth))

                    // 计算对应的数据点索引
                    const viewRange = viewEndIndex - viewStartIndex + 1
                    const relativeIndex = Math.round(positionRatio * viewRange)
                    const targetIndex = viewStartIndex + relativeIndex

                    // 找到对应的日期
                    if (targetIndex >= 0 && targetIndex < chartData.length && originalData) {
                      const targetDate = chartData[targetIndex].name
                      if (typeof targetDate === 'string') {
                        const originalIndex = originalData.findIndex(p => p.date === targetDate)
                        if (originalIndex >= 60 && originalIndex < originalData.length) {
                          if (isFinal) {
                            // 释放鼠标时才触发回测更新
                            backtest.triggerBacktest(targetDate)
                            setIsDraggingSlider(false)
                            setTempSplitDate(null)
                          } else {
                            // 拖拽过程中只更新临时日期，用于显示滑块位置
                            setTempSplitDate(targetDate)
                          }
                        }
                      }
                    }
                  }

                  const handleMouseMove = (e: MouseEvent) => {
                    updateSplitPoint(e.clientX, false) // 拖拽中，不触发回测
                  }

                  const handleMouseUp = (e: MouseEvent) => {
                    updateSplitPoint(e.clientX, true) // 释放时，触发回测
                    window.removeEventListener('mousemove', handleMouseMove)
                    window.removeEventListener('mouseup', handleMouseUp)
                  }

                  // 立即更新一次（拖拽开始）
                  updateSplitPoint(e.clientX, false)

                  // 绑定全局事件以支持拖拽
                  window.addEventListener('mousemove', handleMouseMove)
                  window.addEventListener('mouseup', handleMouseUp)
                }}
              >
                {/* 悬停提示 - 轻微高亮 */}
                <div className="absolute inset-0 opacity-0 hover:opacity-[0.02] bg-orange-400 transition-opacity pointer-events-none" />
              </div>
            </>
          )
        })()}
      </div>

      {
        isZoomed && (
          <div className="mt-2 text-xs text-gray-500 text-center">
            当前视图：{chartData[viewStartIndex]?.name} 至 {chartData[viewEndIndex]?.name}
            ({viewEndIndex - viewStartIndex + 1} / {chartData.length} 个数据点)
          </div>
        )
      }


      {/* 新闻侧边栏 */}
      {
        ticker && (
          <ChartNewsSidebar
            isOpen={newsSidebarOpen}
            onClose={handleCloseSidebar}
            news={newsData}
            loading={newsLoading}
            selectedDate={selectedDate}
            ticker={ticker}
          />
        )
      }
    </div >
  )
}

