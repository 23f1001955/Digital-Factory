"""Analytics data models for sales tracking and insights."""

from collections import defaultdict
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import json
import os
import logging

logger = logging.getLogger(__name__)


class SalesRecord(BaseModel):
    product_slug: str
    channel: str
    date: datetime
    views: int = 0
    sales: int = 0
    revenue: float = 0.0
    refunds: int = 0
    conversion_rate: float = 0.0
    traffic_source: Optional[str] = None


class Insights(BaseModel):
    top_products: list[SalesRecord] = Field(default_factory=list)
    avg_conversion_rate: float = 0.0
    best_channel: str = ""
    monthly_revenue_trend: list[dict] = Field(default_factory=list)
    total_revenue: float = 0.0
    last_updated: datetime = Field(default_factory=datetime.now)

    @classmethod
    def from_records(cls, records: list[SalesRecord]) -> "Insights":
        total_revenue = sum(r.revenue for r in records)
        num = len(records)
        avg_conv = (sum(r.conversion_rate for r in records) / num) if num > 0 else 0.0

        channel_revenue: dict[str, float] = {}
        for r in records:
            channel_revenue[r.channel] = channel_revenue.get(r.channel, 0.0) + r.revenue
        best_channel = max(channel_revenue, key=channel_revenue.get) if channel_revenue else ""

        sorted_products = sorted(records, key=lambda r: r.revenue, reverse=True)

        monthly: dict[str, float] = defaultdict(float)
        for r in records:
            monthly[r.date.strftime("%Y-%m")] += r.revenue
        monthly_revenue_trend = [{"month": k, "revenue": round(v, 2)} for k, v in sorted(monthly.items())]

        return cls(
            top_products=sorted_products[:5],
            avg_conversion_rate=round(avg_conv, 2),
            best_channel=best_channel,
            monthly_revenue_trend=monthly_revenue_trend,
            total_revenue=round(total_revenue, 2),
            last_updated=datetime.now(),
        )


def save_sales_records(records: list[SalesRecord], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    deduped: dict[tuple, SalesRecord] = {}
    for r in records:
        key = (r.product_slug, r.channel, r.date.isoformat())
        if key in deduped:
            logger.warning(f"Duplicate record overwritten: {r.product_slug}/{r.channel}/{r.date}")
        deduped[key] = r
    data = [r.model_dump(mode="json") for r in deduped.values()]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def load_sales_records(path: str) -> list[SalesRecord]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return [SalesRecord(**r) for r in data]
    except Exception as e:
        logger.warning(f"Failed to load sales records from {path}: {e}")
        return []


def save_insights(insights: Insights, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(insights.model_dump(mode="json"), f, indent=2, default=str)


def load_insights(path: str) -> Insights | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return Insights(**data)
    except Exception as e:
        logger.warning(f"Failed to load insights from {path}: {e}")
        return None
