"""
城市工业结构数据获取客户端
==========================

使用LLM获取城市GDP和第二产业增加值数据，计算工业结构比例
"""

from typing import Dict, Optional
import json
from app.agents.base import BaseAgent


class IndustryStructureClient(BaseAgent):
    """城市工业结构数据客户端"""

    DEFAULT_TEMPERATURE = 0.1

    def __init__(self):
        super().__init__()
        self._cache: Dict[str, Dict[str, float]] = {}

    def fetch_industry_structure_data(self, city_name: str) -> Dict[str, float]:
        """
        获取城市工业结构数据

        Args:
            city_name: 城市名称，如"北京"、"上海"

        Returns:
            包含以下字段的字典：
            - second_industry_ratio: 第二产业增加值占GDP的比例 (0-1)
            - year: 数据年份
            - source: 数据来源说明
        """
        # 检查缓存
        if city_name in self._cache:
            print(f"[IndustryStructure] 使用缓存数据: {city_name}")
            return self._cache[city_name]

        # 使用LLM获取数据
        system_prompt = """你是一个经济数据查询助手。根据给定的中国城市名称，查询该城市在2020-2025年之间任意一年的以下数据：

1. 地区生产总值（GDP，单位：亿元人民币）
2. 第二产业增加值（工业+建筑，单位：亿元人民币）

要求：
- 只需选择2020-2025年中任意一个你最容易查到的年份
- 数据来源应来自公开资料，如城市统计公报、统计年鉴摘要或权威新闻稿
- 不要求绝对精确，但数值量级必须合理
- 明确说明所选年份和数据来源

请以JSON格式返回结果：
{
    "year": 2023,
    "gdp": 1234.5,
    "industry2": 456.7,
    "source": "数据来源说明，如：2023年XX市统计公报"
}

如果无法找到数据，返回：
{
    "year": null,
    "gdp": null,
    "industry2": null,
    "source": "无法找到数据"
}"""

        user_prompt = f"请查询城市「{city_name}」的GDP和第二产业增加值数据。"

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response = self.call_llm(
                messages,
                response_format={"type": "json_object"},
                temperature=self.DEFAULT_TEMPERATURE,
                fallback='{"year": null, "gdp": null, "industry2": null, "source": "LLM调用失败"}'
            )

            # 解析JSON响应
            data = json.loads(response)

            # 验证数据
            year = data.get("year")
            gdp = data.get("gdp")
            industry2 = data.get("industry2")
            source = data.get("source", "未知来源")

            if year is None or gdp is None or industry2 is None:
                print(f"[IndustryStructure] 无法获取 {city_name} 的数据，使用默认值")
                result = {
                    "second_industry_ratio": 0.3,  # 全国平均工业结构比例约30%
                    "year": None,
                    "source": "使用默认值（全国平均）"
                }
            else:
                # 验证数据合理性
                if gdp <= 0 or industry2 < 0:
                    print(f"[IndustryStructure] {city_name} 数据不合理（GDP={gdp}, Industry2={industry2}），使用默认值")
                    result = {
                        "second_industry_ratio": 0.3,
                        "year": year,
                        "source": "数据不合理，使用默认值"
                    }
                else:
                    # 计算第二产业比例
                    ratio = industry2 / gdp
                    # 确保比例在合理范围内（0-1）
                    ratio = max(0.0, min(1.0, ratio))

                    result = {
                        "second_industry_ratio": ratio,
                        "year": year,
                        "source": source
                    }

                    print(f"[IndustryStructure] {city_name} ({year}年): GDP={gdp:.2f}亿元, 第二产业={industry2:.2f}亿元, 比例={ratio:.2%}")

            # 缓存结果
            self._cache[city_name] = result
            return result

        except Exception as e:
            print(f"[IndustryStructure] 获取 {city_name} 数据失败: {e}")
            result = {
                "second_industry_ratio": 0.3,
                "year": None,
                "source": f"错误: {str(e)}"
            }
            # 即使出错也缓存，避免重复调用
            self._cache[city_name] = result
            return result


# 单例实例
_industry_structure_client: Optional[IndustryStructureClient] = None


def get_industry_structure_client() -> IndustryStructureClient:
    """获取城市工业结构客户端单例"""
    global _industry_structure_client
    if _industry_structure_client is None:
        _industry_structure_client = IndustryStructureClient()
    return _industry_structure_client
