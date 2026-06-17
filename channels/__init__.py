from .base import BaseChannel, ProductArtifact, PublishResult, ArtifactFile
from .gumroad_channel import GumroadChannel

CHANNEL_REGISTRY: dict[str, type[BaseChannel]] = {
    "gumroad": GumroadChannel,
}

__all__ = ["BaseChannel", "ProductArtifact", "PublishResult", "ArtifactFile", "GumroadChannel", "CHANNEL_REGISTRY"]
