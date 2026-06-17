from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class SocialPost:
    id: str = field(default_factory=_new_id)
    platform: str = ""
    content: str = ""
    media_urls: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    scheduled_at: Optional[datetime] = None
    sequence: str = "launch"
    day: int = 0
    status: str = "draft"
    angle: str = ""


@dataclass
class ContentCalendar:
    niche: str = ""
    product_type: str = ""
    launch_date: Optional[datetime] = None
    posts: list[SocialPost] = field(default_factory=list)
    days: int = 14


@dataclass
class PostResult:
    post_id: str = ""
    platform: str = ""
    status: str = "failed"
    external_id: Optional[str] = None
    error: Optional[str] = None
    posted_at: Optional[datetime] = None


@dataclass
class EngagementMetrics:
    post_id: str = ""
    platform: str = ""
    likes: int = 0
    comments: int = 0
    shares: int = 0
    clicks: int = 0
    impressions: int = 0


@dataclass
class PlatformConfig:
    platform: str = ""
    enabled: bool = True
    max_hashtags: int = 30
    image_required: bool = True
    character_limit: int = 2200
    posting_frequency: str = "daily"
