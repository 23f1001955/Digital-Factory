from abc import ABC, abstractmethod
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


class PublishResult(BaseModel):
    status: str
    product_url: str = ""
    product_id: Optional[str] = None
    price_cents: int = 0
    error: Optional[str] = None


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

    def get_analytics(self, product_id: str) -> dict:
        return {}
