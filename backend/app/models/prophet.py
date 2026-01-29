"""
Prophet 预测模型
================

基于 Facebook Prophet 的时序预测实现
支持传统 Prophet 预测和基于历史同期数据的预测
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from .base import BaseForecaster
from prophet import Prophet
from app.schemas.session_schema import ForecastResult, ForecastMetrics, TimeSeriesPoint


class ProphetForecaster(BaseForecaster):
    """Prophet 时序预测器"""

    def forecast(
        self,
        df: pd.DataFrame,
        horizon: int = 30,
        prophet_params: Dict[str, Any] = None,
        weather_df: Optional[pd.DataFrame] = None
    ) -> ForecastResult:
        """
        使用 Prophet 模型进行时序预测

        Args:
            df: 标准化的时序数据，包含 ds 和 y 列
            horizon: 预测天数
            prophet_params: Prophet 模型参数（可选），支持:
                - changepoint_prior_scale: 趋势变化敏感度 (默认 0.05)
                - seasonality_prior_scale: 季节性强度 (默认 10)
                - changepoint_range: 变点检测范围 (默认 0.8)
            weather_df: 天气数据（可选），包含 date, temperature 列

        Returns:
            ForecastResult: 统一的预测结果
        """
        # 使用传入参数或默认值
        params = prophet_params or {}

        # Prophet不支持带时区的datetime，需要移除时区信息
        df_clean = df[["ds", "y"]].copy()
        if df_clean["ds"].dt.tz is not None:
            df_clean["ds"] = df_clean["ds"].dt.tz_localize(None)

        # 确保数据按日期排序
        df_clean = df_clean.sort_values("ds").reset_index(drop=True)

        # 配置模型
        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True,
            changepoint_prior_scale=params.get("changepoint_prior_scale", 0.05),
            seasonality_prior_scale=params.get("seasonality_prior_scale", 5),  # 降低以减少波动
            changepoint_range=params.get("changepoint_range", 0.8),
        )

        # 处理温度作为外生变量（如果提供了天气数据）
        use_temperature = False
        if weather_df is not None and not weather_df.empty and "temperature" in weather_df.columns:
            df_clean, use_temperature = self._prepare_temperature_data(
                df_clean, weather_df, model
            )

        # 使用全部数据训练
        train_cols = ["ds", "y", "temperature"] if use_temperature else ["ds", "y"]
        model.fit(df_clean[train_cols])

        # 记录训练数据的最后日期
        last_date = df_clean["ds"].max()

        # 生成未来时间点（从训练数据最后一天之后开始）
        future = model.make_future_dataframe(periods=horizon, freq="D")

        # 为未来日期添加温度（如果使用温度特征）
        if use_temperature:
            future = self._add_future_temperature(future, weather_df, df_clean)

        # 预测
        forecast = model.predict(future)

        # 提取预测点（只取未来的点，不需要交易日历过滤）
        pred = forecast[forecast["ds"] > last_date].head(horizon)

        # 计算历史数据的最小值作为下界参考
        historical_min = df_clean["y"].min()
        lower_bound = max(historical_min * 0.7, 0)  # 至少为历史最小值的70%，且非负

        forecast_points = []
        for _, row in pred.iterrows():
            date_str = row["ds"].strftime("%Y-%m-%d")
            # 约束预测值：不低于下界
            value = max(row["yhat"], lower_bound)
            forecast_points.append(TimeSeriesPoint(
                date=date_str,
                value=round(value, 2),
                is_prediction=True
            ))

        # 计算训练集拟合误差
        train_forecast = forecast[forecast["ds"] <= last_date]
        if len(train_forecast) == len(df_clean):
            residuals = df_clean["y"].values - train_forecast["yhat"].values
        else:
            # 按日期匹配
            merged = df_clean.merge(
                train_forecast[["ds", "yhat"]], on="ds", how="inner"
            )
            residuals = merged["y"].values - merged["yhat"].values

        mae = np.mean(np.abs(residuals))
        rmse = np.sqrt(np.mean(residuals ** 2))

        return ForecastResult(
            points=forecast_points,
            metrics=ForecastMetrics(
                mae=round(float(mae), 4),
                rmse=round(float(rmse), 4)
            ),
            model="prophet"
        )

    def _prepare_temperature_data(
        self,
        df_clean: pd.DataFrame,
        weather_df: pd.DataFrame,
        model: Prophet
    ) -> tuple[pd.DataFrame, bool]:
        """
        准备温度数据作为外生变量

        Returns:
            (处理后的df, 是否使用温度)
        """
        try:
            # 准备天气数据
            weather_clean = weather_df.copy()
            weather_clean["date"] = pd.to_datetime(weather_clean["date"])
            if weather_clean["date"].dt.tz is not None:
                weather_clean["date"] = weather_clean["date"].dt.tz_localize(None)

            # 合并温度到训练数据
            df_merged = df_clean.merge(
                weather_clean[["date", "temperature"]],
                left_on="ds",
                right_on="date",
                how="left"
            )
            df_merged = df_merged.drop(columns=["date"], errors="ignore")

            # 检查温度数据覆盖率
            temp_coverage = df_merged["temperature"].notna().mean()
            if temp_coverage >= 0.8:
                # 填充缺失值
                df_merged["temperature"] = df_merged["temperature"].interpolate(method="linear")
                df_merged["temperature"] = df_merged["temperature"].fillna(df_merged["temperature"].mean())

                # 添加温度作为外生变量
                model.add_regressor("temperature")
                print(f"[Prophet] 使用温度作为外生变量，覆盖率: {temp_coverage:.1%}")
                return df_merged, True
            else:
                print(f"[Prophet] 温度数据覆盖率不足 ({temp_coverage:.1%})，不使用温度特征")
                return df_clean, False
        except Exception as e:
            print(f"[Prophet] 处理温度数据失败: {e}")
            return df_clean, False

    def _add_future_temperature(
        self,
        future: pd.DataFrame,
        weather_df: pd.DataFrame,
        df_clean: pd.DataFrame
    ) -> pd.DataFrame:
        """
        为未来日期添加温度预测

        策略：
        1. 如果天气预报中有数据，使用预报数据
        2. 否则使用历史月均温度
        """
        future = future.copy()

        # 准备天气数据
        weather_clean = weather_df.copy()
        weather_clean["date"] = pd.to_datetime(weather_clean["date"])
        if weather_clean["date"].dt.tz is not None:
            weather_clean["date"] = weather_clean["date"].dt.tz_localize(None)

        # 合并已有的温度数据
        future = future.merge(
            weather_clean[["date", "temperature"]],
            left_on="ds",
            right_on="date",
            how="left"
        )
        future = future.drop(columns=["date"], errors="ignore")

        # 对于没有温度数据的日期，使用历史月均温度
        missing_mask = future["temperature"].isna()
        if missing_mask.any():
            # 计算历史月均温度
            historical_temp = df_clean[["ds", "temperature"]].copy()
            historical_temp["month"] = historical_temp["ds"].dt.month
            monthly_avg = historical_temp.groupby("month")["temperature"].mean()

            # 填充缺失的温度
            for idx in future[missing_mask].index:
                month = future.loc[idx, "ds"].month
                if month in monthly_avg.index:
                    future.loc[idx, "temperature"] = monthly_avg[month]
                else:
                    future.loc[idx, "temperature"] = df_clean["temperature"].mean()

        return future

    async def historical_forecast(
        self,
        df: pd.DataFrame,
        horizon: int,
        city_name: str,
        weather_df: Optional[pd.DataFrame] = None,
        years_back: int = 2
    ) -> ForecastResult:
        """
        基于历史同期天气的预测（替代传统 Prophet 预测）

        核心思路：获取目标日期的天气数据（预报或历史同期平均），
        直接用 generate_power_demand(target_date, weather) 生成供电量，
        与历史数据的生成方式完全一致，确保预测曲线平滑。

        Args:
            df: 历史供电数据（用于确定预测起始日期）
            horizon: 预测天数
            city_name: 城市名称
            weather_df: 未来天气预报（优先使用，覆盖 ≤14 天）
            years_back: 回溯年数（默认2年，用于获取历史同期天气）

        Returns:
            ForecastResult: 预测结果
        """
        from app.data.power_data_fetcher import (
            generate_power_demand, CITY_BASE_LOADS, DEFAULT_BASE_LOAD, BEIJING_TZ
        )
        from app.data.weather_client import get_weather_client

        # 确定预测时间范围
        df_clean = df.copy()
        if df_clean["ds"].dt.tz is not None:
            df_clean["ds"] = df_clean["ds"].dt.tz_localize(None)

        last_date = df_clean["ds"].max()
        target_start = last_date + timedelta(days=1)
        target_end = target_start + timedelta(days=horizon - 1)

        print(f"[历史预测] 预测范围: {target_start.date()} ~ {target_end.date()}")

        try:
            base_load = CITY_BASE_LOADS.get(city_name, DEFAULT_BASE_LOAD)

            # 构建目标日期 → 天气 的映射
            target_weather = {}  # date_str -> {temperature, humidity}

            # 1. 优先使用传入的天气预报数据
            if weather_df is not None and not weather_df.empty:
                wdf = weather_df.copy()
                wdf["date"] = pd.to_datetime(wdf["date"])
                if wdf["date"].dt.tz is not None:
                    wdf["date"] = wdf["date"].dt.tz_localize(None)
                for _, row in wdf.iterrows():
                    date_str = row["date"].strftime("%Y-%m-%d")
                    temp = row.get("temperature")
                    hum = row.get("humidity")
                    if not pd.isna(temp):
                        target_weather[date_str] = {
                            "temperature": float(temp),
                            "humidity": float(hum) if hum is not None and not pd.isna(hum) else 50.0
                        }

            # 2. 对于预报未覆盖的日期，获取历史同期天气平均值
            missing_dates = []
            current = target_start
            while current <= target_end:
                if current.strftime("%Y-%m-%d") not in target_weather:
                    missing_dates.append(current)
                current += timedelta(days=1)

            if missing_dates:
                print(f"[历史预测] {len(missing_dates)} 天无预报，使用历史同期天气")
                weather_client = get_weather_client()

                # 批量获取：按年份一次请求整个日期范围，而不是逐天请求
                missing_start = min(missing_dates)
                missing_end = max(missing_dates)
                # 收集每年的历史天气 {date_str -> [{temp, hum}, ...]}
                collected = {}
                for year_offset in range(1, years_back + 1):
                    hist_start = missing_start - timedelta(days=365 * year_offset)
                    hist_end = missing_end - timedelta(days=365 * year_offset)
                    try:
                        hist_weather = await weather_client.fetch_archive_weather(
                            city_name,
                            hist_start.strftime("%Y-%m-%d"),
                            hist_end.strftime("%Y-%m-%d")
                        )
                        if hist_weather.empty:
                            continue
                        hist_weather["date"] = pd.to_datetime(hist_weather["date"])
                        for _, row in hist_weather.iterrows():
                            # 将历史日期映射回目标日期
                            days_offset = (row["date"].date() - hist_start.date()).days
                            target_date = missing_start + timedelta(days=days_offset)
                            date_str = target_date.strftime("%Y-%m-%d")
                            if date_str not in collected:
                                collected[date_str] = {"temps": [], "hums": []}
                            t = row.get("temperature")
                            if t is not None and not pd.isna(t):
                                collected[date_str]["temps"].append(float(t))
                            h = row.get("humidity")
                            if h is not None and not pd.isna(h):
                                collected[date_str]["hums"].append(float(h))
                    except Exception as e:
                        print(f"[历史预测] 获取 {year_offset} 年前天气失败: {e}")
                        continue

                # 汇总为平均值
                for target_date in missing_dates:
                    date_str = target_date.strftime("%Y-%m-%d")
                    data = collected.get(date_str)
                    if data and data["temps"]:
                        target_weather[date_str] = {
                            "temperature": sum(data["temps"]) / len(data["temps"]),
                            "humidity": sum(data["hums"]) / len(data["hums"]) if data["hums"] else 50.0
                        }
                    else:
                        target_weather[date_str] = {
                            "temperature": 22.0,
                            "humidity": 50.0
                        }

            # 3. 对每个目标日期，用 generate_power_demand 生成供电量
            forecast_points = []
            current = target_start
            while current <= target_end:
                date_str = current.strftime("%Y-%m-%d")
                w = target_weather.get(date_str, {"temperature": 22.0, "humidity": 50.0})

                target_dt = current
                if target_dt.tzinfo is None:
                    target_dt = target_dt.replace(tzinfo=BEIJING_TZ)

                demand = generate_power_demand(
                    base_load=base_load,
                    temperature=w["temperature"],
                    date=target_dt,
                    humidity=w["humidity"]
                )

                forecast_points.append(TimeSeriesPoint(
                    date=date_str,
                    value=round(demand, 2),
                    is_prediction=True
                ))
                current += timedelta(days=1)

            mae = 0.0
            rmse = 0.0

            print(f"[历史预测] 生成预测点: {len(forecast_points)} 个")

            return ForecastResult(
                points=forecast_points,
                metrics=ForecastMetrics(mae=mae, rmse=rmse),
                model="historical_average"
            )

        except Exception as e:
            # 回退到传统 Prophet 预测
            print(f"[历史预测] 失败，回退到 Prophet: {e}")
            return self.forecast(
                df=df,
                horizon=horizon,
                prophet_params={},
                weather_df=weather_df
            )

