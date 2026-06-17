"""CLI dashboard for analytics data."""

import sys
import argparse
from datetime import datetime, timedelta

from orchestrator.analytics_models import (
    SalesRecord, Insights,
    load_sales_records, load_insights,
)

SALES_RECORDS_PATH = "outputs/_analytics/sales_records.json"
INSIGHTS_PATH = "outputs/_analytics/insights.json"


def format_summary(records: list[SalesRecord]) -> str:
    if not records:
        return "No sales data available. Run a pipeline first."

    lines = ["=== Sales Summary ==="]
    lines.append(f"{'Product':<25} {'Channel':<12} {'Sales':<8} {'Revenue':<12} {'Conv%':<8}")
    lines.append("-" * 65)

    total_rev = sum(r.revenue for r in records)
    total_sales = sum(r.sales for r in records)

    for r in sorted(records, key=lambda x: x.revenue, reverse=True)[:20]:
        name = r.product_slug[:24]
        conv = f"{r.conversion_rate:.1f}%" if r.conversion_rate else "N/A"
        lines.append(
            f"{name:<25} {r.channel:<12} {r.sales:<8} ${r.revenue:<8.2f} {conv:<8}"
        )

    lines.append("-" * 65)
    lines.append(f"{'TOTAL':<25} {'':<12} {total_sales:<8} ${total_rev:<8.2f}")

    lines.append("")
    lines.append("=== Revenue by Product ===")
    max_rev = max(r.revenue for r in records) if records else 1
    for r in sorted(records, key=lambda x: x.revenue, reverse=True)[:20]:
        name = r.product_slug[:23]
        bar_len = max(1, int(r.revenue / max_rev * 30))
        bars = "█" * bar_len
        lines.append(f"  {name:<23} {bars} ${r.revenue:.0f}")

    return "\n".join(lines)


def format_insights(insights: Insights | None) -> str:
    if not insights:
        return "No insights available."

    lines = ["=== Key Insights ==="]
    lines.append(f"  Total Revenue:    ${insights.total_revenue:.2f}")
    lines.append(f"  Avg Conv Rate:    {insights.avg_conversion_rate:.2f}%")
    lines.append(f"  Best Channel:     {insights.best_channel or 'N/A'}")
    lines.append("")
    lines.append("  Top Products:")
    for i, p in enumerate(insights.top_products[:5], 1):
        lines.append(f"    {i}. {p.product_slug} — ${p.revenue:.2f} ({p.sales} sales)")
    return "\n".join(lines)


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Analytics Dashboard")
    parser.add_argument("--days", type=int, default=30, help="Days of history")
    parser.add_argument("--slug", type=str, default="", help="Filter by product slug")
    args, _ = parser.parse_known_args(argv)

    records = load_sales_records(SALES_RECORDS_PATH)
    insights = load_insights(INSIGHTS_PATH)

    if args.days and args.days > 0:
        cutoff = datetime.now() - timedelta(days=args.days)
        records = [r for r in records if r.date >= cutoff]

    if args.slug:
        records = [r for r in records if r.product_slug == args.slug]

    print(format_insights(insights))
    print()
    print(format_summary(records))


if __name__ == "__main__":
    main()
