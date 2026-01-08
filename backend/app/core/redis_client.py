"""
Redis 客户端模块
===============

管理 Redis 连接
"""

import os
import redis
from redis import Redis
from typing import Optional


class RedisClient:
    """Redis 客户端单例"""
    
    _instance: Optional[Redis] = None
    
    @classmethod
    def get_client(cls) -> Redis:
        """获取 Redis 客户端实例"""
        if cls._instance is None:
            cls._instance = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=int(os.getenv("REDIS_DB", 0)),
                decode_responses=True,  # 自动解码为字符串
                socket_connect_timeout=5,
                socket_timeout=5
            )
        return cls._instance
    
    @classmethod
    def close(cls):
        """关闭 Redis 连接"""
        if cls._instance:
            cls._instance.close()
            cls._instance = None


def get_redis() -> Redis:
    """获取 Redis 客户端（依赖注入使用）"""
    return RedisClient.get_client()
