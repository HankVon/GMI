"""Redis 缓存服务 — 字段元数据读取热点, 含自动降级 + 熔断"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger("cache")


class CacheService:
    """Redis 缓存封装（Redis 不可用时自动降级 + 熔断保护）"""

    def __init__(self):
        self.redis: aioredis.Redis | None = None
        # 熔断状态(阈值参数来自 Settings, 支持环境变量覆盖)
        self._failure_count: int = 0
        self._circuit_open_until: float = 0
        self._max_failures: int = settings.CIRCUIT_MAX_FAILURES
        self._circuit_timeout: int = settings.CIRCUIT_TIMEOUT_SECONDS

    async def connect(self):
        try:
            self.redis = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
            self._failure_count = 0
            self._circuit_open_until = 0
        except Exception as e:  # noqa: BLE001 - Redis 不可用时缓存自动降级, 属设计意图
            logger.warning("[cache] connect failed, running without cache: %s", e)
            self.redis = None

    async def close(self):
        if self.redis:
            try:
                await self.redis.close()
            except Exception:  # noqa: BLE001, S110 - 关闭异常忽略即可
                pass
            self.redis = None

    def _circuit_closed(self) -> bool:
        """熔断检查: 连续失败超阈值且未过冷却期 → 断路(直接返回 False,不走 Redis)"""
        if self._failure_count >= self._max_failures:
            if time.time() < self._circuit_open_until:
                return True  # circuit is OPEN, skip Redis
            else:
                # 冷却期过,半开状态尝试恢复
                self._failure_count = 0
                self._circuit_open_until = 0
        return False

    def _record_failure(self):
        self._failure_count += 1
        if self._failure_count >= self._max_failures:
            self._circuit_open_until = time.time() + self._circuit_timeout
            logger.warning("[cache] circuit breaker OPEN for %ds (failures=%d)", self._circuit_timeout, self._failure_count)

    # ── 通用操作（带降级 + 熔断） ──
    def _client(self) -> aioredis.Redis | None:
        """返回已连接且未熔断的 Redis 客户端; 否则返回 None。"""
        if self.redis is None:
            return None
        if self._circuit_closed():
            return None
        return self.redis

    async def get(self, key: str) -> str | None:
        r = self._client()
        if r is None:
            return None
        try:
            val = await r.get(key)
            self._failure_count = 0
            return val
        except Exception as e:  # noqa: BLE001 - Redis 故障降级, 属设计意图
            logger.warning("[cache] get(%s) failed, fallback: %s", key, e)
            self._record_failure()
            return None

    async def set(self, key: str, value: str, ttl: int = 3600):
        r = self._client()
        if r is None:
            return
        try:
            await r.set(key, value, ex=ttl)
            self._failure_count = 0
        except Exception as e:  # noqa: BLE001 - Redis 故障降级, 属设计意图
            logger.warning("[cache] set(%s) failed: %s", key, e)
            self._record_failure()

    async def delete(self, key: str):
        r = self._client()
        if r is None:
            return
        try:
            await r.delete(key)
            self._failure_count = 0
        except Exception as e:  # noqa: BLE001 - Redis 故障降级, 属设计意图
            logger.warning("[cache] delete(%s) failed: %s", key, e)
            self._record_failure()

    async def incr(self, key: str, ttl: int = 60) -> int | None:
        """原子自增并设置过期(限流计数)。Redis 不可用返回 None(调用方降级放行)。"""
        r = self._client()
        if r is None:
            return None
        try:
            n = await r.incr(key)
            if n == 1:
                await r.expire(key, ttl)
            self._failure_count = 0
            return n
        except Exception as e:  # noqa: BLE001 - Redis 故障降级, 属设计意图
            logger.warning("[cache] incr(%s) failed: %s", key, e)
            self._record_failure()
            return None

    async def ping(self) -> bool:
        """健康探测: Redis 连通性检查。"""
        r = self._client()
        if r is None:
            return False
        try:
            await r.ping()
            self._failure_count = 0
            return True
        except Exception as e:  # noqa: BLE001 - Redis 故障降级, 属设计意图
            logger.warning("[cache] ping failed: %s", e)
            self._record_failure()
            return False

    async def delete_pattern(self, pattern: str):
        r = self._client()
        if r is None:
            return
        try:
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor, match=pattern, count=100)
                if keys:
                    await r.delete(*keys)
                if cursor == 0:
                    break
            self._failure_count = 0
        except Exception as e:  # noqa: BLE001 - Redis 故障降级, 属设计意图
            logger.warning("[cache] delete_pattern(%s) failed: %s", pattern, e)
            self._record_failure()

    async def get_json(self, key: str) -> Any:
        """从缓存读取并反序列化为 JSON 对象(结构动态, 由调用方决定具体类型)。"""
        data = await self.get(key)
        if data:
            try:
                return json.loads(data)
            except Exception:  # noqa: BLE001 - 非法 JSON 视作缓存未命中
                return None
        return None

    async def set_json(self, key: str, value: Any, ttl: int = 3600):
        await self.set(key, json.dumps(value, ensure_ascii=False, default=str), ttl)

    # ── 字段元数据缓存 ──
    def _field_meta_key(self, entity_type: str, suffix: str = "all") -> str:
        return f"cache:field_meta:{entity_type}:{suffix}"

    async def get_field_meta_list(self, entity_type: str) -> list[dict] | None:
        return await self.get_json(self._field_meta_key(entity_type, "all"))

    async def set_field_meta_list(self, entity_type: str, meta_list: list[dict]):
        await self.set_json(
            self._field_meta_key(entity_type, "all"),
            meta_list,
            ttl=settings.CACHE_FIELD_META_TTL,
        )

    async def invalidate_field_meta(self, entity_type: str):
        await self.delete_pattern(f"cache:field_meta:{entity_type}:*")

    # ── 选项集缓存 ──
    async def get_option_set(self, code: str) -> dict | None:
        return await self.get_json(f"cache:option_set:{code}")

    async def set_option_set(self, code: str, data: dict):
        await self.set_json(
            f"cache:option_set:{code}", data, ttl=settings.CACHE_OPTION_SET_TTL
        )

    async def invalidate_option_set(self, code: str):
        await self.delete(f"cache:option_set:{code}")

    # ── 用户权限缓存 ──
    async def get_user_permissions(self, user_id: int) -> dict | None:
        return await self.get_json(f"cache:user_perm:{user_id}")

    async def set_user_permissions(self, user_id: int, perm_data: dict):
        await self.set_json(
            f"cache:user_perm:{user_id}",
            perm_data,
            ttl=settings.CACHE_USER_PERM_TTL,
        )

    async def invalidate_user_permissions(self, user_id: int):
        await self.delete(f"cache:user_perm:{user_id}")


cache_service = CacheService()
