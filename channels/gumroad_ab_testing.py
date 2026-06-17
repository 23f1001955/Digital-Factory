"""Cover/thumbnail A/B testing variant management."""

import os
import json
import logging
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class VariantSet:
    covers: list[str]
    thumbnails: list[str]
    active_cover: int = 0
    active_thumbnail: int = 0


def save_variant_state(variants: VariantSet, state_path: str) -> None:
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, "w") as f:
        json.dump(asdict(variants), f, indent=2)


def load_variant_state(state_path: str) -> VariantSet | None:
    try:
        with open(state_path) as f:
            data = json.load(f)
        return VariantSet(**data)
    except (FileNotFoundError, json.JSONDecodeError, TypeError) as e:
        logger.warning(f"Failed to load variant state from {state_path}: {e}")
        return None


def cycle_variant(current: int, count: int) -> int:
    return (current + 1) % count if count > 0 else 0


def upload_variants(product_id: str, variants: VariantSet, slug: str) -> dict:
    """Upload all variant covers/thumbnails to Gumroad, deploy active[0]."""
    import httpx
    token = os.getenv("GUMROAD_ACCESS_TOKEN")
    if not token:
        return {}
    result: dict = {}
    base = "https://api.gumroad.com/v2"

    for idx, cover_path in enumerate(variants.covers):
        if os.path.isfile(cover_path):
            from channels.gumroad_channel import _gumroad_upload_file
            url = _gumroad_upload_file(cover_path)
            if url and idx == variants.active_cover:
                try:
                    resp = httpx.post(
                        f"{base}/products/{product_id}/covers",
                        data={"access_token": token, "url": url},
                        timeout=60.0,
                    )
                    if resp.status_code == 200:
                        result["cover_deployed"] = url
                except Exception as e:
                    logger.warning(f"Cover deploy failed for variant {idx}: {e}")

    for idx, thumb_path in enumerate(variants.thumbnails):
        if os.path.isfile(thumb_path):
            from channels.gumroad_channel import _gumroad_upload_file
            url = _gumroad_upload_file(thumb_path)
            if url and idx == variants.active_thumbnail:
                try:
                    resp = httpx.post(
                        f"{base}/products/{product_id}/thumbnail",
                        data={"access_token": token, "url": url},
                        timeout=60.0,
                    )
                    if resp.status_code == 200:
                        result["thumbnail_deployed"] = url
                except Exception as e:
                    logger.warning(f"Thumbnail deploy failed for variant {idx}: {e}")

    return result
