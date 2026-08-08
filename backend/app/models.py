from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class RawTrend:
    platform: str
    external_id: str
    title: str
    url: str
    rank: int
    score: float
    source: str
    author: str | None = None
    thumbnail_url: str | None = None
    mobile_url: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class TrendItem:
    platform: str
    external_id: str
    title: str
    url: str
    rank: int
    score: float
    delta: int
    source: str
    captured_at: datetime
    author: str | None = None
    thumbnail_url: str | None = None
    mobile_url: str | None = None
    metadata: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "external_id": self.external_id,
            "title": self.title,
            "url": self.url,
            "mobile_url": self.mobile_url,
            "rank": self.rank,
            "score": round(self.score, 2),
            "delta": self.delta,
            "source": self.source,
            "captured_at": self.captured_at.isoformat(),
            "author": self.author,
            "thumbnail_url": self.thumbnail_url,
            "metadata": self.metadata or {},
        }

