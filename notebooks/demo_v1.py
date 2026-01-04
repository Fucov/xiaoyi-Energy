"""
金融数据分析管道
================

将用户需求翻译为 AKShare 数据获取逻辑，使用 TimeCopilot 进行分析预测

架构:
    用户需求 -> DeepSeek Agent 解析 -> AKShare 获取数据 -> 数据转换 -> TimeCopilot 预测 -> 结果输出

依赖安装:
    pip install akshare timecopilot openai pandas matplotlib

环境变量:
    DEEPSEEK_API_KEY: DeepSeek API Key
    OPENAI_API_KEY: OpenAI API Key (TimeCopilot 需要)
"""

import os
import json
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pydantic_ai.providers.deepseek import DeepSeekProvider
from pydantic_ai.models.openai import OpenAIChatModel

# ============================================================
# 配置
# ============================================================

AKSHARE_API_DOCS = """
## AKShare 常用数据接口

### 股票数据
1. **stock_zh_a_hist** - A股历史行情数据
   - 参数: symbol(股票代码如"000001"), period("daily"/"weekly"/"monthly"), 
           start_date("YYYYMMDD"), end_date("YYYYMMDD"), adjust("qfq"/"hfq"/"")
   - 返回: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率

2. **stock_zh_a_spot_em** - A股实时行情
   - 参数: 无
   - 返回: 所有A股实时行情数据

### 指数数据
3. **stock_zh_index_daily_em** - 股票指数历史数据
   - 参数: symbol(指数代码如"sh000001"上证指数, "sz399001"深证成指)
   - 返回: date,open,close,high,low,volume,amount

4. **index_zh_a_hist** - 指数历史行情(带日期范围)
   - 参数: symbol, period, start_date, end_date

### 基金数据
5. **fund_etf_hist_em** - ETF基金历史数据
   - 参数: symbol(ETF代码), period, start_date, end_date, adjust

### 常用股票代码示例
- 平安银行: 000001
- 贵州茅台: 600519
- 比亚迪: 002594
- 宁德时代: 300750

### 常用指数代码
- 上证指数: sh000001 或 000001
- 深证成指: sz399001 或 399001
- 创业板指: sz399006 或 399006
- 沪深300: sh000300 或 000300
"""


# ============================================================
# 数据类
# ============================================================

@dataclass
class PipelineResult:
    """管道执行结果"""
    config: Dict[str, Any]
    raw_data: pd.DataFrame
    transformed_data: pd.DataFrame
    forecast_df: pd.DataFrame
    forecast_values: Dict[str, Any]
    summary: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": self.config,
            "forecast_values": self.forecast_values,
            "summary": self.summary,
            "forecast_df": self.forecast_df.to_dict(orient="records") if self.forecast_df is not None else []
        }


# ============================================================
# Agent - 需求解析器
# ============================================================

class DataRequestAgent:
    """使用 DeepSeek API 将用户自然语言需求转换为 AKShare 调用"""
    
    def __init__(self, api_key: str):
        from openai import OpenAI
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        self.model = "deepseek-chat"
    
    def parse_request(self, user_query: str) -> Dict[str, Any]:
        """解析用户需求，返回数据获取配置"""
        
        system_prompt = f"""
你是一个金融数据分析助手。你的任务是将用户的自然语言需求转换为 AKShare 数据获取配置。

{AKSHARE_API_DOCS}

请根据用户需求，返回一个 JSON 格式的配置，包含以下字段：
1. api_function: AKShare 函数名
2. params: 函数参数字典
3. data_type: 数据类型 (stock/index/fund/futures/macro)
4. analysis_type: 分析类型 (forecast预测/analysis分析)
5. forecast_horizon: 预测周期(天数)，如果是预测任务
6. target_column: 目标列名（通常是"收盘"或"close"）
7. user_question: 用户原始问题的核心诉求

注意：
- 如果用户没有指定日期范围，默认获取最近1年的数据
- 日期格式为 YYYYMMDD
- 只返回 JSON，不要其他解释

今天日期: {datetime.now().strftime('%Y-%m-%d')}
"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    
    def generate_summary(self, forecast_result: Dict, original_query: str) -> str:
        """根据预测结果生成自然语言总结"""
        
        prompt = f"""
用户原始问题: {original_query}

预测结果:
- 选用模型: {forecast_result.get('selected_model', 'N/A')}
- 模型选择原因: {forecast_result.get('reason_for_selection', 'N/A')}
- 时序特征分析: {forecast_result.get('tsfeatures_analysis', 'N/A')}
- 预测分析: {forecast_result.get('forecast_analysis', 'N/A')}
- 预测值: {forecast_result.get('forecast', [])[:10]}... (前10个)

请用中文为用户生成一个简洁专业的分析报告，包含:
1. 数据特征概述
2. 模型选择说明
3. 预测趋势总结
4. 投资建议（风险提示）

注意: 保持客观，添加必要的风险提示。
"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        return response.choices[0].message.content


# ============================================================
# 数据获取层
# ============================================================

class DataFetcher:
    """使用 AKShare 获取金融数据"""
    
    @staticmethod
    def fetch_data(config: Dict[str, Any]) -> pd.DataFrame:
        """根据配置获取数据"""
        import akshare as ak
        
        api_mapping = {
            "stock_zh_a_hist": ak.stock_zh_a_hist,
            "stock_zh_a_spot_em": ak.stock_zh_a_spot_em,
            "stock_zh_index_daily_em": ak.stock_zh_index_daily_em,
            "index_zh_a_hist": ak.index_zh_a_hist,
            "fund_etf_hist_em": ak.fund_etf_hist_em,
        }
        
        api_function = config.get("api_function")
        params = config.get("params", {})
        
        if api_function not in api_mapping:
            raise ValueError(f"不支持的 API 函数: {api_function}")
        
        func = api_mapping[api_function]
        df = func(**params)
        
        print(f"✅ 成功获取数据，共 {len(df)} 条记录")
        return df


# ============================================================
# 数据转换层
# ============================================================

class DataTransformer:
    """将 AKShare 数据转换为 TimeCopilot 所需格式"""
    
    @staticmethod
    def transform_for_timecopilot(
        df: pd.DataFrame, 
        config: Dict[str, Any]
    ) -> pd.DataFrame:
        """
        转换数据格式
        
        TimeCopilot 要求的格式:
        - unique_id: 时序唯一标识 (string)
        - ds: 日期列 (datetime)
        - y: 目标变量 (float)
        """
        
        df_copy = df.copy()
        
        # 检测日期列
        date_columns = ["日期", "date", "Date", "时间", "time"]
        date_col = None
        for col in date_columns:
            if col in df_copy.columns:
                date_col = col
                break
        
        if date_col is None:
            if isinstance(df_copy.index, pd.DatetimeIndex):
                df_copy = df_copy.reset_index()
                date_col = df_copy.columns[0]
            else:
                raise ValueError("未找到日期列")
        
        # 检测目标列
        target_col = config.get("target_column", "收盘")
        target_columns = [target_col, "close", "Close", "收盘", "收盘价"]
        y_col = None
        for col in target_columns:
            if col in df_copy.columns:
                y_col = col
                break
        
        if y_col is None:
            numeric_cols = df_copy.select_dtypes(include=['float64', 'int64']).columns
            if len(numeric_cols) > 0:
                y_col = numeric_cols[0]
            else:
                raise ValueError("未找到目标数值列")
        
        # 生成 unique_id
        symbol = config.get("params", {}).get("symbol", "unknown")
        
        # 构建 TimeCopilot 格式
        result = pd.DataFrame({
            "unique_id": symbol,
            "ds": pd.to_datetime(df_copy[date_col]),
            "y": df_copy[y_col].astype(float)
        })
        
        result = result.sort_values("ds").drop_duplicates(subset=["ds"]).reset_index(drop=True)
        
        print(f"✅ 数据转换完成: {len(result)} 条记录")
        print(f"   日期范围: {result['ds'].min()} ~ {result['ds'].max()}")
        
        return result


# ============================================================
# 分析/预测层
# ============================================================

class TimeSeriesAnalyzer:
    """使用 TimeCopilot 进行时序分析和预测"""
    
    def __init__(self, llm_model: str = "openai:gpt-4o-mini"):
        from timecopilot import TimeCopilot
        self.tc = TimeCopilot(llm=llm_model, retries=3)
    
    def forecast(
        self, 
        df: pd.DataFrame, 
        horizon: int = 30,
        freq: str = "D",
        query: Optional[str] = None
    ) -> Tuple[Any, pd.DataFrame]:
        """执行时序预测"""
        
        print(f"🔮 开始预测，预测周期: {horizon} {freq}")
        
        result = self.tc.forecast(
            df=df,
            freq=freq,
            h=horizon,
            query=query
        )
        
        return result.output, result.fcst_df
    
    @staticmethod
    def extract_forecast_values(result_output) -> Dict[str, Any]:
        """提取预测结果的关键信息"""
        return {
            "selected_model": getattr(result_output, 'selected_model', 'N/A'),
            "model_details": getattr(result_output, 'model_details', 'N/A'),
            "tsfeatures_analysis": getattr(result_output, 'tsfeatures_analysis', 'N/A'),
            "forecast_analysis": getattr(result_output, 'forecast_analysis', 'N/A'),
            "reason_for_selection": getattr(result_output, 'reason_for_selection', 'N/A'),
            "forecast": getattr(result_output, 'forecast', []),
            "is_better_than_seasonal_naive": getattr(result_output, 'is_better_than_seasonal_naive', None),
            "cross_validation_results": getattr(result_output, 'cross_validation_results', []),
            "user_query_response": getattr(result_output, 'user_query_response', None)
        }


# ============================================================
# 完整管道
# ============================================================

class FinancialDataPipeline:
    """
    金融数据分析管道
    
    完整流程:
    用户需求 -> Agent解析 -> 数据获取 -> 数据转换 -> 时序分析 -> 结果输出
    """
    
    def __init__(self, deepseek_api_key: str, openai_api_key: str):
   
        self.agent = DataRequestAgent(deepseek_api_key)
        self.llm_model = OpenAIChatModel(
            'deepseek-chat',
            provider=DeepSeekProvider(api_key=deepseek_api_key),
        )
        self.analyzer = TimeSeriesAnalyzer(llm_model=self.llm_model)
        
        # 确保环境变量设置
        # os.environ["OPENAI_API_KEY"] = openai_api_key
    
    def run(self, user_query: str) -> PipelineResult:
        """执行完整的分析管道"""
        
        print("="*60)
        print(f"📝 用户需求: {user_query}")
        print("="*60)
        
        # Step 1: Agent 解析需求
        print("\n🤖 Step 1: 解析用户需求...")
        config = self.agent.parse_request(user_query)
        print(f"   API函数: {config.get('api_function')}")
        print(f"   参数: {config.get('params')}")
        
        # Step 2: 获取数据
        print("\n📊 Step 2: 获取数据...")
        raw_data = DataFetcher.fetch_data(config)
        print(raw_data.head())
        
        # Step 3: 转换数据
        print("\n🔄 Step 3: 转换数据格式...")
        transformed_data = DataTransformer.transform_for_timecopilot(raw_data, config)
        print(transformed_data.head())
        
        # Step 4: 时序分析/预测
        print("\n🔮 Step 4: 执行时序预测...")
        forecast_horizon = config.get("forecast_horizon", 30)
        forecast_query = config.get("user_question", user_query)
        
        forecast_output, forecast_df = self.analyzer.forecast(
            df=transformed_data,
            horizon=forecast_horizon,
            freq="D",
            query=forecast_query
        )
        
        forecast_values = self.analyzer.extract_forecast_values(forecast_output)
        
        # Step 5: 生成总结
        print("\n📋 Step 5: 生成分析报告...")
        summary = self.agent.generate_summary(forecast_values, user_query)
        
        # 构建结果
        result = PipelineResult(
            config=config,
            raw_data=raw_data,
            transformed_data=transformed_data,
            forecast_df=forecast_df,
            forecast_values=forecast_values,
            summary=summary
        )
        
        print("\n" + "="*60)
        print("📊 分析报告")
        print("="*60)
        print(summary)
        
        return result


# ============================================================
# 便捷函数
# ============================================================

def analyze(
    query: str, 
    deepseek_key: str = None, 
    openai_key: str = None
) -> PipelineResult:
    """
    快速分析函数
    
    Args:
        query: 自然语言分析需求
        deepseek_key: DeepSeek API Key
        openai_key: OpenAI API Key
        
    Returns:
        PipelineResult 对象
        
    Example:
        result = analyze("分析贵州茅台最近的走势并预测未来30天")
        print(result.summary)
        print(result.forecast_df)
    """
    deepseek_key = deepseek_key or os.environ.get("DEEPSEEK_API_KEY")
    openai_key = openai_key or os.environ.get("OPENAI_API_KEY")
    
    if not deepseek_key:
        raise ValueError("请设置 DEEPSEEK_API_KEY 和 OPENAI_API_KEY 环境变量")
    
    pipeline = FinancialDataPipeline(deepseek_key, openai_key)
    return pipeline.run(query)


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = input("请输入您的分析需求: ")
    
    try:
        result = analyze(query)
        
        print("\n" + "="*60)
        print("预测数值 (前10个):")
        print("="*60)
        if result.forecast_df is not None:
            print(result.forecast_df.head(10))
            
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        raise