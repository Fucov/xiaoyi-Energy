"""
PMI数据获取客户端
=================

使用AKShare获取中国PMI（采购经理人指数）数据

PMI是工业活动代理变量，用于分析工业活动对供电需求的影响
"""

import pandas as pd
import numpy as np
from typing import Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# 北京时区
BEIJING_TZ = ZoneInfo("Asia/Shanghai")


class PMIClient:
    """PMI数据客户端"""

    def __init__(self):
        self._pmi_cache: Optional[pd.DataFrame] = None

    def _fetch_pmi_data(self) -> pd.DataFrame:
        """
        从AKShare获取PMI数据

        Returns:
            DataFrame，包含日期和PMI值
        """
        try:
            import akshare as ak
            
            # 获取中国PMI数据
            # AKShare的PMI数据通常包含多个指标，我们使用制造业PMI
            df = ak.macro_china_pmi()
            
            # 检查数据格式，AKShare的PMI数据格式可能因版本而异
            # 通常包含日期列和PMI值列
            # 如果列名不同，需要适配
            
            # 尝试识别日期列
            date_col = None
            for col in ["日期", "date", "Date", "时间", "time"]:
                if col in df.columns:
                    date_col = col
                    break
            
            # 尝试识别PMI列
            pmi_col = None
            for col in ["PMI", "pmi", "制造业PMI", "制造业pmi", "PMI-制造业"]:
                if col in df.columns:
                    pmi_col = col
                    break
            
            if date_col is None or pmi_col is None:
                # 如果无法识别列，尝试使用第一列作为日期，第二列作为PMI
                if len(df.columns) >= 2:
                    date_col = df.columns[0]
                    pmi_col = df.columns[1]
                else:
                    raise ValueError(f"无法识别PMI数据列: {list(df.columns)}")

            # 提取日期和PMI值
            # 处理中文日期格式（如"2025年12月份"）
            def parse_chinese_date(date_str):
                try:
                    # 尝试解析中文格式：2025年12月份 -> 2025-12-01
                    import re
                    match = re.match(r'(\d{4})年(\d{1,2})月份?', str(date_str))
                    if match:
                        year = int(match.group(1))
                        month = int(match.group(2))
                        return pd.Timestamp(year=year, month=month, day=1)
                    # 尝试标准格式
                    return pd.to_datetime(date_str)
                except:
                    return pd.NaT
            
            dates = df[date_col].apply(parse_chinese_date)
            
            result_df = pd.DataFrame({
                "date": dates,
                "pmi": pd.to_numeric(df[pmi_col], errors='coerce')
            })

            # 移除无效值
            result_df = result_df.dropna(subset=["date", "pmi"])
            result_df = result_df.sort_values("date").reset_index(drop=True)

            print(f"[PMI] 获取PMI数据: {len(result_df)} 条")
            return result_df

        except Exception as e:
            print(f"[PMI] 获取PMI数据失败: {str(e)}")
            import traceback
            traceback.print_exc()
            # 返回空DataFrame
            return pd.DataFrame(columns=["date", "pmi"])

    def _interpolate_pmi(
        self, 
        pmi_df: pd.DataFrame, 
        target_dates: pd.DatetimeIndex
    ) -> pd.DataFrame:
        """
        对PMI数据进行插值，填充缺失日期

        Args:
            pmi_df: 原始PMI数据
            target_dates: 目标日期范围

        Returns:
            插值后的DataFrame
        """
        if pmi_df.empty:
            # 如果没有PMI数据，使用默认值50（PMI的中性值）
            print(f"[PMI] 警告: PMI数据为空，使用默认值50.0")
            return pd.DataFrame({
                "date": target_dates,
                "pmi": [50.0] * len(target_dates)
            })

        # 创建完整的日期范围
        full_dates = pd.DataFrame({
            "date": target_dates
        })

        # 合并数据
        merged = pd.merge(
            full_dates,
            pmi_df,
            on="date",
            how="left"
        )

        # 检查原始PMI数据是否有有效值
        valid_pmi_count = merged["pmi"].notna().sum()
        if valid_pmi_count == 0:
            print(f"[PMI] 警告: 合并后没有有效的PMI值，使用默认值50.0")
            merged["pmi"] = 50.0
        else:
            # 使用线性插值填充缺失值
            merged["pmi"] = merged["pmi"].interpolate(method="linear")

            # 如果开头或结尾仍有缺失值，使用前向填充和后向填充
            merged["pmi"] = merged["pmi"].ffill().bfill()

            # 如果仍然有缺失值，使用默认值50
            merged["pmi"] = merged["pmi"].fillna(50.0)
            
            # 检查插值后的数据是否有变化
            pmi_std = merged["pmi"].std()
            if pmi_std < 0.01:
                print(f"[PMI] 警告: 插值后PMI数据几乎为常数（标准差={pmi_std:.2f}），原始数据可能不足")

        return merged

    def fetch_pmi_data(
        self,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        获取指定日期范围内的PMI数据

        Args:
            start_date: 开始日期，格式 "YYYY-MM-DD" 或 "YYYYMMDD"
            end_date: 结束日期，格式 "YYYY-MM-DD" 或 "YYYYMMDD"

        Returns:
            DataFrame，包含以下列：
            - date: 日期
            - pmi: PMI值（已插值）
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

        # 获取PMI数据（带缓存）
        if self._pmi_cache is None:
            self._pmi_cache = self._fetch_pmi_data()

        # 创建目标日期范围
        target_dates = pd.date_range(
            start=start_dt.date(),
            end=end_dt.date(),
            freq="D"
        )

        # 如果缓存为空，直接返回插值后的默认值
        if self._pmi_cache.empty:
            result_df = pd.DataFrame({
                "date": target_dates,
                "pmi": [50.0] * len(target_dates)
            })
        else:
            # 确保日期列是datetime类型（移除时区以便比较）
            pmi_cache_clean = self._pmi_cache.copy()
            if pmi_cache_clean["date"].dt.tz is not None:
                pmi_cache_clean["date"] = pmi_cache_clean["date"].dt.tz_localize(None)
            
            # 移除start_dt和end_dt的时区信息以便比较
            start_dt_naive = start_dt.replace(tzinfo=None) if start_dt.tzinfo else start_dt
            end_dt_naive = end_dt.replace(tzinfo=None) if end_dt.tzinfo else end_dt
            
            # 过滤出日期范围内的数据
            date_mask = (pmi_cache_clean["date"] >= start_dt_naive) & \
                       (pmi_cache_clean["date"] <= end_dt_naive)
            filtered_pmi = pmi_cache_clean[date_mask].copy()

            # 如果需要更多历史数据用于插值，扩展范围
            if len(filtered_pmi) < len(target_dates) * 0.5:
                # 扩展前后各30天用于插值
                extended_start = start_dt_naive - timedelta(days=30)
                extended_end = end_dt_naive + timedelta(days=30)
                extended_mask = (pmi_cache_clean["date"] >= extended_start) & \
                                (pmi_cache_clean["date"] <= extended_end)
                filtered_pmi = pmi_cache_clean[extended_mask].copy()

            # 插值到目标日期
            result_df = self._interpolate_pmi(filtered_pmi, target_dates)

        # 确保日期格式一致
        result_df["date"] = pd.to_datetime(result_df["date"])
        result_df = result_df.sort_values("date").reset_index(drop=True)

        # 检查PMI数据是否有变化
        pmi_values = result_df["pmi"].values
        pmi_unique = np.unique(pmi_values)
        pmi_std = np.std(pmi_values)
        
        print(f"[PMI] 返回PMI数据: {len(result_df)} 天 ({start_date} ~ {end_date})")
        print(f"[PMI] PMI值范围: {pmi_values.min():.2f} ~ {pmi_values.max():.2f}, 标准差: {pmi_std:.2f}, 唯一值数量: {len(pmi_unique)}")
        
        if pmi_std < 0.01:
            print(f"[PMI] 警告: PMI数据几乎为常数（标准差={pmi_std:.2f}），可能无法计算有效的相关性")
        
        return result_df


# 单例实例
_pmi_client: Optional[PMIClient] = None


def get_pmi_client() -> PMIClient:
    """获取PMI客户端单例"""
    global _pmi_client
    if _pmi_client is None:
        _pmi_client = PMIClient()
    return _pmi_client
