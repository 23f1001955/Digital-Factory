import os
import logging
from typing import Optional

import httpx

from channels.base import BaseChannel, ProductArtifact, PublishResult, AnalyticsData

logger = logging.getLogger(__name__)

ETSY_API_BASE = "https://api.etsy.com/v3"


class EtsyChannel(BaseChannel):
    name = "etsy"

    def __init__(self):
        self.api_key = os.getenv("ETSY_API_KEY", "")
        self.api_secret = os.getenv("ETSY_API_SECRET", "")
        self._access_token: Optional[str] = None
        self._shop_id: Optional[int] = None

    def _ensure_token(self) -> Optional[str]:
        if self._access_token:
            return self._access_token
        token = os.getenv("ETSY_ACCESS_TOKEN")
        if token:
            self._access_token = token
            return token
        return None

    def _get_shop_id(self) -> Optional[int]:
        if self._shop_id:
            return self._shop_id
        token = self._ensure_token()
        if not token:
            return None
        try:
            resp = httpx.get(
                f"{ETSY_API_BASE}/application/shops",
                headers={"x-api-key": self.api_key, "Authorization": f"Bearer {token}"},
                timeout=30.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                shops = data.get("results", data.get("data", []))
                if shops:
                    self._shop_id = shops[0].get("shop_id")
                    return self._shop_id
        except Exception as e:
            logger.warning(f"Failed to get Etsy shop ID: {e}")
        return None

    def validate(self) -> bool:
        if not self.api_key or not self.api_secret:
            return False
        token = self._ensure_token()
        if not token:
            return False
        shop_id = self._get_shop_id()
        return shop_id is not None

    def publish(self, artifact: ProductArtifact) -> PublishResult:
        token = self._ensure_token()
        shop_id = self._get_shop_id()
        if not token or not shop_id:
            return PublishResult(status="failed", error="Etsy auth not configured")

        try:
            listing_data = {
                "quantity": 1,
                "title": artifact.display_name or artifact.niche,
                "description": artifact.description or f"A {artifact.product_type.replace('_', ' ')} for {artifact.niche}.",
                "price": str(round(artifact.price_cents / 100, 2)),
                "who_made": "someone_else",
                "when_made": "made_to_order",
                "taxonomy_id": self._guess_taxonomy_id(artifact.product_type),
                "type": "download",
            }

            resp = httpx.post(
                f"{ETSY_API_BASE}/application/shops/{shop_id}/listings",
                headers={"x-api-key": self.api_key, "Authorization": f"Bearer {token}"},
                json=listing_data,
                timeout=60.0,
            )

            if resp.status_code not in (200, 201):
                return PublishResult(
                    status="failed",
                    error=f"Etsy listing create failed: {resp.status_code} {resp.text[:300]}",
                )

            listing = resp.json()
            listing_id = listing.get("listing_id")
            product_url = listing.get("url", f"https://www.etsy.com/listing/{listing_id}")

            for f in artifact.files:
                if os.path.isfile(f.path):
                    self._upload_file(listing_id, f.path)

            if listing_id:
                httpx.put(
                    f"{ETSY_API_BASE}/application/listings/{listing_id}",
                    headers={"x-api-key": self.api_key, "Authorization": f"Bearer {token}"},
                    json={"state": "active"},
                    timeout=30.0,
                )

            return PublishResult(
                status="published",
                product_id=str(listing_id) if listing_id else None,
                product_url=product_url or "",
                price_cents=artifact.price_cents,
            )

        except Exception as e:
            logger.error(f"Etsy publish failed: {e}", exc_info=True)
            return PublishResult(status="failed", error=str(e))

    def update(self, product_id: str, artifact: ProductArtifact) -> PublishResult:
        token = self._ensure_token()
        if not token:
            return PublishResult(status="failed", error="Etsy auth not configured")

        try:
            resp = httpx.put(
                f"{ETSY_API_BASE}/application/listings/{product_id}",
                headers={"x-api-key": self.api_key, "Authorization": f"Bearer {token}"},
                json={
                    "title": artifact.display_name or artifact.niche,
                    "description": artifact.description or "",
                    "price": str(round(artifact.price_cents / 100, 2)),
                },
                timeout=60.0,
            )

            if resp.status_code != 200:
                return PublishResult(
                    status="failed",
                    error=f"Etsy update failed: {resp.status_code} {resp.text[:300]}",
                )

            return PublishResult(
                status="published",
                product_id=product_id,
                price_cents=artifact.price_cents,
            )

        except Exception as e:
            logger.error(f"Etsy update failed: {e}", exc_info=True)
            return PublishResult(status="failed", error=str(e))

    def get_analytics(self, product_id: str) -> AnalyticsData:
        token = self._ensure_token()
        if not token:
            return AnalyticsData(product_slug="", product_id=product_id)
        try:
            resp = httpx.get(
                f"{ETSY_API_BASE}/application/listings/{product_id}/stats",
                headers={"x-api-key": self.api_key, "Authorization": f"Bearer {token}"},
                timeout=30.0,
            )
            if resp.status_code == 200:
                stats = resp.json()
                return AnalyticsData(
                    product_slug="",
                    product_id=product_id,
                    views=stats.get("views", 0),
                    sales=stats.get("sales", 0),
                    revenue=float(stats.get("revenue", stats.get("sales", 0))) * 0.01,
                )
        except Exception as e:
            logger.warning(f"Etsy analytics failed: {e}")
        return AnalyticsData(product_slug="", product_id=product_id)

    def _upload_file(self, listing_id: int, file_path: str) -> bool:
        token = self._ensure_token()
        if not token:
            return False
        try:
            with open(file_path, "rb") as fh:
                resp = httpx.post(
                    f"{ETSY_API_BASE}/application/listings/{listing_id}/files",
                    headers={"x-api-key": self.api_key, "Authorization": f"Bearer {token}"},
                    files={"file": (os.path.basename(file_path), fh)},
                    timeout=300.0,
                )
            return resp.status_code in (200, 201)
        except Exception as e:
            logger.warning(f"Etsy file upload failed: {e}")
            return False

    @staticmethod
    def _guess_taxonomy_id(product_type: str) -> int:
        mapping = {
            "research_pack": 1,
            "blog_kit": 1,
            "course_launch": 1,
            "prompt_pack": 1,
            "resource_pack": 1,
            "checklist": 1,
            "template": 1,
        }
        return mapping.get(product_type, 1)
