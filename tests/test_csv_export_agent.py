import json
import os

from agents.csv_export_agent import run
from orchestrator.models import ComponentSpec, JobSpec


def test_csv_export_reads_from_market_research(tmp_path):
    """csv_export_agent reads database key from market_research when no separate database context."""
    output_dir = tmp_path / "outputs" / "test-slug" / "data"
    output_dir.mkdir(parents=True)
    # Set output to relative path expected by agent
    output_path = output_dir / "test_db.csv"

    research_data = {
        "niche": "real estate agents",
        "database": [
            {"name": "Agent A", "city": "NYC", "phone": "555-0101"},
            {"name": "Agent B", "city": "LA", "phone": "555-0102"},
        ],
    }
    research_path = tmp_path / "research.json"
    with open(research_path, "w") as f:
        json.dump(research_data, f)

    comp = ComponentSpec(
        id="database_export",
        agent="csv_export_agent",
        output="data/test_db.csv",
        depends_on=["market_research"],
        delivery=["zip"],
    )
    job = JobSpec(slug="test-slug", product_type="database", niche="real estate")
    context = {"market_research": str(research_path)}

    result = run(comp, job, context)
    assert result.status == "done"
    with open(result.output_path) as f:
        content = f.read()
    assert "Agent A" in content
    assert "NYC" in content


def test_csv_export_agent(tmp_path):
    """Original test: reads database from context directly."""
    job_spec = JobSpec(
        slug="test-slug", product_type="research_pack", niche="test niche"
    )

    comp = ComponentSpec(
        id="csv",
        agent="csv_export_agent",
        output="test_output.csv",
        depends_on=["database"],
    )

    db_path = tmp_path / "database.json"
    db_data = [
        {"name": "Tool A", "url": "http://a.com"},
        {"name": "Tool B", "url": "http://b.com"},
    ]
    db_path.write_text(json.dumps(db_data))

    context = {"database": str(db_path)}

    result = run(comp, job_spec, context)

    assert result.status == "done"
    assert os.path.exists(result.output_path)


def test_csv_export_fails_without_context(tmp_path):
    """Fails cleanly when neither database nor market_research in context."""
    comp = ComponentSpec(
        id="csv",
        agent="csv_export_agent",
        output="test_output.csv",
        depends_on=[],
    )
    job = JobSpec(slug="test-slug", product_type="database", niche="test")
    result = run(comp, job, {})
    assert result.status == "failed"
    assert "Neither 'database' nor 'market_research'" in result.error
