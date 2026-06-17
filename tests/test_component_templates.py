import pytest
from orchestrator.component_templates import (
    COMPONENT_TEMPLATES,
    validate_template,
    resolve_template,
    list_templates,
)
from orchestrator.models import ComponentSpec


class TestComponentTemplates:
    def test_all_templates_have_required_fields(self):
        for name, tmpl in COMPONENT_TEMPLATES.items():
            assert "agent" in tmpl, f"{name} missing agent"
            assert "output" in tmpl, f"{name} missing output"
            assert "delivery" in tmpl, f"{name} missing delivery"
            assert isinstance(tmpl["delivery"], list), f"{name} delivery not list"

    def test_validate_template_known(self):
        assert validate_template("case_study") is True
        assert validate_template("checklist") is True

    def test_validate_template_unknown(self):
        assert validate_template("nonexistent_template") is False
        assert validate_template("") is False

    def test_list_templates(self):
        names = list_templates()
        assert isinstance(names, list)
        assert len(names) > 0
        assert "case_study" in names

    def test_resolve_template_returns_component_spec(self):
        spec = resolve_template("faq_section", overrides={"depends_on": ["market_research"]})
        assert isinstance(spec, ComponentSpec)
        assert spec.id == "faq_section"
        assert spec.agent == "content_agent"
        assert spec.depends_on == ["market_research"]
        assert "zip" in spec.delivery

    def test_resolve_template_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown template"):
            resolve_template("bogus_template")

    def test_resolve_template_preserves_default_delivery(self):
        spec = resolve_template("resource_list")
        assert "zip" in spec.delivery
        assert "gumroad" in spec.delivery

    def test_resolve_template_blocks_override_of_id(self):
        spec = resolve_template("checklist", overrides={"id": "hacked_id"})
        assert spec.id == "checklist"

    def test_resolve_template_blocks_override_of_agent(self):
        spec = resolve_template("case_study", overrides={"agent": "malicious_agent"})
        assert spec.agent == "content_agent"

    def test_resolve_template_blocks_override_of_output(self):
        spec = resolve_template("comparison_table", overrides={"output": "../evil.md"})
        assert "comparison_table" in spec.output
        assert "../" not in spec.output
