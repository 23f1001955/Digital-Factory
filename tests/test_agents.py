import os
import json
import shutil
from agents import csv_export_agent
from orchestrator.models import ComponentSpec, JobSpec


def test_csv_export_agent(tmp_path):
    # Mock job spec
    job_spec = JobSpec(
        slug="test-slug",
        product_type="research_pack",
        niche="test niche"
    )

    # Mock component
    comp = ComponentSpec(
        id="csv",
        agent="csv_export_agent",
        output="test_output.csv",
        depends_on=["database"]
    )

    # Mock database file
    db_path = tmp_path / "database.json"
    db_data = [
        {"name": "Tool A", "url": "http://a.com"},
        {"name": "Tool B", "url": "http://b.com"}
    ]
    db_path.write_text(json.dumps(db_data))

    context = {"database": str(db_path)}

    # Run
    result = csv_export_agent.run(comp, job_spec, context)

    assert result.status == "done"
    assert os.path.exists(result.output_path)

    # Clean up
    if os.path.exists(result.output_path):
        os.remove(result.output_path)


def test_notion_agent_skipped(monkeypatch):
    from agents import notion_agent

    # Force missing env vars
    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_PARENT_PAGE_ID", raising=False)

    job_spec = JobSpec(
        slug="test-os",
        product_type="operating_system",
        niche="test niche"
    )

    comp = ComponentSpec(
        id="notion_tree",
        agent="notion_agent",
        output="notion_sync.json",
        depends_on=["guide"]
    )

    result = notion_agent.run(comp, job_spec, {})
    assert result.status == "skipped"
    assert "Notion not configured" in result.error


def test_visual_agent_placeholder(tmp_path, monkeypatch):
    from agents import visual_agent

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    job_spec = JobSpec(
        slug="test-visual",
        product_type="visual_pack",
        niche="test niche"
    )

    comp = ComponentSpec(
        id="images",
        agent="visual_agent",
        output="assets/images",
        depends_on=["image_prompts"]
    )

    prompts_path = tmp_path / "prompts.json"
    prompts_data = ["A beautiful landscape", "A futuristic city"]
    prompts_path.write_text(json.dumps(prompts_data))

    context = {"image_prompts": str(prompts_path)}

    result = visual_agent.run(comp, job_spec, context)

    assert result.status == "done"
    assert os.path.exists(result.output_path)

    files = os.listdir(result.output_path)
    svg_files = [f for f in files if f.endswith(".svg")]
    assert len(svg_files) >= 2
    assert "_manifest.json" in files


def test_content_agent(monkeypatch):
    from agents import content_agent

    monkeypatch.setattr(content_agent, "generate_text", lambda p: "# Test Title\n\nTest content generated")

    job_spec = JobSpec(slug="test-content", product_type="research_pack", niche="test niche")
    comp = ComponentSpec(id="report", agent="content_agent", output="content/report.md", depends_on=[])
    context = {}

    result = content_agent.run(comp, job_spec, context)
    assert result.status == "done"
    assert result.output_path.endswith("report.md")

    output_dir = os.path.join("outputs", "test-content")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_research_agent(monkeypatch):
    from agents import research_agent

    monkeypatch.setattr(research_agent, "generate_text", lambda p: "# Database\n\nEntry 1: test")

    job_spec = JobSpec(slug="test-research", product_type="research_pack", niche="test niche")
    comp = ComponentSpec(id="database", agent="research_agent", output="data/database.json", depends_on=[])
    context = {}

    result = research_agent.run(comp, job_spec, context)
    assert result.status == "done"

    output_dir = os.path.join("outputs", "test-research")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_render_agent(monkeypatch):
    from agents import render_agent

    class MockRenderer:
        def render_pdf(self, html, path):
            with open(path, "w") as f:
                f.write(html)

    job_spec = JobSpec(slug="test-render", product_type="research_pack", niche="test niche")
    comp = ComponentSpec(
        id="report_pdf", agent="render_agent", output="presentation/report.pdf",
        depends_on=["report"], uses_renderer=True, template="shared/basic_doc.html.j2"
    )
    context = {"renderer": MockRenderer()}

    result = render_agent.run(comp, job_spec, context)
    assert result.status == "done"

    output_dir = os.path.join("outputs", "test-render")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_packaging_agent(monkeypatch):
    from agents import packaging_agent

    job_spec = JobSpec(slug="test-pkg", product_type="research_pack", niche="test niche")
    comp = ComponentSpec(id="package", agent="packaging_agent", output="{slug}.zip", depends_on=["report_pdf"])

    pdf_dir = os.path.join("outputs", "test-pkg", "presentation")
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_file = os.path.join(pdf_dir, "report.pdf")
    with open(pdf_file, "w") as f:
        f.write("mock pdf content")

    context = {"report_pdf": pdf_file}

    result = packaging_agent.run(comp, job_spec, context)
    assert result.status == "done"

    output_dir = os.path.join("outputs", "test-pkg")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_gumroad_agent_research(monkeypatch):
    from agents import gumroad_agent

    monkeypatch.delenv("GUMROAD_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr("agents.llm_client.generate_text", lambda p: json.dumps({
        "analysis": "Test analysis",
        "recommendations": ["test"]
    }))

    job_spec = JobSpec(slug="test-gumroad", product_type="research_pack", niche="test niche")
    comp = ComponentSpec(id="gumroad_research", agent="gumroad_agent", output="gumroad/research.json", depends_on=[])
    context = {}

    result = gumroad_agent.run(comp, job_spec, context)
    assert result.status in ("done", "failed")

    output_dir = os.path.join("outputs", "test-gumroad")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_landing_agent_fallback(tmp_path, monkeypatch):
    from agents import landing_agent

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("STITCH_API_KEY", raising=False)
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    monkeypatch.setattr("agents.image_agent.generate_images", lambda **kw: {
        "hero_banner": {"path": "/fake/hero.png"},
        "feature_showcase": {"path": "/fake/feature.png"},
        "benefit_visual": {"path": "/fake/benefit.png"},
    })
    monkeypatch.setattr(
        "agents.llm_client.generate_text",
        lambda p: "<html><body><h1>Test Landing</h1></body></html>",
    )

    job_spec = JobSpec(slug="test-landing", product_type="research_pack", niche="test niche", landing_page_enabled=True)
    comp = ComponentSpec(id="landing_page", agent="landing_agent", output="landing/deployed.json", depends_on=["gumroad_publish"])
    context = {}

    result = landing_agent.run(comp, job_spec, context)
    assert result.status == "done"
    assert os.path.exists(result.output_path)

    output_dir = os.path.join("outputs", "test-landing")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_social_agent(monkeypatch):
    from agents import social_agent

    monkeypatch.setattr("agents.llm_client.generate_text", lambda p: json.dumps({
        "instagram": {"caption": "Test post", "hashtags": ["#test"]},
        "threads": {"caption": "Test thread", "hashtags": ["#test"]},
        "facebook": {"caption": "Test fb", "hashtags": ["#test"]},
        "pinterest": {"title": "Test Pin", "caption": "Test pin", "hashtags": ["#test"]},
    }))

    job_spec = JobSpec(slug="test-social", product_type="research_pack", niche="test niche")
    comp = ComponentSpec(id="social_promotion", agent="social_agent", output="landing/social_results.json", depends_on=["landing_page"])
    context = {}

    result = social_agent.run(comp, job_spec, context)
    assert result.status == "done"

    output_dir = os.path.join("outputs", "test-social")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_market_agent(monkeypatch):
    from agents import market_agent

    monkeypatch.delenv("GUMROAD_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr("agents.llm_client.generate_text", lambda p: json.dumps({
        "competitors": [], "pricing": {}, "gaps": [], "keywords": []
    }))

    job_spec = JobSpec(slug="test-market", product_type="research_pack", niche="test niche")
    comp = ComponentSpec(id="market_research", agent="market_agent", output="data/market_research.json", depends_on=[])
    context = {}

    result = market_agent.run(comp, job_spec, context)
    assert result.status == "done"

    output_dir = os.path.join("outputs", "test-market")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_image_agent_svg_fallback(tmp_path, monkeypatch):
    from agents import image_agent

    monkeypatch.setattr("agents.llm_client.generate_text", lambda p: json.dumps([
        {"id": "cover", "prompt": "test cover", "style": "modern"},
        {"id": "thumbnail", "prompt": "test thumb", "style": "modern"},
        {"id": "social", "prompt": "test social", "style": "modern"},
    ]))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    job_spec = JobSpec(slug="test-img", product_type="research_pack", niche="test niche")
    comp = ComponentSpec(id="images", agent="image_agent", output="data/images_generated.json", depends_on=["market_research"])
    context = {}

    result = image_agent.run(comp, job_spec, context)
    assert result.status == "done"
    assert os.path.exists(result.output_path)

    output_dir = os.path.join("outputs", "test-img")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_catalog_agent(tmp_path, monkeypatch):
    from agents import catalog_agent

    monkeypatch.setattr(catalog_agent, "generate_text", lambda p: json.dumps([
        {"title": "Item 1", "description": "First item"},
        {"title": "Item 2", "description": "Second item"},
    ]))

    job_spec = JobSpec(slug="test-catalog", product_type="visual_pack", niche="test niche")
    comp = ComponentSpec(id="catalog", agent="catalog_agent", output="content/catalog.json", depends_on=["image_prompts"])

    prompts_path = tmp_path / "prompts.json"
    prompts_path.write_text(json.dumps(["Prompt 1", "Prompt 2"]))
    context = {"image_prompts": str(prompts_path)}

    result = catalog_agent.run(comp, job_spec, context)
    assert result.status == "done"

    output_dir = os.path.join("outputs", "test-catalog")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_notion_schema_agent(monkeypatch):
    from agents import notion_schema_agent

    monkeypatch.setattr(notion_schema_agent, "generate_text", lambda p: json.dumps({
        "pages": [{"name": "Page 1", "source": "guide", "type": "page"}]
    }))

    job_spec = JobSpec(slug="test-notion-schema", product_type="operating_system", niche="test niche")
    comp = ComponentSpec(id="notion_schema", agent="notion_schema_agent", output="data/notion_schema.json", depends_on=["guide"])
    context = {}

    result = notion_schema_agent.run(comp, job_spec, context)
    assert result.status == "done"

    output_dir = os.path.join("outputs", "test-notion-schema")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_diagram_agent(monkeypatch):
    from agents import diagram_agent

    monkeypatch.setattr(diagram_agent, "generate_text", lambda p: "flowchart LR\nA-->B")

    job_spec = JobSpec(slug="test-diagram", product_type="workflow_kit", niche="test")
    comp = ComponentSpec(id="workflow_diagram_src", agent="diagram_agent", output="content/diagram.mmd", depends_on=[])
    context = {}

    result = diagram_agent.run(comp, job_spec, context)
    assert result.status == "done"

    output_dir = os.path.join("outputs", "test-diagram")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
