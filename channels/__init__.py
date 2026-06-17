from .base import AnalyticsData, BaseChannel, ListingQualityScore, ProductArtifact, PublishResult, ArtifactFile
from .gumroad_channel import GumroadChannel

CHANNEL_REGISTRY: dict[str, type[BaseChannel]] = {
    "gumroad": GumroadChannel,
}

__all__ = ["AnalyticsData", "BaseChannel", "ListingQualityScore", "ProductArtifact", "PublishResult", "ArtifactFile", "GumroadChannel", "CHANNEL_REGISTRY"]
