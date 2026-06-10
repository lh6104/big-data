from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    accident = "accident"
    flood = "flood"
    road_work = "road_work"
    event = "event"
    weather = "weather"
    other = "other"


class City(str, Enum):
    ha_noi = "Ha Noi"
    ho_chi_minh = "Ho Chi Minh"
    unknown = "unknown"


class GeocodeStatus(str, Enum):
    ok = "ok"
    failed = "failed"
    skipped = "skipped"


class NewsEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"ev_{uuid.uuid4().hex[:12]}")
    source: str
    source_url: str
    crawled_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: Optional[datetime] = None

    title: str
    content: str = ""

    event_type: EventType = EventType.other
    severity: int = Field(default=0, ge=0, le=3)

    location_entity: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    snapped_segment_id: Optional[str] = None
    snap_distance_m: Optional[float] = None
    event_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    geocode_status: GeocodeStatus = GeocodeStatus.skipped

    city: City = City.unknown
    mirrored_sources: List[str] = Field(default_factory=list)
    raw_html_path: Optional[str] = None

    @field_validator("severity")
    @classmethod
    def severity_range(cls, v: int) -> int:
        return max(0, min(3, v))

    def make_event_id(self) -> str:
        ts = self.crawled_at.strftime("%Y%m%d%H")
        h = hashlib.sha1(self.source_url.encode()).hexdigest()[:6]
        return f"ev_{ts}_{h}"

    def to_kafka_dict(self) -> dict:
        data = self.model_dump(mode="json")
        data["crawled_at"] = self.crawled_at.isoformat()
        if self.published_at:
            data["published_at"] = self.published_at.isoformat()
        return data


class RawArticle(BaseModel):
    """Bài viết thô trước khi qua NLP/Geocoder."""
    external_id: str
    source: str
    source_type: str          # "rss" | "html"
    title: str
    summary: str = ""
    content: str = ""
    link: str
    published_at: Optional[datetime] = None
    city_hint: Optional[str] = None
    html_raw: bytes = b""
