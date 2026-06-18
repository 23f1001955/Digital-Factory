import os
import logging

import httpx

from channels.base import BaseChannel, ProductArtifact, PublishResult, AnalyticsData

logger = logging.getLogger(__name__)

STRIPE_API_BASE = "https://api.stripe.com/v1"


class StoreChannel(BaseChannel):
    name = "store"

    def __init__(self):
        self.secret_key = os.getenv("STRIPE_SECRET_KEY", "")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def validate(self) -> bool:
        if not self.secret_key:
            return False
        try:
            resp = httpx.get(
                f"{STRIPE_API_BASE}/products",
                headers=self._headers(),
                params={"limit": 1},
                timeout=15.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def publish(self, artifact: ProductArtifact) -> PublishResult:
        if not self.secret_key:
            return PublishResult(status="failed", error="STRIPE_SECRET_KEY not set")

        try:
            product_data = {
                "name": artifact.display_name or artifact.niche,
                "description": artifact.description or "",
                "metadata[slug]": artifact.slug,
                "metadata[product_type]": artifact.product_type,
                "metadata[niche]": artifact.niche,
            }

            resp = httpx.post(
                f"{STRIPE_API_BASE}/products",
                headers=self._headers(),
                data=product_data,
                timeout=30.0,
            )
            if resp.status_code not in (200, 201):
                return PublishResult(
                    status="failed",
                    error=f"Stripe product creation failed: {resp.status_code} {resp.text[:300]}",
                )

            product = resp.json()
            product_id = product["id"]

            price_data = {
                "product": product_id,
                "unit_amount": str(artifact.price_cents),
                "currency": "usd",
            }

            price_resp = httpx.post(
                f"{STRIPE_API_BASE}/prices",
                headers=self._headers(),
                data=price_data,
                timeout=30.0,
            )
            if price_resp.status_code not in (200, 201):
                logger.warning(f"Stripe price creation failed: {price_resp.text[:300]}")

            product_url = product.get("url", "")
            return PublishResult(
                status="published",
                product_id=product_id,
                product_url=product_url,
                price_cents=artifact.price_cents,
            )

        except Exception as e:
            logger.error(f"Store channel publish failed: {e}", exc_info=True)
            return PublishResult(status="failed", error=str(e))

    def update(self, product_id: str, artifact: ProductArtifact) -> PublishResult:
        if not self.secret_key:
            return PublishResult(status="failed", error="STRIPE_SECRET_KEY not set")

        try:
            resp = httpx.post(
                f"{STRIPE_API_BASE}/products/{product_id}",
                headers=self._headers(),
                data={
                    "name": artifact.display_name or artifact.niche,
                    "description": artifact.description or "",
                    "metadata[slug]": artifact.slug,
                },
                timeout=30.0,
            )

            if resp.status_code != 200:
                return PublishResult(
                    status="failed",
                    error=f"Stripe product update failed: {resp.status_code} {resp.text[:300]}",
                )

            return PublishResult(
                status="published",
                product_id=product_id,
                price_cents=artifact.price_cents,
            )

        except Exception as e:
            logger.error(f"Store channel update failed: {e}", exc_info=True)
            return PublishResult(status="failed", error=str(e))

    def get_analytics(self, product_id: str) -> AnalyticsData:
        if not self.secret_key:
            return AnalyticsData(product_slug="", product_id=product_id)
        try:
            resp = httpx.get(
                f"{STRIPE_API_BASE}/charges",
                headers=self._headers(),
                params={"product": product_id},
                timeout=30.0,
            )
            if resp.status_code == 200:
                charges = resp.json().get("data", [])
                total_revenue = sum(float(c.get("amount", 0)) for c in charges) / 100
                return AnalyticsData(
                    product_slug="",
                    product_id=product_id,
                    sales=len(charges),
                    revenue=total_revenue,
                )
        except Exception as e:
            logger.warning(f"Stripe analytics failed: {e}")
        return AnalyticsData(product_slug="", product_id=product_id)
