"""
节假日数据获取客户端
====================

封装节假日API调用，获取中国节假日数据并计算前后效应

API文档: https://timor.tech/api/holiday
"""

import httpx
import pandas as pd
import asyncio
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# 北京时区
BEIJING_TZ = ZoneInfo("Asia/Shanghai")


class HolidayClient:
    """节假日数据客户端"""

    BASE_URL = "https://timor.tech/api/holiday"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self._holiday_cache: Dict[str, Dict] = {}  # 缓存节假日数据

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    async def _fetch_holiday_info(self, date: datetime) -> Optional[Dict]:
        """
        获取指定日期的节假日信息

        Args:
            date: 日期

        Returns:
            节假日信息字典，如果不是节假日则返回None
        """
        date_str = date.strftime("%Y-%m-%d")
        
        # 检查缓存
        if date_str in self._holiday_cache:
            return self._holiday_cache[date_str]

        try:
            url = f"{self.BASE_URL}/info"
            params = {"date": date_str}
            
            response = await self.client.get(url, params=params)
            
            # 处理429错误（请求频率限制）
            if response.status_code == 429:
                # 等待一段时间后重试
                await asyncio.sleep(0.5)
                response = await self.client.get(url, params=params)
            
            response.raise_for_status()
            data = response.json()

            # API返回格式: {"code": 0, "holiday": {...} 或 null}
            if data.get("code") == 0:
                holiday_info = data.get("holiday")
                if holiday_info:
                    # 是节假日
                    result = {
                        "is_holiday": True,
                        "holiday_name": holiday_info.get("name", ""),
                        "holiday_type": holiday_info.get("type", ""),
                    }
                else:
                    # 不是节假日
                    result = {
                        "is_holiday": False,
                        "holiday_name": "",
                        "holiday_type": "",
                    }
                
                # 缓存结果
                self._holiday_cache[date_str] = result
                return result
            else:
                # API返回错误
                print(f"[Holiday] API返回错误: {data}")
                return None

        except httpx.HTTPStatusError as e:
            print(f"[Holiday] HTTP错误: {e.response.status_code}")
            return None
        except Exception as e:
            print(f"[Holiday] 获取节假日信息失败: {str(e)}")
            return None

    def _calculate_holiday_effects(
        self, 
        date: datetime, 
        holiday_dates: Set[str]
    ) -> Dict[str, int]:
        """
        计算节假日前后效应

        Args:
            date: 当前日期
            holiday_dates: 节假日日期集合（格式：YYYY-MM-DD）

        Returns:
            {"before_effect": int, "after_effect": int}
            before_effect: 节前效应，-2到0（-2表示节前2天，-1表示节前1天，0表示不是节前）
            after_effect: 节后效应，0到2（0表示不是节后，1表示节后1天，2表示节后2天）
        """
        date_str = date.strftime("%Y-%m-%d")
        
        before_effect = 0
        after_effect = 0

        # 检查节前效应（检查未来1-2天是否是节假日）
        for i in range(1, 3):
            future_date = date + timedelta(days=i)
            future_str = future_date.strftime("%Y-%m-%d")
            if future_str in holiday_dates:
                before_effect = -i  # 负数表示节前
                break

        # 检查节后效应（检查过去1-2天是否是节假日）
        for i in range(1, 3):
            past_date = date - timedelta(days=i)
            past_str = past_date.strftime("%Y-%m-%d")
            if past_str in holiday_dates:
                after_effect = i  # 正数表示节后
                break

        return {
            "before_effect": before_effect,
            "after_effect": after_effect
        }

    async def fetch_holiday_data(
        self,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        获取指定日期范围内的节假日数据（含前后效应）

        Args:
            start_date: 开始日期，格式 "YYYY-MM-DD" 或 "YYYYMMDD"
            end_date: 结束日期，格式 "YYYY-MM-DD" 或 "YYYYMMDD"

        Returns:
            DataFrame，包含以下列：
            - date: 日期
            - is_holiday: 是否为节假日 (bool)
            - holiday_name: 节假日名称
            - before_effect: 节前效应 (-2到0)
            - after_effect: 节后效应 (0到2)
            - holiday_score: 综合得分 (0-2)
        """
        # 标准化日期格式
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

        # 扩展日期范围以计算前后效应（前后各加2天）
        extended_start = start_dt - timedelta(days=2)
        extended_end = end_dt + timedelta(days=2)

        # 获取扩展范围内的所有节假日（批量获取，减少API调用）
        holiday_dates: Set[str] = set()
        current_date = extended_start
        
        # 添加延迟以避免429错误
        batch_size = 5
        batch_count = 0
        
        while current_date <= extended_end:
            holiday_info = await self._fetch_holiday_info(current_date)
            if holiday_info and holiday_info.get("is_holiday"):
                date_str = current_date.strftime("%Y-%m-%d")
                holiday_dates.add(date_str)
            current_date += timedelta(days=1)
            
            # 每5个请求后等待一下
            batch_count += 1
            if batch_count >= batch_size:
                await asyncio.sleep(0.3)
                batch_count = 0

        # 生成结果数据（批量获取，减少API调用）
        result_data = []
        current_date = start_dt
        batch_count = 0
        batch_size = 5  # 每5个请求等待一次
        
        while current_date <= end_dt:
            date_str = current_date.strftime("%Y-%m-%d")
            
            # 获取节假日信息
            holiday_info = await self._fetch_holiday_info(current_date)
            if holiday_info is None:
                # API失败，使用降级方案（假设不是节假日）
                is_holiday = False
                holiday_name = ""
            else:
                is_holiday = holiday_info.get("is_holiday", False)
                holiday_name = holiday_info.get("holiday_name", "")

            # 计算前后效应
            effects = self._calculate_holiday_effects(current_date, holiday_dates)
            before_effect = effects["before_effect"]
            after_effect = effects["after_effect"]

            # 计算综合得分
            # 基础分：节假日本身 = 1
            # 节前效应：每1天 = 0.5
            # 节后效应：每1天 = 0.5
            holiday_score = (1.0 if is_holiday else 0.0) + \
                           (0.5 * abs(before_effect)) + \
                           (0.5 * abs(after_effect))

            result_data.append({
                "date": current_date,
                "is_holiday": is_holiday,
                "holiday_name": holiday_name,
                "before_effect": before_effect,
                "after_effect": after_effect,
                "holiday_score": round(holiday_score, 2)
            })

            current_date += timedelta(days=1)
            
            # 每5个请求后等待一下，避免429错误
            batch_count += 1
            if batch_count >= batch_size:
                await asyncio.sleep(0.3)
                batch_count = 0

        df = pd.DataFrame(result_data)
        df = df.sort_values("date").reset_index(drop=True)

        print(f"[Holiday] 获取节假日数据: {len(df)} 天 ({start_date} ~ {end_date})")
        return df


# 单例实例
_holiday_client: Optional[HolidayClient] = None


def get_holiday_client() -> HolidayClient:
    """获取节假日客户端单例"""
    global _holiday_client
    if _holiday_client is None:
        _holiday_client = HolidayClient()
    return _holiday_client
