from .base import AnalyticsData, BaseChannel, ListingQualityScore, ProductArtifact, PublishResult, ArtifactFile
from .gumroad_channel import GumroadChannel
from .etsy_channel import EtsyChannel

CHANNEL_REGISTRY: dict[str, type[BaseChannel]] = {
    "gumroad": GumroadChannel,
    "etsy": EtsyChannel,
}

__all__ = ["AnalyticsData", "BaseChannel", "ListingQualityScore", "ProductArtifact", "PublishResult", "ArtifactFile", "GumroadChannel", "EtsyChannel", "CHANNEL_REGISTRY"]
