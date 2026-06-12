import pytest
from orchestrator.models import ComponentSpec
from orchestrator.orchestrator import Orchestrator


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
