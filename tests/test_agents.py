import os
import json
import shutil
from agents import csv_export_agent
from orchestrator.models import ComponentSpec, JobSpec


def test_csv_export_agent(tmp_path):
    # Mock job spec
    job_spec = JobSpec(
        slug="test-slug", product_type="research_pack", niche="test niche"
    )

    # Mock component
    comp = ComponentSpec(
        id="csv",
        agent="csv_export_agent",
        output="test_output.csv",
        depends_on=["database"],
    )

    # Mock database file
    db_path = tmp_path / "database.json"
    db_data = [
        {"name": "Tool A", "url": "http://a.com"},
        {"name": "Tool B", "url": "http://b.com"},
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
        slug="test-os", product_type="operating_system", niche="test niche"
    )

    comp = ComponentSpec(
        id="notion_tree",
        agent="notion_agent",
        output="notion_sync.json",
        depends_on=["guide"],
    )

    result = notion_agent.run(comp, job_spec, {})
    assert result.status == "skipped"
    assert "Notion not configured" in result.error


def test_visual_agent_placeholder(tmp_path, monkeypatch):
    from agents import visual_agent

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    job_spec = JobSpec(
        slug="test-visual", product_type="visual_pack", niche="test niche"
    )

    comp = ComponentSpec(
        id="images",
        agent="visual_agent",
        output="assets/images",
        depends_on=["image_prompts"],
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

    monkeypatch.setattr(
        content_agent,
        "generate_text",
        lambda p: "# Test Title\n\nTest content generated",
    )

    job_spec = JobSpec(
        slug="test-content", product_type="research_pack", niche="test niche"
    )
    comp = ComponentSpec(
        id="report", agent="content_agent", output="content/report.md", depends_on=[]
    )
    context = {}

    result = content_agent.run(comp, job_spec, context)
    assert result.status == "done"
    assert result.output_path.endswith("report.md")

    output_dir = os.path.join("outputs", "test-content")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_research_agent(monkeypatch):
    from agents import research_agent

    monkeypatch.setattr(
        research_agent, "generate_text", lambda p: "# Database\n\nEntry 1: test"
    )

    job_spec = JobSpec(
        slug="test-research", product_type="research_pack", niche="test niche"
    )
    comp = ComponentSpec(
        id="database",
        agent="research_agent",
        output="data/database.json",
        depends_on=[],
    )
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

    job_spec = JobSpec(
        slug="test-render", product_type="research_pack", niche="test niche"
    )
    comp = ComponentSpec(
        id="report_pdf",
        agent="render_agent",
        output="presentation/report.pdf",
        depends_on=["report"],
        uses_renderer=True,
        template="shared/basic_doc.html.j2",
    )
    context = {"renderer": MockRenderer()}

    result = render_agent.run(comp, job_spec, context)
    assert result.status == "done"

    output_dir = os.path.join("outputs", "test-render")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_packaging_agent(monkeypatch):
    from agents import packaging_agent

    job_spec = JobSpec(
        slug="test-pkg", product_type="research_pack", niche="test niche"
    )
    comp = ComponentSpec(
        id="package",
        agent="packaging_agent",
        output="{slug}.zip",
        depends_on=["report_pdf"],
    )

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
    monkeypatch.setattr(
        "agents.llm_client.generate_text",
        lambda p: json.dumps(
            {"analysis": "Test analysis", "recommendations": ["test"]}
        ),
    )

    job_spec = JobSpec(
        slug="test-gumroad", product_type="research_pack", niche="test niche"
    )
    comp = ComponentSpec(
        id="gumroad_research",
        agent="gumroad_agent",
        output="gumroad/research.json",
        depends_on=[],
    )
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

    monkeypatch.setattr(
        "agents.image_agent.generate_images",
        lambda **kw: {
            "hero_banner": {"path": "/fake/hero.png"},
            "feature_showcase": {"path": "/fake/feature.png"},
            "benefit_visual": {"path": "/fake/benefit.png"},
        },
    )
    monkeypatch.setattr(
        "agents.llm_client.generate_text",
        lambda p: "<html><body><h1>Test Landing</h1></body></html>",
    )

    job_spec = JobSpec(
        slug="test-landing",
        product_type="research_pack",
        niche="test niche",
        landing_page_enabled=True,
    )
    comp = ComponentSpec(
        id="landing_page",
        agent="landing_agent",
        output="landing/deployed.json",
        depends_on=["gumroad_publish"],
    )
    context = {}

    result = landing_agent.run(comp, job_spec, context)
    assert result.status == "done"
    assert os.path.exists(result.output_path)

    output_dir = os.path.join("outputs", "test-landing")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_social_agent(monkeypatch):
    from agents import social_agent

    monkeypatch.setattr(
        "agents.llm_client.generate_text",
        lambda p: json.dumps(
            {
                "instagram": {"caption": "Test post", "hashtags": ["#test"]},
                "threads": {"caption": "Test thread", "hashtags": ["#test"]},
                "facebook": {"caption": "Test fb", "hashtags": ["#test"]},
                "pinterest": {
                    "title": "Test Pin",
                    "caption": "Test pin",
                    "hashtags": ["#test"],
                },
            }
        ),
    )

    job_spec = JobSpec(
        slug="test-social", product_type="research_pack", niche="test niche"
    )
    comp = ComponentSpec(
        id="social_promotion",
        agent="social_agent",
        output="landing/social_results.json",
        depends_on=["landing_page"],
    )
    context = {}

    result = social_agent.run(comp, job_spec, context)
    assert result.status == "done"

    output_dir = os.path.join("outputs", "test-social")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_gumroad_agent_publish(tmp_path, monkeypatch):
    from agents import gumroad_agent

    monkeypatch.setenv("GUMROAD_ACCESS_TOKEN", "fake_token")

    # Mock product ID lookup
    monkeypatch.setattr(
        gumroad_agent, "_get_previous_product_id", lambda *a, **kw: "prod_test123"
    )

    # Mock file uploads
    urls = iter(
        [
            "https://s3.example.com/report.pdf",
            "https://s3.example.com/package.zip",
            "https://s3.example.com/cover.png",
        ]
    )
    monkeypatch.setattr(gumroad_agent, "_gumroad_upload_file", lambda p: next(urls))

    # Mock PUT with Rails params (both attach + rich_content calls)
    monkeypatch.setattr(
        gumroad_agent,
        "_gumroad_put_with_rails_params",
        lambda pid, body: {
            "success": True,
            "product": {
                "id": pid,
                "short_url": "https://testuser.gumroad.com/l/test-publish",
                "files": [
                    {"id": "f1", "url": "https://s3.example.com/report.pdf"},
                    {"id": "f2", "url": "https://s3.example.com/package.zip"},
                    {"id": "f3", "url": "https://s3.example.com/cover.png"},
                ],
            },
        },
    )

    # Mock httpx.request for GET /products/{id} reads
    def mock_request(method, url, **kwargs):
        class MockResponse:
            status_code = 200

            def json(self):
                if "user" in url.lower():
                    return {"user": {"subdomain": "testuser"}}
                return {
                    "product": {
                        "id": "prod_test123",
                        "short_url": "https://testuser.gumroad.com/l/test-publish",
                        "files": [
                            {"id": "f0", "url": "https://s3.example.com/old.pdf"}
                        ],
                    }
                }

            @property
            def text(self):
                return json.dumps(self.json())

        return MockResponse()

    monkeypatch.setattr("httpx.request", mock_request)

    # Mock httpx.put for enable endpoint
    def mock_put(url, **kwargs):
        class MockResponse:
            status_code = 200

            def json(self):
                return {
                    "success": True,
                    "product": {
                        "short_url": "https://testuser.gumroad.com/l/test-publish"
                    },
                }

            @property
            def text(self):
                return json.dumps(self.json())

        return MockResponse()

    monkeypatch.setattr("httpx.put", mock_put)

    # Mock httpx.post for cover + thumbnail uploads
    def mock_post(url, **kwargs):
        class MockResponse:
            status_code = 200

            def json(self):
                return {"success": True}

            @property
            def text(self):
                return json.dumps(self.json())

        return MockResponse()

    monkeypatch.setattr("httpx.post", mock_post)

    # Mock LLM listing generation
    monkeypatch.setattr(
        "agents.llm_client.generate_text",
        lambda p: json.dumps(
            {
                "product_name": "Test Product",
                "tagline": "A great test product",
                "description": "Full description of the test product",
            }
        ),
    )

    # Set up fake output directory with files
    job_spec = JobSpec(
        slug="test-publish",
        product_type="research_pack",
        niche="test niche",
        display_name="Test Product",
    )
    comp = ComponentSpec(
        id="gumroad_publish",
        agent="gumroad_agent",
        output="gumroad/published.json",
        depends_on=["gumroad_research"],
    )

    output_dir = os.path.join("outputs", "test-publish")
    os.makedirs(os.path.join(output_dir, "presentation"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "assets"), exist_ok=True)

    with open(os.path.join(output_dir, "presentation", "report.pdf"), "w") as f:
        f.write("fake pdf content")
    with open(os.path.join(output_dir, "test-publish.zip"), "w") as f:
        f.write("fake zip content")
    with open(os.path.join(output_dir, "assets", "cover.png"), "w") as f:
        f.write("fake png content")

    context = {}

    result = gumroad_agent.run(comp, job_spec, context)
    assert result.status == "done"
    assert os.path.exists(result.output_path)

    with open(result.output_path) as f:
        data = json.load(f)
    assert data["status"] == "published"
    assert data["product_id"] == "prod_test123"
    assert "testuser.gumroad.com" in data["product_url"]

    # Clean up
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_market_agent(monkeypatch):
    from agents import market_agent

    monkeypatch.delenv("GUMROAD_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(
        "agents.llm_client.generate_text",
        lambda p: json.dumps(
            {"competitors": [], "pricing": {}, "gaps": [], "keywords": []}
        ),
    )

    job_spec = JobSpec(
        slug="test-market", product_type="research_pack", niche="test niche"
    )
    comp = ComponentSpec(
        id="market_research",
        agent="market_agent",
        output="data/market_research.json",
        depends_on=[],
    )
    context = {}

    result = market_agent.run(comp, job_spec, context)
    assert result.status == "done"

    output_dir = os.path.join("outputs", "test-market")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_image_agent_svg_fallback(tmp_path, monkeypatch):
    from agents import image_agent

    monkeypatch.setattr(
        "agents.llm_client.generate_text",
        lambda p: json.dumps(
            [
                {"id": "cover", "prompt": "test cover", "style": "modern"},
                {"id": "thumbnail", "prompt": "test thumb", "style": "modern"},
                {"id": "social", "prompt": "test social", "style": "modern"},
            ]
        ),
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    job_spec = JobSpec(
        slug="test-img", product_type="research_pack", niche="test niche"
    )
    comp = ComponentSpec(
        id="images",
        agent="image_agent",
        output="data/images_generated.json",
        depends_on=["market_research"],
    )
    context = {}

    result = image_agent.run(comp, job_spec, context)
    assert result.status == "done"
    assert os.path.exists(result.output_path)

    output_dir = os.path.join("outputs", "test-img")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_catalog_agent(tmp_path, monkeypatch):
    from agents import catalog_agent

    monkeypatch.setattr(
        catalog_agent,
        "generate_text",
        lambda p: json.dumps(
            [
                {"title": "Item 1", "description": "First item"},
                {"title": "Item 2", "description": "Second item"},
            ]
        ),
    )

    job_spec = JobSpec(
        slug="test-catalog", product_type="visual_pack", niche="test niche"
    )
    comp = ComponentSpec(
        id="catalog",
        agent="catalog_agent",
        output="content/catalog.json",
        depends_on=["image_prompts"],
    )

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

    monkeypatch.setattr(
        notion_schema_agent,
        "generate_text",
        lambda p: json.dumps(
            {"pages": [{"name": "Page 1", "source": "guide", "type": "page"}]}
        ),
    )

    job_spec = JobSpec(
        slug="test-notion-schema", product_type="operating_system", niche="test niche"
    )
    comp = ComponentSpec(
        id="notion_schema",
        agent="notion_schema_agent",
        output="data/notion_schema.json",
        depends_on=["guide"],
    )
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
    comp = ComponentSpec(
        id="workflow_diagram_src",
        agent="diagram_agent",
        output="content/diagram.mmd",
        depends_on=[],
    )
    context = {}

    result = diagram_agent.run(comp, job_spec, context)
    assert result.status == "done"

    output_dir = os.path.join("outputs", "test-diagram")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)


def test_component_spec_with_delivery():
    from orchestrator.models import ComponentSpec

    comp = ComponentSpec(id="test", agent="test_agent", output="out.pdf", depends_on=[])
    assert comp.delivery == ["zip"]

    comp2 = ComponentSpec(
        id="test2", agent="test_agent", output="out.pdf", depends_on=[], delivery=["gumroad"]
    )
    assert comp2.delivery == ["gumroad"]

    comp3 = ComponentSpec(
        id="test3", agent="test_agent", output="data.json", depends_on=[], delivery=[]
    )
    assert comp3.delivery == []


def test_pipeline_component_with_delivery():
    from orchestrator.models import PipelineComponent

    comp = PipelineComponent(
        id="dyn", agent="render_agent", output="out.pdf", depends_on=[]
    )
    assert comp.delivery == ["zip"]

    comp2 = PipelineComponent(
        id="dyn2",
        agent="render_agent",
        output="out.pdf",
        depends_on=[],
        delivery=["gumroad"],
    )
    assert comp2.delivery == ["gumroad"]

    comp3 = PipelineComponent(
        id="dyn3",
        agent="render_agent",
        output="data.json",
        depends_on=[],
        delivery=[],
    )
    assert comp3.delivery == []


def test_packaging_agent_with_delivery_map(tmp_path):
    from agents import packaging_agent
    from orchestrator.models import ComponentSpec, JobSpec
    import os
    import shutil
    import zipfile

    job_spec = JobSpec(
        slug="test-pkg-delivery", product_type="research_pack", niche="test niche"
    )
    comp = ComponentSpec(
        id="package",
        agent="packaging_agent",
        output="{slug}.zip",
        depends_on=[],
        delivery=["zip"],
    )

    base_dir = os.path.join("outputs", "test-pkg-delivery")
    os.makedirs(os.path.join(base_dir, "presentation"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "assets"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "data"), exist_ok=True)

    # File that should be in ZIP (delivery=["zip"])
    zip_file = os.path.join(base_dir, "presentation", "report.pdf")
    with open(zip_file, "w") as f:
        f.write("zip content")

    # File that should NOT be in ZIP (delivery=["gumroad"])
    gumroad_file = os.path.join(base_dir, "presentation", "cheatsheet.pdf")
    with open(gumroad_file, "w") as f:
        f.write("gumroad only content")

    # A data file that should not be in ZIP (delivery=[])
    data_file = os.path.join(base_dir, "data", "internal.json")
    with open(data_file, "w") as f:
        f.write("internal")

    # A file not in delivery_map at all — should NOT be in ZIP
    asset_img = os.path.join(base_dir, "assets", "hero.png")
    with open(asset_img, "w") as f:
        f.write("png")

    delivery_map = {
        "report_pdf": {"output": zip_file, "delivery": ["zip"]},
        "cheatsheet": {"output": gumroad_file, "delivery": ["gumroad"]},
        "internal_data": {"output": data_file, "delivery": []},
        "package": {"output": os.path.join(base_dir, "test-pkg-delivery.zip"), "delivery": ["zip"]},
    }
    context = {"_delivery_map": delivery_map}

    result = packaging_agent.run(comp, job_spec, context)
    assert result.status == "done"

    with zipfile.ZipFile(result.output_path, "r") as zf:
        names = zf.namelist()

    # report.pdf should be in ZIP
    assert any("report.pdf" in n for n in names), "report.pdf should be in ZIP"
    # cheatsheet.pdf should NOT be in ZIP
    assert not any("cheatsheet.pdf" in n for n in names), "cheatsheet.pdf should NOT be in ZIP"
    # internal.json should NOT be in ZIP
    assert not any("internal.json" in n for n in names), "internal.json should NOT be in ZIP"
    # hero.png should be in ZIP (assets/ always included)
    assert any("hero.png" in n for n in names), "hero.png should be in ZIP (assets/ always included)"

    # Clean up
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)


def test_gumroad_agent_publish_with_delivery_map(tmp_path, monkeypatch):
    from agents import gumroad_agent
    from orchestrator.models import ComponentSpec, JobSpec
    import json
    import os

    monkeypatch.setenv("GUMROAD_ACCESS_TOKEN", "fake_token")
    monkeypatch.setattr(gumroad_agent, "_get_previous_product_id", lambda *a, **kw: "prod_test456")

    urls = iter([
        "https://s3.example.com/cheatsheet.pdf",
        "https://s3.example.com/report.pdf",
        "https://s3.example.com/cover.png",
    ])
    monkeypatch.setattr(gumroad_agent, "_gumroad_upload_file", lambda p: next(urls))

    monkeypatch.setattr(
        gumroad_agent, "_gumroad_put_with_rails_params",
        lambda pid, body: {
            "success": True,
            "product": {
                "id": pid,
                "short_url": "https://testuser.gumroad.com/l/test-publish-dm",
                "files": [
                    {"id": "f1", "url": "https://s3.example.com/cheatsheet.pdf"},
                    {"id": "f2", "url": "https://s3.example.com/report.pdf"},
                    {"id": "f3", "url": "https://s3.example.com/cover.png"},
                ],
            },
        },
    )

    def mock_request(method, url, **kwargs):
        class MockResponse:
            status_code = 200
            def json(self):
                if "user" in url.lower():
                    return {"user": {"subdomain": "testuser"}}
                return {"product": {"id": "prod_test456", "short_url": "https://testuser.gumroad.com/l/test", "files": []}}
            @property
            def text(self):
                return json.dumps(self.json())
        return MockResponse()

    monkeypatch.setattr("httpx.request", mock_request)

    def mock_put(url, **kwargs):
        class MockResponse:
            status_code = 200
            def json(self):
                return {"success": True, "product": {"short_url": "https://testuser.gumroad.com/l/test-publish-dm"}}
            @property
            def text(self):
                return json.dumps(self.json())
        return MockResponse()

    monkeypatch.setattr("httpx.put", mock_put)

    def mock_post(url, **kwargs):
        class MockResponse:
            status_code = 200
            def json(self):
                return {"success": True}
            @property
            def text(self):
                return json.dumps(self.json())
        return MockResponse()

    monkeypatch.setattr("httpx.post", mock_post)

    monkeypatch.setattr(
        "agents.llm_client.generate_text",
        lambda p: json.dumps({"product_name": "Test Product", "tagline": "Test", "description": "Desc"}),
    )

    job_spec = JobSpec(
        slug="test-publish-dm", product_type="research_pack", niche="test niche", display_name="Test Product"
    )
    comp = ComponentSpec(
        id="gumroad_publish", agent="gumroad_agent", output="gumroad/published.json",
        depends_on=["gumroad_research"],
    )

    output_dir = os.path.join("outputs", "test-publish-dm")
    os.makedirs(os.path.join(output_dir, "presentation"), exist_ok=True)
    os.makedirs(os.path.join(output_dir, "assets"), exist_ok=True)

    # A file tagged delivery=["gumroad"] — should be uploaded individually
    cheatsheet = os.path.join(output_dir, "presentation", "cheatsheet.pdf")
    with open(cheatsheet, "w") as f:
        f.write("individual upload content")

    # A file tagged delivery=["zip"] — should NOT be uploaded individually
    report = os.path.join(output_dir, "presentation", "report.pdf")
    with open(report, "w") as f:
        f.write("zip only content")

    # ZIP file (package output) — should be uploaded
    zip_path = os.path.join(output_dir, "test-publish-dm.zip")
    with open(zip_path, "w") as f:
        f.write("fake zip")

    # Cover image
    cover = os.path.join(output_dir, "assets", "cover.png")
    with open(cover, "w") as f:
        f.write("fake cover")

    delivery_map = {
        "cheatsheet_pdf": {"output": cheatsheet, "delivery": ["gumroad"]},
        "report_pdf": {"output": report, "delivery": ["zip"]},
        "package": {"output": zip_path, "delivery": ["zip"]},
    }
    context = {"_delivery_map": delivery_map}

    result = gumroad_agent.run(comp, job_spec, context)
    assert result.status == "done"

    # Clean up
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
