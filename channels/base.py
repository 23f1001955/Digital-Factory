from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class ArtifactFile(BaseModel):
    path: str
    name: str
    delivery_tags: List[str] = []


class ProductArtifact(BaseModel):
    slug: str
    product_type: str
    niche: str
    display_name: str
    files: List[ArtifactFile]
    cover_image: Optional[str] = None
    thumbnail: Optional[str] = None
    description: str = ""
    price_cents: int = 0
    tags: List[str] = []
    research_data_path: Optional[str] = None
    cover_variants: list[str] = []
    thumbnail_variants: list[str] = []


class PublishResult(BaseModel):
    status: str
    product_url: str = ""
    product_id: Optional[str] = None
    price_cents: int = 0
    error: Optional[str] = None


class AnalyticsData(BaseModel):
    product_slug: str
    product_id: str
    date: datetime = datetime.now()
    views: int = 0
    sales: int = 0
    revenue: float = 0.0
    refunds: int = 0
    conversion_rate: float = 0.0
    traffic_source: Optional[str] = None


class ListingQualityScore(BaseModel):
    overall_score: float = 0.0
    description_score: float = 0.0
    tag_score: float = 0.0
    cover_score: float = 0.0
    price_score: float = 0.0
    research_alignment: float = 0.0
    issues: list[str] = []
    passed: bool = True


class BaseChannel(ABC):
    name: str = "base"

    @abstractmethod
    def validate(self) -> bool:
        ...

    @abstractmethod
    def publish(self, artifact: ProductArtifact) -> PublishResult:
        ...

    @abstractmethod
    def update(self, product_id: str, artifact: ProductArtifact) -> PublishResult:
        ...

    def get_analytics(self, product_id: str) -> "AnalyticsData":
        return AnalyticsData(product_slug="", product_id=product_id)
