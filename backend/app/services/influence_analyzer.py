"""
多因素影响力分析服务
====================

分析多个因子对供电需求的影响，包括：
- 日平均气温
- 日平均湿度
- 年内季节位置
- 城市工业结构（第二产业增加值占GDP比例）
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime
from scipy import stats


class InfluenceAnalyzer:
    """多因素影响力分析器"""
    
    @staticmethod
    def analyze_factors_influence(
        power_df: pd.DataFrame,
        weather_df: pd.DataFrame,
        holiday_df: pd.DataFrame,
        industry_structure_ratio: float = 0.3
    ) -> Dict[str, Any]:
        """
        分析多个因子对供电需求的影响
        
        Args:
            power_df: 供电需求数据，包含 ds 和 y 列
            weather_df: 天气数据，包含 date, temperature, humidity 等列
            holiday_df: 节假日数据（已废弃，保留参数以兼容）
            industry_structure_ratio: 城市工业结构比例（第二产业增加值占GDP比例，0-1）
            
        Returns:
            包含各因子分析结果的字典
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
        
        # 合并所有数据
        merged_df = power_df_copy.copy()
        
        # 合并天气数据
        merged_df = pd.merge(
            merged_df,
            weather_df_copy[['date', 'temperature', 'humidity']],
            left_on='ds',
            right_on='date',
            how='left'
        )
        
        # 计算季节位置（归一化到0-1范围）
        merged_df['day_of_year'] = merged_df['ds'].dt.dayofyear
        merged_df['season'] = merged_df['day_of_year'] / 365.0
        
        # 填充缺失值
        merged_df['temperature'] = merged_df['temperature'].fillna(merged_df['temperature'].mean())
        merged_df['humidity'] = merged_df['humidity'].fillna(merged_df['humidity'].mean())
        
        # 城市工业结构因子：固定值（所有日期都是同一个ratio值）
        merged_df['industry_structure'] = industry_structure_ratio
        
        if len(merged_df) < 10:
            # 数据不足，返回默认值
            return InfluenceAnalyzer._get_default_result()
        
        # 提取因子数据
        factors_data = {
            'temperature': merged_df['temperature'].values,
            'humidity': merged_df['humidity'].values,
            'season': merged_df['season'].values,
            'industry_structure': merged_df['industry_structure'].values,
        }
        
        power_values = merged_df['y'].values
        
        # 计算各因子的相关性和影响力得分
        factors_result = {}
        for factor_name, factor_values in factors_data.items():
            # 对于城市工业结构因子，使用理论模型计算影响力得分
            if factor_name == 'industry_structure':
                # 固定值无法计算相关性，设为0
                correlation = 0.0
                # 基于理论模型：工业结构比例越高，对供电需求的影响越大
                # influence_score = min(second_industry_ratio * 2, 1.0)
                influence_score = min(industry_structure_ratio * 2.0, 1.0)
            else:
                correlation, influence_score = InfluenceAnalyzer._calculate_factor_influence(
                    power_values, factor_values, factor_name
                )
            
            # 准备时序数据点
            data_points = []
            for i in range(len(merged_df)):
                data_points.append({
                    'date': merged_df.iloc[i]['ds'].strftime('%Y-%m-%d'),
                    'power': float(power_values[i]),
                    'factor_value': float(factor_values[i])
                })
            
            # 确保值不是NaN
            correlation_clean = correlation if not (np.isnan(correlation) or np.isinf(correlation)) else 0.0
            influence_score_clean = influence_score if not (np.isnan(influence_score) or np.isinf(influence_score)) else 0.0
            
            factors_result[factor_name] = {
                'correlation': round(float(correlation_clean), 4),
                'influence_score': round(float(influence_score_clean), 4),
                'data': data_points
            }
        
        # 计算相关性矩阵（供电量 + 4个因子 = 5x5）
        correlation_matrix = InfluenceAnalyzer._calculate_correlation_matrix(
            power_values, factors_data
        )
        
        # 生成影响力排行榜
        ranking = InfluenceAnalyzer._generate_ranking(factors_result)
        
        # 生成分析摘要
        summary = InfluenceAnalyzer._generate_summary(factors_result, ranking)
        
        # 获取时间范围
        time_range = {
            'start': merged_df['ds'].min().strftime('%Y-%m-%d'),
            'end': merged_df['ds'].max().strftime('%Y-%m-%d')
        }
        
        # 计算总体得分（过滤掉NaN值）
        valid_scores = [
            factor['influence_score'] 
            for factor in ranking 
            if not (np.isnan(factor['influence_score']) or np.isinf(factor['influence_score']))
        ]
        overall_score = np.mean(valid_scores) if valid_scores else 0.0
        if np.isnan(overall_score) or np.isinf(overall_score):
            overall_score = 0.0
        
        result = {
            'factors': factors_result,
            'correlation_matrix': correlation_matrix.tolist(),
            'ranking': ranking,
            'time_range': time_range,
            'summary': summary,
            'overall_score': round(float(overall_score), 4)
        }
        
        return result
    
    @staticmethod
    def _calculate_factor_influence(
        power_values: np.ndarray,
        factor_values: np.ndarray,
        factor_name: str
    ) -> tuple:
        """
        计算单个因子的相关性和影响力得分
        
        Args:
            power_values: 供电量数组
            factor_values: 因子值数组
            factor_name: 因子名称
            
        Returns:
            (correlation, influence_score) 元组
        """
        # 计算Pearson相关系数
        if len(power_values) < 2 or len(factor_values) < 2:
            return 0.0, 0.0
        
        # 移除NaN值
        mask = ~(np.isnan(power_values) | np.isnan(factor_values))
        if mask.sum() < 2:
            return 0.0, 0.0
        
        power_clean = power_values[mask]
        factor_clean = factor_values[mask]
        
        # 计算相关系数
        try:
            # 检查数据是否为常数（方差为0）
            if len(factor_clean) > 1 and np.std(factor_clean) == 0:
                # 如果因子值是常数，无法计算相关性
                correlation = 0.0
                p_value = 1.0
            elif len(power_clean) > 1 and np.std(power_clean) == 0:
                # 如果供电量值是常数，无法计算相关性
                correlation = 0.0
                p_value = 1.0
            else:
                correlation, p_value = stats.pearsonr(power_clean, factor_clean)
                if np.isnan(correlation):
                    correlation = 0.0
        except Exception:
            correlation = 0.0
            p_value = 1.0
        
        # 计算影响力得分
        # 基于相关系数的绝对值，考虑显著性（p值越小，权重越高）
        significance_weight = 1.0 - min(p_value, 0.1) / 0.1  # p值从0到0.1映射到1到0
        influence_score = abs(correlation) * (0.7 + 0.3 * significance_weight)
        
        # 确保influence_score不是NaN
        if np.isnan(influence_score) or np.isinf(influence_score):
            influence_score = 0.0
        
        return correlation, influence_score
    
    @staticmethod
    def _calculate_correlation_matrix(
        power_values: np.ndarray,
        factors_data: Dict[str, np.ndarray]
    ) -> np.ndarray:
        """
        计算相关性矩阵（5x5：供电量 + 4个因子）
        
        Args:
            power_values: 供电量数组
            factors_data: 因子数据字典
            
        Returns:
            5x5的相关性矩阵
        """
        # 准备所有变量
        variables = {
            'power': power_values,
            **factors_data
        }
        
        variable_names = ['power', 'temperature', 'humidity', 'season', 'industry_structure']
        
        # 确保所有变量长度一致
        min_len = min(len(v) for v in variables.values())
        variables_clean = {name: values[:min_len] for name, values in variables.items()}
        
        # 构建矩阵
        matrix_size = len(variable_names)
        correlation_matrix = np.zeros((matrix_size, matrix_size))
        
        for i, name1 in enumerate(variable_names):
            for j, name2 in enumerate(variable_names):
                if i == j:
                    correlation_matrix[i, j] = 1.0
                else:
                    var1 = variables_clean[name1]
                    var2 = variables_clean[name2]
                    
                    # 移除NaN值
                    mask = ~(np.isnan(var1) | np.isnan(var2))
                    if mask.sum() < 2:
                        correlation_matrix[i, j] = 0.0
                    else:
                        try:
                            var1_clean = var1[mask]
                            var2_clean = var2[mask]
                            # 检查数据是否为常数
                            if np.std(var1_clean) == 0 or np.std(var2_clean) == 0:
                                correlation_matrix[i, j] = 0.0
                            else:
                                corr, _ = stats.pearsonr(var1_clean, var2_clean)
                                correlation_matrix[i, j] = corr if not np.isnan(corr) else 0.0
                        except Exception:
                            correlation_matrix[i, j] = 0.0
        
        return correlation_matrix
    
    @staticmethod
    def _generate_ranking(factors_result: Dict[str, Dict]) -> List[Dict[str, Any]]:
        """
        生成影响力排行榜
        
        Args:
            factors_result: 因子分析结果字典
            
        Returns:
            排序后的排行榜列表
        """
        ranking = []
        
        factor_names_map = {
            'temperature': '日平均气温',
            'humidity': '日平均湿度',
            'season': '季节位置',
            'industry_structure': '城市工业结构'
        }
        
        for factor_name, result in factors_result.items():
            ranking.append({
                'factor': factor_name,
                'factor_name_cn': factor_names_map.get(factor_name, factor_name),
                'influence_score': result['influence_score'],
                'correlation': result['correlation']
            })
        
        # 按影响力得分降序排序
        ranking.sort(key=lambda x: x['influence_score'], reverse=True)
        
        return ranking
    
    @staticmethod
    def _generate_summary(
        factors_result: Dict[str, Dict],
        ranking: List[Dict[str, Any]]
    ) -> str:
        """
        生成分析摘要
        
        Args:
            factors_result: 因子分析结果字典
            ranking: 影响力排行榜
            
        Returns:
            分析摘要文本
        """
        if not ranking:
            return "数据不足，无法生成分析摘要"
        
        # 过滤掉NaN值的因子
        valid_ranking = [
            f for f in ranking 
            if not (np.isnan(f.get('influence_score', np.nan)) or np.isinf(f.get('influence_score', np.nan)))
        ]
        
        if not valid_ranking:
            return "数据不足，无法生成分析摘要"
        
        top_factor = valid_ranking[0]
        factor_name_cn = top_factor['factor_name_cn']
        influence_score = top_factor['influence_score']
        correlation = top_factor['correlation']
        
        # 判断相关性方向
        if correlation > 0.3:
            direction = "正相关"
        elif correlation < -0.3:
            direction = "负相关"
        else:
            direction = "相关性较弱"
        
        summary_parts = [
            f"在分析的时间段内，{factor_name_cn}对供电需求的影响最为显著（影响力得分：{influence_score:.2f}），"
            f"与供电需求呈{direction}关系（相关系数：{correlation:.3f}）。"
        ]
        
        # 添加其他重要因子
        if len(ranking) > 1:
            second_factor = ranking[1]
            if second_factor['influence_score'] > 0.3:
                summary_parts.append(
                    f"{second_factor['factor_name_cn']}的影响次之（影响力得分：{second_factor['influence_score']:.2f}）。"
                )
        
        return "".join(summary_parts)
    
    @staticmethod
    def _get_default_result() -> Dict[str, Any]:
        """返回默认结果（数据不足时）"""
        return {
            'factors': {
                'temperature': {'correlation': 0.0, 'influence_score': 0.0, 'data': []},
                'humidity': {'correlation': 0.0, 'influence_score': 0.0, 'data': []},
                'season': {'correlation': 0.0, 'influence_score': 0.0, 'data': []},
                'industry_structure': {'correlation': 0.0, 'influence_score': 0.0, 'data': []},
            },
            'correlation_matrix': [[1.0] * 5] * 5,
            'ranking': [],
            'time_range': {'start': '', 'end': ''},
            'summary': '数据量不足，使用默认影响因子'
        }
    
    # 保留旧方法以兼容
    @staticmethod
    def analyze_weather_influence(
        power_df: pd.DataFrame,
        weather_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        分析天气因素对供电需求的影响（保留以兼容旧代码）
        
        Args:
            power_df: 供电需求数据，包含 ds 和 y 列
            weather_df: 天气数据，包含 date, temperature, humidity 等列
            
        Returns:
            包含各因素影响力得分的字典
        """
        # 创建空的节假日数据
        holiday_df = pd.DataFrame(columns=['date', 'is_holiday', 'holiday_score'])
        
        # 调用新方法（使用默认工业结构比例0.3）
        result = InfluenceAnalyzer.analyze_factors_influence(
            power_df, weather_df, holiday_df, industry_structure_ratio=0.3
        )
        
        # 转换为旧格式
        return {
            "temperature_influence": result['factors']['temperature']['influence_score'],
            "humidity_influence": result['factors']['humidity']['influence_score'],
            "seasonality_influence": result['factors']['season']['influence_score'],
            "trend_influence": 0.5,  # 旧版本没有趋势分析
            "volatility_influence": 0.3,  # 旧版本没有波动性分析
            "description": result['summary']
        }
