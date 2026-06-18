import os
import logging
import base64
from typing import Optional

import httpx

from channels.base import BaseChannel, ProductArtifact, PublishResult, AnalyticsData

logger = logging.getLogger(__name__)


class ShopifyChannel(BaseChannel):
    name = "shopify"

    def __init__(self):
        self.store_url = os.getenv("SHOPIFY_STORE_URL", "")
        self.access_token = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
        if self.store_url and not self.store_url.startswith("https://"):
            self.store_url = f"https://{self.store_url}"

    def _api_base(self) -> str:
        return f"{self.store_url}/admin/api/2024-01"

    def _headers(self) -> dict:
        return {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    def validate(self) -> bool:
        if not self.store_url or not self.access_token:
            return False
        try:
            resp = httpx.get(
                f"{self._api_base()}/products.json",
                headers=self._headers(),
                params={"limit": 1},
                timeout=15.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def publish(self, artifact: ProductArtifact) -> PublishResult:
        if not self.validate():
            return PublishResult(status="failed", error="Shopify auth not configured")

        try:
            product_data = {
                "product": {
                    "title": artifact.display_name or artifact.niche,
                    "body_html": artifact.description or "",
                    "vendor": "Digital Factory",
                    "product_type": artifact.product_type.replace("_", " ").title(),
                    "tags": ", ".join(artifact.tags) if artifact.tags else artifact.niche,
                    "status": "draft",
                    "variants": [
                        {
                            "price": str(round(artifact.price_cents / 100, 2)),
                            "requires_shipping": False,
                        }
                    ],
                }
            }

            resp = httpx.post(
                f"{self._api_base()}/products.json",
                headers=self._headers(),
                json=product_data,
                timeout=60.0,
            )

            if resp.status_code not in (200, 201):
                return PublishResult(
                    status="failed",
                    error=f"Shopify product creation failed: {resp.status_code} {resp.text[:300]}",
                )

            product = resp.json()["product"]
            product_id = product["id"]
            product_url = f"https://{self.store_url}/products/{product.get('handle', '')}"

            if artifact.cover_image and os.path.isfile(artifact.cover_image):
                self._upload_image(product_id, artifact.cover_image)

            return PublishResult(
                status="published",
                product_id=str(product_id),
                product_url=product_url,
                price_cents=artifact.price_cents,
            )

        except Exception as e:
            logger.error(f"Shopify publish failed: {e}", exc_info=True)
            return PublishResult(status="failed", error=str(e))

    def update(self, product_id: str, artifact: ProductArtifact) -> PublishResult:
        if not self.validate():
            return PublishResult(status="failed", error="Shopify auth not configured")

        try:
            numeric_id = product_id.split("/")[-1] if "gid" in product_id else product_id
            resp = httpx.put(
                f"{self._api_base()}/products/{numeric_id}.json",
                headers=self._headers(),
                json={
                    "product": {
                        "id": int(numeric_id),
                        "title": artifact.display_name or artifact.niche,
                        "body_html": artifact.description or "",
                    }
                },
                timeout=60.0,
            )

            if resp.status_code != 200:
                return PublishResult(
                    status="failed",
                    error=f"Shopify update failed: {resp.status_code} {resp.text[:300]}",
                )

            return PublishResult(
                status="published",
                product_id=product_id,
                price_cents=artifact.price_cents,
            )

        except Exception as e:
            logger.error(f"Shopify update failed: {e}", exc_info=True)
            return PublishResult(status="failed", error=str(e))

    def get_analytics(self, product_id: str) -> AnalyticsData:
        if not self.validate():
            return AnalyticsData(product_slug="", product_id=product_id)
        try:
            numeric_id = product_id.split("/")[-1] if "gid" in product_id else product_id
            resp = httpx.get(
                f"{self._api_base()}/orders.json",
                headers=self._headers(),
                params={"status": "any", "limit": 250},
                timeout=30.0,
            )
            if resp.status_code == 200:
                orders = resp.json().get("orders", [])
                product_orders = [
                    o
                    for o in orders
                    for item in o.get("line_items", [])
                    if str(item.get("product_id")) == numeric_id
                ]
                total_revenue = sum(float(o.get("total_price", 0)) for o in product_orders)
                return AnalyticsData(
                    product_slug="",
                    product_id=product_id,
                    sales=len(product_orders),
                    revenue=total_revenue,
                )
        except Exception as e:
            logger.warning(f"Shopify analytics failed: {e}")
        return AnalyticsData(product_slug="", product_id=product_id)

    def _upload_image(self, product_id: int, image_path: str) -> bool:
        try:
            with open(image_path, "rb") as fh:
                encoded = base64.b64encode(fh.read()).decode("utf-8")
            resp = httpx.post(
                f"{self._api_base()}/products/{product_id}/images.json",
                headers=self._headers(),
                json={"image": {"attachment": encoded, "filename": os.path.basename(image_path)}},
                timeout=120.0,
            )
            return resp.status_code in (200, 201)
        except Exception as e:
            logger.warning(f"Shopify image upload failed: {e}")
            return False
