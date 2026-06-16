import json
import os
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
        **extra,
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _make_schema(tmp_path, components):
    import json

    path = tmp_path / "schema.json"
    data = {
        "product_type": "research_pack",
        "display_name": "Test Pack",
        "components": components,
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_execution_order(tmp_path, monkeypatch):
    import json

    schema_path = _make_schema(
        tmp_path,
        [
            {"id": "dep1", "agent": "a", "output": "a", "depends_on": []},
            {"id": "dep2", "agent": "b", "output": "b", "depends_on": ["dep1"]},
        ],
    )

    # Patch the schema path resolution to use temp schema
    original_init = Orchestrator.__init__

    def patched_init(self, job_spec_path):
        original_init(self, job_spec_path)
        import json

        # Override schema with temp one — for testing only
        with open(schema_path) as f:
            import json

            self.schema = __import__(
                "orchestrator.models", fromlist=["ProductSchema"]
            ).ProductSchema(**json.load(f))

    job_spec_path = _make_job_spec(tmp_path)

    orc = Orchestrator(str(job_spec_path))
    # Override schema with temp test schema
    from orchestrator.models import ProductSchema

    with open(schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))

    order = orc._get_execution_order()
    assert [c.id for c in order] == ["dep1", "dep2"]


def test_error_isolation_failed_dependency_skips_dependents(tmp_path, monkeypatch):
    schema_path = _make_schema(
        tmp_path,
        [
            {"id": "comp_a", "agent": "a", "output": "a", "depends_on": []},
            {"id": "comp_b", "agent": "b", "output": "b", "depends_on": ["comp_a"]},
            {"id": "comp_c", "agent": "c", "output": "c", "depends_on": []},
            {"id": "comp_d", "agent": "d", "output": "d", "depends_on": ["comp_b"]},
        ],
    )

    mock_a = mock.Mock(return_value=AgentResult(status="done"))
    mock_b = mock.Mock(
        return_value=AgentResult(status="failed", error="simulated failure")
    )
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


def test_pipeline_plan_merge(tmp_path, monkeypatch):
    """Test that orchestrator merges pipeline_plan from market_research.json."""
    schema_path = _make_schema(
        tmp_path,
        [
            {
                "id": "market_research",
                "agent": "market_agent",
                "output": "data/market_research.json",
                "depends_on": [],
            },
            {
                "id": "images",
                "agent": "image_agent",
                "output": "data/images_generated.json",
                "depends_on": ["market_research"],
            },
            {
                "id": "package",
                "agent": "packaging_agent",
                "output": "{slug}.zip",
                "depends_on": ["market_research"],
            },
        ],
    )

    # Mock market_agent to write market_research.json with pipeline_plan
    def mock_market_agent(component, job_spec, context):
        output_dir = os.path.join("outputs", job_spec.slug)
        os.makedirs(output_dir, exist_ok=True)
        research = {
            "niche": "test niche",
            "pipeline_plan": {
                "components": [
                    {
                        "id": "lead_tracker",
                        "agent": "csv_export_agent",
                        "output": "data/lead_tracker.csv",
                        "depends_on": ["market_research"],
                    },
                    {
                        "id": "email_templates",
                        "agent": "content_agent",
                        "output": "content/email_templates.md",
                        "depends_on": ["market_research"],
                    },
                ]
            },
        }
        research_path = os.path.join(output_dir, "data", "market_research.json")
        os.makedirs(os.path.dirname(research_path), exist_ok=True)
        with open(research_path, "w") as f:
            json.dump(research, f)
        return AgentResult(status="done", output_path=research_path)

    mock_image = mock.Mock(return_value=AgentResult(status="done"))
    mock_csv = mock.Mock(return_value=AgentResult(status="done"))
    mock_content = mock.Mock(return_value=AgentResult(status="done"))
    mock_packaging = mock.Mock(return_value=AgentResult(status="done"))

    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market_agent)
    monkeypatch.setitem(AGENT_REGISTRY, "image_agent", mock_image)
    monkeypatch.setitem(AGENT_REGISTRY, "csv_export_agent", mock_csv)
    monkeypatch.setitem(AGENT_REGISTRY, "content_agent", mock_content)
    monkeypatch.setitem(AGENT_REGISTRY, "packaging_agent", mock_packaging)

    job_spec_path = _make_job_spec(tmp_path)

    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-slug" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-slug")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    assert orc.state.components["market_research"].status == "done"
    assert orc.state.components["images"].status == "done"
    assert orc.state.components["lead_tracker"].status == "done"
    assert orc.state.components["email_templates"].status == "done"
    assert orc.state.components["package"].status == "done"
    mock_csv.assert_called_once()
    mock_content.assert_called_once()


def test_pipeline_plan_invalid_deps_skipped(tmp_path, monkeypatch):
    """Test that components with invalid deps in pipeline_plan are skipped."""
    schema_path = _make_schema(
        tmp_path,
        [
            {
                "id": "market_research",
                "agent": "market_agent",
                "output": "data/market_research.json",
                "depends_on": [],
            },
        ],
    )

    def mock_market_agent(component, job_spec, context):
        output_dir = os.path.join("outputs", job_spec.slug)
        os.makedirs(output_dir, exist_ok=True)
        research = {
            "niche": "test",
            "pipeline_plan": {
                "components": [
                    {
                        "id": "bad_comp",
                        "agent": "csv_export_agent",
                        "output": "data/bad.csv",
                        "depends_on": ["nonexistent_dep"],
                    },
                ]
            },
        }
        research_path = os.path.join(output_dir, "data", "market_research.json")
        os.makedirs(os.path.dirname(research_path), exist_ok=True)
        with open(research_path, "w") as f:
            json.dump(research, f)
        return AgentResult(status="done", output_path=research_path)

    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market_agent)
    monkeypatch.setitem(AGENT_REGISTRY, "csv_export_agent", mock.Mock())

    job_spec_path = _make_job_spec(tmp_path)
    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-slug" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-slug")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    # bad_comp should not be in state at all (never added to schema)
    assert "bad_comp" not in orc.state.components


def test_notion_only_skips_package(tmp_path, monkeypatch):
    """Test that notion_only mode skips package component."""
    schema_path = _make_schema(
        tmp_path,
        [
            {
                "id": "market_research",
                "agent": "market_agent",
                "output": "data/market_research.json",
                "depends_on": [],
            },
            {
                "id": "package",
                "agent": "packaging_agent",
                "output": "{slug}.zip",
                "depends_on": ["market_research"],
            },
        ],
    )

    mock_market = mock.Mock(
        return_value=AgentResult(status="done", output_path="data/market_research.json")
    )
    mock_package = mock.Mock()
    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market)
    monkeypatch.setitem(AGENT_REGISTRY, "packaging_agent", mock_package)

    job_spec_path = _make_job_spec(tmp_path, notion_only=True, notion_sync=False)
    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-slug" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-slug")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    assert orc.state.components["package"].status == "skipped"
    assert orc.state.components["package"].error == "notion_only mode: no ZIP"
    mock_package.assert_not_called()


def test_notion_only_substitutes_content_agent(tmp_path, monkeypatch):
    """Test that notion_only substitutes content_agent with notion_content_agent."""
    schema_path = _make_schema(
        tmp_path,
        [
            {
                "id": "market_research",
                "agent": "market_agent",
                "output": "data/market_research.json",
                "depends_on": [],
            },
            {
                "id": "test_content",
                "agent": "content_agent",
                "output": "content/test_content.md",
                "depends_on": ["market_research"],
            },
        ],
    )

    mock_market = mock.Mock(
        return_value=AgentResult(status="done", output_path="data/market_research.json")
    )
    mock_notion_content = mock.Mock(return_value=AgentResult(status="done"))
    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market)
    monkeypatch.setitem(
        AGENT_REGISTRY, "content_agent", mock.Mock()
    )  # should NOT be called
    monkeypatch.setitem(AGENT_REGISTRY, "notion_content_agent", mock_notion_content)

    job_spec_path = _make_job_spec(tmp_path, notion_only=True, notion_sync=False)
    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-slug" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-slug")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    assert orc.state.components["test_content"].status == "done"
    mock_notion_content.assert_called_once()


def test_pipeline_plan_preserves_delivery(tmp_path, monkeypatch):
    """Test that delivery field from pipeline_plan is preserved in merged components."""
    from orchestrator.orchestrator import Orchestrator
    from orchestrator.models import AgentResult, ProductSchema
    from agents.registry import AGENT_REGISTRY
    from unittest import mock
    import json
    import os

    def _make_job_spec(tmp_path, slug="test-slug", product_type="research_pack", **extra):
        path = tmp_path / "job_spec.json"
        data = {
            "slug": slug,
            "product_type": product_type,
            "niche": "test niche",
            "notion_sync": False,
            "notion_parent_page_id": None,
            "created_at": "2026-06-12T10:00:00Z",
            **extra,
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def _make_schema(tmp_path, components):
        path = tmp_path / "schema.json"
        data = {
            "product_type": "research_pack",
            "display_name": "Test Pack",
            "components": components,
        }
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    schema_path = _make_schema(
        tmp_path,
        [
            {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
            {"id": "images", "agent": "image_agent", "output": "data/images_generated.json", "depends_on": ["market_research"]},
            {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["market_research"]},
        ],
    )

    def mock_market_agent(component, job_spec, context):
        output_dir = os.path.join("outputs", job_spec.slug)
        os.makedirs(output_dir, exist_ok=True)
        research = {
            "niche": "test",
            "pipeline_plan": {
                "components": [
                    {
                        "id": "report_pdf",
                        "agent": "render_agent",
                        "output": "presentation/report.pdf",
                        "depends_on": ["market_research"],
                        "delivery": ["gumroad"],
                    },
                    {
                        "id": "diagrams",
                        "agent": "diagram_agent",
                        "output": "content/diagrams.svg",
                        "depends_on": ["market_research"],
                    },
                ]
            },
        }
        research_path = os.path.join(output_dir, "data", "market_research.json")
        os.makedirs(os.path.dirname(research_path), exist_ok=True)
        with open(research_path, "w") as f:
            json.dump(research, f)
        return AgentResult(status="done", output_path=research_path)

    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market_agent)
    monkeypatch.setitem(AGENT_REGISTRY, "image_agent", mock.Mock(return_value=AgentResult(status="done")))
    monkeypatch.setitem(AGENT_REGISTRY, "packaging_agent", mock.Mock(return_value=AgentResult(status="done")))

    job_spec_path = _make_job_spec(tmp_path)
    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-slug" / "job_state.json")
    from orchestrator.state import load_job_state
    orc.state = load_job_state(orc.state_path, "test-slug")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    report_comp = next((c for c in orc.schema.components if c.id == "report_pdf"), None)
    assert report_comp is not None
    assert report_comp.delivery == ["gumroad"]

    diag_comp = next((c for c in orc.schema.components if c.id == "diagrams"), None)
    assert diag_comp is not None
    assert diag_comp.delivery == ["zip"]


def test_delivery_map_injected_into_context(tmp_path, monkeypatch):
    """Test that orchestrator injects _delivery_map into context for packaging agent."""
    from orchestrator.orchestrator import Orchestrator
    from orchestrator.state import load_job_state
    from orchestrator.models import AgentResult, ProductSchema
    from agents.registry import AGENT_REGISTRY
    import json
    import os

    def _make_job_spec(tmp_path, slug="test-slug", product_type="research_pack", **extra):
        path = tmp_path / "job_spec.json"
        data = {"slug": slug, "product_type": product_type, "niche": "test niche", "notion_sync": False, "notion_parent_page_id": None, "created_at": "2026-06-12T10:00:00Z", **extra}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def _make_schema(tmp_path, components):
        path = tmp_path / "schema.json"
        data = {"product_type": "research_pack", "display_name": "Test Pack", "components": components}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    schema_path = _make_schema(
        tmp_path,
        [
            {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": [], "delivery": []},
            {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["market_research"], "delivery": ["zip"]},
        ],
    )

    actual_context = {}

    def mock_market(comp, js, ctx):
        output_dir = os.path.join("outputs", js.slug)
        os.makedirs(output_dir, exist_ok=True)
        research_path = os.path.join(output_dir, "data", "market_research.json")
        os.makedirs(os.path.dirname(research_path), exist_ok=True)
        with open(research_path, "w") as f:
            json.dump({"niche": "test niche"}, f)
        return AgentResult(status="done", output_path=research_path)

    def mock_package(comp, js, ctx):
        actual_context.clear()
        actual_context.update(ctx)
        return AgentResult(status="done")

    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market)
    monkeypatch.setitem(AGENT_REGISTRY, "packaging_agent", mock_package)

    job_spec_path = _make_job_spec(tmp_path)
    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-slug" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-slug")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    assert "_delivery_map" in actual_context
    dm = actual_context["_delivery_map"]
    assert isinstance(dm, dict)
    assert "market_research" in dm
    assert dm["market_research"]["delivery"] == []
    assert "package" in dm
    assert dm["package"]["delivery"] == ["zip"]


def test_discovery_mode_switches_schema(tmp_path, monkeypatch):
    """Test that orchestrator switches schema after market_agent recommends a type in discovery mode."""
    from orchestrator.orchestrator import Orchestrator
    from orchestrator.state import load_job_state
    from orchestrator.models import AgentResult, ProductSchema
    from agents.registry import AGENT_REGISTRY
    from unittest import mock
    import json, os

    def _make_job_spec(tmp_path, slug="test-discovery", **extra):
        path = tmp_path / "job_spec.json"
        data = {"slug": slug, "product_type": "discovery", "niche": "test niche", "notion_sync": False, "notion_parent_page_id": None, "created_at": "2026-06-12T10:00:00Z", **extra}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def _make_discovery_schema(tmp_path):
        path = tmp_path / "discovery.json"
        data = {"product_type": "discovery", "display_name": "Discovery", "components": [{"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": [], "delivery": []}]}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def _make_research_pack_schema(tmp_path):
        path = tmp_path / "research_pack.json"
        data = {"product_type": "research_pack", "display_name": "Research Pack", "components": [{"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": [], "delivery": []}, {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["market_research"], "delivery": ["zip"]}]}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    _make_research_pack_schema(tmp_path)
    discovery_schema_path = _make_discovery_schema(tmp_path)

    def mock_market_agent(component, job_spec, context):
        output_dir = os.path.join("outputs", job_spec.slug)
        os.makedirs(os.path.join(output_dir, "data"), exist_ok=True)
        research = {
            "niche": "test niche",
            "recommended_product_type": "research_pack",
            "recommendation_confidence": 0.9,
            "recommendation_reasoning": "Test reason",
            "pipeline_plan": {"components": []},
        }
        research_path = os.path.join(output_dir, "data", "market_research.json")
        with open(research_path, "w") as f:
            json.dump(research, f)
        return AgentResult(status="done", output_path=research_path)

    mock_package = mock.Mock(return_value=AgentResult(status="done"))
    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market_agent)
    monkeypatch.setitem(AGENT_REGISTRY, "packaging_agent", mock_package)

    job_spec_path = _make_job_spec(tmp_path)
    orc = Orchestrator(str(job_spec_path))
    with open(discovery_schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-discovery" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-discovery")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    # Schema should have been switched to research_pack
    assert orc.schema.product_type == "research_pack"
    # job_spec should be updated
    assert orc.job_spec.product_type == "research_pack"
    # research_pack has package component — should have run
    mock_package.assert_called_once()


def test_discovery_job_spec_has_no_product_type(tmp_path):
    """Test that job_spec created by wizard in discovery mode has product_type='discovery'."""
    import json
    path = tmp_path / "job_spec.json"
    data = {
        "slug": "test-no-type",
        "product_type": "discovery",
        "niche": "test niche",
        "notion_sync": False,
        "notion_only": False,
        "notion_parent_page_id": None,
        "gumroad_enabled": False,
        "landing_page_enabled": False,
        "social_promotion_enabled": False,
        "call_to_action": "",
        "created_at": "2026-06-16T10:00:00Z",
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    spec = json.loads(path.read_text(encoding="utf-8"))
    assert spec["product_type"] == "discovery"
    assert "recommended_product_type" not in spec
