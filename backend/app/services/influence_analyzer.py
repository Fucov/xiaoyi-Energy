"""
多因素影响力分析服务
====================

分析天气数据对供电需求的影响因子
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime


class InfluenceAnalyzer:
    """多因素影响力分析器"""
    
    @staticmethod
    def analyze_weather_influence(
        power_df: pd.DataFrame,
        weather_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        分析天气因素对供电需求的影响
        
        Args:
            power_df: 供电需求数据，包含 ds 和 y 列
            weather_df: 天气数据，包含 date, temperature, humidity 等列
            
        Returns:
            包含各因素影响力得分的字典
        """
        # 确保日期格式一致
        power_df_copy = power_df.copy()
        weather_df_copy = weather_df.copy()
        
        # 转换日期列为datetime类型（移除时区信息以便匹配）
        if power_df_copy['ds'].dt.tz is not None:
            power_df_copy['ds'] = power_df_copy['ds'].dt.tz_localize(None)
        if 'date' in weather_df_copy.columns:
            if weather_df_copy['date'].dtype == 'object':
                weather_df_copy['date'] = pd.to_datetime(weather_df_copy['date'])
            if weather_df_copy['date'].dt.tz is not None:
                weather_df_copy['date'] = weather_df_copy['date'].dt.tz_localize(None)
        
        # 合并数据
        merged_df = pd.merge(
            power_df_copy,
            weather_df_copy,
            left_on='ds',
            right_on='date',
            how='inner'
        )
        
        if len(merged_df) < 10:
            # 数据不足，返回默认值
            return {
                "temperature_influence": 0.5,
                "humidity_influence": 0.3,
                "seasonality_influence": 0.4,
                "trend_influence": 0.6,
                "volatility_influence": 0.3,
                "description": "数据量不足，使用默认影响因子"
            }
        
        # 1. 温度影响力 (0-1)
        # 计算温度与供电需求的相关性
        temp_corr = abs(np.corrcoef(merged_df['temperature'].values, merged_df['y'].values)[0, 1])
        if np.isnan(temp_corr):
            temp_corr = 0.5
        
        # 计算极端温度的影响
        comfort_temp = 22
        temp_deviations = abs(merged_df['temperature'] - comfort_temp)
        extreme_temp_ratio = (temp_deviations > 10).sum() / len(merged_df)
        temperature_influence = min(0.3 + temp_corr * 0.5 + extreme_temp_ratio * 0.2, 1.0)
        
        # 2. 湿度影响力 (0-1)
        if 'humidity' in merged_df.columns:
            humidity_corr = abs(np.corrcoef(merged_df['humidity'].values, merged_df['y'].values)[0, 1])
            if np.isnan(humidity_corr):
                humidity_corr = 0.2
            humidity_influence = min(0.2 + humidity_corr * 0.5, 0.8)
        else:
            humidity_influence = 0.3
        
        # 3. 季节性影响力 (0-1)
        # 计算月度供电需求的波动
        merged_df['month'] = pd.to_datetime(merged_df['ds']).dt.month
        monthly_std = merged_df.groupby('month')['y'].std().mean()
        monthly_mean = merged_df['y'].mean()
        seasonality_coef = monthly_std / monthly_mean if monthly_mean > 0 else 0
        seasonality_influence = min(0.2 + seasonality_coef * 2, 1.0)
        
        # 4. 趋势影响力 (0-1)
        # 计算供电需求的趋势强度
        y_values = merged_df['y'].values
        mid = len(y_values) // 2
        first_half_mean = np.mean(y_values[:mid])
        second_half_mean = np.mean(y_values[mid:])
        if first_half_mean > 0:
            trend_strength = abs((second_half_mean - first_half_mean) / first_half_mean)
            trend_influence = min(0.3 + trend_strength * 0.7, 1.0)
        else:
            trend_influence = 0.5
        
        # 5. 波动性影响力 (0-1)
        # 计算供电需求的波动程度
        cv = np.std(y_values) / np.mean(y_values) if np.mean(y_values) > 0 else 0
        volatility_influence = min(0.2 + cv * 1.5, 1.0)
        
        # 生成描述
        description = _generate_description(
            temperature_influence,
            humidity_influence,
            seasonality_influence,
            trend_influence,
            volatility_influence,
            merged_df
        )
        
        return {
            "temperature_influence": round(float(temperature_influence), 2),
            "humidity_influence": round(float(humidity_influence), 2),
            "seasonality_influence": round(float(seasonality_influence), 2),
            "trend_influence": round(float(trend_influence), 2),
            "volatility_influence": round(float(volatility_influence), 2),
            "description": description
        }


def _generate_description(
    temp_inf: float,
    humidity_inf: float,
    season_inf: float,
    trend_inf: float,
    vol_inf: float,
    merged_df: pd.DataFrame
) -> str:
    """生成影响力分析描述"""
    factors = []
    
    # 温度影响描述
    if temp_inf > 0.7:
        factors.append(f"温度影响显著（{temp_inf:.2f}），极端天气对供电需求影响较大")
    elif temp_inf > 0.4:
        factors.append(f"温度影响中等（{temp_inf:.2f}），天气变化对供电需求有一定影响")
    else:
        factors.append(f"温度影响较小（{temp_inf:.2f}）")
    
    # 季节性影响描述
    if season_inf > 0.6:
        factors.append(f"季节性特征明显（{season_inf:.2f}），不同季节供电需求差异较大")
    elif season_inf > 0.3:
        factors.append(f"存在一定季节性（{season_inf:.2f}）")
    
    # 趋势影响描述
    if trend_inf > 0.7:
        factors.append(f"趋势变化显著（{trend_inf:.2f}），供电需求呈现明显变化趋势")
    elif trend_inf > 0.4:
        factors.append(f"存在一定趋势性（{trend_inf:.2f}）")
    
    # 波动性描述
    if vol_inf > 0.6:
        factors.append(f"波动性较高（{vol_inf:.2f}），供电需求波动较大")
    
    if not factors:
        return "各因素影响相对均衡"
    
    return "；".join(factors[:3])  # 最多显示3个因素
