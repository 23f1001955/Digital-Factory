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


PRODUCT_TYPE_ALIASES = {
    "research-pack": "research_pack",
    "blog-kit": "blog_kit",
    "prompt-pack": "prompt_pack",
    "visual-pack": "visual_pack",
    "saas-docs": "saas_docs",
    "course-launch": "course_launch",
    "operating-system": "operating_system",
    "workflow-kit": "workflow_kit",
    "sop-pack": "sop_pack",
    "swipe-file": "swipe_file",
    "excel-template": "excel_template",
    "resource-pack": "resource_pack",
    "checklist": "checklist",
    "boilerplate": "boilerplate",
    "database": "database",
}


def _slug_to_product_type(slug: str) -> str:
    for pattern, ptype in PRODUCT_TYPE_ALIASES.items():
        if pattern in slug:
            return ptype
    return ""


def compute_score_adjustment(records: list[SalesRecord]) -> dict[str, float]:
    if not records:
        return {}

    product_type_revenue: dict[str, float] = {}
    for r in records:
        ptype = _slug_to_product_type(r.product_slug)
        if not ptype:
            continue
        if ptype not in product_type_revenue:
            product_type_revenue[ptype] = 0.0
        product_type_revenue[ptype] += r.revenue

    if not product_type_revenue:
        return {}

    max_revenue = max(product_type_revenue.values())
    adjustments: dict[str, float] = {}
    for ptype, revenue in product_type_revenue.items():
        ratio = revenue / max_revenue if max_revenue > 0 else 0
        if ratio >= 0.8:
            adjustments[ptype] = 5.0
        elif ratio >= 0.5:
            adjustments[ptype] = 2.0
        elif ratio >= 0.2:
            adjustments[ptype] = 0.0
        else:
            adjustments[ptype] = -2.0

    return adjustments


def apply_score_adjustments(scores: dict[str, float], adjustments: dict[str, float]) -> dict[str, float]:
    result = dict(scores)
    for ptype, adj in adjustments.items():
        if ptype in result:
            result[ptype] = max(0.0, result[ptype] + adj)
    return result
