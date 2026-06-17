"""Analytics agent: collects sales data from all channels, aggregates, computes insights."""

import os
import logging
from datetime import datetime

from channels import CHANNEL_REGISTRY
from channels.base import AnalyticsData
from orchestrator.models import ComponentSpec, JobSpec, AgentResult
from orchestrator.analytics_models import (
    SalesRecord, Insights,
    load_sales_records, save_sales_records,
    load_insights, save_insights,
)

logger = logging.getLogger(__name__)

SALES_RECORDS_PATH = "outputs/_analytics/sales_records.json"
INSIGHTS_PATH = "outputs/_analytics/insights.json"


def _get_product_ids_from_context(context: dict) -> list[str]:
    ids = []
    channel_results = context.get("channel_results", {})
    for ch_name, ch_result in channel_results.items():
        if hasattr(ch_result, "product_id") and ch_result.product_id:
            ids.append(ch_result.product_id)
        elif isinstance(ch_result, dict):
            pid = ch_result.get("product_id") or ch_result.get("id", "")
            if pid:
                ids.append(pid)
    return ids


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        os.makedirs(os.path.dirname(SALES_RECORDS_PATH), exist_ok=True)
        existing = load_sales_records(SALES_RECORDS_PATH)
        new_records: list[SalesRecord] = []
        product_ids = _get_product_ids_from_context(context)

        if not product_ids:
            logger.info("No product IDs available from channel results — skipping analytics pull")
        else:
            for channel_name, channel_class in CHANNEL_REGISTRY.items():
                try:
                    channel = channel_class() if callable(channel_class) else channel_class
                    for pid in product_ids:
                        record = channel.get_analytics(pid)
                        if record:
                            if isinstance(record, AnalyticsData):
                                record = SalesRecord(
                                    product_slug=job_spec.slug,
                                    channel=channel_name,
                                    date=record.date,
                                    views=record.views,
                                    sales=record.sales,
                                    revenue=record.revenue,
                                    refunds=record.refunds,
                                    conversion_rate=record.conversion_rate,
                                    traffic_source=record.traffic_source,
                                )
                            else:
                                record.product_slug = job_spec.slug
                            new_records.append(record)
                except Exception as e:
                    logger.warning(f"Analytics pull failed for channel {channel_name}: {e}")

        all_records = existing + new_records
        save_sales_records(all_records, SALES_RECORDS_PATH)

        insights = Insights.from_records(all_records)
        save_insights(insights, INSIGHTS_PATH)

        logger.info(
            f"Analytics complete: {len(new_records)} new records, "
            f"{len(all_records)} total, "
            f"revenue=${insights.total_revenue:.2f}"
        )

        return AgentResult(status="done", output_path=SALES_RECORDS_PATH)

    except Exception as e:
        logger.error(f"Analytics agent failed: {e}")
        return AgentResult(status="done", output_path=SALES_RECORDS_PATH)
