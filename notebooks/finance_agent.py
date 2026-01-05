"""
金融数据对话式分析 Agent
========================

完整管道: 自然语言 → AKShare数据 → 时序预测 → 分析报告

依赖:
    pip install prophet xgboost pydantic-ai akshare pandas matplotlib openai

环境变量:
    DEEPSEEK_API_KEY: DeepSeek API Key
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pydantic import BaseModel, Field, ConfigDict
from openai import OpenAI

# ============================================================
# 配置
# ============================================================

AKSHARE_API_DOCS = """
## AKShare 数据接口

### 股票数据
- stock_zh_a_hist: A股历史行情
  参数: symbol(代码), period(daily/weekly/monthly), start_date, end_date, adjust(qfq/hfq/"")
  
### 指数数据  
- stock_zh_index_daily_em: 指数历史数据
  参数: symbol (sh000001=上证, sz399001=深证, sz399006=创业板)

### 常用代码
- 平安银行: 000001, 贵州茅台: 600519, 比亚迪: 002594
- 上证指数: sh000001, 沪深300: sh000300
"""


# ============================================================
# 数据模型
# ============================================================

class DataConfig(BaseModel):
    """数据获取配置"""
    api_function: str
    params: Dict[str, Any]
    data_type: str  # stock / index / fund
    target_column: str = "收盘"

class AnalysisConfig(BaseModel):
    """分析配置"""
    forecast_horizon: int = 30
    model: str = "prophet"
    user_question: str = ""

class PipelineResult(BaseModel):
    """管道结果"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    data_config: Dict[str, Any]
    features: Dict[str, Any]
    forecast: List[Dict[str, Any]]
    metrics: Dict[str, float]
    analysis: str


# ============================================================
# 第一层: 自然语言解析 Agent
# ============================================================

class NLPAgent:
    """自然语言解析 → AKShare 配置"""
    
    def __init__(self, api_key: str):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
    
    def parse(self, user_query: str) -> Dict[str, Any]:
        """解析用户输入，返回数据配置和分析配置"""
        
        today = datetime.now()
        one_year_ago = today - timedelta(days=365)
        
        system_prompt = f"""你是金融数据助手。将用户需求转换为 AKShare 数据获取配置。

{AKSHARE_API_DOCS}

返回 JSON 格式:
{{
    "data_config": {{
        "api_function": "stock_zh_a_hist",
        "params": {{"symbol": "000001", "period": "daily", "start_date": "YYYYMMDD", "end_date": "YYYYMMDD", "adjust": ""}},
        "data_type": "stock",
        "target_column": "收盘"
    }},
    "analysis_config": {{
        "forecast_horizon": 30,
        "model": "prophet",
        "user_question": "用户问题的核心"
    }}
}}

注意:
- 默认获取最近1年数据
- 日期格式 YYYYMMDD
- 今天: {today.strftime('%Y-%m-%d')}
- 一年前: {one_year_ago.strftime('%Y-%m-%d')}
- model 字段固定返回 "prophet"（实际模型选择由外部参数控制）
- 只返回 JSON
"""
        
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)


# ============================================================
# 第二层: 数据获取
# ============================================================

class DataFetcher:
    """AKShare 数据获取"""
    
    @staticmethod
    def fetch(config: Dict[str, Any]) -> pd.DataFrame:
        """根据配置获取数据"""
        import akshare as ak
        
        api_map = {
            "stock_zh_a_hist": ak.stock_zh_a_hist,
            "stock_zh_index_daily_em": ak.stock_zh_index_daily_em,
            "fund_etf_hist_em": ak.fund_etf_hist_em,
        }
        
        func_name = config["api_function"]
        params = config["params"]
        
        if func_name not in api_map:
            raise ValueError(f"不支持: {func_name}")
        
        df = api_map[func_name](**params)
        print(f"✅ 获取数据: {len(df)} 条")
        return df
    
    @staticmethod
    def prepare(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        """转换为标准格式 (ds, y)"""
        
        # 检测日期列
        date_col = None
        for col in ["日期", "date", "Date"]:
            if col in df.columns:
                date_col = col
                break
        
        # 检测值列
        target = config.get("target_column", "收盘")
        value_col = None
        for col in [target, "close", "Close", "收盘"]:
            if col in df.columns:
                value_col = col
                break
        
        if not date_col or not value_col:
            raise ValueError(f"无法识别列: {list(df.columns)}")
        
        result = pd.DataFrame({
            "ds": pd.to_datetime(df[date_col]),
            "y": df[value_col].astype(float)
        }).sort_values("ds").drop_duplicates("ds").reset_index(drop=True)
        
        print(f"✅ 数据准备: {len(result)} 条, {result['ds'].min().date()} ~ {result['ds'].max().date()}")
        return result


# ============================================================
# 第三层: 时序分析
# ============================================================

class TimeSeriesAnalyzer:
    """时序分析 + 预测"""
    
    @staticmethod
    def analyze_features(df: pd.DataFrame) -> Dict[str, Any]:
        """分析时序特征"""
        y = df["y"].values
        
        # 趋势
        mid = len(y) // 2
        first_mean, second_mean = np.mean(y[:mid]), np.mean(y[mid:])
        if second_mean > first_mean * 1.05:
            trend = "上升"
        elif second_mean < first_mean * 0.95:
            trend = "下降"
        else:
            trend = "平稳"
        
        # 波动性
        cv = np.std(y) / np.mean(y) if np.mean(y) != 0 else 0
        volatility = "高" if cv > 0.3 else ("中" if cv > 0.1 else "低")
        
        # 统计
        return {
            "trend": trend,
            "volatility": volatility,
            "mean": round(float(np.mean(y)), 2),
            "std": round(float(np.std(y)), 2),
            "min": round(float(np.min(y)), 2),
            "max": round(float(np.max(y)), 2),
            "latest": round(float(y[-1]), 2),
            "data_points": len(y),
            "date_range": f"{df['ds'].min().date()} ~ {df['ds'].max().date()}"
        }
    
    @staticmethod
    def forecast_prophet(df: pd.DataFrame, horizon: int = 30) -> Dict[str, Any]:
        """Prophet 预测"""
        from prophet import Prophet
        
        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True,
            changepoint_prior_scale=0.05,
        )
        model.fit(df[["ds", "y"]])
        
        future = model.make_future_dataframe(periods=horizon, freq="D")
        forecast = model.predict(future)
        
        # 提取预测
        pred = forecast.tail(horizon)
        forecast_values = [
            {
                "date": row["ds"].strftime("%Y-%m-%d"),
                "value": round(row["yhat"], 2),
                "lower": round(row["yhat_lower"], 2),
                "upper": round(row["yhat_upper"], 2),
            }
            for _, row in pred.iterrows()
        ]
        
        # 计算 MAE
        train_pred = forecast.head(len(df))
        mae = np.mean(np.abs(df["y"].values - train_pred["yhat"].values))
        
        return {
            "forecast": forecast_values,
            "metrics": {"mae": round(mae, 4)},
            "model": "prophet"
        }
    
    @staticmethod
    def _create_features(df: pd.DataFrame, max_lag: int = 30) -> pd.DataFrame:
        """创建时序特征用于 XGBoost"""
        feature_df = df.copy()
        
        # 滞后特征
        for lag in [1, 7, 14, 30]:
            if lag <= max_lag and lag < len(feature_df):
                feature_df[f"lag_{lag}"] = feature_df["y"].shift(lag)
        
        # 移动平均
        for window in [7, 14, 30]:
            if window < len(feature_df):
                feature_df[f"ma_{window}"] = feature_df["y"].rolling(window=window, min_periods=1).mean()
                feature_df[f"std_{window}"] = feature_df["y"].rolling(window=window, min_periods=1).std()
        
        # 时间特征
        feature_df["day_of_week"] = feature_df["ds"].dt.dayofweek
        feature_df["day_of_month"] = feature_df["ds"].dt.day
        feature_df["month"] = feature_df["ds"].dt.month
        feature_df["quarter"] = feature_df["ds"].dt.quarter
        
        # 趋势特征
        feature_df["trend"] = np.arange(len(feature_df))
        
        # 填充 NaN（由滞后和移动平均产生）
        feature_df = feature_df.bfill().fillna(0)
        
        return feature_df
    
    @staticmethod
    def forecast_xgboost(df: pd.DataFrame, horizon: int = 30) -> Dict[str, Any]:
        """XGBoost 预测"""
        try:
            import xgboost as xgb
        except ImportError:
            raise ImportError("请安装 xgboost: pip install xgboost")
        
        # 检查数据量
        if len(df) < 60:
            raise ValueError(f"XGBoost 需要至少60条历史数据，当前只有 {len(df)} 条")
        
        # 创建特征
        feature_df = TimeSeriesAnalyzer._create_features(df, max_lag=min(30, len(df) // 2))
        
        # 准备训练数据
        feature_cols = [col for col in feature_df.columns if col not in ["ds", "y"]]
        X = feature_df[feature_cols].values
        y = feature_df["y"].values
        
        # 划分训练集（使用最后20%作为验证集）
        split_idx = int(len(X) * 0.8)
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        # 训练模型
        model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1
        )
        # 兼容不同版本的 XGBoost
        # XGBoost 2.0+ 使用 callbacks，旧版本使用 early_stopping_rounds
        try:
            # 尝试新版本方式 (XGBoost 2.0+)
            try:
                early_stop = xgb.callback.EarlyStopping(rounds=10, save_best=True)
                model.fit(
                    X_train, y_train,
                    eval_set=[(X_val, y_val)],
                    callbacks=[early_stop],
                    verbose=False
                )
            except (AttributeError, TypeError):
                # 如果 callback 方式失败，尝试旧版本方式
                model.fit(
                    X_train, y_train,
                    eval_set=[(X_val, y_val)],
                    early_stopping_rounds=10,
                    verbose=False
                )
        except TypeError:
            # 如果两种方式都失败，不使用 early stopping
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False
            )
        
        # 在训练集上预测以计算残差
        train_pred = model.predict(X)
        residuals = y - train_pred
        std_error = np.std(residuals)
        
        # 递归预测未来值
        forecast_values = []
        last_features = feature_df.iloc[-1].copy()
        last_date = df["ds"].iloc[-1]
        last_values = df["y"].values[-30:].tolist()  # 保存最近30个值用于特征计算
        
        for i in range(horizon):
            # 创建未来日期
            future_date = last_date + timedelta(days=i + 1)
            
            # 准备特征
            future_features = pd.Series(index=feature_df.columns, dtype=float)
            
            # 滞后特征（使用预测值或历史值）
            if i == 0:
                future_features["lag_1"] = last_features["y"]
            else:
                future_features["lag_1"] = forecast_values[-1]["value"]
            
            for lag in [7, 14, 30]:
                lag_col = f"lag_{lag}"
                if lag_col in feature_cols:
                    if i + 1 >= lag:
                        if i + 1 - lag < len(forecast_values):
                            future_features[lag_col] = forecast_values[i + 1 - lag]["value"]
                        else:
                            idx = len(last_values) - (lag - (i + 1))
                            future_features[lag_col] = last_values[idx] if idx >= 0 else last_values[0]
                    else:
                        idx = len(last_values) - (lag - i - 1)
                        future_features[lag_col] = last_values[idx] if idx >= 0 else last_values[0]
            
            # 移动平均（使用历史值和预测值）
            all_values = last_values + [f["value"] for f in forecast_values]
            for window in [7, 14, 30]:
                ma_col = f"ma_{window}"
                std_col = f"std_{window}"
                if ma_col in feature_cols:
                    window_values = all_values[-window:] if len(all_values) >= window else all_values
                    future_features[ma_col] = np.mean(window_values)
                    future_features[std_col] = np.std(window_values) if len(window_values) > 1 else 0
            
            # 时间特征
            future_features["day_of_week"] = future_date.dayofweek
            future_features["day_of_month"] = future_date.day
            future_features["month"] = future_date.month
            future_features["quarter"] = future_date.quarter
            
            # 趋势特征
            future_features["trend"] = len(df) + i + 1
            
            # 填充缺失值
            for col in feature_cols:
                if pd.isna(future_features[col]):
                    future_features[col] = feature_df[col].iloc[-1] if col in feature_df.columns else 0
            
            # 预测
            X_future = future_features[feature_cols].values.reshape(1, -1)
            pred_value = model.predict(X_future)[0]
            
            # 计算置信区间（使用历史残差的标准差）
            lower = pred_value - 1.96 * std_error
            upper = pred_value + 1.96 * std_error
            
            forecast_values.append({
                "date": future_date.strftime("%Y-%m-%d"),
                "value": round(float(pred_value), 2),
                "lower": round(float(lower), 2),
                "upper": round(float(upper), 2),
            })
        
        # 计算验证集 MAE
        val_pred = model.predict(X_val)
        mae = np.mean(np.abs(y_val - val_pred))
        rmse = np.sqrt(np.mean((y_val - val_pred) ** 2))
        
        return {
            "forecast": forecast_values,
            "metrics": {
                "mae": round(float(mae), 4),
                "rmse": round(float(rmse), 4)
            },
            "model": "xgboost"
        }


# ============================================================
# 第四层: 报告生成
# ============================================================

class ReportGenerator:
    """生成分析报告"""
    
    def __init__(self, api_key: str):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
    
    def generate(
        self, 
        user_question: str,
        features: Dict[str, Any],
        forecast_result: Dict[str, Any]
    ) -> str:
        """生成分析报告"""
        
        forecast_preview = forecast_result["forecast"][:7]  # 前7天
        
        prompt = f"""用户问题: {user_question}

数据特征:
- 趋势: {features['trend']}
- 波动性: {features['volatility']}
- 均值: {features['mean']}, 最新: {features['latest']}
- 区间: [{features['min']}, {features['max']}]
- 数据量: {features['data_points']} 天
- 时间: {features['date_range']}

预测结果 ({forecast_result['model']}):
- 预测天数: {len(forecast_result['forecast'])}
- 未来7天: {json.dumps(forecast_preview, ensure_ascii=False)}
- MAE: {forecast_result['metrics'].get('mae', 'N/A')}

请生成简洁的中文分析报告:
1. 历史走势分析 (2句)
2. 预测趋势解读 (2句)  
3. 投资建议 + 风险提示 (2句)

保持专业客观，总共不超过150字。"""
        
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
        )
        
        return response.choices[0].message.content


# ============================================================
# 主管道
# ============================================================

class FinanceChatAgent:
    """
    金融对话 Agent
    
    完整流程:
    用户输入 → NLP解析 → 数据获取 → 特征分析 → 预测 → 报告生成
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("请设置 DEEPSEEK_API_KEY")
        
        self.nlp = NLPAgent(self.api_key)
        self.reporter = ReportGenerator(self.api_key)
    
    def chat(self, user_input: str, model: str = "prophet", verbose: bool = True) -> Dict[str, Any]:
        """
        对话接口
        
        Args:
            user_input: 用户自然语言输入
            model: 预测模型，可选 "prophet" 或 "xgboost"，默认为 "prophet"
            verbose: 是否打印过程
            
        Returns:
            包含预测结果和分析报告的字典
        """
        if verbose:
            print("="*60)
            print(f"📝 用户: {user_input}")
            print("="*60)
        
        # Step 1: 解析用户输入
        if verbose:
            print("\n🤖 Step 1: 解析需求...")
        
        parsed = self.nlp.parse(user_input)
        data_config = parsed["data_config"]
        analysis_config = parsed["analysis_config"]
        
        if verbose:
            print(f"   → 数据源: {data_config['api_function']}")
            print(f"   → 参数: {data_config['params']}")
            print(f"   → 预测: {analysis_config['forecast_horizon']} 天")
        
        # Step 2: 获取数据
        if verbose:
            print("\n📊 Step 2: 获取数据...")
        
        raw_df = DataFetcher.fetch(data_config)
        df = DataFetcher.prepare(raw_df, data_config)
        
        # Step 3: 特征分析
        if verbose:
            print("\n📈 Step 3: 分析特征...")
        
        features = TimeSeriesAnalyzer.analyze_features(df)
        
        if verbose:
            print(f"   → 趋势: {features['trend']}, 波动: {features['volatility']}")
            print(f"   → 最新价: {features['latest']}")
        
        # Step 4: 预测
        if verbose:
            print("\n🔮 Step 4: 执行预测...")
        
        horizon = analysis_config.get("forecast_horizon", 30)
        # 使用传入的 model 参数，覆盖 NLP Agent 返回的模型选择
        model_name = model.lower() if model else analysis_config.get("model", "prophet").lower()
        
        # 验证模型名称
        if model_name not in ["prophet", "xgboost"]:
            raise ValueError(f"不支持的模型: {model_name}。支持: 'prophet', 'xgboost'")
        
        if model_name == "prophet":
            forecast_result = TimeSeriesAnalyzer.forecast_prophet(df, horizon)
        else:  # xgboost
            forecast_result = TimeSeriesAnalyzer.forecast_xgboost(df, horizon)
        
        if verbose:
            print(f"   → 模型: {forecast_result['model']}")
            metrics_str = ", ".join([f"{k.upper()}: {v}" for k, v in forecast_result['metrics'].items()])
            print(f"   → 指标: {metrics_str}")
        
        # Step 5: 生成报告
        if verbose:
            print("\n📋 Step 5: 生成报告...")
        
        user_question = analysis_config.get("user_question", user_input)
        report = self.reporter.generate(user_question, features, forecast_result)
        
        # 结果
        result = {
            "config": {
                "data": data_config,
                "analysis": analysis_config
            },
            "data": {
                "raw_shape": raw_df.shape,
                "prepared_shape": df.shape,
                "df": df,  # 标准化后的数据
            },
            "features": features,
            "forecast": forecast_result["forecast"],
            "metrics": forecast_result["metrics"],
            "report": report,
        }
        
        if verbose:
            print("\n" + "="*60)
            print("💡 分析报告")
            print("="*60)
            print(report)
            print("="*60)
        
        return result
    
    def plot(self, result: Dict[str, Any], title: str = None):
        """绘制预测图"""
        import matplotlib.pyplot as plt
        
        df = result["data"]["df"]
        forecast = result["forecast"]
        
        fig, ax = plt.subplots(figsize=(12, 5))
        
        # 历史
        ax.plot(df["ds"], df["y"], label="历史数据", color="blue", lw=1.5)
        
        # 预测
        dates = pd.to_datetime([f["date"] for f in forecast])
        values = [f["value"] for f in forecast]
        lower = [f.get("lower") for f in forecast]
        upper = [f.get("upper") for f in forecast]
        
        ax.plot(dates, values, label="预测", color="red", lw=2, ls="--")
        # 只有当置信区间存在时才绘制
        if all(l is not None and u is not None for l, u in zip(lower, upper)):
            ax.fill_between(dates, lower, upper, alpha=0.2, color="red")
        
        ax.set_title(title or "时序预测")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()
        
        return fig


# ============================================================
# 便捷函数
# ============================================================

def chat(query: str, model: str = "prophet", api_key: str = None) -> Dict[str, Any]:
    """
    快速对话接口
    
    Args:
        query: 用户自然语言输入
        model: 预测模型，可选 "prophet" 或 "xgboost"，默认为 "prophet"
        api_key: DeepSeek API Key，如果不提供则从环境变量读取
    
    Example:
        result = chat("分析平安银行近一年走势，预测未来30天", model="xgboost")
        print(result["report"])
    """
    agent = FinanceChatAgent(api_key)
    return agent.chat(query, model=model)


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = input("请输入您的问题: ")
    
    result = chat(query)
    
    print("\n预测值 (前10天):")
    for f in result["forecast"][:10]:
        print(f"  {f['date']}: {f['value']:.2f}")