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
        基于历史同期数据的预测（替代传统 Prophet 预测）

        核心思路：获取近N年同期天气 → 生成历史供电量 → 平均并迁移到今年 → 根据天气差异调整

        Args:
            df: 历史供电数据（用于确定预测起始日期）
            horizon: 预测天数
            city_name: 城市名称
            weather_df: 未来天气预报（用于天气差异调整）
            years_back: 回溯年数（默认2年）

        Returns:
            ForecastResult: 预测结果
        """
        from app.data.power_data_fetcher import fetch_historical_same_period

        # 确定预测时间范围
        df_clean = df.copy()
        if df_clean["ds"].dt.tz is not None:
            df_clean["ds"] = df_clean["ds"].dt.tz_localize(None)

        last_date = df_clean["ds"].max()
        target_start = last_date + timedelta(days=1)
        target_end = target_start + timedelta(days=horizon - 1)

        print(f"[历史预测] 预测范围: {target_start.date()} ~ {target_end.date()}, 回溯 {years_back} 年")

        try:
            # 获取近N年同期数据平均
            hist_power, hist_weather = await fetch_historical_same_period(
                city_name=city_name,
                target_start=target_start,
                target_end=target_end,
                years_back=years_back
            )

            # 天气差异调整
            forecast_points = []
            for _, row in hist_power.iterrows():
                # 处理日期（可能带时区）
                ds_value = row["ds"]
                if hasattr(ds_value, 'tz') and ds_value.tz is not None:
                    ds_value = ds_value.tz_localize(None)
                date_str = pd.to_datetime(ds_value).strftime("%Y-%m-%d")
                base_value = row["y"]

                # 如果有未来天气预报，进行调整
                if weather_df is not None and not weather_df.empty:
                    adjusted_value = self._adjust_by_weather(
                        base_value=base_value,
                        target_date=ds_value,
                        hist_weather=hist_weather,
                        future_weather=weather_df
                    )
                else:
                    adjusted_value = base_value

                # 确保非负
                adjusted_value = max(adjusted_value, 0)

                forecast_points.append(TimeSeriesPoint(
                    date=date_str,
                    value=round(adjusted_value, 2),
                    is_prediction=True
                ))

            # 计算误差指标（基于历史数据的拟合，这里无法计算真实误差）
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

    def _adjust_by_weather(
        self,
        base_value: float,
        target_date: datetime,
        hist_weather: pd.DataFrame,
        future_weather: pd.DataFrame
    ) -> float:
        """
        根据天气差异调整预测值

        调整逻辑：
        - 温度每偏差1°C，调整2%
        - 湿度每偏差5%，调整0.2%
        """
        try:
            # 标准化目标日期
            target_date = pd.to_datetime(target_date)
            if target_date.tz is not None:
                target_date = target_date.tz_localize(None)
            target_date_str = target_date.strftime("%Y-%m-%d")

            # 查找历史同期平均天气
            hist_weather_clean = hist_weather.copy()
            hist_weather_clean["date"] = pd.to_datetime(hist_weather_clean["date"])
            if hist_weather_clean["date"].dt.tz is not None:
                hist_weather_clean["date"] = hist_weather_clean["date"].dt.tz_localize(None)
            hist_weather_clean["date_str"] = hist_weather_clean["date"].dt.strftime("%Y-%m-%d")

            hist_row = hist_weather_clean[hist_weather_clean["date_str"] == target_date_str]
            if hist_row.empty:
                return base_value

            hist_temp = hist_row["temperature"].values[0]
            hist_humidity = hist_row["humidity"].values[0] if "humidity" in hist_row.columns else 50.0

            # 查找未来天气预报
            future_weather_clean = future_weather.copy()
            future_weather_clean["date"] = pd.to_datetime(future_weather_clean["date"])
            if future_weather_clean["date"].dt.tz is not None:
                future_weather_clean["date"] = future_weather_clean["date"].dt.tz_localize(None)
            future_weather_clean["date_str"] = future_weather_clean["date"].dt.strftime("%Y-%m-%d")

            future_row = future_weather_clean[future_weather_clean["date_str"] == target_date_str]
            if future_row.empty:
                return base_value

            future_temp = future_row["temperature"].values[0]
            future_humidity = future_row["humidity"].values[0] if "humidity" in future_row.columns else 50.0

            # 处理 NaN 值
            if pd.isna(hist_temp) or pd.isna(future_temp):
                return base_value
            if pd.isna(hist_humidity):
                hist_humidity = 50.0
            if pd.isna(future_humidity):
                future_humidity = 50.0

            # 计算调整系数
            temp_diff = future_temp - hist_temp
            humidity_diff = future_humidity - hist_humidity

            # 温度调整：每度2%
            temp_adjustment = 0.02 * temp_diff

            # 湿度调整：每%湿度0.2%
            humidity_adjustment = 0.002 * humidity_diff

            total_adjustment = 1 + temp_adjustment + humidity_adjustment

            # 限制调整范围在 ±30%
            total_adjustment = max(0.7, min(1.3, total_adjustment))

            return base_value * total_adjustment

        except Exception as e:
            print(f"[天气调整] 计算失败: {e}")
            return base_value
