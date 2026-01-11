/**
 * BacktestControls Component
 * ===========================
 * 
 * 回测滑块控制UI组件
 */

import React from 'react'
import { Target, RefreshCw, Loader2 } from 'lucide-react'

interface BacktestControlsProps {
    originalData: Array<{ date: string; value: number }>
    splitDate: string | null
    isLoading: boolean
    mae: number | null
    onSplitChange: (date: string) => void
    onReset: () => void
}

export function BacktestControls({
    originalData,
    splitDate,
    isLoading,
    mae,
    onSplitChange,
    onReset
}: BacktestControlsProps) {
    // 过滤可用的分割点（至少需要60个历史数据）
    const validDates = originalData.slice(60)

    if (validDates.length === 0) {
        return null // 数据不足，不显示回测控件
    }

    const currentIndex = splitDate
        ? originalData.findIndex(p => p.date === splitDate)
        : -1

    return (
        <div className="mb-4 p-4 bg-gradient-to-r from-purple-900/20 to-pink-900/20 rounded-xl border border-purple-500/30">
            <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-semibold text-purple-300 flex items-center gap-2">
                    <Target className="w-4 h-4" />
                    时间旅行回测
                </h4>

                {mae !== null && (
                    <div className="flex items-center gap-4">
                        <div className="text-xs text-gray-400">
                            预测误差 (MAE): <span className="text-purple-400 font-mono font-bold">{mae.toFixed(4)}</span>
                        </div>
                        <button
                            onClick={onReset}
                            disabled={isLoading}
                            className="px-3 py-1 text-xs bg-purple-600/20 hover:bg-purple-600/40 disabled:opacity-50 text-purple-300 rounded-md transition-colors flex items-center gap-1"
                        >
                            <RefreshCw className="w-3 h-3" />
                            重置
                        </button>
                    </div>
                )}
            </div>

            <div className="space-y-2">
                <input
                    type="range"
                    min={60}
                    max={originalData.length - 1}
                    value={currentIndex >= 60 ? currentIndex : 60}
                    onChange={(e) => {
                        const newIndex = parseInt(e.target.value)
                        onSplitChange(originalData[newIndex].date)
                    }}
                    disabled={isLoading}
                    className="w-full h-2 bg-purple-900/30 rounded-lg appearance-none cursor-pointer accent-purple-500 disabled:opacity-50"
                    style={{
                        background: currentIndex >= 60
                            ? `linear-gradient(to right, #a855f7 0%, #a855f7 ${((currentIndex - 60) / (originalData.length - 61)) * 100}%, #581c87 ${((currentIndex - 60) / (originalData.length - 61)) * 100}%, #581c87 100%)`
                            : undefined
                    }}
                />

                <div className="flex items-center justify-between text-xs text-gray-500">
                    <span>
                        最早: {originalData[60]?.date}
                    </span>
                    {currentIndex >= 60 && (
                        <span className="text-purple-400 font-semibold">
                            当前: {originalData[currentIndex].date} (索引 {currentIndex})
                        </span>
                    )}
                    <span>
                        最晚: {originalData[originalData.length - 1]?.date}
                    </span>
                </div>

                {isLoading && (
                    <div className="flex items-center justify-center gap-2 text-xs text-purple-400 py-2">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        正在计算回测结果...
                    </div>
                )}

                <p className="text-xs text-gray-500 text-center pt-1">
                    💡 提示：拖动滑块选择历史分割点，系统将基于该点之前的数据重新预测，并与实际历史数据对比
                </p>
            </div>
        </div>
    )
}
