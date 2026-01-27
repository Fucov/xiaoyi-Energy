"""
统一意图识别 Agent
==================

一次 LLM 调用返回所有意图信息:
- is_in_scope: 是否在服务范围内 (金融/股票相关)
- is_forecast: 是否需要预测分析
- 工具开关: enable_rag, enable_search, enable_domain_info
- stock_mention: 提及的股票
- raw_*_keywords: 初步关键词 (股票匹配后优化)
- 预测参数: forecast_model, history_days, forecast_horizon
"""

from typing import Dict, List, Optional, Generator, Callable, Tuple
import json

from .base import BaseAgent
from app.schemas.session_schema import UnifiedIntent, ResolvedKeywords


class IntentAgent(BaseAgent):
    """统一意图识别 Agent"""

    DEFAULT_TEMPERATURE = 0.1

    INTENT_SYSTEM_PROMPT = """你是电力需求预测助手的意图识别模块。根据用户问题，一次性判断所有意图信息。

## 服务范围 (is_in_scope)

**原则：尽可能帮助用户，宽松判断，只对明显无关的问题拒绝**

- in_scope=true（绝大多数情况）:
  - 电力需求分析/预测（如"预测北京供电需求"、"分析上海用电量"）
  - 天气对电力影响相关问题
  - 新闻/资讯查询
  - 日常闲聊、打招呼（如"你好"、"谢谢"）
  - 关于助手自身的问题（如"你是谁"、"你能做什么"）
  - 任何可以用电力/天气知识或常识回答的问题
  - 模糊边界的问题（先尝试回答）

- in_scope=false（仅限明显不相关）:
  - 明确要求非电力服务（如"帮我写代码"、"翻译这段话"、"写一首诗"）
  - 此时设置 out_of_scope_reply 友好拒绝并说明能力范围

## 预测判断 (is_forecast)

判断是否需要执行电力需求预测分析：
- is_forecast=true:
  - 明确要求分析/预测供电需求（"预测北京供电需求"、"分析未来用电量"）
  - 要求改变模型重新分析（"换XGBoost模型"）
  - 要求改变时间参数（"预测未来60天"）

- is_forecast=false:
  - 只是查询新闻/资讯（"北京最近有什么天气新闻"、"寒潮影响"）
  - 闲聊或追问（"刚才的结果什么意思"）
  - 无需预测的问题

## 工具开关

判断需要启用哪些工具（可同时开启多个）：

- enable_rag: 研报知识库检索（电力相关）
  - true: 用户提到研报、研究报告、行业分析
  - 示例: "电力行业研报"、"供电需求分析报告"

- enable_search: 网络搜索
  - true: 用户明确要搜索新闻/资讯，或需要最新信息
  - 示例: "搜索北京天气新闻"、"帮我查一下寒潮影响"

- enable_domain_info: 领域信息获取
  - true: 需要获取天气/电力相关的领域信息（实时新闻、天气数据等）
  - 在预测流程中通常自动开启
  - 示例: "今天有什么天气新闻"

注意：
- 预测流程 (is_forecast=true) 通常自动开启 enable_search 和 enable_domain_info
- 非预测的新闻查询，如果用户只是随便问问，开启 enable_domain_info
- 非预测的明确搜索，开启 enable_search

## 区域提取 (region_mention + region_name)

从用户问题中提取提到的城市/区域名称：
- region_mention: 用户原始输入的区域名称
  - 单区域: "北京"、"上海"、"广州"
  - 多区域: "北京,上海" (逗号分隔，但通常只支持单区域)
  - 无区域: 留空

- region_name: 你需要将用户输入的简称/别名转换为标准城市名称
  - "帝都" → "北京"
  - "魔都" → "上海"
  - "羊城"/"花城" → "广州"
  - "鹏城" → "深圳"
  - "杭城" → "杭州"
  - "蓉城" → "成都"
  - "江城" → "武汉"
  - "古都" → "西安"
  - "金陵" → "南京"
  - "津门" → "天津"
  - 如果用户输入的已经是标准名称，直接使用
  - 多区域时用逗号分隔: "北京,上海"（但通常只支持单区域）
  - 无区域: 留空

## 关键词提取 (raw_*_keywords)

提取初步搜索关键词（后续会根据区域匹配结果优化）：
- raw_search_keywords: 网络搜索关键词
- raw_rag_keywords: 研报检索关键词
- raw_domain_keywords: 领域信息关键词

示例：
- "预测北京供电需求" → raw_search_keywords=["北京 供电需求", "北京 电力"]
- "搜索寒潮影响" → raw_search_keywords=["寒潮", "寒潮 电力"]

## 预测参数

仅 is_forecast=true 时需要设置：
- forecast_model: 如果用户明确指定了模型（如"用XGBoost"、"用prophet模型"），则返回对应的模型名称（prophet/xgboost/randomforest/dlinear）；如果用户没有指定模型，则返回 null（表示自动选择最佳模型）
- history_days: 历史数据天数 (默认365)
- forecast_horizon: 预测天数 (默认30)

根据用户描述调整：
- "用XGBoost" → forecast_model="xgboost"
- "用prophet模型" → forecast_model="prophet"
- 用户没有提到具体模型 → forecast_model=null
- "预测三个月" → forecast_horizon=90
- "看半年数据" → history_days=180

返回 JSON 格式:
{
    "is_in_scope": true/false,
    "is_forecast": true/false,
    "enable_rag": true/false,
    "enable_search": true/false,
    "enable_domain_info": true/false,
    "region_mention": "用户原始输入的区域名称或空字符串",
    "region_name": "转换后的标准城市名称或空字符串",
    "raw_search_keywords": ["关键词1", "关键词2"],
    "raw_rag_keywords": ["关键词1"],
    "raw_domain_keywords": ["关键词1"],
    "forecast_model": null,
    "history_days": 365,
    "forecast_horizon": 30,
    "reason": "判断理由",
    "out_of_scope_reply": "若超出范围的友好回复，否则为null"
}"""

    STREAMING_SYSTEM_PROMPT = """你是电力需求预测助手的意图识别模块。请先分析用户意图，然后返回结果。

## 分析步骤（请详细描述你的思考过程）

1. **理解问题**: 用户在问什么？是否涉及电力需求/天气/供电？
2. **判断范围**: 是否在服务范围内？
3. **识别意图**: 是否需要预测分析？还是只是查询/闲聊？
4. **提取信息**: 提到了哪些城市/区域？需要哪些工具？
5. **设置参数**: 如果需要预测，设置预测参数

## 服务范围 (is_in_scope) - 宽松判断
- true: 电力需求/天气相关问题、日常闲聊、关于助手的问题、任何可以回答的问题
- false: 仅限明确要求非电力服务（如写代码、翻译），需设置 out_of_scope_reply

## 预测判断 (is_forecast)
- true: 明确要求分析/预测供电需求
- false: 只是查询新闻/资讯、闲聊或追问

## 工具开关
- enable_rag: 研报知识库检索（电力相关）
- enable_search: 网络搜索
- enable_domain_info: 领域信息获取（天气新闻、电力资讯）

## 预测参数（仅 is_forecast=true）
- forecast_model: 如果用户明确指定了模型（如"用XGBoost"、"用prophet模型"），则返回对应的模型名称（prophet/xgboost/randomforest/dlinear）；如果用户没有指定模型，则返回 null（表示自动选择最佳模型）
- history_days: 历史数据天数
- forecast_horizon: 预测天数

请先输出你的思考过程，然后用 ```json 代码块输出结果：
```json
{
    "is_in_scope": true/false,
    "is_forecast": true/false,
    "enable_rag": true/false,
    "enable_search": true/false,
    "enable_domain_info": true/false,
    "region_mention": "用户原始输入的区域名称或空字符串",
    "region_name": "转换后的标准城市名称或空字符串",
    "raw_search_keywords": ["关键词"],
    "raw_rag_keywords": ["关键词"],
    "raw_domain_keywords": ["关键词"],
    "forecast_model": null,
    "history_days": 365,
    "forecast_horizon": 30,
    "reason": "简短判断理由",
    "out_of_scope_reply": null
}
```"""

    CHAT_SYSTEM_PROMPT = """你是专业的金融分析助手。根据上下文和对话历史回答用户问题。

要求：
1. 回答简洁专业
2. 如果引用了来源，使用 markdown 链接格式 [标题](url)
3. 如果引用了研报，使用格式 [研报名称](rag://文件名.pdf#page=页码)
4. 如果无法从上下文找到相关信息，如实说明"""

    def _build_intent(self, result: Dict) -> UnifiedIntent:
        """从 LLM 返回的 dict 构建 UnifiedIntent 对象"""
        return UnifiedIntent(
            is_in_scope=result.get("is_in_scope", True),
            is_forecast=result.get("is_forecast", False),
            enable_rag=result.get("enable_rag", False),
            enable_search=result.get("enable_search", False),
            enable_domain_info=result.get("enable_domain_info", False),
            # 优先使用region字段，如果没有则使用stock字段（兼容）
            region_mention=result.get("region_mention") or result.get("stock_mention") or None,
            region_name=result.get("region_name") or result.get("stock_full_name") or None,
            # 保留stock字段以兼容旧数据
            stock_mention=result.get("stock_mention") or None,
            stock_full_name=result.get("stock_full_name") or None,
            raw_search_keywords=result.get("raw_search_keywords", []),
            raw_rag_keywords=result.get("raw_rag_keywords", []),
            raw_domain_keywords=result.get("raw_domain_keywords", []),
            forecast_model=result.get("forecast_model"),  # None 表示自动选择
            history_days=result.get("history_days", 365),
            forecast_horizon=result.get("forecast_horizon", 30),
            reason=result.get("reason", ""),
            out_of_scope_reply=result.get("out_of_scope_reply")
        )

    def recognize_intent_streaming(
        self,
        user_query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        on_thinking_chunk: Optional[Callable[[str], None]] = None
    ) -> Tuple[UnifiedIntent, str]:
        """
        流式意图识别 - 实时返回思考过程

        Args:
            user_query: 用户问题
            conversation_history: 对话历史
            on_thinking_chunk: 回调函数，接收思考内容片段

        Returns:
            (UnifiedIntent, 完整思考内容)
        """
        messages = self.build_messages(
            user_content=f"用户问题: {user_query}\n\n请分析意图。",
            system_prompt=self.STREAMING_SYSTEM_PROMPT,
            conversation_history=conversation_history
        )

        # 使用状态变量跟踪是否进入 JSON 块
        state = {"full_content": "", "in_json_block": False, "thinking_content": ""}

        def _on_chunk(delta: str):
            state["full_content"] += delta

            if "```json" in state["full_content"] and not state["in_json_block"]:
                state["in_json_block"] = True
                state["thinking_content"] = state["full_content"].split("```json")[0].strip()

            if not state["in_json_block"] and on_thinking_chunk:
                on_thinking_chunk(delta)

        full_content = self.call_llm(messages, stream=True, on_chunk=_on_chunk)

        # 提取 JSON 结果
        try:
            if "```json" in full_content:
                json_str = full_content.split("```json")[1]
                if "```" in json_str:
                    json_str = json_str.split("```")[0]
                result = json.loads(json_str.strip())
            else:
                result = json.loads(full_content)
        except json.JSONDecodeError:
            print(f"[{self.agent_name}] JSON 解析失败: {full_content}")
            result = {
                "is_in_scope": True,
                "is_forecast": False,
                "reason": "解析失败，使用默认值"
            }

        thinking_content = state["thinking_content"]
        if not thinking_content:
            thinking_content = result.get("reason", "")

        return self._build_intent(result), thinking_content

    def resolve_keywords(
        self,
        intent: UnifiedIntent,
        stock_name: Optional[str] = None,  # 保留以兼容
        stock_code: Optional[str] = None,  # 保留以兼容
        region_name: Optional[str] = None,
        region_code: Optional[str] = None,
    ) -> ResolvedKeywords:
        """
        根据区域匹配结果解析最终关键词

        将 raw_*_keywords 中的区域简称替换为标准名称/代码

        Args:
            intent: 意图识别结果
            stock_name: 匹配到的股票名称（已废弃，保留以兼容）
            stock_code: 匹配到的股票代码（已废弃，保留以兼容）
            region_name: 匹配到的区域名称 (如 "北京")
            region_code: 匹配到的区域代码 (如 "BJ")

        Returns:
            ResolvedKeywords
        """
        # 优先使用region，如果没有则使用stock（兼容）
        matched_name = region_name or stock_name
        matched_code = region_code or stock_code
        
        if not matched_name and not matched_code:
            return ResolvedKeywords(
                search_keywords=intent.raw_search_keywords,
                rag_keywords=intent.raw_rag_keywords,
                domain_keywords=intent.raw_domain_keywords
            )

        search_keywords = list(intent.raw_search_keywords)
        rag_keywords = list(intent.raw_rag_keywords)
        domain_keywords = list(intent.raw_domain_keywords)

        if matched_name:
            if matched_name not in search_keywords:
                search_keywords.insert(0, matched_name)
            if matched_name not in rag_keywords:
                rag_keywords.insert(0, matched_name)
            if matched_name not in domain_keywords:
                domain_keywords.insert(0, matched_name)

        if matched_code:
            if matched_code not in search_keywords:
                search_keywords.append(matched_code)
            if matched_code not in domain_keywords:
                domain_keywords.append(matched_code)

        # 优先使用region_mention，如果没有则使用stock_mention（兼容）
        region_mention = intent.region_mention or intent.stock_mention
        
        if region_mention and matched_name and region_mention != matched_name:
            for i, kw in enumerate(search_keywords):
                if region_mention in kw:
                    search_keywords[i] = kw.replace(region_mention, matched_name)
            for i, kw in enumerate(rag_keywords):
                if region_mention in kw:
                    rag_keywords[i] = kw.replace(region_mention, matched_name)
            for i, kw in enumerate(domain_keywords):
                if region_mention in kw:
                    domain_keywords[i] = kw.replace(region_mention, matched_name)

        return ResolvedKeywords(
            search_keywords=search_keywords,
            rag_keywords=rag_keywords,
            domain_keywords=domain_keywords
        )

    def generate_chat_response(
        self,
        user_query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        context: Optional[str] = None,
        stream: bool = False
    ):
        """
        生成聊天回复 (非预测流程)

        Args:
            user_query: 用户问题
            conversation_history: 对话历史
            context: 额外上下文 (如检索到的内容)
            stream: 是否流式输出

        Returns:
            回复文本或生成器
        """
        user_content = user_query
        if context:
            user_content = f"参考信息:\n{context}\n\n用户问题: {user_query}"

        messages = self.build_messages(
            user_content=user_content,
            system_prompt=self.CHAT_SYSTEM_PROMPT,
            conversation_history=conversation_history,
            history_window=10
        )

        if stream:
            return self._stream_response(messages)
        else:
            return self.call_llm(messages, temperature=0.3)

    def _stream_response(self, messages: List[Dict]) -> Generator[str, None, None]:
        """流式响应 - 生成器模式"""
        # 使用底层 client 直接调用以支持生成器模式
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.3,
            stream=True
        )

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
