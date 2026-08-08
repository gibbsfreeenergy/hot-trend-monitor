from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .collectors import PLATFORMS, TrendCollectors
from .config import settings
from .sample_data import PLATFORM_COLORS, PLATFORM_LABELS, PLATFORM_URLS
from .storage import Storage

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)


def _format_score(value: float) -> str:
    if value >= 100_000_000:
        return f"{value / 100_000_000:.1f}亿"
    if value >= 10_000:
        return f"{value / 10_000:.1f}万"
    return str(int(value))


def _platform_meta(platform: str) -> dict[str, Any]:
    return {
        "id": platform,
        "name": PLATFORM_LABELS[platform],
        "color": PLATFORM_COLORS[platform],
        "url": PLATFORM_URLS[platform],
    }


async def _dashboard(storage: Storage, platform: str | None = None) -> dict[str, Any]:
    cache_key = f"hot-trend:dashboard:{platform or 'all'}"
    cached = await storage.cache_get(cache_key)
    if cached:
        return cached

    items = await storage.current_items(platform=platform, limit=100)
    statuses = {row["platform"]: row for row in await storage.status_rows()}
    series = await storage.history_series()
    platform_rows: list[dict[str, Any]] = []
    for item_platform in PLATFORMS:
        status = statuses.get(item_platform, {})
        item_count = int(status.get("item_count") or 0)
        platform_rows.append(
            {
                **_platform_meta(item_platform),
                "item_count": item_count,
                "status": status.get("status", "pending"),
                "source": status.get("source", "pending"),
                "last_synced": status.get("captured_at").isoformat()
                if status.get("captured_at")
                else None,
                "error": status.get("error"),
                "average_score": round(float(status.get("average_score") or 0), 2),
                "rising_count": sum(1 for item in items if item.platform == item_platform and item.delta > 0),
            }
        )

    response = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "storage_mode": storage.mode,
        "platforms": platform_rows,
        "items": [item.as_dict() for item in items],
        "series": series,
        "summary": {
            "total_topics": len(items),
            "rising_topics": sum(1 for item in items if item.delta > 0),
            "active_platforms": sum(1 for row in platform_rows if row["status"] == "ok"),
            "healthy_platforms": sum(1 for row in platform_rows if row["status"] in {"ok", "pending"}),
        },
    }
    await storage.cache_set(cache_key, response)
    return response


async def _background_collect(app: FastAPI) -> None:
    if not settings.collect_on_startup:
        return
    while True:
        try:
            await app.state.collectors.collect_all()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("background collection failed")
        await asyncio.sleep(settings.collect_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = Storage(settings.database_url, settings.redis_url)
    await storage.initialize()
    collectors = TrendCollectors(storage, settings)
    await collectors.seed_if_empty()
    app.state.storage = storage
    app.state.collectors = collectors
    task = asyncio.create_task(_background_collect(app))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await storage.close()


app = FastAPI(title="热榜观测台 API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    storage: Storage = app.state.storage
    return {
        "status": "ok",
        "storage_mode": storage.mode,
        "redis": storage.redis is not None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/platforms")
async def platforms() -> list[dict[str, Any]]:
    dashboard = await _dashboard(app.state.storage)
    return dashboard["platforms"]


@app.get("/api/dashboard")
async def dashboard(platform: str | None = Query(default=None)) -> dict[str, Any]:
    if platform not in {None, "all", *PLATFORMS}:
        raise HTTPException(status_code=400, detail="不支持的平台")
    return await _dashboard(app.state.storage, None if platform in {None, "all"} else platform)


@app.post("/api/collect")
async def collect() -> dict[str, Any]:
    results = await app.state.collectors.collect_all()
    await app.state.storage.cache_clear()
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "results": results}


@app.get("/api/trends")
async def trends(
    platform: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    q: str | None = Query(default=None, max_length=100),
) -> dict[str, Any]:
    if platform not in {None, "all", *PLATFORMS}:
        raise HTTPException(status_code=400, detail="不支持的平台")
    items = await app.state.storage.current_items(None if platform in {None, "all"} else platform, limit=limit)
    if q:
        items = [item for item in items if q.lower() in item.title.lower()]
    return {"items": [item.as_dict() for item in items], "count": len(items)}


static_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{path:path}")
    async def spa(path: str) -> FileResponse:
        requested = static_dir / path
        if path and requested.is_file():
            return FileResponse(requested)
        return FileResponse(static_dir / "index.html")

