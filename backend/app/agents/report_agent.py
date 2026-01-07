"""
Report Agent 模块
=================

负责生成金融分析报告
"""

import json
from typing import Dict, Any, List, Optional
from openai import OpenAI


class ReportAgent:
    """分析报告生成 Agent"""

    def __init__(self, api_key: str):
        """
        初始化 Report Agent
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )

    def generate(
        self,
        user_question: str,
        features: Dict[str, Any],
        forecast_result: Dict[str, Any],
        sentiment_result: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        生成分析报告内容
        """
        # 提取预测数据
        forecast_summary = forecast_result.get("forecast", [])
        forecast_preview = forecast_summary[:7]
        
        # 1. 安全计算预测趋势（确保数值为 float）
        try:
            if len(forecast_summary) >= 7:
                start_val = float(forecast_summary[0]["value"])
                end_val_7d = float(forecast_summary[6]["value"])
                end_val_total = float(forecast_summary[-1]["value"])
                
                short_term_change = end_val_7d - start_val
                long_term_change = end_val_total - start_val
                
                st_pct = (short_term_change / start_val * 100) if start_val != 0 else 0
                lt_pct = (long_term_change / start_val * 100) if start_val != 0 else 0
            else:
                short_term_change = long_term_change = st_pct = lt_pct = 0
        except (ValueError, TypeError, KeyError):
            short_term_change = long_term_change = st_pct = lt_pct = 0
        
        # 2. 构建情绪分析块
        sentiment_section = ""
        if sentiment_result and sentiment_result.get("news_count", 0) > 0:
            key_events = sentiment_result.get('key_events', [])
            key_events_str = ', '.join(key_events[:3]) if key_events else '无'
            # 这里的 overall_score 强制转 float 避免报错
            score = float(sentiment_result.get('overall_score', 0))
            
            sentiment_section = f"""
情绪分析:
- 整体情绪: {sentiment_result.get('sentiment', '中性')}
- 情绪得分: {score:.2f} (-1到1)
- 关键事件: {key_events_str}
- 分析说明: {sentiment_result.get('analysis_text', '')}
"""

        system_prompt = """你是资深的金融分析师。你的分析报告需要：
1. 专业严谨：基于数据和技术指标
2. 逻辑清晰：层层递进
3. 风险意识：明确风险点
4. 实用建议：给出操作方向"""

        # 3. 构建 Prompt (对 features 中的数值进行 float 强制转换)
        try:
            f_latest = float(features.get('latest', 0))
            f_mean = float(features.get('mean', 1)) # 避免除以0
            change_pct = (f_latest - f_mean) / f_mean * 100
            
            prompt = f"""用户问题: {user_question}

## 数据特征分析
【基本面信息】
- 数据时间范围: {features.get('date_range', '未知')}
- 有效数据点: {features.get('data_points', 0)} 天
- 价格区间: [{float(features.get('min', 0)):.2f}, {float(features.get('max', 0)):.2f}]
- 当前价位: {f_latest:.2f} (均值: {f_mean:.2f})

【技术指标】
- 趋势方向: {features.get('trend', '横盘')}
- 波动程度: {features.get('volatility', '低')}
- 变化幅度: {change_pct:.2f}%

{sentiment_section}
## 预测结果
【模型信息】
- 模型: {str(forecast_result.get('model', 'unknown')).upper()}
- 预测精度: MAE={float(forecast_result.get('metrics', {}).get('mae', 0)):.4f}
- 预测期限: {len(forecast_summary)} 天

【趋势分析】
- 短期变化（7天）: {short_term_change:+.2f} ({st_pct:+.2f}%)
- 长期变化（{len(forecast_summary)}天）: {long_term_change:+.2f} ({lt_pct:+.2f}%)

## 报告要求
请生成一份完整的 Markdown 格式专业报告。包含：历史走势分析、市场情绪、预测解读、投资建议、风险提示。总字数在500以内。
"""
        except (ValueError, TypeError) as e:
            # 如果转换依然失败，回退到无格式模式
            prompt = f"数据分析请求: {user_question}\n数据详情: {str(features)}\n预测详情: {str(forecast_result)}"

        # 4. 消息发送
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history[-5:])
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.3,
                max_tokens=1500,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"生成报告时发生 API 错误: {str(e)}"