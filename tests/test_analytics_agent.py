import os
import json
import pytest
from datetime import datetime
from orchestrator.models import ComponentSpec, JobSpec
from orchestrator.analytics_models import SalesRecord, Insights


def test_analytics_agent_run_no_channels(monkeypatch):
    monkeypatch.setattr("agents.analytics_agent.CHANNEL_REGISTRY", {})
    from agents.analytics_agent import run
    comp = ComponentSpec(id="analytics", agent="analytics_agent", output="analytics")
    job_spec = JobSpec(slug="test-slug", product_type="research_pack", niche="test")
    result = run(comp, job_spec, {"channel_results": {}})
    assert result.status == "done"
    assert result.output_path is not None


def test_analytics_agent_run_with_gumroad(monkeypatch):
    monkeypatch.delenv("GUMROAD_ACCESS_TOKEN", raising=False)
    from channels.base import AnalyticsData

    class FakeChannel:
        name = "gumroad"
        def get_analytics(self, product_id: str):
            return AnalyticsData(
                product_slug="test-product", product_id=product_id,
                date=datetime.now(), views=100, sales=5,
                revenue=49.99, conversion_rate=5.0,
            )

    monkeypatch.setattr("agents.analytics_agent.CHANNEL_REGISTRY", {"gumroad": lambda: FakeChannel()})

    from agents.analytics_agent import run
    comp = ComponentSpec(id="analytics", agent="analytics_agent", output="analytics")
    job_spec = JobSpec(slug="test-slug", product_type="research_pack", niche="test")
    context = {"channel_results": {"gumroad": type("obj", (), {"product_id": "prod_123", "status": "published"})()}}
    result = run(comp, job_spec, context)
    assert result.status == "done"
    assert result.output_path is not None


def test_analytics_agent_aggregates_data(monkeypatch, tmp_path):
    records_path = tmp_path / "sales_records.json"
    monkeypatch.setattr("agents.analytics_agent.SALES_RECORDS_PATH", str(records_path))
    monkeypatch.setattr("agents.analytics_agent.CHANNEL_REGISTRY", {})

    from agents.analytics_agent import run
    comp = ComponentSpec(id="analytics", agent="analytics_agent", output="analytics")
    job_spec = JobSpec(slug="test-slug", product_type="research_pack", niche="test")
    result = run(comp, job_spec, {"channel_results": {}})

    assert os.path.exists(records_path)
    with open(records_path) as f:
        data = json.load(f)
    assert isinstance(data, list)


def test_analytics_agent_skips_if_disabled(monkeypatch):
    monkeypatch.setattr("agents.analytics_agent.CHANNEL_REGISTRY", {})
    from agents.analytics_agent import run
    comp = ComponentSpec(id="analytics", agent="analytics_agent", output="analytics")
    job_spec = JobSpec(slug="test-slug", product_type="research_pack", niche="test", channels=[])
    result = run(comp, job_spec, {"channel_results": {}})
    assert result.status == "done"


def test_analytics_agent_preserves_existing_records(monkeypatch, tmp_path):
    existing = tmp_path / "sales_records.json"
    existing.write_text(json.dumps([
        {"product_slug": "old-product", "channel": "gumroad", "date": "2026-06-01T00:00:00",
         "views": 50, "sales": 2, "revenue": 19.99, "refunds": 0, "conversion_rate": 4.0, "traffic_source": None},
    ]))
    monkeypatch.setattr("agents.analytics_agent.SALES_RECORDS_PATH", str(existing))
    monkeypatch.setattr("agents.analytics_agent.CHANNEL_REGISTRY", {})

    from agents.analytics_agent import run
    comp = ComponentSpec(id="analytics", agent="analytics_agent", output="analytics")
    job_spec = JobSpec(slug="new-slug", product_type="research_pack", niche="test")
    run(comp, job_spec, {"channel_results": {}})

    with open(existing) as f:
        data = json.load(f)
    assert any(r["product_slug"] == "old-product" for r in data)
