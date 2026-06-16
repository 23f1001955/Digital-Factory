import json
import os
import pytest
from agents.csv_export_agent import run
from orchestrator.models import ComponentSpec, JobSpec


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
