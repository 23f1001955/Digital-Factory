from .base import AnalyticsData, BaseChannel, ListingQualityScore, ProductArtifact, PublishResult, ArtifactFile
from .gumroad_channel import GumroadChannel
from .etsy_channel import EtsyChannel
from .store_channel import StoreChannel
from .shopify_channel import ShopifyChannel

CHANNEL_REGISTRY: dict[str, type[BaseChannel]] = {
    "gumroad": GumroadChannel,
    "etsy": EtsyChannel,
    "store": StoreChannel,
    "shopify": ShopifyChannel,
}

__all__ = ["AnalyticsData", "BaseChannel", "ListingQualityScore", "ProductArtifact", "PublishResult", "ArtifactFile", "GumroadChannel", "EtsyChannel", "StoreChannel", "ShopifyChannel", "CHANNEL_REGISTRY"]
