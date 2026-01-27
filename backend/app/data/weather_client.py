"""
天气数据获取客户端
==================

封装 Open-Meteo API 调用，获取历史天气和未来天气预报

API文档: https://open-meteo.com/en/docs
"""

import httpx
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# 北京时区
BEIJING_TZ = ZoneInfo("Asia/Shanghai")

# 城市坐标映射（纬度, 经度）
CITY_COORDINATES = {
    "北京": (39.9042, 116.4074),
    "上海": (31.2304, 121.4737),
    "广州": (23.1291, 113.2644),
    "深圳": (22.5431, 114.0579),
    "杭州": (30.2741, 120.1551),
    "成都": (30.6624, 104.0633),
    "武汉": (30.5928, 114.3055),
    "西安": (34.3416, 108.9398),
    "南京": (32.0603, 118.7969),
    "天津": (39.3434, 117.3616),
}


class WeatherClient:
    """Open-Meteo 天气数据客户端"""

    BASE_URL = "https://api.open-meteo.com/v1"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    def _get_city_coordinates(self, city_name: str) -> tuple:
        """
        获取城市坐标

        Args:
            city_name: 城市名称，如"北京"

        Returns:
            (latitude, longitude) 元组

        Raises:
            ValueError: 如果城市名称不支持
        """
        city_name = city_name.strip()
        if city_name not in CITY_COORDINATES:
            raise ValueError(
                f"不支持的城市: {city_name}。支持的城市: {', '.join(CITY_COORDINATES.keys())}"
            )
        return CITY_COORDINATES[city_name]

    async def fetch_historical_weather(
        self,
        city_name: str,
        days: int = 10,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取历史天气数据

        Args:
            city_name: 城市名称
            days: 获取过去多少天的数据（默认10天，最多92天）
            end_date: 结束日期（YYYY-MM-DD），默认今天

        Returns:
            DataFrame，包含日期、温度、湿度等字段
        """
        lat, lon = self._get_city_coordinates(city_name)

        if end_date is None:
            end_date = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
        else:
            # 确保日期格式正确
            try:
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"日期格式错误，应为 YYYY-MM-DD: {end_date}")

        # Open-Meteo forecast API 限制：最多92天历史数据（使用past_days参数）
        # 限制days不超过92天
        days = min(days, 92)
        
        # 使用 forecast API 的 past_days 参数获取历史数据
        # 这样可以避免日期范围限制问题
        url = f"{self.BASE_URL}/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "past_days": days,  # 使用past_days参数，而不是start_date/end_date
            "hourly": "temperature_2m,relative_humidity_2m,weather_code",
            "timezone": "Asia/Shanghai",
        }

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # 解析数据
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            temperatures = hourly.get("temperature_2m", [])
            humidities = hourly.get("relative_humidity_2m", [])
            weather_codes = hourly.get("weather_code", [])

            # 转换为DataFrame
            df = pd.DataFrame({
                "datetime": pd.to_datetime(times),
                "temperature": temperatures,
                "humidity": humidities,
                "weather_code": weather_codes,
            })

            # 过滤掉无效数据（NaN值）
            df = df.dropna(subset=["temperature", "datetime"])
            
            if len(df) == 0:
                raise ValueError(f"天气API返回的数据中没有有效的温度数据")
            
            # 按日期聚合（取每日平均值）
            df["date"] = df["datetime"].dt.date
            daily_df = df.groupby("date").agg({
                "temperature": "mean",
                "humidity": "mean",
                "weather_code": "first",  # 使用第一个值作为代表
            }).reset_index()

            # 再次过滤NaN值
            daily_df = daily_df.dropna(subset=["temperature", "date"])
            
            if len(daily_df) == 0:
                raise ValueError(f"聚合后的天气数据中没有有效数据")
            
            daily_df["date"] = pd.to_datetime(daily_df["date"])
            daily_df = daily_df.sort_values("date").reset_index(drop=True)

            print(f"[Weather] 获取 {city_name} 历史天气: {len(daily_df)} 天 ({start_date} ~ {end_date})")
            return daily_df

        except httpx.HTTPStatusError as e:
            error_msg = f"天气API请求失败: {e.response.status_code} - {e.response.text}"
            print(f"[Weather] Error: {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"获取天气数据失败: {str(e)}"
            print(f"[Weather] Error: {error_msg}")
            import traceback
            traceback.print_exc()
            raise ValueError(error_msg)

    async def fetch_forecast_weather(
        self,
        city_name: str,
        days: int = 7,
    ) -> pd.DataFrame:
        """
        获取未来天气预报

        Args:
            city_name: 城市名称
            days: 预测未来多少天（默认7天，最多14天）

        Returns:
            DataFrame，包含日期、温度、湿度等字段
        """
        lat, lon = self._get_city_coordinates(city_name)
        days = min(days, 14)  # Open-Meteo最多支持14天

        url = f"{self.BASE_URL}/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "forecast_days": days,
            "hourly": "temperature_2m,relative_humidity_2m,weather_code",
            "timezone": "Asia/Shanghai",
        }

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # 解析数据
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            temperatures = hourly.get("temperature_2m", [])
            humidities = hourly.get("relative_humidity_2m", [])
            weather_codes = hourly.get("weather_code", [])

            # 转换为DataFrame
            df = pd.DataFrame({
                "datetime": pd.to_datetime(times),
                "temperature": temperatures,
                "humidity": humidities,
                "weather_code": weather_codes,
            })

            # 过滤掉无效数据（NaN值）
            df = df.dropna(subset=["temperature", "datetime"])
            
            if len(df) == 0:
                raise ValueError(f"天气API返回的数据中没有有效的温度数据")
            
            # 按日期聚合（取每日平均值）
            df["date"] = df["datetime"].dt.date
            daily_df = df.groupby("date").agg({
                "temperature": "mean",
                "humidity": "mean",
                "weather_code": "first",
            }).reset_index()

            # 再次过滤NaN值
            daily_df = daily_df.dropna(subset=["temperature", "date"])
            
            if len(daily_df) == 0:
                raise ValueError(f"聚合后的天气数据中没有有效数据")
            
            daily_df["date"] = pd.to_datetime(daily_df["date"])
            daily_df = daily_df.sort_values("date").reset_index(drop=True)

            print(f"[Weather] 获取 {city_name} 天气预报: {len(daily_df)} 天")
            return daily_df

        except httpx.HTTPStatusError as e:
            raise ValueError(f"天气API请求失败: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise ValueError(f"获取天气预报失败: {str(e)}")

    async def fetch_combined_weather(
        self,
        city_name: str,
        historical_days: int = 10,
        forecast_days: int = 7,
    ) -> pd.DataFrame:
        """
        获取历史+未来天气数据（合并）

        Args:
            city_name: 城市名称
            historical_days: 历史天数（最多92天）
            forecast_days: 预测天数（最多14天）

        Returns:
            合并后的DataFrame
        """
        # 限制历史天数
        historical_days = min(historical_days, 92)
        forecast_days = min(forecast_days, 14)
        
        # 使用单个API调用获取历史+未来数据（更高效）
        lat, lon = self._get_city_coordinates(city_name)
        
        url = f"{self.BASE_URL}/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "past_days": historical_days,
            "forecast_days": forecast_days,
            "hourly": "temperature_2m,relative_humidity_2m,weather_code",
            "timezone": "Asia/Shanghai",
        }
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # 解析数据
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            temperatures = hourly.get("temperature_2m", [])
            humidities = hourly.get("relative_humidity_2m", [])
            weather_codes = hourly.get("weather_code", [])

            # 转换为DataFrame
            df = pd.DataFrame({
                "datetime": pd.to_datetime(times),
                "temperature": temperatures,
                "humidity": humidities,
                "weather_code": weather_codes,
            })

            # 按日期聚合（取每日平均值）
            df["date"] = df["datetime"].dt.date
            daily_df = df.groupby("date").agg({
                "temperature": "mean",
                "humidity": "mean",
                "weather_code": "first",
            }).reset_index()

            # 过滤掉无效的温度数据（NaN）
            daily_df = daily_df.dropna(subset=["temperature"])
            
            daily_df["date"] = pd.to_datetime(daily_df["date"])
            daily_df = daily_df.sort_values("date").reset_index(drop=True)

            print(f"[Weather] 获取 {city_name} 历史+未来天气: {len(daily_df)} 天")
            return daily_df

        except httpx.HTTPStatusError as e:
            error_msg = f"天气API请求失败: {e.response.status_code} - {e.response.text}"
            print(f"[Weather] Error: {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"获取天气数据失败: {str(e)}"
            print(f"[Weather] Error: {error_msg}")
            import traceback
            traceback.print_exc()
            raise ValueError(error_msg)


# 单例实例
_weather_client: Optional[WeatherClient] = None


def get_weather_client() -> WeatherClient:
    """获取天气客户端单例"""
    global _weather_client
    if _weather_client is None:
        _weather_client = WeatherClient()
    return _weather_client
