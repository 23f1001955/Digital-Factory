import pytest
from orchestrator.models import ComponentSpec
from orchestrator.orchestrator import Orchestrator

# Basic test to check topological sort
def test_execution_order(tmp_path):
    import json
    
    # Mock job_spec
    job_spec_path = tmp_path / "job_spec.json"
    job_spec_path.write_text(json.dumps({
        "slug": "test-slug",
        "product_type": "research_pack",
        "niche": "test niche",
        "notion_sync": False,
        "notion_parent_page_id": None,
        "created_at": "2026-06-12T10:00:00Z"
    }))
    
    # Needs to mock schemas/research_pack.json
    import os
    os.makedirs("schemas", exist_ok=True)
    with open("schemas/research_pack.json", "w") as f:
        json.dump({
            "product_type": "research_pack",
            "display_name": "Test Pack",
            "notion_sync": False,
            "components": [
                {"id": "dep1", "agent": "a", "output": "a", "depends_on": []},
                {"id": "dep2", "agent": "b", "output": "b", "depends_on": ["dep1"]}
            ]
        }, f)
        
    orc = Orchestrator(str(job_spec_path))
    order = orc._get_execution_order()
    assert [c.id for c in order] == ["dep1", "dep2"]
