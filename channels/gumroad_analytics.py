"""Gumroad analytics: sales/views data pull + listing quality scoring."""

import os
import logging
from datetime import datetime

import httpx

from channels.base import AnalyticsData, ListingQualityScore, ProductArtifact

logger = logging.getLogger(__name__)

GUMROAD_API_BASE = "https://api.gumroad.com/v2"


def _gumroad_get(path: str) -> dict | None:
    token = os.getenv("GUMROAD_ACCESS_TOKEN")
    if not token:
        return None
    try:
        resp = httpx.get(
            f"{GUMROAD_API_BASE}/{path.lstrip('/')}",
            params={"access_token": token},
            timeout=60.0,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning(f"Gumroad GET {path} failed: {e}")
    return None


def pull_analytics(product_id: str) -> AnalyticsData:
    product_data = _gumroad_get(f"products/{product_id}")
    sales_data = _gumroad_get("sales")

    views = 0
    sales = 0
    revenue = 0.0
    refunds = 0
    conversion_rate = 0.0

    if product_data and "product" in product_data:
        p = product_data["product"]
        views = int(p.get("views", 0) or 0)
        sales = int(p.get("sales_count", 0) or 0)
        revenue = float(p.get("total_revenue", 0.0) or 0.0)
        conversion_rate = float(p.get("conversion_rate", 0.0) or 0.0)
        refunds = int(p.get("refund_count", 0) or 0)

    if product_data is None and sales_data and "sales" in sales_data:
        for sale in sales_data.get("sales", []):
            if sale.get("product_id") == product_id:
                sales += 1
                price_str = sale.get("formatted_price", "0")
                try:
                    revenue += float(price_str.replace("$", "").replace(",", ""))
                except (ValueError, TypeError):
                    revenue += 0.0
                if sale.get("charged") is False:
                    refunds += 1

    return AnalyticsData(
        product_slug="",
        product_id=product_id,
        date=datetime.now(),
        views=views,
        sales=sales,
        revenue=revenue,
        refunds=refunds,
        conversion_rate=conversion_rate,
    )


def _check_description(description: str) -> tuple[float, list[str]]:
    issues = []
    words = description.split()
    word_count = len(words)
    if word_count < 100:
        issues.append(f"Description too short ({word_count} words, min 100)")
        return 0.1, issues
    if word_count < 300:
        return 0.5, issues
    aida_keywords = [
        "attention", "struggl", "problem", "interest", "solution",
        "desire", "proof", "result", "action", "download", "buy", "start",
    ]
    aida_count = sum(1 for kw in aida_keywords if kw in description.lower())
    aida_score = min(aida_count / 6, 1.0)
    return 0.5 + 0.5 * aida_score, issues


def _check_tags(tags: list[str]) -> tuple[float, list[str]]:
    issues = []
    if len(tags) < 3:
        issues.append(f"Only {len(tags)} tags (min 3)")
        return len(tags) / 3.0, issues
    if len(tags) >= 5:
        return 1.0, issues
    return 0.7, issues


def _check_cover(cover_image: str | None) -> tuple[float, list[str]]:
    issues = []
    if not cover_image:
        issues.append("No cover image")
        return 0.0, issues
    if os.path.isfile(cover_image):
        return 1.0, issues
    issues.append(f"Cover image not found: {cover_image}")
    return 0.3, issues


def _check_price(price_cents: int, research_data: dict | None) -> tuple[float, list[str]]:
    issues = []
    if price_cents <= 0:
        issues.append("Price is $0 or negative")
        return 0.0, issues
    if not research_data:
        return 0.7, issues
    prices = []
    for comp in (research_data.get("competitors", []) or []):
        p = comp.get("price_cents") or comp.get("price", 0)
        if isinstance(p, (int, float)) and p > 0:
            prices.append(int(p))
    if not prices:
        return 0.7, issues
    median = sorted(prices)[len(prices) // 2]
    ratio = price_cents / max(median, 1)
    if 0.7 <= ratio <= 1.3:
        return 1.0, issues
    issues.append(f"Price ${price_cents/100:.2f} outside 30% of median ${median/100:.2f}")
    return 0.4, issues


def _check_research_alignment(artifact: ProductArtifact, research_data: dict | None) -> tuple[float, list[str]]:
    if not research_data:
        return 0.5, []
    desc_lower = (artifact.description or "").lower()
    competitors = research_data.get("competitors", []) or []
    for comp in competitors:
        name = comp.get("name", "")
        if name and name.lower() in desc_lower:
            return 1.0, []
    trending = research_data.get("trending_keywords", []) or []
    for kw in trending:
        if isinstance(kw, str) and kw.lower() in desc_lower:
            return 0.8, []
    return 0.3, []


def score_listing_quality(
    artifact: ProductArtifact,
    research_data: dict | None = None,
) -> ListingQualityScore:
    all_issues: list[str] = []
    desc_score, desc_issues = _check_description(artifact.description or "")
    all_issues.extend(desc_issues)
    tag_score, tag_issues = _check_tags(artifact.tags or [])
    all_issues.extend(tag_issues)
    cover_score, cover_issues = _check_cover(artifact.cover_image)
    all_issues.extend(cover_issues)
    price_score, price_issues = _check_price(artifact.price_cents, research_data)
    all_issues.extend(price_issues)
    research_alignment, alignment_issues = _check_research_alignment(artifact, research_data)
    all_issues.extend(alignment_issues)

    overall = (
        desc_score * 0.30
        + tag_score * 0.15
        + cover_score * 0.20
        + price_score * 0.20
        + research_alignment * 0.15
    )

    return ListingQualityScore(
        overall_score=round(overall, 2),
        description_score=round(desc_score, 2),
        tag_score=round(tag_score, 2),
        cover_score=round(cover_score, 2),
        price_score=round(price_score, 2),
        research_alignment=round(research_alignment, 2),
        issues=all_issues,
        passed=overall >= 0.4,
    )
