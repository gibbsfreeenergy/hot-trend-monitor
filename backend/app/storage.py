from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    import asyncpg
except ImportError:  # pragma: no cover - local fallback when dependencies are absent
    asyncpg = None

try:
    from redis.asyncio import Redis
except ImportError:  # pragma: no cover - local fallback when dependencies are absent
    Redis = None

from .models import TrendItem

logger = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS trend_snapshots (
    id BIGSERIAL PRIMARY KEY,
    platform TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    item_count INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ok',
    error TEXT,
    average_score DOUBLE PRECISION NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS trend_snapshots_platform_time_idx
    ON trend_snapshots (platform, captured_at DESC);
CREATE TABLE IF NOT EXISTS trend_items (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT NOT NULL REFERENCES trend_snapshots(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    mobile_url TEXT,
    rank INTEGER NOT NULL,
    score DOUBLE PRECISION NOT NULL DEFAULT 0,
    delta INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL,
    author TEXT,
    thumbnail_url TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    captured_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS trend_items_current_idx
    ON trend_items (platform, captured_at DESC, rank ASC);
CREATE INDEX IF NOT EXISTS trend_items_external_idx
    ON trend_items (platform, external_id, captured_at DESC);
"""


class Storage:
    def __init__(self, database_url: str, redis_url: str) -> None:
        self.database_url = database_url
        self.redis_url = redis_url
        self.pool: Any = None
        self.redis: Any = None
        self.memory_items: list[TrendItem] = []
        self.memory_snapshots: list[dict[str, Any]] = []
        self.mode = "memory"

    async def initialize(self) -> None:
        if self.database_url and asyncpg is not None:
            try:
                self.pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=5)
                async with self.pool.acquire() as connection:
                    await connection.execute(SCHEMA)
                self.mode = "postgres"
                logger.info("storage initialized with PostgreSQL")
            except Exception as exc:  # noqa: BLE001
                logger.warning("PostgreSQL unavailable, using memory storage: %s", exc)
                self.pool = None

        if self.redis_url and Redis is not None:
            try:
                self.redis = Redis.from_url(self.redis_url, decode_responses=True)
                await self.redis.ping()
                logger.info("cache initialized with Redis")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis unavailable, continuing without cache: %s", exc)
                self.redis = None

    async def close(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()
        if self.pool is not None:
            await self.pool.close()

    async def cache_get(self, key: str) -> Any:
        if self.redis is None:
            return None
        try:
            value = await self.redis.get(key)
            return json.loads(value) if value else None
        except Exception:  # noqa: BLE001
            return None

    async def cache_set(self, key: str, value: Any, ttl: int = 30) -> None:
        if self.redis is None:
            return
        try:
            await self.redis.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
        except Exception:  # noqa: BLE001
            return

    async def cache_clear(self) -> None:
        if self.redis is None:
            return
        try:
            keys = [key async for key in self.redis.scan_iter(match="hot-trend:*")]
            if keys:
                await self.redis.delete(*keys)
        except Exception:  # noqa: BLE001
            return

    async def get_latest_rank_map(self, platform: str) -> dict[str, int]:
        if self.pool is None:
            platform_snapshots = [
                row for row in self.memory_snapshots if row["platform"] == platform
            ]
            if not platform_snapshots:
                return {}
            captured_at = max(row["captured_at"] for row in platform_snapshots)
            return {
                item.external_id: item.rank
                for item in self.memory_items
                if item.platform == platform and item.captured_at == captured_at
            }

        query = """
        SELECT item.external_id, item.rank
        FROM trend_items item
        JOIN (
            SELECT DISTINCT ON (platform) id
            FROM trend_snapshots
            WHERE platform = $1
            ORDER BY platform, captured_at DESC
        ) latest ON latest.id = item.snapshot_id
        """
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(query, platform)
        return {row["external_id"]: row["rank"] for row in rows}

    async def save_snapshot(
        self,
        platform: str,
        items: list[TrendItem],
        *,
        source: str,
        status: str,
        error: str | None = None,
    ) -> None:
        average_score = sum(item.score for item in items) / len(items) if items else 0
        captured_at = items[0].captured_at if items else datetime.now(timezone.utc)
        if self.pool is None:
            self.memory_items.extend(items)
            self.memory_snapshots.append(
                {
                    "platform": platform,
                    "captured_at": captured_at,
                    "item_count": len(items),
                    "source": source,
                    "status": status,
                    "error": error,
                    "average_score": average_score,
                }
            )
            self.memory_items = self.memory_items[-1000:]
            self.memory_snapshots = self.memory_snapshots[-200:]
            return

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                snapshot_id = await connection.fetchval(
                    """
                    INSERT INTO trend_snapshots
                        (platform, captured_at, item_count, source, status, error, average_score)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    RETURNING id
                    """,
                    platform,
                    captured_at,
                    len(items),
                    source,
                    status,
                    error,
                    average_score,
                )
                await connection.executemany(
                    """
                    INSERT INTO trend_items
                        (snapshot_id, platform, external_id, title, url, mobile_url, rank,
                         score, delta, source, author, thumbnail_url, metadata, captured_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    """,
                    [
                        (
                            snapshot_id,
                            item.platform,
                            item.external_id,
                            item.title,
                            item.url,
                            item.mobile_url,
                            item.rank,
                            item.score,
                            item.delta,
                            item.source,
                            item.author,
                            item.thumbnail_url,
                            json.dumps(item.metadata or {}, ensure_ascii=False),
                            item.captured_at,
                        )
                        for item in items
                    ],
                )
        await self.cache_clear()

    async def current_items(self, platform: str | None = None, limit: int = 100) -> list[TrendItem]:
        if self.pool is None:
            platforms = {platform} if platform else {row["platform"] for row in self.memory_snapshots}
            current: list[TrendItem] = []
            for item_platform in platforms:
                timestamps = [
                    row["captured_at"]
                    for row in self.memory_snapshots
                    if row["platform"] == item_platform
                ]
                if not timestamps:
                    continue
                latest_time = max(timestamps)
                current.extend(
                    item
                    for item in self.memory_items
                    if item.platform == item_platform and item.captured_at == latest_time
                )
            return sorted(current, key=lambda item: (item.rank, item.platform))[:limit]

        query = """
        SELECT item.platform, item.external_id, item.title, item.url, item.mobile_url,
               item.rank, item.score, item.delta, item.source, item.author,
               item.thumbnail_url, item.metadata, item.captured_at
        FROM trend_items item
        JOIN (
            SELECT DISTINCT ON (platform) id, platform
            FROM trend_snapshots
            WHERE ($1::text IS NULL OR platform = $1)
            ORDER BY platform, captured_at DESC
        ) latest ON latest.id = item.snapshot_id
        ORDER BY item.platform, item.rank
        LIMIT $2
        """
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(query, platform, limit)
        return [self._row_to_item(row) for row in rows]

    async def status_rows(self) -> list[dict[str, Any]]:
        if self.pool is None:
            latest: dict[str, dict[str, Any]] = {}
            for row in self.memory_snapshots:
                old = latest.get(row["platform"])
                if old is None or row["captured_at"] > old["captured_at"]:
                    latest[row["platform"]] = row
            return list(latest.values())

        query = """
        SELECT DISTINCT ON (platform)
            platform, captured_at, item_count, source, status, error, average_score
        FROM trend_snapshots
        ORDER BY platform, captured_at DESC
        """
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(query)
        return [dict(row) for row in rows]

    async def history_series(self, hours: int = 24) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        if self.pool is None:
            return [
                {
                    "platform": row["platform"],
                    "captured_at": row["captured_at"].isoformat(),
                    "average_score": round(row["average_score"], 2),
                }
                for row in self.memory_snapshots
                if row["captured_at"] >= cutoff
            ]

        query = """
        SELECT platform, date_trunc('hour', captured_at) AS captured_at,
               ROUND(AVG(average_score)::numeric, 2) AS average_score
        FROM trend_snapshots
        WHERE captured_at >= $1
        GROUP BY platform, date_trunc('hour', captured_at)
        ORDER BY captured_at ASC
        """
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(query, cutoff)
        return [
            {
                "platform": row["platform"],
                "captured_at": row["captured_at"].isoformat(),
                "average_score": float(row["average_score"]),
            }
            for row in rows
        ]

    @staticmethod
    def _row_to_item(row: Any) -> TrendItem:
        metadata = row["metadata"] or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        return TrendItem(
            platform=row["platform"],
            external_id=row["external_id"],
            title=row["title"],
            url=row["url"],
            mobile_url=row["mobile_url"],
            rank=row["rank"],
            score=float(row["score"]),
            delta=row["delta"],
            source=row["source"],
            author=row["author"],
            thumbnail_url=row["thumbnail_url"],
            metadata=metadata,
            captured_at=row["captured_at"],
        )
