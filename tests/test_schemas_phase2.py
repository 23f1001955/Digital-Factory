import json
import os

import pytest
from orchestrator.models import ProductSchema

SCHEMA_DIR = "schemas"
PHASE2_SCHEMAS = [
    "database",
    "sop_pack",
    "prompt_pack",
    "swipe_file",
    "checklist",
    "excel_template",
    "resource_pack",
    "boilerplate",
]


class TestPhase2Schemas:
    @pytest.mark.parametrize("name", PHASE2_SCHEMAS)
    def test_schema_loads(self, name):
        path = os.path.join(SCHEMA_DIR, f"{name}.json")
        assert os.path.exists(path), f"Schema file missing: {path}"
        with open(path) as f:
            raw = json.load(f)
        schema = ProductSchema(**raw)
        assert schema.product_type == name
        assert len(schema.components) >= 3

    @pytest.mark.parametrize("name", PHASE2_SCHEMAS)
    def test_dependency_chain(self, name):
        path = os.path.join(SCHEMA_DIR, f"{name}.json")
        with open(path) as f:
            raw = json.load(f)
        schema = ProductSchema(**raw)
        comp_ids = {c.id for c in schema.components}
        for comp in schema.components:
            for dep in comp.depends_on:
                assert dep in comp_ids, (
                    f"{name}: component '{comp.id}' depends on '{dep}' "
                    f"which is not in schema"
                )

    def test_checklist_has_notion(self):
        with open(os.path.join(SCHEMA_DIR, "checklist.json")) as f:
            raw = json.load(f)
        schema = ProductSchema(**raw)
        assert schema.notion_sync is True
        assert schema.notion_structure is not None

    @pytest.mark.parametrize(
        "name",
        [
            "database",
            "sop_pack",
            "prompt_pack",
            "swipe_file",
            "excel_template",
            "resource_pack",
            "boilerplate",
        ],
    )
    def test_non_notion_schemas(self, name):
        with open(os.path.join(SCHEMA_DIR, f"{name}.json")) as f:
            raw = json.load(f)
        schema = ProductSchema(**raw)
        assert schema.notion_sync is False

    def test_database_uses_csv_agent(self):
        with open(os.path.join(SCHEMA_DIR, "database.json")) as f:
            raw = json.load(f)
        schema = ProductSchema(**raw)
        assert any(
            c.id == "database_export" and c.agent == "csv_export_agent"
            for c in schema.components
        )

    def test_prompt_pack_uses_catalog_agent_with_format(self):
        with open(os.path.join(SCHEMA_DIR, "prompt_pack.json")) as f:
            raw = json.load(f)
        schema = ProductSchema(**raw)
        assert any(
            c.id == "prompt_catalog"
            and c.agent == "catalog_agent"
            and c.format == "prompt"
            for c in schema.components
        )

    def test_resource_pack_uses_catalog_agent_with_format(self):
        with open(os.path.join(SCHEMA_DIR, "resource_pack.json")) as f:
            raw = json.load(f)
        schema = ProductSchema(**raw)
        assert any(
            c.id == "resource_catalog"
            and c.agent == "catalog_agent"
            and c.format == "resource"
            for c in schema.components
        )
