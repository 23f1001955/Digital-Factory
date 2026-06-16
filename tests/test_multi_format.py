import json
import os
import shutil

import pytest
from agents.csv_export_agent import run
from agents import market_agent
from orchestrator.models import ComponentSpec, JobSpec


def _clean_output(slug: str):
    path = os.path.join("outputs", slug)
    if os.path.exists(path):
        shutil.rmtree(path)


def test_csv_export_agent_multi_format(tmp_path):
    """csv_export_agent writes both CSV and XLSX when active_formats has both."""
    research_data = {
        "niche": "real estate agents",
        "database": [
            {"name": "Agent A", "city": "NYC", "phone": "555-0101"},
            {"name": "Agent B", "city": "LA", "phone": "555-0102"},
        ]
    }
    research_path = tmp_path / "research.json"
    with open(research_path, "w") as f:
        json.dump(research_data, f)

    comp = ComponentSpec(
        id="database_export",
        agent="csv_export_agent",
        output="data/test_multi_db.csv",
        depends_on=["market_research"],
        delivery=["zip"],
        capabilities=["csv", "xlsx"],
        active_formats=["csv", "xlsx"],
    )
    job = JobSpec(slug="test-multi", product_type="database", niche="real estate")
    context = {"market_research": str(research_path)}

    _clean_output("test-multi")
    result = run(comp, job, context)
    assert result.status == "done"
    assert result.output_paths is not None
    assert "csv" in result.output_paths
    assert "xlsx" in result.output_paths

    with open(result.output_paths["csv"]) as f:
        content = f.read()
    assert "Agent A" in content
    assert "NYC" in content

    import openpyxl
    wb = openpyxl.load_workbook(result.output_paths["xlsx"])
    ws = wb.active
    assert ws["A1"].value == "name"
    assert ws["A2"].value == "Agent A"
    assert ws["B2"].value == "NYC"


def test_market_agent_recommends_formats(monkeypatch):
    """Market_agent includes recommended_formats when LLM provides them."""
    monkeypatch.setattr(
        "agents.llm_client.generate_text",
        lambda p: json.dumps({
            "competitor_landscape": {"direct_competitors": [], "pricing_tiers": {}, "recommended_price": 29, "quality_gaps": [], "trending_keywords": []},
            "content_recommendations": {"tone": "professional", "key_themes": [], "seo_keywords": []},
            "market_insights": {},
            "recommended_product_type": "database",
            "recommendation_confidence": 0.85,
            "recommendation_reasoning": "High demand for lead lists",
            "recommended_formats": {
                "database_export": ["csv", "xlsx"],
                "market_research": ["pdf"],
            },
            "pipeline_plan": {"components": []},
        }),
    )

    monkeypatch.setattr("agents.research_tools.brave_search", lambda q, n: [])
    monkeypatch.setattr("agents.research_tools.duckduckgo_search", lambda q, n: [])
    monkeypatch.setattr("agents.research_tools.reddit_search", lambda q, n: [])
    monkeypatch.setattr("agents.research_tools.gdelt_news", lambda q, n: [])
    monkeypatch.setattr("agents.research_tools.newsapi_headlines", lambda q, n: [])
    monkeypatch.setattr("agents.research_tools.pytrends_data", lambda q: {})
    monkeypatch.setattr("agents.research_tools.firecrawl_scrape", lambda u: None)

    job_spec = JobSpec(slug="test-format-rec", product_type="database", niche="real estate")
    comp = ComponentSpec(id="market_research", agent="market_agent", output="data/market_research.json", depends_on=[])
    context = {}

    _clean_output("test-format-rec")
    result = market_agent.run(comp, job_spec, context)
    assert result.status == "done"

    with open(result.output_path) as f:
        research = json.load(f)

    assert "recommended_formats" in research
    assert "database_export" in research["recommended_formats"]
    assert "xlsx" in research["recommended_formats"]["database_export"]


def test_market_agent_fallback_formats(monkeypatch):
    """Market_agent fallback includes empty recommended_formats."""
    monkeypatch.setattr(
        "agents.llm_client.generate_text",
        lambda p: (_ for _ in ()).throw(Exception("LLM unavailable")),
    )

    monkeypatch.setattr("agents.research_tools.brave_search", lambda q, n: [])
    monkeypatch.setattr("agents.research_tools.duckduckgo_search", lambda q, n: [])
    monkeypatch.setattr("agents.research_tools.reddit_search", lambda q, n: [])
    monkeypatch.setattr("agents.research_tools.gdelt_news", lambda q, n: [])
    monkeypatch.setattr("agents.research_tools.newsapi_headlines", lambda q, n: [])
    monkeypatch.setattr("agents.research_tools.pytrends_data", lambda q: {})
    monkeypatch.setattr("agents.research_tools.firecrawl_scrape", lambda u: None)

    job_spec = JobSpec(slug="test-fallback-rec", product_type="discovery", niche="test")
    comp = ComponentSpec(id="market_research", agent="market_agent", output="data/market_research.json", depends_on=[])
    context = {}

    _clean_output("test-fallback-rec")
    result = market_agent.run(comp, job_spec, context)
    assert result.status == "done"

    with open(result.output_path) as f:
        research = json.load(f)

    assert "recommended_formats" in research
    assert research["recommended_formats"] == {}
