from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import Settings
from .models import RawTrend, TrendItem
from .sample_data import PLATFORM_LABELS, PLATFORM_URLS, sample_rows
from .storage import Storage

logger = logging.getLogger(__name__)

PLATFORMS = tuple(PLATFORM_LABELS)


class CollectorError(RuntimeError):
    """Raised when a platform cannot return a usable hot-list."""


def _number(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("value", "score", "heat", "hot", "hot_score"):
            if key in value:
                return _number(value[key])
        return 0
    if not value:
        return 0
    text = str(value).strip().replace(",", "")
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*(亿|万|千|k|m|b)?", text, re.I)
    if not match:
        return 0
    base = float(match.group(1))
    suffix = (match.group(2) or "").lower()
    return base * {"千": 1_000, "万": 10_000, "亿": 100_000_000, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(suffix, 1)


def _external_id(platform: str, title: str, url: str, raw_id: Any = None) -> str:
    identity = str(raw_id or url or title)
    digest = hashlib.sha1(f"{platform}:{identity}".encode("utf-8")).hexdigest()[:20]
    return f"{platform}-{digest}"


def _list_candidates(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list) and payload and all(isinstance(row, dict) for row in payload):
        return payload
    if isinstance(payload, dict):
        for key in (
            "items",
            "data",
            "list",
            "word_list",
            "trending_list",
            "hot_search_list",
            "hotSearchList",
            "realtime",
        ):
            candidate = payload.get(key)
            found = _list_candidates(candidate)
            if found:
                return found
        for value in payload.values():
            found = _list_candidates(value)
            if found:
                return found
    return []


def _title(row: dict[str, Any]) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    for key in ("title", "word", "keyword", "query", "name", "desc"):
        value = row.get(key) or target.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _url(row: dict[str, Any], platform: str) -> str:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    for key in ("url", "mobileUrl", "mobile_url", "link", "jump_url"):
        value = row.get(key) or target.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    return PLATFORM_URLS[platform]


class TrendCollectors:
    def __init__(self, storage: Storage, settings: Settings) -> None:
        self.storage = storage
        self.settings = settings
        self._lock = asyncio.Lock()
        headers = {
            "User-Agent": "HotTrendMonitor/0.1 (+https://github.com/gibbsfreeenergy/hot-trend-monitor)",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
        }
        self.headers = headers

    def _client(self) -> httpx.AsyncClient:
        kwargs: dict[str, Any] = {"headers": self.headers, "timeout": 15, "follow_redirects": True}
        if self.settings.http_proxy_url:
            kwargs["proxy"] = self.settings.http_proxy_url
        return httpx.AsyncClient(**kwargs)

    async def collect_all(self) -> list[dict[str, Any]]:
        async with self._lock:
            async with self._client() as client:
                results = await asyncio.gather(
                    *(self._collect_platform(platform, client) for platform in PLATFORMS),
                    return_exceptions=False,
                )
            return results

    async def seed_if_empty(self) -> None:
        current = await self.storage.current_items(limit=1)
        if current:
            return
        captured_at = datetime.now(timezone.utc)
        for platform in PLATFORMS:
            raw = sample_rows(platform)
            items = [
                TrendItem(
                    platform=row.platform,
                    external_id=row.external_id,
                    title=row.title,
                    url=row.url,
                    mobile_url=row.mobile_url,
                    rank=row.rank,
                    score=row.score,
                    # Seed data should make the trend language useful on a fresh install.
                    # Live snapshots still calculate delta from the previous rank map.
                    delta=max(0, 126 - ((row.rank - 1) * 17)),
                    source="sample",
                    captured_at=captured_at,
                    author=row.author,
                    thumbnail_url=row.thumbnail_url,
                    metadata=row.metadata,
                )
                for row in raw
            ]
            await self.storage.save_snapshot(
                platform, items, source="sample", status="degraded", error="尚未完成首次实时采样"
            )

    async def _collect_platform(self, platform: str, client: httpx.AsyncClient) -> dict[str, Any]:
        previous_ranks = await self.storage.get_latest_rank_map(platform)
        captured_at = datetime.now(timezone.utc)
        try:
            raw_rows, source = await self._fetch_live(platform, client)
            if not raw_rows:
                raise CollectorError("上游返回空榜单")
            status = "ok"
            error = None
        except Exception as exc:  # noqa: BLE001
            logger.warning("collector failed for %s: %s", platform, exc)
            if not self.settings.allow_sample_fallback:
                await self.storage.save_snapshot(platform, [], source="unavailable", status="failed", error=str(exc))
                return {"platform": platform, "status": "failed", "error": str(exc), "item_count": 0}
            raw_rows = sample_rows(platform)
            source = "sample"
            status = "degraded"
            error = str(exc)[:500]

        items = [
            TrendItem(
                platform=row.platform,
                external_id=row.external_id,
                title=row.title,
                url=row.url or PLATFORM_URLS[platform],
                mobile_url=row.mobile_url or row.url or PLATFORM_URLS[platform],
                rank=row.rank,
                score=row.score,
                delta=(previous_ranks.get(row.external_id, row.rank) - row.rank)
                if row.external_id in previous_ranks
                else 0,
                source=source,
                captured_at=captured_at,
                author=row.author,
                thumbnail_url=row.thumbnail_url,
                metadata=row.metadata,
            )
            for row in raw_rows[:50]
        ]
        await self.storage.save_snapshot(platform, items, source=source, status=status, error=error)
        return {
            "platform": platform,
            "status": status,
            "source": source,
            "error": error,
            "item_count": len(items),
            "captured_at": captured_at.isoformat(),
        }

    async def _fetch_live(self, platform: str, client: httpx.AsyncClient) -> tuple[list[RawTrend], str]:
        errors: list[str] = []
        if platform == "xiaohongshu":
            try:
                return await self._fetch_xhs(client), "xhs-configured"
            except Exception as exc:  # noqa: BLE001
                errors.append(f"xhs: {exc}")
            try:
                return await self._fetch_newsnow(self.settings.newsnow_xhs_id, platform, client), "newsnow"
            except Exception as exc:  # noqa: BLE001
                errors.append(f"newsnow: {exc}")
        else:
            try:
                direct = await self._fetch_direct(platform, client)
                return direct, "platform-direct"
            except Exception as exc:  # noqa: BLE001
                errors.append(f"direct: {exc}")
            newsnow_id = "bilibili-hot-search" if platform == "bilibili" else platform
            try:
                return await self._fetch_newsnow(newsnow_id, platform, client), "newsnow"
            except Exception as exc:  # noqa: BLE001
                errors.append(f"newsnow: {exc}")
        raise CollectorError("；".join(errors) or "无可用采集器")

    async def _fetch_newsnow(self, source_id: str, platform: str, client: httpx.AsyncClient) -> list[RawTrend]:
        response = await client.get(self.settings.newsnow_api_url, params={"id": source_id, "latest": ""})
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") not in {None, "success", "cache"}:
            raise CollectorError(f"NewsNow status={payload.get('status')}")
        items = payload.get("items") or []
        rows: list[RawTrend] = []
        for rank, row in enumerate(items, 1):
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            if not title:
                continue
            url = str(row.get("url") or row.get("mobileUrl") or PLATFORM_URLS[platform])
            rows.append(
                RawTrend(
                    platform=platform,
                    external_id=_external_id(platform, title, url),
                    title=title,
                    url=url,
                    mobile_url=row.get("mobileUrl") or url,
                    rank=rank,
                    score=_number(row.get("score") or row.get("hot") or row.get("extra") or rank * 1000),
                    source="newsnow",
                    metadata={"upstream": source_id},
                )
            )
        if not rows:
            raise CollectorError("NewsNow items 为空")
        return rows

    async def _fetch_direct(self, platform: str, client: httpx.AsyncClient) -> list[RawTrend]:
        endpoints = {
            "douyin": "https://www.douyin.com/aweme/v1/web/hot/search/list/?device_platform=webapp&aid=6383",
            "weibo": "https://weibo.com/ajax/side/hotSearch",
            "bilibili": "https://s.search.bilibili.com/main/hotword?limit=50",
            "zhihu": "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50&desktop=true",
        }
        headers = dict(self.headers)
        headers["Referer"] = PLATFORM_URLS[platform]
        if platform == "zhihu":
            headers.update({"x-api-version": "3.0.91", "x-requested-with": "fetch"})
        response = await client.get(endpoints[platform], headers=headers)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error"):
            raise CollectorError(str(payload["error"].get("message") or "direct api error"))
        rows = _list_candidates(payload)
        result: list[RawTrend] = []
        for rank, row in enumerate(rows, 1):
            title = _title(row)
            if not title:
                continue
            url = _url(row, platform)
            score = _number(
                row.get("hot_score")
                or row.get("heat_score")
                or row.get("hotValue")
                or row.get("score")
                or row.get("metrics")
                or row.get("detail_text")
                or rank * 1000
            )
            result.append(
                RawTrend(
                    platform=platform,
                    external_id=_external_id(platform, title, url, row.get("id") or row.get("hot_id")),
                    title=title,
                    url=url,
                    mobile_url=url,
                    rank=rank,
                    score=score,
                    source="platform-direct",
                    thumbnail_url=row.get("icon") or row.get("thumbnail_url"),
                    metadata={"direct": True},
                )
            )
        if not result:
            raise CollectorError("direct api returned no usable rows")
        return result

    async def _fetch_xhs(self, client: httpx.AsyncClient) -> list[RawTrend]:
        if not self.settings.xhs_trend_url:
            raise CollectorError("未配置 XHS_TREND_URL；小红书榜单需使用获授权 JSON 源")
        headers = dict(self.headers)
        if self.settings.xhs_cookie:
            headers["Cookie"] = self.settings.xhs_cookie
        response = await client.get(self.settings.xhs_trend_url, headers=headers)
        response.raise_for_status()
        payload = response.json()
        rows = _list_candidates(payload)
        result: list[RawTrend] = []
        for rank, row in enumerate(rows, 1):
            title = _title(row)
            if not title:
                continue
            url = _url(row, "xiaohongshu")
            result.append(
                RawTrend(
                    platform="xiaohongshu",
                    external_id=_external_id("xiaohongshu", title, url, row.get("id") or row.get("note_id")),
                    title=title,
                    url=url,
                    mobile_url=url,
                    rank=rank,
                    score=_number(row.get("score") or row.get("hot") or row.get("likes") or rank * 1000),
                    source="xhs-configured",
                    author=row.get("author") or row.get("user_nickname"),
                    thumbnail_url=row.get("thumbnail") or row.get("image"),
                    metadata={"configured_endpoint": True},
                )
            )
        if not result:
            raise CollectorError("XHS_TREND_URL returned no usable rows")
        return result
