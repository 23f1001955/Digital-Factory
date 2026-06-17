"""Analytics agent: collects sales data from all channels, aggregates, computes insights."""

import os
import json
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


def _get_product_ids() -> list[str]:
    ids: list[str] = []
    output_dir = "outputs"
    if not os.path.isdir(output_dir):
        return ids
    for slug in os.listdir(output_dir):
        state_path = os.path.join(output_dir, slug, "job_state.json")
        if os.path.isfile(state_path):
            try:
                with open(state_path) as f:
                    state = json.load(f)
                publish_result = state.get("components", {}).get("gumroad_publish", {})
                publish_path = publish_result.get("output_path")
                if publish_path and os.path.exists(publish_path):
                    with open(publish_path) as pf:
                        pd = json.load(pf)
                    ids.extend(_extract_product_ids(pd))
            except Exception:
                continue
    return ids


def _extract_product_ids(publish_data: dict) -> list[str]:
    ids = []
    if isinstance(publish_data, dict):
        pid = publish_data.get("product_id")
        if pid:
            ids.append(pid)
    return ids


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        os.makedirs(os.path.dirname(SALES_RECORDS_PATH), exist_ok=True)

        existing = load_sales_records(SALES_RECORDS_PATH)

        new_records: list[SalesRecord] = []
        slug = job_spec.slug

        for channel_name, channel_class in CHANNEL_REGISTRY.items():
            try:
                channel = channel_class() if callable(channel_class) else channel_class
                product_ids = _get_product_ids()
                for pid in product_ids:
                    record = channel.get_analytics(pid)
                    if record:
                        if isinstance(record, AnalyticsData):
                            record = SalesRecord(
                                product_slug=slug,
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
                            record.product_slug = slug
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
