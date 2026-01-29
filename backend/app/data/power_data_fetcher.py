"""
供电需求数据获取与预处理模块
============================

基于天气数据生成Mock供电需求数据，并进行标准化预处理

架构:
- fetch_power_data(): 获取天气数据并生成供电需求
- fetch_historical_same_period(): 获取近N年同期数据用于预测
- generate_power_demand(): Mock供电需求生成算法
- prepare(): 数据预处理为标准时序格式 (ds, y)
"""

import pandas as pd
import numpy as np
import math
from typing import Optional, Tuple
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


def _is_weekend(date: datetime) -> bool:
    """判断是否为周末"""
    return date.weekday() >= 5


def generate_power_demand(
    base_load: float,
    temperature: float,
    date: datetime,
    humidity: Optional[float] = None,
) -> float:
    """
    生成供电需求（Mock算法，乘法模型）

    所有影响因子都是接近 1.0 的系数，对基础负荷做比例调整：
    demand = base_load × weekday_factor × season_factor × temp_factor × humidity_factor × (1 + noise)

    Args:
        base_load: 基础负荷（MW）
        temperature: 当前温度（摄氏度）
        date: 日期
        humidity: 当前湿度（百分比，0-100）

    Returns:
        供电需求（MW）
    """
    # 处理缺失值：如果temperature是NaN或None，使用默认值
    if temperature is None:
        temperature = 22
    if pd.isna(temperature) or (isinstance(temperature, float) and math.isnan(temperature)):
        temperature = 22
    try:
        temperature = float(temperature)
        if math.isnan(temperature):
            temperature = 22
    except (ValueError, TypeError):
        temperature = 22

    # 处理湿度缺失值
    if humidity is None:
        humidity = 50
    if pd.isna(humidity) or (isinstance(humidity, float) and math.isnan(humidity)):
        humidity = 50
    try:
        humidity = float(humidity)
        if math.isnan(humidity):
            humidity = 50
    except (ValueError, TypeError):
        humidity = 50

    # --- 温度因子：tanh 平滑衰减 ---
    # 22°C 为舒适温度，偏离越多用电越高，渐近上限 ~15%
    temp_diff = abs(temperature - 22)
    temp_factor = 1.0 + 0.15 * math.tanh(temp_diff / 20.0)

    # --- 湿度因子：舒适区内无影响，区外 tanh 平滑 ---
    # 40-60% 为舒适区，极端湿度渐近上限 ~4%
    if humidity < 40:
        humidity_diff = 40 - humidity
    elif humidity > 60:
        humidity_diff = humidity - 60
    else:
        humidity_diff = 0
    humidity_factor = 1.0 + 0.04 * math.tanh(humidity_diff / 30.0)

    # --- 季节因子：cos双峰（冬夏高、春秋低）---
    day_of_year = date.timetuple().tm_yday
    t = day_of_year / 365.0
    season_factor = 1.0 + 0.05 * math.cos(4 * math.pi * t) + 0.015 * math.cos(2 * math.pi * (t - 0.5))

    # --- 工作日因子 ---
    weekday_factor = 1.0 if not _is_weekend(date) else 0.90

    # --- 确定性噪声（同一天同一城市返回相同值）---
    seed = hash((date.year, date.month, date.day, round(base_load))) % (2**31)
    rng = np.random.RandomState(seed)
    noise = rng.normal(0, 0.008)

    # --- 乘法合成 ---
    demand = base_load * weekday_factor * season_factor * temp_factor * humidity_factor * (1 + noise)

    return round(demand, 2)


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

    async def fetch_power_data(
        self,
        city_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        historical_days: Optional[int] = None,
        forecast_days: Optional[int] = None,
    ):
        """
        获取供电需求数据（基于天气数据生成）
        
        Args:
            city_name: 城市名称，如"北京"
            start_date: 开始日期，如 "20240101" 或 "2024-01-01"（可选，默认使用近未来模式）
            end_date: 结束日期，如 "20250101" 或 "2025-01-01"（可选，默认使用近未来模式）
            historical_days: 历史天数（默认30天，用于近未来模式）
            forecast_days: 未来天数（默认7天，用于近未来模式）
        
        Returns:
            标准化的 DataFrame，包含 ds (日期) 和 y (供电需求MW) 列
        """
        now = datetime.now(BEIJING_TZ)
        
        # 如果未指定日期范围，使用"近未来"模式（历史30天+未来7天）
        if start_date is None or end_date is None:
            if historical_days is None:
                historical_days = 30  # 默认历史30天
            if forecast_days is None:
                forecast_days = 7  # 默认未来7天
            
            start_dt = now - timedelta(days=historical_days)
            end_dt = now + timedelta(days=forecast_days)
        else:
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
        if historical_days is None:
            # 计算从开始日期到现在的天数
            days_diff = (now - start_dt).days + 1
            historical_days = max(days_diff, 10)  # 至少10天

        # 确保end_dt有时区信息
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=BEIJING_TZ)

        # 计算未来天数
        if forecast_days is None:
            forecast_days = max((end_dt - now).days + 1, 0)
        forecast_days = min(forecast_days, 14)  # 最多14天

        # 获取天气数据
        if historical_days > 92:
            # 超过92天：用 Archive API 获取老数据 + combined API 获取近期数据
            recent_days = 92
            archive_start = (now - timedelta(days=historical_days)).strftime("%Y-%m-%d")
            archive_end = (now - timedelta(days=recent_days + 1)).strftime("%Y-%m-%d")

            try:
                archive_weather = await self.weather_client.fetch_archive_weather(
                    city_name, archive_start, archive_end
                )
            except Exception as e:
                print(f"[PowerData] Archive API 获取失败，回退到92天: {e}")
                archive_weather = pd.DataFrame()

            recent_weather = await self.weather_client.fetch_combined_weather(
                city_name,
                historical_days=recent_days,
                forecast_days=forecast_days,
            )

            if not archive_weather.empty and not recent_weather.empty:
                # 统一列名后合并
                archive_weather["date"] = pd.to_datetime(archive_weather["date"])
                recent_weather["date"] = pd.to_datetime(recent_weather["date"])
                # 去重：以 recent_weather 为准（更准确）
                weather_df = pd.concat([archive_weather, recent_weather], ignore_index=True)
                weather_df = weather_df.drop_duplicates(subset=["date"], keep="last")
                weather_df = weather_df.sort_values("date").reset_index(drop=True)
            elif not recent_weather.empty:
                weather_df = recent_weather
            else:
                weather_df = archive_weather
        else:
            # 92天以内：直接用 combined API
            weather_df = await self.weather_client.fetch_combined_weather(
                city_name,
                historical_days=historical_days,
                forecast_days=forecast_days,
            )

        if weather_df.empty:
            raise ValueError(f"未能获取到 {city_name} 的天气数据")

        # 获取基础负荷
        base_load = self._get_base_load(city_name)

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
            
            # 获取湿度数据
            humidity = row.get("humidity")
            if pd.isna(humidity):
                humidity = None  # 传递给函数处理默认值
            
            # 只生成指定日期范围内的数据
            if start_dt <= date <= end_dt:
                try:
                    demand = generate_power_demand(
                        base_load=base_load,
                        temperature=temperature,
                        date=date,
                        humidity=humidity,
                    )
                    power_demands.append({
                        "ds": date,
                        "y": demand,
                        "temperature": float(temperature),
                        "humidity": float(humidity) if humidity is not None and not pd.isna(humidity) else 50.0,
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


async def fetch_historical_same_period(
    city_name: str,
    target_start: datetime,
    target_end: datetime,
    years_back: int = 2
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    获取近N年同期数据并平均迁移到目标日期范围

    用于基于历史同期数据的预测方法，替代纯机器学习预测。

    Args:
        city_name: 城市名称，如"北京"
        target_start: 目标预测开始日期
        target_end: 目标预测结束日期
        years_back: 回溯年数（默认2年）

    Returns:
        (avg_power, avg_weather) 元组:
        - avg_power: DataFrame，包含 ds（目标日期）和 y（平均供电量）
        - avg_weather: DataFrame，包含历史同期平均天气数据
    """
    weather_client = get_weather_client()
    base_load = CITY_BASE_LOADS.get(city_name, DEFAULT_BASE_LOAD)

    all_power_data = []
    all_weather_data = []

    # 确保日期有时区信息
    if target_start.tzinfo is None:
        target_start = target_start.replace(tzinfo=BEIJING_TZ)
    if target_end.tzinfo is None:
        target_end = target_end.replace(tzinfo=BEIJING_TZ)

    for year_offset in range(1, years_back + 1):
        # 计算历史同期日期
        hist_start = target_start - timedelta(days=365 * year_offset)
        hist_end = target_end - timedelta(days=365 * year_offset)

        try:
            # 获取历史天气（使用 Archive API）
            hist_weather = await weather_client.fetch_archive_weather(
                city_name,
                hist_start.strftime("%Y-%m-%d"),
                hist_end.strftime("%Y-%m-%d")
            )

            if hist_weather.empty:
                print(f"[历史同期] {year_offset}年前无天气数据，跳过")
                continue

            # 基于历史天气生成供电量
            year_power = []
            for _, row in hist_weather.iterrows():
                # 确保日期是 datetime 类型
                hist_date = pd.to_datetime(row["date"])
                if hist_date.tzinfo is None:
                    hist_date = hist_date.tz_localize(BEIJING_TZ)

                demand = generate_power_demand(
                    base_load=base_load,
                    temperature=row["temperature"],
                    date=hist_date,
                    humidity=row.get("humidity")
                )

                # 计算相对于目标日期的偏移天数
                days_from_start = (hist_date.date() - hist_start.date()).days
                target_date = target_start + timedelta(days=days_from_start)

                year_power.append({
                    "ds": target_date,
                    "y": demand,
                    "year_offset": year_offset
                })

            all_power_data.extend(year_power)

            # 记录天气数据（用于后续调整）
            weather_copy = hist_weather.copy()
            weather_copy["year_offset"] = year_offset
            weather_copy["target_date"] = weather_copy["date"].apply(
                lambda d: target_start + timedelta(days=(pd.to_datetime(d).date() - hist_start.date()).days)
            )
            all_weather_data.append(weather_copy)

            print(f"[历史同期] 获取 {year_offset} 年前数据成功: {len(year_power)} 天")

        except Exception as e:
            print(f"[历史同期] 获取 {year_offset} 年前数据失败: {e}")
            continue

    if not all_power_data:
        raise ValueError(f"无法获取 {city_name} 的任何历史同期数据")

    # 按目标日期分组平均
    power_df = pd.DataFrame(all_power_data)
    avg_power = power_df.groupby("ds")["y"].mean().reset_index()
    avg_power = avg_power.sort_values("ds").reset_index(drop=True)

    # 合并天气数据并计算平均
    if all_weather_data:
        weather_df = pd.concat(all_weather_data, ignore_index=True)
        avg_weather = weather_df.groupby("target_date").agg({
            "temperature": "mean",
            "humidity": "mean"
        }).reset_index()
        avg_weather.columns = ["date", "temperature", "humidity"]
        avg_weather = avg_weather.sort_values("date").reset_index(drop=True)
    else:
        avg_weather = pd.DataFrame(columns=["date", "temperature", "humidity"])

    print(f"[历史同期] 平均后数据: {len(avg_power)} 天, 基于 {years_back} 年同期")

    return avg_power, avg_weather
