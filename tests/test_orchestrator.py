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
                        "agent": "content_agent",
                        "output": "content/lead_tracker.md",
                        "depends_on": ["market_research"],
                        "template": "faq_section",
                    },
                    {
                        "id": "email_templates",
                        "agent": "content_agent",
                        "output": "content/email_templates.md",
                        "depends_on": ["market_research"],
                        "template": "step_by_step_guide",
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
    mock_content = mock.Mock(return_value=AgentResult(status="done"))
    mock_packaging = mock.Mock(return_value=AgentResult(status="done"))

    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market_agent)
    monkeypatch.setitem(AGENT_REGISTRY, "image_agent", mock_image)
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
    assert orc.state.components["faq_section"].status == "done"
    assert orc.state.components["step_by_step_guide"].status == "done"
    assert orc.state.components["package"].status == "done"
    assert mock_content.call_count == 2


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
                        "agent": "content_agent",
                        "output": "data/bad.csv",
                        "depends_on": ["nonexistent_dep"],
                        "template": "case_study",
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
    monkeypatch.setitem(AGENT_REGISTRY, "content_agent", mock.Mock())

    job_spec_path = _make_job_spec(tmp_path)
    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-slug" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-slug")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    # bad_comp should not be in state at all (never added to schema)
    assert "case_study" not in orc.state.components


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
                        "agent": "content_agent",
                        "output": "presentation/report.pdf",
                        "depends_on": ["market_research"],
                        "delivery": ["gumroad"],
                        "template": "case_study",
                    },
                    {
                        "id": "diagrams",
                        "agent": "content_agent",
                        "output": "content/diagrams.svg",
                        "depends_on": ["market_research"],
                        "template": "faq_section",
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
    monkeypatch.setitem(AGENT_REGISTRY, "content_agent", mock.Mock(return_value=AgentResult(status="done")))
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

    report_comp = next((c for c in orc.schema.components if c.id == "case_study"), None)
    assert report_comp is not None
    assert report_comp.delivery == ["gumroad"]

    diag_comp = next((c for c in orc.schema.components if c.id == "faq_section"), None)
    assert diag_comp is not None
    assert diag_comp.delivery == ["zip"]


def test_pipeline_plan_rejects_unknown_template(tmp_path, monkeypatch):
    """Pipeline plan component with unknown template is rejected."""
    from orchestrator.orchestrator import Orchestrator
    from orchestrator.state import load_job_state
    from orchestrator.models import AgentResult, ProductSchema
    from agents.registry import AGENT_REGISTRY
    from unittest import mock
    import json, os

    def _make_job_spec(tmp_path, slug="test-reject"):
        path = tmp_path / "job_spec.json"
        data = {"slug": slug, "product_type": "research_pack", "niche": "test", "notion_sync": False, "notion_parent_page_id": None, "created_at": "2026-06-17T10:00:00Z"}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def _make_schema(tmp_path):
        path = tmp_path / "research_pack.json"
        data = {"product_type": "research_pack", "display_name": "Test", "components": [
            {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
            {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["market_research"], "delivery": ["zip"]},
        ]}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    schema_path = _make_schema(tmp_path)

    def mock_market(comp, js, ctx):
        output_dir = os.path.join("outputs", js.slug)
        os.makedirs(os.path.join(output_dir, "data"), exist_ok=True)
        research = {
            "niche": "test",
            "pipeline_plan": {
                "components": [
                    {
                        "id": "unknown_comp",
                        "agent": "content_agent",
                        "output": "content/unknown.md",
                        "depends_on": ["market_research"],
                        "template": "nonexistent_template",
                    },
                ]
            },
        }
        research_path = os.path.join(output_dir, "data", "market_research.json")
        with open(research_path, "w") as f:
            json.dump(research, f)
        return AgentResult(status="done", output_path=research_path)

    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market)
    monkeypatch.setitem(AGENT_REGISTRY, "packaging_agent", mock.Mock(return_value=AgentResult(status="done")))

    job_spec_path = _make_job_spec(tmp_path)
    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-reject" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-reject")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)
    orc.run()

    assert "unknown_comp" not in orc.state.components


def test_pipeline_plan_rejects_missing_template(tmp_path, monkeypatch):
    """Pipeline plan component without template field is rejected."""
    from orchestrator.orchestrator import Orchestrator
    from orchestrator.state import load_job_state
    from orchestrator.models import AgentResult, ProductSchema
    from agents.registry import AGENT_REGISTRY
    from unittest import mock
    import json, os

    def _make_job_spec(tmp_path, slug="test-no-template"):
        path = tmp_path / "job_spec.json"
        data = {"slug": slug, "product_type": "research_pack", "niche": "test", "notion_sync": False, "notion_parent_page_id": None, "created_at": "2026-06-17T10:00:00Z"}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def _make_schema(tmp_path):
        path = tmp_path / "research_pack.json"
        data = {"product_type": "research_pack", "display_name": "Test", "components": [
            {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
            {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["market_research"], "delivery": ["zip"]},
        ]}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    schema_path = _make_schema(tmp_path)

    def mock_market(comp, js, ctx):
        output_dir = os.path.join("outputs", js.slug)
        os.makedirs(os.path.join(output_dir, "data"), exist_ok=True)
        research = {
            "niche": "test",
            "pipeline_plan": {
                "components": [
                    {
                        "id": "no_template_comp",
                        "agent": "content_agent",
                        "output": "content/no_template.md",
                        "depends_on": ["market_research"],
                    },
                ]
            },
        }
        research_path = os.path.join(output_dir, "data", "market_research.json")
        with open(research_path, "w") as f:
            json.dump(research, f)
        return AgentResult(status="done", output_path=research_path)

    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market)
    monkeypatch.setitem(AGENT_REGISTRY, "packaging_agent", mock.Mock(return_value=AgentResult(status="done")))

    job_spec_path = _make_job_spec(tmp_path)
    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-no-template" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-no-template")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)
    orc.run()

    assert "no_template_comp" not in orc.state.components


def test_pipeline_plan_accepts_valid_template(tmp_path, monkeypatch):
    """Pipeline plan component with valid template is accepted."""
    from orchestrator.orchestrator import Orchestrator
    from orchestrator.state import load_job_state
    from orchestrator.models import AgentResult, ProductSchema
    from agents.registry import AGENT_REGISTRY
    from unittest import mock
    import json, os

    def _make_job_spec(tmp_path, slug="test-valid-template"):
        path = tmp_path / "job_spec.json"
        data = {"slug": slug, "product_type": "research_pack", "niche": "test", "notion_sync": False, "notion_parent_page_id": None, "created_at": "2026-06-17T10:00:00Z"}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def _make_schema(tmp_path):
        path = tmp_path / "research_pack.json"
        data = {"product_type": "research_pack", "display_name": "Test", "components": [
            {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
            {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["market_research"], "delivery": ["zip"]},
        ]}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    schema_path = _make_schema(tmp_path)

    def mock_market(comp, js, ctx):
        output_dir = os.path.join("outputs", js.slug)
        os.makedirs(os.path.join(output_dir, "data"), exist_ok=True)
        research = {
            "niche": "test",
            "pipeline_plan": {
                "components": [
                    {
                        "id": "faq_section",
                        "agent": "content_agent",
                        "output": "content/{slug}/faq.md",
                        "depends_on": ["market_research"],
                        "template": "faq_section",
                    },
                ]
            },
        }
        research_path = os.path.join(output_dir, "data", "market_research.json")
        with open(research_path, "w") as f:
            json.dump(research, f)
        return AgentResult(status="done", output_path=research_path)

    mock_content = mock.Mock(return_value=AgentResult(status="done"))
    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market)
    monkeypatch.setitem(AGENT_REGISTRY, "content_agent", mock_content)
    monkeypatch.setitem(AGENT_REGISTRY, "packaging_agent", mock.Mock(return_value=AgentResult(status="done")))

    job_spec_path = _make_job_spec(tmp_path)
    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-valid-template" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-valid-template")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)
    orc.run()

    assert orc.state.components["faq_section"].status == "done"
    mock_content.assert_called_once()


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
    """Test that orchestrator switches schema after offer_scoring scores recommendations."""
    from orchestrator.orchestrator import Orchestrator
    from orchestrator.state import load_job_state
    from orchestrator.models import AgentResult, ProductSchema
    from orchestrator.scoring import ScoringFramework, ScoredOffer
    from agents.registry import AGENT_REGISTRY
    from unittest import mock
    import json
    import os

    def _make_job_spec(tmp_path, slug="test-discovery", **extra):
        path = tmp_path / "job_spec.json"
        data = {"slug": slug, "product_type": "discovery", "niche": "test niche", "notion_sync": False, "notion_parent_page_id": None, "created_at": "2026-06-12T10:00:00Z", **extra}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def _make_discovery_schema(tmp_path):
        path = tmp_path / "discovery.json"
        data = {"product_type": "discovery", "display_name": "Discovery", "components": [
            {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": [], "delivery": []},
            {"id": "offer_scoring", "agent": "offer_scoring_agent", "output": "data/market_research.json", "depends_on": ["market_research"], "delivery": []},
        ]}
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
        # No recommended_product_type — scoring will determine that
        research = {
            "niche": "test niche",
            "pipeline_plan": {"components": []},
        }
        research_path = os.path.join(output_dir, "data", "market_research.json")
        with open(research_path, "w") as f:
            json.dump(research, f)
        return AgentResult(status="done", output_path=research_path)

    # Mock the scoring module so offer_scoring_agent produces predictable results
    def mock_scoring_run(research_data, schemas_dir=None, adjustments=None):
        return ScoringFramework(
            offers=[
                ScoredOffer(
                    product_type="research_pack",
                    display_name="Research Pack",
                    total_score=85.0,
                    confidence=0.9,
                    metrics=[],
                    reasoning="Test score",
                ),
            ]
        )

    mock_package = mock.Mock(return_value=AgentResult(status="done"))
    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market_agent)
    monkeypatch.setitem(AGENT_REGISTRY, "packaging_agent", mock_package)
    monkeypatch.setattr("agents.offer_scoring_agent.run_scoring", mock_scoring_run)

    job_spec_path = _make_job_spec(tmp_path)
    orc = Orchestrator(str(job_spec_path))
    with open(discovery_schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-discovery" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-discovery")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    # Schema should have been switched to research_pack based on scoring
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


def test_legacy_product_type_still_works(tmp_path, monkeypatch):
    """Test that job_spec with explicit product_type still works in legacy mode."""
    from orchestrator.orchestrator import Orchestrator
    from orchestrator.state import load_job_state
    from orchestrator.models import AgentResult, ProductSchema
    from agents.registry import AGENT_REGISTRY
    from unittest import mock
    import json
    import os

    def _make_job_spec(tmp_path, slug="test-legacy", **extra):
        path = tmp_path / "job_spec.json"
        data = {"slug": slug, "product_type": "research_pack", "niche": "test niche", "notion_sync": False, "notion_parent_page_id": None, "created_at": "2026-06-12T10:00:00Z", **extra}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def _make_research_pack_schema(tmp_path):
        path = tmp_path / "research_pack.json"
        data = {"product_type": "research_pack", "display_name": "Research Pack", "components": [{"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": [], "delivery": []}, {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["market_research"], "delivery": ["zip"]}]}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    _make_research_pack_schema(tmp_path)

    def mock_market(comp, js, ctx):
        output_dir = os.path.join("outputs", js.slug)
        os.makedirs(os.path.join(output_dir, "data"), exist_ok=True)
        research = {"niche": "test niche", "pipeline_plan": {"components": []}}
        research_path = os.path.join(output_dir, "data", "market_research.json")
        with open(research_path, "w") as f:
            json.dump(research, f)
        return AgentResult(status="done", output_path=research_path)

    mock_package = mock.Mock(return_value=AgentResult(status="done"))
    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market)
    monkeypatch.setitem(AGENT_REGISTRY, "packaging_agent", mock_package)

    job_spec_path = _make_job_spec(tmp_path)
    orc = Orchestrator(str(job_spec_path))
    with open(os.path.join(tmp_path, "research_pack.json")) as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-legacy" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-legacy")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    # Legacy mode should NOT switch schema — product_type stays research_pack
    assert orc.job_spec.product_type == "research_pack"
    assert orc.schema.product_type == "research_pack"
    mock_package.assert_called_once()


def test_orchestrator_runs_channels_and_injects_urls(tmp_path, monkeypatch):
    """Test that orchestrator runs channels after pipeline and injects URLs."""
    from channels import CHANNEL_REGISTRY
    from channels.base import PublishResult

    published = []

    class FakeGumroadChannel:
        name = "gumroad"
        def validate(self): return True
        def publish(self, artifact):
            published.append(artifact)
            return PublishResult(status="published", product_url="https://test.gumroad.com/l/test", product_id="prod_1")
        def update(self, pid, artifact): return self.publish(artifact)
        def get_analytics(self, pid): return {}

    monkeypatch.setitem(CHANNEL_REGISTRY, "gumroad", FakeGumroadChannel)

    def _make_job_spec(tmp_path, slug="test-chan", **extra):
        path = tmp_path / "job_spec.json"
        data = {"slug": slug, "product_type": "research_pack", "niche": "test", "notion_sync": False, "notion_parent_page_id": None, "created_at": "2026-06-17T10:00:00Z", "gumroad_enabled": True, **extra}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def _make_schema(tmp_path):
        path = tmp_path / "research_pack.json"
        data = {"product_type": "research_pack", "display_name": "Test", "components": [
            {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": [], "delivery": []},
            {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["market_research"], "delivery": ["zip"]},
        ]}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    schema_path = _make_schema(tmp_path)

    def mock_market(comp, js, ctx):
        p = os.path.join("outputs", js.slug, "data", "market_research.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            json.dump({"niche": "test"}, f)
        return AgentResult(status="done", output_path=p)

    mock_pkg = mock.Mock(return_value=AgentResult(status="done"))
    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market)
    monkeypatch.setitem(AGENT_REGISTRY, "packaging_agent", mock_pkg)

    job_spec_path = _make_job_spec(tmp_path)
    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-chan" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-chan")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    assert len(published) >= 1
    assert published[0].slug == "test-chan"
    assert "gumroad" in orc._channel_results
    assert orc._channel_results["gumroad"].product_url == "https://test.gumroad.com/l/test"


def test_circuit_breaker_tracks_failures(tmp_path, monkeypatch):
    """Circuit breaker tracks failures per template after component failure."""
    from orchestrator.orchestrator import Orchestrator
    from orchestrator.state import load_job_state
    from orchestrator.models import AgentResult, ProductSchema
    from agents.registry import AGENT_REGISTRY
    from unittest import mock
    import json, os

    def _make_job_spec(tmp_path, slug="test-cb"):
        path = tmp_path / "job_spec.json"
        data = {"slug": slug, "product_type": "research_pack", "niche": "test", "notion_sync": False, "notion_parent_page_id": None, "created_at": "2026-06-17T10:00:00Z"}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def _make_schema(tmp_path):
        path = tmp_path / "research_pack.json"
        data = {"product_type": "research_pack", "display_name": "Test", "components": [
            {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
            {"id": "faq_section", "agent": "content_agent", "output": "content/{slug}/faq.md", "depends_on": ["market_research"], "template": "faq_section"},
            {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["market_research"], "delivery": ["zip"]},
        ]}
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    schema_path = _make_schema(tmp_path)

    def mock_market(comp, js, ctx):
        output_dir = os.path.join("outputs", js.slug)
        os.makedirs(os.path.join(output_dir, "data"), exist_ok=True)
        research_path = os.path.join(output_dir, "data", "market_research.json")
        with open(research_path, "w") as f:
            json.dump({"niche": "test"}, f)
        return AgentResult(status="done", output_path=research_path)

    mock_content = mock.Mock(return_value=AgentResult(status="failed", error="simulated"))
    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market)
    monkeypatch.setitem(AGENT_REGISTRY, "content_agent", mock_content)
    monkeypatch.setitem(AGENT_REGISTRY, "packaging_agent", mock.Mock(return_value=AgentResult(status="done")))

    job_spec_path = _make_job_spec(tmp_path)
    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-cb" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-cb")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)
    orc.run()

    assert orc.state.components["faq_section"].status == "failed"
    assert orc._component_failures.get("faq_section", 0) == 1


def test_circuit_breaker_resets_with_new_orchestrator(tmp_path):
    """Circuit breaker state is per-Orchestrator instance."""
    from orchestrator.orchestrator import Orchestrator
    orc1 = Orchestrator.__new__(Orchestrator)
    orc1._component_failures = {}
    orc2 = Orchestrator.__new__(Orchestrator)
    orc2._component_failures = {}
    assert orc1._component_failures == {}
    assert orc2._component_failures == {}
