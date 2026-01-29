"""
多因素相关性分析摘要生成 Agent
==============================

使用 LLM 生成多因素相关性分析的摘要
"""

from typing import Dict, Any, List, Optional

from .base import BaseAgent


class InfluenceSummaryAgent(BaseAgent):
    """多因素相关性分析摘要生成 Agent"""

    DEFAULT_TEMPERATURE = 0.4

    SYSTEM_PROMPT = """你是资深的电力需求分析专家。你的任务是根据多因素相关性分析结果，生成一段简洁、准确、逻辑自洽的分析摘要。

**核心要求：**
1. 摘要长度控制在150-250字，语言自然流畅
2. 准确描述主要影响因子及其影响力得分
3. 准确描述相关性关系（正相关/负相关）及其含义
4. 如果提供了时间段变化数据，要具体描述该时间段内的变化情况，但不要明确说明具体的日期范围
5. 使用模糊的时间描述，如"在分析的时间段内"、"在近期"、"在某段时间"等，避免使用具体的日期（如"2025年11月10日至2026年1月27日"）
6. 确保逻辑自洽：如果整体是负相关，时间段内两者同向变化时要说明差异和可能原因
7. 使用专业但易懂的语言，避免过于技术化的表述
8. 关键数据要准确，不要编造或推测
9. 如果时间段内的变化趋势与整体相关性不一致，要明确说明并解释可能的原因"""

    def generate_summary(
        self,
        time_range: Dict[str, str],
        ranking: List[Dict[str, Any]],
        period_info: Optional[Dict[str, Any]] = None,
        factor_name_cn: Optional[str] = None
    ) -> str:
        """
        生成多因素相关性分析摘要

        Args:
            time_range: 时间范围字典，包含 'start' 和 'end'
            ranking: 因子影响力排行榜列表
            period_info: 时间段变化信息（可选）
            factor_name_cn: 主要因子的中文名称（可选）

        Returns:
            生成的摘要文本
        """
        prompt = self._build_prompt(time_range, ranking, period_info, factor_name_cn)
        
        messages = self.build_messages(user_content=prompt, system_prompt=self.SYSTEM_PROMPT)
        
        content = self.call_llm(messages, fallback=None)
        
        if content is None:
            print(f"[{self.agent_name}] LLM 生成摘要失败")
            return None
        
        return content.strip()

    def _build_prompt(
        self,
        time_range: Dict[str, str],
        ranking: List[Dict[str, Any]],
        period_info: Optional[Dict[str, Any]] = None,
        factor_name_cn: Optional[str] = None
    ) -> str:
        """
        构建生成摘要的 prompt

        Args:
            time_range: 时间范围字典
            ranking: 因子影响力排行榜
            period_info: 时间段变化信息
            factor_name_cn: 主要因子中文名称

        Returns:
            prompt 文本
        """
        prompt_parts = []
        
        # 时间范围（不明确显示，仅用于内部参考）
        # 注意：不要在摘要中明确说明具体的时间段，使用模糊描述
        prompt_parts.append("## 分析时间范围（内部参考，不要在摘要中明确说明）")
        prompt_parts.append(f"数据时间范围：{time_range.get('start', '未知')} 至 {time_range.get('end', '未知')}")
        prompt_parts.append("请在摘要中使用模糊的时间描述，如'在分析的时间段内'、'在近期'等，不要使用具体日期。")
        prompt_parts.append("")
        
        # 因子影响力排名
        prompt_parts.append("## 因子影响力排名")
        for i, factor in enumerate(ranking[:5], 1):  # 只取前5个因子
            factor_name_cn_val = factor.get('factor_name_cn', factor.get('factor', '未知'))
            influence_score = factor.get('influence_score', 0)
            correlation = factor.get('correlation', 0)
            
            # 判断相关性方向
            if correlation > 0.3:
                corr_desc = f"正相关（相关系数：{correlation:.3f}）"
            elif correlation < -0.3:
                corr_desc = f"负相关（相关系数：{correlation:.3f}）"
            else:
                corr_desc = f"相关性较弱（相关系数：{correlation:.3f}）"
            
            prompt_parts.append(
                f"{i}. {factor_name_cn_val}: 影响力得分 {influence_score:.2f}, {corr_desc}"
            )
        prompt_parts.append("")
        
        # 时间段变化信息（如果存在）
        if period_info:
            prompt_parts.append("## 主要因子时间段变化（内部参考，不要在摘要中使用具体日期）")
            
            # 格式化日期（仅用于内部参考，不在摘要中显示）
            start_date = period_info.get('start_date', '')
            end_date = period_info.get('end_date', '')
            if hasattr(start_date, 'strftime'):
                start_date_str = start_date.strftime('%Y-%m-%d')
            else:
                start_date_str = str(start_date)
            if hasattr(end_date, 'strftime'):
                end_date_str = end_date.strftime('%Y-%m-%d')
            else:
                end_date_str = str(end_date)
            
            prompt_parts.append(f"内部时间段参考：{start_date_str} 至 {end_date_str}")
            prompt_parts.append("请在摘要中使用模糊描述，如'在某段时间'、'在近期某段时期'等，不要使用具体日期。")
            
            if factor_name_cn:
                factor_start = period_info.get('factor_start', 0)
                factor_end = period_info.get('factor_end', 0)
                factor_change = period_info.get('factor_change', 0)
                
                # 判断因子类型，生成合适的描述
                factor_name_val = str(period_info.get('factor_name', ''))
                if 'temperature' in factor_name_val or '气温' in factor_name_cn:
                    unit = "℃"
                    if factor_change < 0:
                        factor_desc = f"{factor_name_cn}从{factor_start:.1f}{unit}降至{factor_end:.1f}{unit}（下降{abs(factor_change):.1f}{unit}）"
                    else:
                        factor_desc = f"{factor_name_cn}从{factor_start:.1f}{unit}升至{factor_end:.1f}{unit}（上升{factor_change:.1f}{unit}）"
                elif 'humidity' in factor_name_val or '湿度' in factor_name_cn:
                    unit = "%"
                    if factor_change < 0:
                        factor_desc = f"{factor_name_cn}从{factor_start:.1f}{unit}降至{factor_end:.1f}{unit}（下降{abs(factor_change):.1f}{unit}）"
                    else:
                        factor_desc = f"{factor_name_cn}从{factor_start:.1f}{unit}升至{factor_end:.1f}{unit}（上升{factor_change:.1f}{unit}）"
                else:
                    factor_desc = f"{factor_name_cn}从{factor_start:.2f}变化至{factor_end:.2f}（变化{factor_change:+.2f}）"
                
                prompt_parts.append(f"{factor_desc}")
            
            power_start = period_info.get('power_start', 0)
            power_end = period_info.get('power_end', 0)
            power_change = period_info.get('power_change', 0)
            power_change_pct = period_info.get('power_change_pct', 0)
            
            if power_change > 0:
                power_desc = f"供电需求从{power_start:.0f}MW增至{power_end:.0f}MW（增加{power_change:.0f}MW，增幅{abs(power_change_pct):.1f}%）"
            else:
                power_desc = f"供电需求从{power_start:.0f}MW降至{power_end:.0f}MW（减少{abs(power_change):.0f}MW，降幅{abs(power_change_pct):.1f}%）"
            
            prompt_parts.append(f"{power_desc}")
            prompt_parts.append("")
        
        prompt_parts.append("请基于以上数据生成分析摘要。")
        
        return "\n".join(prompt_parts)
