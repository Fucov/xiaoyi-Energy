"""
快速追问建议生成 Agent
=======================

根据对话上下文生成相关的快速追问建议
"""

from typing import List, Dict, Optional

from .base import BaseAgent


class SuggestionAgent(BaseAgent):
    """快速追问建议生成 Agent"""

    DEFAULT_TEMPERATURE = 0.7

    SYSTEM_PROMPT = """你是电力分析助手的快速追问建议生成器。根据对话历史，生成4个相关的快速追问建议。

要求：
1. 如果对话中提到了具体的区域（如"北京"、"上海"），追问建议应该围绕该区域的供电/天气情况
2. 如果对话中提到了预测结果，追问建议可以包括：准确率、极端天气风险、保障建议等
3. 如果对话中提到了模型，追问建议可以包括：换模型、参数调整等
4. 如果对话为空或没有明确主题，提供通用的电力/天气分析建议
5. 每个建议应该简洁明了，不超过20个字
6. 建议应该具有实际价值，能够帮助用户深入了解分析结果

返回格式：JSON数组，包含4个字符串
{
    "suggestions": ["建议1", "建议2", "建议3", "建议4"]
}"""

    DEFAULT_SUGGESTIONS = [
        "帮我预测北京下周供电需求",
        "分析最近的寒潮天气影响",
        "查看上海的历史用电数据",
        "生成一份供电保障分析报告",
    ]

    def generate_suggestions(
        self, conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> List[str]:
        """
        根据对话历史生成快速追问建议

        Args:
            conversation_history: 对话历史，格式: [{"role": "user", "content": "..."}, ...]

        Returns:
            4个相关的快速追问建议列表
        """
        # 构建用户消息
        if conversation_history:
            context_parts = ["对话历史："]
            recent_history = (
                conversation_history[-6:]
                if len(conversation_history) > 6
                else conversation_history
            )
            for msg in recent_history:
                role_name = "用户" if msg["role"] == "user" else "助手"
                context_parts.append(f"{role_name}: {msg['content']}")
            user_content = (
                "\n".join(context_parts)
                + "\n\n请根据以上对话历史，生成4个相关的快速追问建议。"
            )
        else:
            user_content = "当前没有对话历史，请生成4个通用的股票分析快速追问建议。"

        messages = self.build_messages(
            user_content=user_content, system_prompt=self.SYSTEM_PROMPT
        )

        content = self.call_llm(
            messages, fallback="{}", response_format={"type": "json_object"}
        )

        result = self.parse_json_safe(content, {"suggestions": []})
        suggestions = result.get("suggestions", [])

        # 确保返回4个建议，不足则补充默认建议
        while len(suggestions) < 4:
            suggestions.append(self.DEFAULT_SUGGESTIONS[len(suggestions)])

        return suggestions[:4]
