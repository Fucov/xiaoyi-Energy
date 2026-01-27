"""
供电需求数据获取与预处理模块
============================

基于天气数据生成Mock供电需求数据，并进行标准化预处理

架构:
- fetch_power_data(): 获取天气数据并生成供电需求
- generate_power_demand(): Mock供电需求生成算法
- prepare(): 数据预处理为标准时序格式 (ds, y)
"""

import pandas as pd
import numpy as np
import math
from typing import Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.data.weather_client import get_weather_client
from app.core.config import settings

# 北京时区
BEIJING_TZ = ZoneInfo("Asia/Shanghai")

# 城市基础负荷配置（MW）
CITY_BASE_LOADS = {
    "北京": 10000,
    "上海": 12000,
    "广州": 8000,
    "深圳": 9000,
    "杭州": 6000,
    "成都": 7000,
    "武汉": 6500,
    "西安": 5500,
    "南京": 5800,
    "天津": 7500,
}

# 默认配置
DEFAULT_BASE_LOAD = 10000  # MW
DEFAULT_TEMP_COEFFICIENT = 0.5  # 温度影响系数


def _is_weekend(date: datetime) -> bool:
    """判断是否为周末"""
    return date.weekday() >= 5


def _get_season_factor(date: datetime) -> float:
    """
    获取季节性因子
    
    Args:
        date: 日期
    
    Returns:
        季节性因子 (0.9-1.1)
    """
    month = date.month
    
    # 夏季（6-8月）和冬季（12-2月）用电高峰
    if month in [6, 7, 8]:
        return 1.1  # 夏季空调需求
    elif month in [12, 1, 2]:
        return 1.05  # 冬季取暖需求
    elif month in [3, 4, 5]:
        return 0.95  # 春季
    else:  # 9, 10, 11
        return 0.98  # 秋季


def generate_power_demand(
    base_load: float,
    temperature: float,
    date: datetime,
    temp_coefficient: float = DEFAULT_TEMP_COEFFICIENT,
) -> float:
    """
    生成供电需求（Mock算法）
    
    Args:
        base_load: 基础负荷（MW）
        temperature: 当前温度（摄氏度）
        date: 日期
        temp_coefficient: 温度影响系数（默认0.5）
    
    Returns:
        供电需求（MW）
    """
    # 处理缺失值：如果temperature是NaN或None，使用默认值
    if temperature is None:
        temperature = 22  # 使用舒适温度作为默认值
    
    # 检查是否为NaN（包括numpy和pandas的NaN）
    if pd.isna(temperature) or (isinstance(temperature, float) and math.isnan(temperature)):
        temperature = 22  # 使用舒适温度作为默认值
    
    # 确保temperature是数值类型
    try:
        temperature = float(temperature)
        # 再次检查转换后是否为NaN
        if math.isnan(temperature):
            temperature = 22
    except (ValueError, TypeError):
        temperature = 22  # 如果转换失败，使用默认值
    
    # 舒适温度范围：18-26度
    comfort_temp = 22
    
    # 温度影响（二次函数，极端温度影响更大）
    temp_diff = abs(temperature - comfort_temp)
    temp_impact = temp_coefficient * temp_diff ** 2
    
    # 工作日系数
    weekday_factor = 1.0 if not _is_weekend(date) else 0.85
    
    # 季节性因子
    season_factor = _get_season_factor(date)
    
    # 计算最终需求
    demand = base_load * season_factor * weekday_factor + temp_impact * 100
    
    # 添加一些随机波动（±5%）
    noise = np.random.normal(0, 0.02)  # 2%标准差
    demand = demand * (1 + noise)
    
    return round(max(demand, base_load * 0.7), 2)  # 最低不低于基础负荷的70%


class PowerDataFetcher:
    """供电需求数据获取器"""

    def __init__(self):
        self.weather_client = get_weather_client()

    def _get_base_load(self, city_name: str) -> float:
        """获取城市基础负荷"""
        base_load = CITY_BASE_LOADS.get(city_name, DEFAULT_BASE_LOAD)
        
        # 从环境变量读取（如果配置）
        env_key = f"POWER_BASE_LOAD_{city_name.upper()}"
        import os
        env_value = os.getenv(env_key)
        if env_value:
            try:
                base_load = float(env_value)
            except ValueError:
                pass
        
        return base_load

    def _get_temp_coefficient(self) -> float:
        """获取温度影响系数"""
        import os
        env_value = os.getenv("POWER_TEMP_COEFFICIENT")
        if env_value:
            try:
                return float(env_value)
            except ValueError:
                pass
        return DEFAULT_TEMP_COEFFICIENT

    async def fetch_power_data(
        self,
        city_name: str,
        start_date: str,
        end_date: str,
        historical_days: Optional[int] = None,
    ):
        """
        获取供电需求数据（基于天气数据生成）
        
        Args:
            city_name: 城市名称，如"北京"
            start_date: 开始日期，如 "20240101" 或 "2024-01-01"
            end_date: 结束日期，如 "20250101" 或 "2025-01-01"
            historical_days: 历史天数（如果指定，会获取更多历史数据用于训练）
        
        Returns:
            标准化的 DataFrame，包含 ds (日期) 和 y (供电需求MW) 列
        """
        # 标准化日期格式（添加时区信息）
        try:
            if len(start_date) == 8:  # YYYYMMDD
                start_dt = datetime.strptime(start_date, "%Y%m%d").replace(tzinfo=BEIJING_TZ)
            else:  # YYYY-MM-DD
                start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=BEIJING_TZ)
            
            if len(end_date) == 8:  # YYYYMMDD
                end_dt = datetime.strptime(end_date, "%Y%m%d").replace(tzinfo=BEIJING_TZ)
            else:  # YYYY-MM-DD
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=BEIJING_TZ)
        except ValueError as e:
            raise ValueError(f"日期格式错误: {start_date} 或 {end_date}")

        # 计算需要获取的历史天数
        now = datetime.now(BEIJING_TZ)
        if historical_days is None:
            # 默认获取从开始日期到结束日期的数据
            days_diff = (end_dt - start_dt).days + 1
            historical_days = max(days_diff, 10)  # 至少10天
        
        # 限制历史天数（Open-Meteo最多支持92天历史数据）
        historical_days = min(historical_days, 92)
        
        # 确保end_dt有时区信息
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=BEIJING_TZ)
        
        # 计算未来天数
        forecast_days = max((end_dt - now).days + 1, 0)
        forecast_days = min(forecast_days, 14)  # 最多14天
        
        # 获取天气数据（历史+未来）
        # 使用combined API一次性获取，避免日期范围问题
        weather_df = await self.weather_client.fetch_combined_weather(
            city_name,
            historical_days=historical_days,
            forecast_days=forecast_days,
        )

        if weather_df.empty:
            raise ValueError(f"未能获取到 {city_name} 的天气数据")

        # 获取基础负荷和系数
        base_load = self._get_base_load(city_name)
        temp_coefficient = self._get_temp_coefficient()

        # 生成供电需求数据
        power_demands = []
        for _, row in weather_df.iterrows():
            # 检查日期是否有效
            date_val = row.get("date")
            if pd.isna(date_val):
                continue
            
            date = pd.to_datetime(date_val).to_pydatetime()
            # 确保date有时区信息
            if date.tzinfo is None:
                date = date.replace(tzinfo=BEIJING_TZ)
            
            # 检查温度是否有效
            temperature = row.get("temperature")
            if pd.isna(temperature):
                # 如果温度缺失，跳过这条记录或使用默认值
                print(f"[PowerData] 警告: 日期 {date.date()} 的温度数据缺失，跳过")
                continue
            
            # 只生成指定日期范围内的数据
            if start_dt <= date <= end_dt:
                try:
                    demand = generate_power_demand(
                        base_load, temperature, date, temp_coefficient
                    )
                    power_demands.append({
                        "ds": date,
                        "y": demand,
                        "temperature": float(temperature),
                        "humidity": float(row.get("humidity", 0)) if not pd.isna(row.get("humidity")) else 0,
                    })
                except Exception as e:
                    print(f"[PowerData] 警告: 生成日期 {date.date()} 的供电需求失败: {e}")
                    continue

        if not power_demands:
            raise ValueError(f"日期范围内没有生成供电需求数据: {start_date} ~ {end_date}")

        # 转换为DataFrame
        result_df = pd.DataFrame(power_demands)
        result_df = result_df.sort_values("ds").reset_index(drop=True)

        if len(result_df) > 0:
            print(
                f"[PowerData] 供电需求数据生成: {city_name} {len(result_df)} 条, "
                f"{result_df['ds'].min().date()} ~ {result_df['ds'].max().date()}"
            )
        else:
            print(f"[PowerData] 警告: 未生成任何供电需求数据")

        return result_df[["ds", "y"]], weather_df  # 返回供电数据和天气数据

    @staticmethod
    def prepare(df: pd.DataFrame, target_column: str = "y") -> pd.DataFrame:
        """
        将原始数据转换为标准时序格式 (ds, y)
        
        Args:
            df: 原始数据 DataFrame（应该已经包含 ds 和 y 列）
            target_column: 目标值列名（默认 "y"，通常不需要修改）
        
        Returns:
            标准化的 DataFrame，包含 ds (日期) 和 y (目标值) 列
        """
        # 如果已经是标准格式，直接返回
        if "ds" in df.columns and "y" in df.columns:
            result = df[["ds", "y"]].copy()
            result = result.sort_values("ds").drop_duplicates("ds").reset_index(drop=True)
            print(f"✅ 数据准备: {len(result)} 条, {result['ds'].min().date()} ~ {result['ds'].max().date()}")
            return result

        # 否则尝试检测列
        date_col = None
        for col in ["日期", "date", "Date", "ds"]:
            if col in df.columns:
                date_col = col
                break

        value_col = None
        for col in [target_column, "close", "Close", "收盘", "y", "demand", "power"]:
            if col in df.columns:
                value_col = col
                break

        if not date_col or not value_col:
            raise ValueError(f"无法识别列: {list(df.columns)}")

        # 标准化格式
        result = pd.DataFrame({
            "ds": pd.to_datetime(df[date_col]),
            "y": df[value_col].astype(float)
        }).sort_values("ds").drop_duplicates("ds").reset_index(drop=True)

        print(f"✅ 数据准备: {len(result)} 条, {result['ds'].min().date()} ~ {result['ds'].max().date()}")
        return result
