from .base import AnalyticsData, BaseChannel, ListingQualityScore, ProductArtifact, PublishResult, ArtifactFile
from .gumroad_channel import GumroadChannel
from .etsy_channel import EtsyChannel
from .store_channel import StoreChannel

CHANNEL_REGISTRY: dict[str, type[BaseChannel]] = {
    "gumroad": GumroadChannel,
    "etsy": EtsyChannel,
    "store": StoreChannel,
}

__all__ = ["AnalyticsData", "BaseChannel", "ListingQualityScore", "ProductArtifact", "PublishResult", "ArtifactFile", "GumroadChannel", "EtsyChannel", "StoreChannel", "CHANNEL_REGISTRY"]
