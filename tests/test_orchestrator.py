import json
from unittest import mock

from agents.registry import AGENT_REGISTRY
from orchestrator.models import AgentResult, ProductSchema
from orchestrator.orchestrator import Orchestrator
from orchestrator.state import load_job_state


def _make_job_spec(tmp_path, slug="test-slug", product_type="research_pack", **extra):
    import json
    path = tmp_path / "job_spec.json"
    data = {
        "slug": slug,
        "product_type": product_type,
        "niche": "test niche",
        "notion_sync": False,
        "notion_parent_page_id": None,
        "created_at": "2026-06-12T10:00:00Z",
        **extra
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _make_schema(tmp_path, components):
    import json
    path = tmp_path / "schema.json"
    data = {
        "product_type": "research_pack",
        "display_name": "Test Pack",
        "components": components
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_execution_order(tmp_path, monkeypatch):
    import json

    schema_path = _make_schema(tmp_path, [
        {"id": "dep1", "agent": "a", "output": "a", "depends_on": []},
        {"id": "dep2", "agent": "b", "output": "b", "depends_on": ["dep1"]}
    ])

    # Patch the schema path resolution to use temp schema
    original_init = Orchestrator.__init__
    def patched_init(self, job_spec_path):
        original_init(self, job_spec_path)
        import json
        # Override schema with temp one — for testing only
        with open(schema_path) as f:
            import json
            self.schema = __import__("orchestrator.models", fromlist=["ProductSchema"]).ProductSchema(**json.load(f))

    job_spec_path = _make_job_spec(tmp_path)

    orc = Orchestrator(str(job_spec_path))
    # Override schema with temp test schema
    from orchestrator.models import ProductSchema
    with open(schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))

    order = orc._get_execution_order()
    assert [c.id for c in order] == ["dep1", "dep2"]


def test_error_isolation_failed_dependency_skips_dependents(tmp_path, monkeypatch):
    schema_path = _make_schema(tmp_path, [
        {"id": "comp_a", "agent": "a", "output": "a", "depends_on": []},
        {"id": "comp_b", "agent": "b", "output": "b", "depends_on": ["comp_a"]},
        {"id": "comp_c", "agent": "c", "output": "c", "depends_on": []},
        {"id": "comp_d", "agent": "d", "output": "d", "depends_on": ["comp_b"]},
    ])

    mock_a = mock.Mock(return_value=AgentResult(status="done"))
    mock_b = mock.Mock(return_value=AgentResult(status="failed", error="simulated failure"))
    mock_c = mock.Mock(return_value=AgentResult(status="done"))
    mock_d = mock.Mock()

    monkeypatch.setitem(AGENT_REGISTRY, "a", mock_a)
    monkeypatch.setitem(AGENT_REGISTRY, "b", mock_b)
    monkeypatch.setitem(AGENT_REGISTRY, "c", mock_c)
    monkeypatch.setitem(AGENT_REGISTRY, "d", mock_d)

    job_spec_path = _make_job_spec(tmp_path)

    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-slug" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-slug")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    assert orc.state.components["comp_a"].status == "done"
    assert orc.state.components["comp_b"].status == "failed"
    assert orc.state.components["comp_c"].status == "done"
    assert orc.state.components["comp_d"].status == "skipped"

    mock_a.assert_called_once()
    mock_b.assert_called_once()
    mock_c.assert_called_once()
    mock_d.assert_not_called()
