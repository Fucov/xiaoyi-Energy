'use client'

import { useState, useEffect } from 'react'
import { BarChart, Bar, ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { InfluenceAnalysisResult } from '@/lib/api/analysis'
import { TrendingUp, TrendingDown, Minus, Sparkles } from 'lucide-react'

interface MultiFactorInfluencePanelProps {
  influenceData: InfluenceAnalysisResult | null
}

// 因子颜色映射（使用更现代的渐变色）
const FACTOR_COLORS: Record<string, { main: string; light: string; gradient: string }> = {
  temperature: {
    main: '#06b6d4',
    light: '#22d3ee',
    gradient: 'linear-gradient(90deg, #06b6d4 0%, #22d3ee 100%)'
  },
  humidity: {
    main: '#8b5cf6',
    light: '#a78bfa',
    gradient: 'linear-gradient(90deg, #8b5cf6 0%, #a78bfa 100%)'
  },
  season: {
    main: '#10b981',
    light: '#34d399',
    gradient: 'linear-gradient(90deg, #10b981 0%, #34d399 100%)'
  },
  industry_structure: {
    main: '#f59e0b',
    light: '#fbbf24',
    gradient: 'linear-gradient(90deg, #f59e0b 0%, #fbbf24 100%)'
  },
}

const FACTOR_NAMES_CN: Record<string, string> = {
  temperature: '日平均气温',
  humidity: '日平均湿度',
  season: '季节位置',
  industry_structure: '城市工业结构',
}

// 自定义渐变条形图组件
const GradientBar = ({ entry, index }: { entry: any; index: number }) => {
  const color = FACTOR_COLORS[entry.factor] || { main: '#9ca3af', light: '#d1d5db', gradient: 'linear-gradient(90deg, #9ca3af 0%, #d1d5db 100%)' }
  return (
    <defs>
      <linearGradient id={`gradient-${entry.factor}`} x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stopColor={color.main} stopOpacity={0.9} />
        <stop offset="100%" stopColor={color.light} stopOpacity={0.7} />
      </linearGradient>
    </defs>
  )
}

export function MultiFactorInfluencePanel({ influenceData }: MultiFactorInfluencePanelProps) {
  if (!influenceData) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="flex flex-col items-center gap-3">
          <div className="relative">
            <div className="w-12 h-12 border-4 border-violet-500/20 border-t-violet-500 rounded-full animate-spin" />
            <Sparkles className="w-6 h-6 text-violet-400 absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 animate-pulse" />
          </div>
          <span className="text-sm text-gray-400">相关性分析中...</span>
        </div>
      </div>
    )
  }

  const { factors, ranking, time_range, summary } = influenceData

  // 过滤有效的因子数据（排除NaN值）
  const validFactors = Object.keys(factors).filter(factorName => {
    const factor = factors[factorName]
    const score = factor?.influence_score
    return score !== null && score !== undefined && !isNaN(score) && isFinite(score)
  })

  // 默认选择第一个有效因子
  const [selectedFactor, setSelectedFactor] = useState<string | null>(null)
  
  // 当validFactors变化时，设置默认选中的因子
  useEffect(() => {
    if (!selectedFactor && validFactors.length > 0) {
      setSelectedFactor(validFactors[0])
    } else if (selectedFactor && !validFactors.includes(selectedFactor) && validFactors.length > 0) {
      setSelectedFactor(validFactors[0])
    }
  }, [validFactors, selectedFactor])

  // 准备相关性仪表盘数据（按得分降序）
  const dashboardData = ranking
    .filter(item => {
      const score = item.influence_score
      return score !== null && score !== undefined && !isNaN(score) && isFinite(score)
    })
    .map(item => ({
      name: item.factor_name_cn || item.factor,
      factor: item.factor,
      influence_score: item.influence_score,
      correlation: item.correlation || 0,
      color: FACTOR_COLORS[item.factor] || { main: '#9ca3af', light: '#d1d5db', gradient: '' }
    }))
    .sort((a, b) => b.influence_score - a.influence_score)

  // 准备当前选中因子的散点图数据
  const currentScatterData = selectedFactor && factors[selectedFactor]
    ? factors[selectedFactor].data.map(point => ({
        x: point.factor_value,
        y: point.power,
        date: point.date
      }))
    : []

  const currentFactor = selectedFactor ? factors[selectedFactor] : null
  const selectedColor = selectedFactor ? FACTOR_COLORS[selectedFactor] : null

  return (
    <div className="space-y-6">
      {/* 顶部：标题和时间段 */}
      <div className="flex items-start justify-between pb-4 border-b border-white/10">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <div className="p-1.5 rounded-lg bg-gradient-to-br from-violet-500/20 to-purple-500/20 border border-violet-500/30">
              <Sparkles className="w-4 h-4 text-violet-400" />
            </div>
            <h3 className="text-xl font-bold bg-gradient-to-r from-gray-200 via-gray-100 to-gray-300 bg-clip-text text-transparent">
              多因素相关性分析
            </h3>
          </div>
          {time_range.start && time_range.end && (
            <div className="flex items-center gap-2 text-sm text-gray-400 ml-7">
              <span className="px-2 py-0.5 bg-dark-700/50 rounded border border-white/5">
                {time_range.start} ~ {time_range.end}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 分析摘要 */}
      {summary && (
        <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-dark-700/60 via-dark-800/60 to-dark-700/60 p-4 border border-white/10 shadow-lg backdrop-blur-sm">
          <div className="absolute inset-0 bg-gradient-to-r from-violet-500/5 via-transparent to-purple-500/5" />
          <div className="relative">
            <div className="flex items-start gap-2 mb-2">
              <div className="w-1 h-4 bg-gradient-to-b from-violet-400 to-purple-400 rounded-full" />
              <span className="text-xs font-semibold text-violet-300 uppercase tracking-wide">分析摘要</span>
            </div>
            <p className="text-sm text-gray-300 leading-relaxed pl-3">{summary}</p>
          </div>
        </div>
      )}

      {/* 相关性仪表盘 */}
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-dark-800/80 via-dark-800/60 to-dark-900/80 px-1 py-4 border border-white/10 shadow-xl backdrop-blur-sm">
        <div className="absolute inset-0 bg-gradient-to-r from-violet-500/5 via-transparent to-purple-500/5" />
        <div className="relative">
          <div className="flex items-center justify-center mb-6">
            <div className="flex items-center gap-3">
              <div className="w-1.5 h-6 bg-gradient-to-b from-cyan-400 to-blue-400 rounded-full" />
              <h4 className="text-lg font-semibold text-gray-200">相关性得分仪表盘</h4>
              <div className="text-xs text-gray-500 px-2.5 py-1 bg-dark-700/50 rounded border border-white/5 ml-2">
                {dashboardData.length} 个因子
              </div>
            </div>
          </div>
          
          <div className="w-full">
            <ResponsiveContainer width="100%" height={250}>
              <BarChart
                data={dashboardData}
                layout="vertical"
                margin={{ top: 10, right: 20, left: 20, bottom: 10 }}
                barCategoryGap="15%"
              >
              <defs>
                {dashboardData.map((entry, index) => (
                  <GradientBar key={entry.factor} entry={entry} index={index} />
                ))}
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
              <XAxis 
                type="number"
                domain={[0, 1]}
                stroke="#6b7280"
                tick={{ fill: '#9ca3af', fontSize: 12 }}
                tickLine={{ stroke: '#4b5563' }}
                label={{ value: '相关性得分', position: 'insideBottom', offset: -5, fill: '#9ca3af', fontSize: 13 }}
                tickMargin={8}
              />
              <YAxis 
                type="category"
                dataKey="name"
                stroke="#6b7280"
                tick={{ fill: '#d1d5db', fontSize: 12, fontWeight: 500 }}
                tickLine={{ stroke: '#4b5563' }}
                width={75}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(17, 24, 39, 0.98)',
                  border: '1px solid rgba(139, 92, 246, 0.3)',
                  borderRadius: '8px',
                  boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
                  padding: '12px',
                  color: '#e5e7eb'
                }}
                wrapperStyle={{
                  outline: 'none',
                  border: 'none',
                  boxShadow: 'none',
                  backgroundColor: 'transparent',
                  background: 'transparent'
                }}
                itemStyle={{
                  padding: '0',
                  margin: '0',
                  backgroundColor: 'transparent',
                  background: 'transparent'
                }}
                labelStyle={{
                  display: 'none',
                  backgroundColor: 'transparent',
                  background: 'transparent'
                }}
                cursor={{ fill: 'transparent' }}
                formatter={(value: number, name: string, props: any) => {
                  if (name === 'influence_score') {
                    const corr = props.payload.correlation || 0
                    const corrIcon = corr > 0 ? '↑' : corr < 0 ? '↓' : '—'
                    const corrColor = corr > 0 ? '#60a5fa' : corr < 0 ? '#f87171' : '#9ca3af'
                    return [
                      <div key="tooltip" className="space-y-1.5">
                        <div className="text-gray-200 font-semibold text-sm">{props.payload.name}</div>
                        <div className="flex items-center gap-2">
                          <span className="text-cyan-400 font-medium">相关性得分:</span>
                          <span className="text-white font-bold">{value.toFixed(3)}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-gray-400">相关系数:</span>
                          <span style={{ color: corrColor }} className="font-semibold">
                            {corrIcon} {Math.abs(corr).toFixed(3)}
                          </span>
                        </div>
                      </div>,
                      ''
                    ]
                  }
                  return [value.toFixed(3), name]
                }}
                labelFormatter={() => ''}
              />
              <Bar 
                dataKey="influence_score" 
                radius={[0, 12, 12, 0]}
                animationDuration={800}
                animationEasing="ease-out"
                barSize={35}
              >
                {dashboardData.map((entry, index) => (
                  <Cell 
                    key={`cell-${index}`} 
                    fill={`url(#gradient-${entry.factor})`}
                    className={`cursor-pointer transition-all duration-200 ${
                      selectedFactor === entry.factor 
                        ? 'opacity-100 shadow-lg shadow-violet-500/20' 
                        : 'opacity-90 hover:opacity-100'
                    }`}
                    onClick={() => setSelectedFactor(entry.factor)}
                    style={{
                      filter: selectedFactor === entry.factor ? 'brightness(1.1)' : 'none'
                    }}
                  />
                ))}
              </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          
          {/* 图例：显示相关性指示 - 2x2网格布局 */}
          <div className="mt-6">
            <div className="grid grid-cols-2 gap-3 w-full">
              {dashboardData.map(item => {
                const isSelected = selectedFactor === item.factor
                const corr = item.correlation || 0
                const CorrIcon = corr > 0 ? TrendingUp : corr < 0 ? TrendingDown : Minus
                const corrColor = corr > 0 ? 'text-blue-400' : corr < 0 ? 'text-red-400' : 'text-gray-500'
                
                return (
                  <button
                    key={item.factor}
                    onClick={() => setSelectedFactor(item.factor)}
                    className={`group flex items-center justify-between gap-3 px-5 py-3 rounded-xl transition-all duration-200 ${
                      isSelected
                        ? 'bg-gradient-to-r from-violet-500/20 to-purple-500/20 border-2 border-violet-500/50 shadow-lg shadow-violet-500/20 scale-[1.02]'
                        : 'bg-dark-700/40 border border-white/10 hover:border-violet-500/30 hover:bg-dark-700/60'
                    }`}
                  >
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <div 
                        className="w-4 h-4 rounded-full shadow-sm flex-shrink-0"
                        style={{ 
                          backgroundColor: item.color.main,
                          boxShadow: `0 0 10px ${item.color.main}50`
                        }}
                      />
                      <span className={`text-sm font-semibold transition-colors truncate ${
                        isSelected ? 'text-gray-100' : 'text-gray-300 group-hover:text-gray-100'
                      }`}>
                        {item.name}
                      </span>
                    </div>
                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <span className={`text-xs font-medium ${isSelected ? 'text-gray-400' : 'text-gray-500'}`}>
                        相关性得分
                      </span>
                      <div className={`flex items-center gap-1.5 text-sm font-bold ${corrColor}`}>
                        <CorrIcon className="w-4 h-4" />
                        <span>{item.influence_score.toFixed(2)}</span>
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      {/* 散点图分析 */}
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-dark-800/80 via-dark-800/60 to-dark-900/80 p-6 border border-white/10 shadow-xl backdrop-blur-sm">
        <div className="absolute inset-0 bg-gradient-to-r from-violet-500/5 via-transparent to-purple-500/5" />
        <div className="relative">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <div className="w-1 h-5 bg-gradient-to-b from-green-400 to-emerald-400 rounded-full" />
              <h4 className="text-base font-semibold text-gray-200">
                散点图分析
                {selectedFactor && (
                  <span className="ml-3 text-sm text-gray-400 font-normal">
                    {FACTOR_NAMES_CN[selectedFactor] || selectedFactor}
                  </span>
                )}
              </h4>
            </div>
            {currentFactor && (
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 px-3 py-1.5 bg-dark-700/50 rounded-lg border border-white/5">
                  <span className="text-xs text-gray-400">相关性得分</span>
                  <span className="text-sm font-bold text-gray-200">{currentFactor.influence_score.toFixed(3)}</span>
                </div>
                <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${
                  currentFactor.correlation > 0 
                    ? 'bg-blue-500/10 border-blue-500/30 text-blue-400' 
                    : currentFactor.correlation < 0 
                    ? 'bg-red-500/10 border-red-500/30 text-red-400'
                    : 'bg-dark-700/50 border-white/5 text-gray-400'
                }`}>
                  {currentFactor.correlation > 0 ? (
                    <TrendingUp className="w-3.5 h-3.5" />
                  ) : currentFactor.correlation < 0 ? (
                    <TrendingDown className="w-3.5 h-3.5" />
                  ) : (
                    <Minus className="w-3.5 h-3.5" />
                  )}
                  <span className="text-xs font-semibold">
                    {currentFactor.correlation > 0 ? '+' : ''}{currentFactor.correlation.toFixed(3)}
                  </span>
                </div>
              </div>
            )}
          </div>
          
          {currentScatterData.length > 0 && selectedFactor && selectedColor ? (
            <ResponsiveContainer width="100%" height={420}>
              <ScatterChart
                data={currentScatterData}
                margin={{ top: 20, right: 30, bottom: 70, left: 70 }}
              >
                <defs>
                  <linearGradient id={`scatter-gradient-${selectedFactor}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={selectedColor.main} stopOpacity={0.8} />
                    <stop offset="100%" stopColor={selectedColor.light} stopOpacity={0.4} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
                <XAxis 
                  type="number"
                  dataKey="x"
                  name={FACTOR_NAMES_CN[selectedFactor] || selectedFactor}
                  stroke="#6b7280"
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  tickLine={{ stroke: '#4b5563' }}
                  label={{ 
                    value: FACTOR_NAMES_CN[selectedFactor] || selectedFactor, 
                    position: 'insideBottom', 
                    offset: -10, 
                    fill: '#9ca3af',
                    fontSize: 12,
                    fontWeight: 500
                  }}
                />
                <YAxis 
                  type="number"
                  dataKey="y"
                  name="供电量"
                  stroke="#6b7280"
                  tick={{ fill: '#9ca3af', fontSize: 11 }}
                  tickLine={{ stroke: '#4b5563' }}
                  label={{ 
                    value: '供电量 (MW)', 
                    angle: -90, 
                    position: 'insideLeft', 
                    fill: '#9ca3af',
                    fontSize: 12,
                    fontWeight: 500
                  }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'rgba(17, 24, 39, 0.98)',
                    border: `1px solid ${selectedColor.main}40`,
                    borderRadius: '8px',
                    boxShadow: `0 4px 12px rgba(0, 0, 0, 0.5), 0 0 20px ${selectedColor.main}20`,
                    padding: '12px',
                    color: '#e5e7eb'
                  }}
                  wrapperStyle={{
                    outline: 'none',
                    border: 'none',
                    boxShadow: 'none',
                    backgroundColor: 'transparent',
                    background: 'transparent'
                  }}
                  itemStyle={{
                    padding: '0',
                    margin: '0',
                    backgroundColor: 'transparent',
                    background: 'transparent'
                  }}
                  labelStyle={{
                    display: 'none',
                    backgroundColor: 'transparent',
                    background: 'transparent'
                  }}
                  cursor={{ fill: 'transparent' }}
                  formatter={(value: number, name: string, props: any) => {
                    if (name === 'y') {
                      return [
                        <div key="scatter-tooltip" className="space-y-1.5">
                          <div className="text-xs text-gray-400 border-b border-white/10 pb-1 mb-1">
                            {props.payload.date}
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-gray-400 text-xs">{FACTOR_NAMES_CN[selectedFactor]}:</span>
                            <span className="text-white font-semibold">{props.payload.x.toFixed(2)}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-gray-400 text-xs">供电量:</span>
                            <span className="text-cyan-400 font-bold">{value.toFixed(2)} MW</span>
                          </div>
                        </div>,
                        ''
                      ]
                    }
                    return [value.toFixed(2), name]
                  }}
                  labelFormatter={() => ''}
                />
                <Scatter 
                  name="数据点"
                  dataKey="y"
                  fill={selectedColor.main}
                  fillOpacity={0.7}
                >
                  {currentScatterData.map((entry, index) => (
                    <Cell
                      key={`scatter-${index}`}
                      fill={selectedColor.main}
                      fillOpacity={0.7}
                    />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex flex-col items-center justify-center h-[420px] text-gray-400">
              <div className="w-16 h-16 rounded-full bg-dark-700/50 border border-white/10 flex items-center justify-center mb-4">
                <Sparkles className="w-8 h-8 text-violet-400/50" />
              </div>
              <div className="text-sm font-medium mb-1">暂无数据</div>
              <div className="text-xs text-gray-500">请选择上方的因子查看散点图</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
