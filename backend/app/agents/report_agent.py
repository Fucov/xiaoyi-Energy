"""
Report Agent 模块
=================

负责生成金融分析报告
"""

from typing import Dict, Any, List, Optional

from .base import BaseAgent


class ReportAgent(BaseAgent):
    """分析报告生成 Agent"""

    DEFAULT_TEMPERATURE = 0.3

    SYSTEM_PROMPT = """你是资深的电力需求分析师。你的任务是生成自然段格式的分析报告，而非要点列表。

**核心要求：**
1. 使用自然段陈述，语气连贯流畅，避免使用"-"、"•"等列表符号
2. 将要点式内容改写为连贯的自然段落
3. 在关键数据、重要结论处使用 **加粗** 标记
4. 保持专业严谨，基于数据和技术指标
5. 逻辑清晰，层层递进
6. 明确风险点，给出实用建议（如供电保障措施、需求侧管理等）"""

    def generate_streaming(
        self,
        user_question: str,
        features: Dict[str, Any],
        forecast_result: Dict[str, Any],
        sentiment_result: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        on_chunk: Optional[callable] = None,
    ) -> str:
        """
        流式生成分析报告

        Args:
            user_question: 用户原始问题
            features: 时序特征数据
            forecast_result: 预测结果
            sentiment_result: 情绪分析结果（可选）
            conversation_history: 对话历史（可选）
            on_chunk: 每个 chunk 的回调函数

        Returns:
            完整报告内容
        """
        try:
            prompt = self._build_prompt(
                user_question, features, forecast_result, sentiment_result
            )
        except (ValueError, TypeError) as e:
            prompt = f"数据分析请求: {user_question}\n数据详情: {str(features)}\n预测详情: {str(forecast_result)}"

        messages = self.build_messages(
            user_content=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            conversation_history=conversation_history,
            history_window=5,
        )

        content = self.call_llm(messages, stream=True, on_chunk=on_chunk)
        return content

    def _build_prompt(
        self,
        user_question: str,
        features: Dict[str, Any],
        forecast_result: Dict[str, Any],
        sentiment_result: Optional[Dict[str, Any]] = None,
    ) -> str:
        """构建报告生成 prompt"""
        forecast_summary = forecast_result.get("forecast", [])
        forecast_preview = forecast_summary[:7]

        # 1. 计算预测趋势
        short_term_change = long_term_change = st_pct = lt_pct = 0
        if len(forecast_summary) >= 7:
            start_val = float(forecast_summary[0]["value"])
            end_val_7d = float(forecast_summary[6]["value"])
            end_val_total = float(forecast_summary[-1]["value"])

            short_term_change = end_val_7d - start_val
            long_term_change = end_val_total - start_val

            st_pct = (short_term_change / start_val * 100) if start_val != 0 else 0
            lt_pct = (long_term_change / start_val * 100) if start_val != 0 else 0

        # 2. 构建情绪分析块
        sentiment_section = ""
        if sentiment_result:
            if isinstance(sentiment_result, dict):
                score = float(sentiment_result.get("score", 0))
                description = sentiment_result.get("description", "")
            else:
                score = float(sentiment_result.score)
                description = sentiment_result.description

            if score > 0.6:
                sentiment_label = "需求大幅增加"
            elif score > 0.3:
                sentiment_label = "需求增加"
            elif score > -0.3:
                sentiment_label = "需求稳定"
            elif score > -0.6:
                sentiment_label = "需求减少"
            else:
                sentiment_label = "需求大幅减少"

            sentiment_section = f"""
## 影响因素分析
整体影响为**{sentiment_label}**，影响得分为{score:.2f}（范围-1到1，正值表示需求增加，负值表示需求减少）。{description}
"""

        # 3. 构建主 Prompt
        f_latest = float(features.get("latest", 0))
        f_mean = float(features.get("mean", 1))
        change_pct = (f_latest - f_mean) / f_mean * 100

        model_name_raw = str(forecast_result.get("model", "unknown"))
        model_display = {"historical_average": "电力预测模型"}.get(
            model_name_raw, model_name_raw.upper() + "模型"
        )

        prompt = f"""用户问题: {user_question}

## 数据特征分析
数据时间范围为{features.get("date_range", "未知")}，共包含{features.get("data_points", 0)}个有效数据点。供电需求在{float(features.get("min", 0)):.2f}MW至{float(features.get("max", 0)):.2f}MW区间内波动，当前需求为**{f_latest:.2f}MW**，略{"高于" if change_pct > 0 else "低于" if change_pct < 0 else "等于"}均值{f_mean:.2f}MW（偏离幅度{abs(change_pct):.2f}%）。

从趋势分析来看，趋势方向为**{features.get("trend", "横盘")}**，波动程度为**{features.get("volatility", "低")}**，整体呈现出相对稳定的需求特征。

{sentiment_section}
## 预测结果
采用**{model_display}**进行预测，预测期限为{len(forecast_summary)}天。

根据预测结果，短期（7天）内预计变化为{short_term_change:+.2f}MW（{st_pct:+.2f}%），长期（{len(forecast_summary)}天）累计变化为{long_term_change:+.2f}MW（{lt_pct:+.2f}%）。

## 报告要求

**重要：请生成自然段格式的报告，不要使用要点列表。**

### 示例（Question + Case）

**问题：** 分析某区域下季度供电需求

**要点式报告（错误示例）：**
```
- 历史走势：需求在8000-12000MW区间波动
- 技术指标：趋势平稳，波动性低
- 预测结果：预计增加5%
- 建议：做好供电保障
```

**自然段报告（正确示例）：**
```
基于过去一年的数据分析，该区域供电需求呈现出**平稳增长的格局**，需求在8000-12000MW区间内波动，整体波动性较低，反映出用电模式相对稳定。从趋势分析来看，当前需求处于均值附近，趋势方向为缓慢上升，这种稳定增长状态通常与经济发展和季节性因素相关。

根据Prophet模型的预测分析，预计未来90天该区域供电需求将呈现**温和上升趋势**，累计增幅约**5%**，峰值需求预计在12500-13000MW区间。这一预测基于模型的历史回测表现（MAE=250），具有一定的参考价值。然而，考虑到极端天气事件（如寒潮、高温）可能带来的需求激增，建议电力部门采取**提前准备**的策略，在需求高峰前加强供电保障措施，同时做好需求侧管理，引导用户错峰用电，以应对可能的供电压力。
```

### 你的任务

请基于上述数据，生成一份自然段格式的分析报告，包含以下内容（以自然段形式呈现，不要用列表）：
1. 历史需求与特征分析（1-2段）
2. 影响因素评估（1段）
3. 模型预测解读（1-2段）
4. 供电保障建议（1段）
5. 风险提示（1段）

**要求：**
- 总字数控制在600-800字
- 使用自然段陈述，语气连贯
- 关键数据和结论使用 **加粗** 标记
- 避免使用"-"、"•"、"1."等列表符号
"""
        return prompt
