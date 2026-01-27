"""
区域匹配服务
============

基于城市名称的区域匹配，支持常见城市名称识别

流程:
1. LLM 意图识别生成 region_name (城市名称)
2. 匹配城市名称到标准区域信息
3. 返回区域信息（区域代码、坐标、时区）
"""

from typing import Optional, Dict
from functools import lru_cache

from app.schemas.session_schema import RegionInfo, RegionMatchResult


# 支持的城市列表（标准名称 -> 区域信息）
SUPPORTED_REGIONS: Dict[str, Dict[str, str]] = {
    "北京": {
        "region_code": "BJ",
        "region_name": "北京",
        "timezone": "Asia/Shanghai",
        "latitude": "39.9042",
        "longitude": "116.4074",
    },
    "上海": {
        "region_code": "SH",
        "region_name": "上海",
        "timezone": "Asia/Shanghai",
        "latitude": "31.2304",
        "longitude": "121.4737",
    },
    "广州": {
        "region_code": "GZ",
        "region_name": "广州",
        "timezone": "Asia/Shanghai",
        "latitude": "23.1291",
        "longitude": "113.2644",
    },
    "深圳": {
        "region_code": "SZ",
        "region_name": "深圳",
        "timezone": "Asia/Shanghai",
        "latitude": "22.5431",
        "longitude": "114.0579",
    },
    "杭州": {
        "region_code": "HZ",
        "region_name": "杭州",
        "timezone": "Asia/Shanghai",
        "latitude": "30.2741",
        "longitude": "120.1551",
    },
    "成都": {
        "region_code": "CD",
        "region_name": "成都",
        "timezone": "Asia/Shanghai",
        "latitude": "30.6624",
        "longitude": "104.0633",
    },
    "武汉": {
        "region_code": "WH",
        "region_name": "武汉",
        "timezone": "Asia/Shanghai",
        "latitude": "30.5928",
        "longitude": "114.3055",
    },
    "西安": {
        "region_code": "XA",
        "region_name": "西安",
        "timezone": "Asia/Shanghai",
        "latitude": "34.3416",
        "longitude": "108.9398",
    },
    "南京": {
        "region_code": "NJ",
        "region_name": "南京",
        "timezone": "Asia/Shanghai",
        "latitude": "32.0603",
        "longitude": "118.7969",
    },
    "天津": {
        "region_code": "TJ",
        "region_name": "天津",
        "timezone": "Asia/Shanghai",
        "latitude": "39.3434",
        "longitude": "117.3616",
    },
}

# 城市别名映射（别名 -> 标准名称）
CITY_ALIASES: Dict[str, str] = {
    "帝都": "北京",
    "魔都": "上海",
    "羊城": "广州",
    "花城": "广州",
    "鹏城": "深圳",
    "杭城": "杭州",
    "蓉城": "成都",
    "江城": "武汉",
    "古都": "西安",
    "金陵": "南京",
    "津门": "天津",
}


class RegionMatcher:
    """区域匹配服务"""

    _instance: Optional["RegionMatcher"] = None
    _region_cache: Optional[Dict] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self._region_cache = SUPPORTED_REGIONS.copy()
        print("[RegionMatcher] 初始化完成，支持城市:", ", ".join(SUPPORTED_REGIONS.keys()))

    def _normalize_region_name(self, region_name: str) -> Optional[str]:
        """
        标准化区域名称
        
        Args:
            region_name: 用户输入的区域名称
        
        Returns:
            标准化的区域名称，如果无法匹配则返回None
        """
        if not region_name:
            return None

        region_name = region_name.strip()

        # 直接匹配
        if region_name in SUPPORTED_REGIONS:
            return region_name

        # 别名匹配
        if region_name in CITY_ALIASES:
            return CITY_ALIASES[region_name]

        # 模糊匹配（包含关系）
        for standard_name in SUPPORTED_REGIONS.keys():
            if standard_name in region_name or region_name in standard_name:
                return standard_name

        # 别名模糊匹配
        for alias, standard_name in CITY_ALIASES.items():
            if alias in region_name or region_name in alias:
                return standard_name

        return None

    def match(self, region_mention: str) -> Optional[RegionMatchResult]:
        """
        匹配区域
        
        Args:
            region_mention: 用户提及的区域名称（可能是简称、别名等）
        
        Returns:
            RegionMatchResult 如果匹配成功，否则返回None
        """
        if not region_mention:
            return None

        # 标准化区域名称
        normalized_name = self._normalize_region_name(region_mention)
        if not normalized_name:
            return None

        # 获取区域信息
        region_data = self._region_cache.get(normalized_name)
        if not region_data:
            return None

        # 构建RegionInfo
        region_info = RegionInfo(
            region_code=region_data["region_code"],
            region_name=region_data["region_name"],
            timezone=region_data["timezone"],
        )

        return RegionMatchResult(
            region_info=region_info,
            matched=True,
            original_input=region_mention,
        )

    def get_all_regions(self) -> Dict[str, Dict[str, str]]:
        """获取所有支持的区域"""
        return self._region_cache.copy()

    def is_supported(self, region_name: str) -> bool:
        """检查区域是否支持"""
        normalized = self._normalize_region_name(region_name)
        return normalized is not None


# 单例获取函数
def get_region_matcher() -> RegionMatcher:
    """获取区域匹配器单例"""
    return RegionMatcher()
