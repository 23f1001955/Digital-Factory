import pytest
from cli.dry_run import print_dry_run
from orchestrator.models import ComponentSpec


class TestDryRun:
    def test_print_dry_run_with_components(self, capsys):
        components = [
            ComponentSpec(id="market_research", agent="market_agent", output="data/research.json", depends_on=[]),
            ComponentSpec(id="faq_section", agent="content_agent", output="content/faq.md", depends_on=["market_research"], template="faq_section"),
            ComponentSpec(id="package", agent="packaging_agent", output="{slug}.zip", depends_on=["market_research", "faq_section"], delivery=["zip"]),
        ]
        templates = ["faq_section", "case_study"]
        print_dry_run(components, templates)
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert "faq_section" in captured.out
        assert "content_agent" in captured.out
        assert "Total: 3" in captured.out
        assert "Available templates" in captured.out

    def test_print_dry_run_without_templates(self, capsys):
        components = [
            ComponentSpec(id="market_research", agent="market_agent", output="data/research.json", depends_on=[]),
        ]
        print_dry_run(components, [])
        captured = capsys.readouterr()
        assert "market_research" in captured.out
        assert "(core)" in captured.out

    def test_print_dry_run_shows_template_name(self, capsys):
        components = [
            ComponentSpec(id="faq_section", agent="content_agent", output="content/faq.md", depends_on=["market_research"], template="faq_section"),
        ]
        print_dry_run(components, ["faq_section"])
        captured = capsys.readouterr()
        assert "template=faq_section" in captured.out
