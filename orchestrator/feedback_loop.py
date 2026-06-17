"""Feedback loop: past performance data → next pipeline run context."""

import logging
from datetime import datetime

from orchestrator.analytics_models import SalesRecord, Insights

logger = logging.getLogger(__name__)


def build_past_performance(records: list[SalesRecord], insights: Insights) -> dict:
    if not records:
        return {
            "total_revenue": 0.0,
            "avg_conversion_rate": 0.0,
            "total_sales": 0,
            "total_views": 0,
            "top_seller": None,
            "best_performing_niches": [],
        }

    top = max(records, key=lambda r: r.revenue) if records else None
    top_seller = None
    if top:
        top_seller = {
            "slug": top.product_slug,
            "revenue": round(top.revenue, 2),
            "sales": top.sales,
            "niche": top.product_slug.replace("-", " ").title(),
        }

    total_views = sum(r.views for r in records)
    weighted_conv = sum(r.views * r.conversion_rate for r in records) / total_views if total_views > 0 else 0.0

    niches: dict[str, dict] = {}
    for r in records:
        niche_key = r.product_slug.split("-")[0] if "-" in r.product_slug else r.product_slug
        if niche_key not in niches:
            niches[niche_key] = {"revenue": 0.0, "sales": 0, "count": 0}
        niches[niche_key]["revenue"] += r.revenue
        niches[niche_key]["sales"] += r.sales
        niches[niche_key]["count"] += 1

    sorted_niches = sorted(niches.items(), key=lambda x: x[1]["revenue"], reverse=True)
    best_niches = [n[0].title() for n in sorted_niches[:3]]

    return {
        "total_revenue": round(insights.total_revenue, 2),
        "avg_conversion_rate": round(weighted_conv, 2),
        "total_sales": sum(r.sales for r in records),
        "total_views": sum(r.views for r in records),
        "top_seller": top_seller,
        "best_performing_niches": best_niches,
    }


def generate_prompt_section(past_performance: dict) -> str:
    if not past_performance or not past_performance.get("total_revenue", 0) > 0:
        return ""

    lines = [
        "=== PAST PERFORMANCE DATA ===",
        f"Total Revenue: ${past_performance.get('total_revenue', 0):,.2f}",
        f"Average Conversion Rate: {past_performance.get('avg_conversion_rate', 0):.2f}%",
        f"Total Sales: {past_performance.get('total_sales', 0)}",
    ]

    top = past_performance.get("top_seller")
    if top:
        lines.append(f"Top Seller: {top['slug']} (${top['revenue']:.2f})")
        lines.append(f"Top Niche Signal: {top['niche']}")

    niches = past_performance.get("best_performing_niches", [])
    if niches:
        lines.append(f"Best Performing Niches: {', '.join(niches)}")

    lines.append("Focus on niches and product types similar to your top performers.")
    lines.append("")

    return "\n".join(lines)


def inject_feedback(context: dict, records: list[SalesRecord], insights: Insights) -> None:
    pp = build_past_performance(records, insights)
    context["past_performance"] = pp
    prompt_section = generate_prompt_section(pp)
    if prompt_section:
        context["_feedback_prompt_section"] = prompt_section
        logger.info(f"Feedback injected: ${pp['total_revenue']:.2f} total revenue from {len(records)} records")
    else:
        logger.info("No past performance data to inject")
