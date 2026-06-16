# Delivery Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Execute tasks using test-driven-development. Each task: RED (write failing test) → verify fail → GREEN (implement) → verify pass → REFACTOR. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add explicit `delivery` field to ComponentSpec so every component declares whether its output goes to ZIP, Gumroad individual upload, or nowhere — eliminating duplicate file uploads.

**Architecture:** A new `delivery: List[str]` field on ComponentSpec/PipelineComponent controls routing. The orchestrator builds a `_delivery_map` from all components and injects it into context for packaging and gumroad agents. Both agents switch from filesystem-scanning to delivery-map-driven file selection when the map is present.

**Tech Stack:** Python, Pydantic, schemas/*.json, existing packaging/gumroad agents

**Key rule:** A file cannot be in both ZIP and Gumroad individual upload. `["zip"]` = ZIP only, `["gumroad"]` = Gumroad individual upload only, `[]` = neither (internal data).

---

### Task 1: Add `delivery` field to ComponentSpec + PipelineComponent

**Files:**
- Modify: `orchestrator/models.py:6-13`
- Modify: `orchestrator/models.py:47-54`
- Test: `tests/test_agents.py` (new test)

- [ ] **Step 1: Write failing test for delivery field**

```python
def test_component_spec_with_delivery():
    from orchestrator.models import ComponentSpec

    # Default should be ["zip"] for backward compat
    comp = ComponentSpec(id="test", agent="test_agent", output="out.pdf", depends_on=[])
    assert comp.delivery == ["zip"]

    # Can set explicit delivery
    comp2 = ComponentSpec(id="test2", agent="test_agent", output="out.pdf", depends_on=[], delivery=["gumroad"])
    assert comp2.delivery == ["gumroad"]

    # Empty list means no delivery
    comp3 = ComponentSpec(id="test3", agent="test_agent", output="data.json", depends_on=[], delivery=[])
    assert comp3.delivery == []
```

Add this test to the end of `tests/test_agents.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agents.py::test_component_spec_with_delivery -v`
Expected: FAIL — ComponentSpec has no field `delivery`

- [ ] **Step 3: Add delivery field to ComponentSpec**

In `orchestrator/models.py`, add `delivery` to ComponentSpec:

```python
class ComponentSpec(BaseModel):
    id: str
    agent: str
    output: str
    depends_on: List[str] = Field(default_factory=list)
    uses_renderer: bool = False
    template: Optional[str] = None
    format: Literal["full", "guide", "notion"] = "full"
    delivery: List[str] = Field(default_factory=lambda: ["zip"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_agents.py::test_component_spec_with_delivery -v`
Expected: PASS

- [ ] **Step 5: Add delivery to PipelineComponent and test**

In `orchestrator/models.py`, add same field to PipelineComponent:

```python
class PipelineComponent(BaseModel):
    id: str
    agent: str
    output: str
    depends_on: List[str] = Field(default_factory=list)
    uses_renderer: bool = False
    template: Optional[str] = None
    format: Literal["full", "guide", "notion"] = "full"
    delivery: List[str] = Field(default_factory=lambda: ["zip"])
```

Add test for PipelineComponent:

```python
def test_pipeline_component_with_delivery():
    from orchestrator.models import PipelineComponent

    comp = PipelineComponent(id="dyn", agent="render_agent", output="out.pdf", depends_on=[])
    assert comp.delivery == ["zip"]

    comp2 = PipelineComponent(id="dyn2", agent="render_agent", output="out.pdf", depends_on=[], delivery=["gumroad"])
    assert comp2.delivery == ["gumroad"]
```

Run: `python -m pytest tests/test_agents.py::test_pipeline_component_with_delivery -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add orchestrator/models.py tests/test_agents.py
git commit -m "feat: add delivery field to ComponentSpec and PipelineComponent"
```

---

### Task 2: Update `_merge_pipeline_plan` to pass delivery

**Files:**
- Modify: `orchestrator/orchestrator.py:117-124`

- [ ] **Step 1: Write failing test for delivery in pipeline merge**

In `tests/test_orchestrator.py`, add a test that verifies delivery is preserved when merging pipeline_plan:

```python
def test_pipeline_plan_preserves_delivery(tmp_path, monkeypatch):
    """Test that delivery field from pipeline_plan is preserved in merged components."""
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
    orc.state = load_job_state(orc.state_path, "test-slug")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    # Find the merged components in schema
    report_comp = next((c for c in orc.schema.components if c.id == "report_pdf"), None)
    assert report_comp is not None
    assert report_comp.delivery == ["gumroad"]

    diag_comp = next((c for c in orc.schema.components if c.id == "diagrams"), None)
    assert diag_comp is not None
    assert diag_comp.delivery == ["zip"]  # default
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orchestrator.py::test_pipeline_plan_preserves_delivery -v`
Expected: FAIL — ComponentSpec created from PipelineComponent doesn't pass delivery

- [ ] **Step 3: Update `_merge_pipeline_plan` to pass delivery**

In `orchestrator/orchestrator.py:117-124`, update the ComponentSpec creation:

```python
spec = ComponentSpec(
    id=comp.id,
    agent=comp.agent,
    output=comp.output,
    depends_on=comp.depends_on,
    template=comp.template,
    format=comp.format,
    delivery=comp.delivery,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_orchestrator.py::test_pipeline_plan_preserves_delivery -v`
Expected: PASS

- [ ] **Step 5: Run all orchestrator tests to confirm no regressions**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add orchestrator/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: pass delivery field from pipeline_plan to merged components"
```

---

### Task 3: Build `_delivery_map` in orchestrator

**Files:**
- Modify: `orchestrator/orchestrator.py` (in `run()` method, inject delivery_map into context)

- [ ] **Step 1: Write failing test for delivery_map in context**

In `tests/test_orchestrator.py`, add a test that verifies `_delivery_map` is passed to packaging agent:

```python
def test_delivery_map_injected_into_context(tmp_path, monkeypatch):
    """Test that orchestrator injects _delivery_map into context for packaging agent."""
    schema_path = _make_schema(
        tmp_path,
        [
            {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
            {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["market_research"]},
        ],
    )

    actual_context = {}

    def mock_market(comp, js, ctx):
        return AgentResult(status="done", output_path=os.path.join("outputs", js.slug, "data", "market_research.json"))

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
    # market_research: delivery=[], should be in map
    assert "market_research" in dm
    assert dm["market_research"]["delivery"] == []
    # package: default delivery=["zip"]
    assert "package" in dm
    assert dm["package"]["delivery"] == ["zip"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orchestrator.py::test_delivery_map_injected_into_context -v`
Expected: FAIL — no _delivery_map in context

- [ ] **Step 3: Build delivery_map and inject into context**

In `orchestrator/orchestrator.py:run()`, before calling agent_func for packaging and gumroad agents, build and inject `_delivery_map`.

Add this method to `Orchestrator`:

```python
def _build_delivery_map(self) -> dict:
    """Build delivery map from all schema components with resolved output paths."""
    delivery_map = {}
    for comp in self.schema.components:
        output_path = None
        state = self.state.components.get(comp.id)
        if state and state.output_path:
            output_path = state.output_path
        else:
            # Component hasn't run yet — resolve output path from spec
            resolved = comp.output.replace("{slug}", self.job_spec.slug)
            output_path = os.path.join(os.getcwd(), "outputs", self.job_spec.slug, resolved)
        delivery_map[comp.id] = {
            "output": output_path,
            "delivery": comp.delivery,
        }
    return delivery_map
```

Then in the `run()` method, just before calling `agent_func` (line 328), inject delivery_map for appropriate agents:

```python
# Inject delivery_map for agents that need routing info
if component.agent in ("packaging_agent", "gumroad_agent"):
    context["_delivery_map"] = self._build_delivery_map()
```

Add this block right before `result = agent_func(component, self.job_spec, context)` on line 328.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_orchestrator.py::test_delivery_map_injected_into_context -v`
Expected: PASS

- [ ] **Step 5: Run all orchestrator tests**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add orchestrator/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: build and inject _delivery_map into agent context"
```

---

### Task 4: Update packaging agent to use delivery_map

**Files:**
- Modify: `agents/packaging_agent.py`
- Test: `tests/test_agents.py` (update test_packaging_agent)

- [ ] **Step 1: Write failing test for delivery-aware packaging**

Update `test_packaging_agent` to pass `_delivery_map` in context and verify only tagged files are included:

```python
def test_packaging_agent_with_delivery_map(tmp_path):
    from agents import packaging_agent

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
    os.makedirs(os.path.join(base_dir, "data"), exist_ok=True)
    with open(data_file, "w") as f:
        f.write("internal")

    # An image in assets that should be in ZIP
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

    # Verify ZIP contents
    import zipfile
    with zipfile.ZipFile(result.output_path, "r") as zf:
        names = zf.namelist()

    # report.pdf should be in ZIP
    assert any("report.pdf" in n for n in names), "report.pdf should be in ZIP"
    # cheatsheet.pdf should NOT be in ZIP (delivery=["gumroad"])
    assert not any("cheatsheet.pdf" in n for n in names), "cheatsheet.pdf should NOT be in ZIP"
    # data/internal.json should NOT be in ZIP (delivery=[])
    assert not any("internal.json" in n for n in names), "internal.json should NOT be in ZIP"

    # Clean up
    shutil.rmtree(base_dir, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agents.py::test_packaging_agent_with_delivery_map -v`
Expected: FAIL — packaging agent includes all files regardless of delivery_map

- [ ] **Step 3: Update packaging agent to use delivery_map**

Replace the entire `run()` function in `agents/packaging_agent.py`:

```python
def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        base_dir = os.path.join("outputs", job_spec.slug)
        output_path_resolved = component.output.replace("{slug}", job_spec.slug)
        output_zip = os.path.join("outputs", job_spec.slug, output_path_resolved)

        delivery_map = context.get("_delivery_map")

        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            if delivery_map:
                _add_delivery_map_files(zf, delivery_map, base_dir)
            else:
                _walk_filesystem(zf, base_dir)

        return AgentResult(status="done", output_path=output_zip, error=None)

    except Exception as e:
        logger.error(f"Packaging agent failed: {e}")
        return AgentResult(status="failed", error=str(e))


def _add_delivery_map_files(zf, delivery_map, base_dir):
    """Add files from delivery_map entries with 'zip' delivery."""
    added = set()
    for comp_id, entry in delivery_map.items():
        if "zip" not in entry.get("delivery", []):
            continue
        path = entry.get("output")
        if not path or not os.path.exists(path):
            continue
        if os.path.isfile(path):
            if os.path.isabs(path):
                rel = os.path.relpath(path, base_dir)
            else:
                rel = path
            ext = os.path.splitext(path)[1].lower()
            if ext in DELIVERABLE_EXTENSIONS:
                zf.write(path, rel)
                added.add(rel)
        elif os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                for file in files:
                    fpath = os.path.join(root, file)
                    frel = os.path.relpath(fpath, base_dir)
                    if frel in added:
                        continue
                    ext = os.path.splitext(file)[1].lower()
                    if ext in DELIVERABLE_EXTENSIONS:
                        zf.write(fpath, frel)
                        added.add(frel)


def _walk_filesystem(zf, base_dir):
    """Fallback: walk filesystem and filter by _is_deliverable."""
    for root, _dirs, files in os.walk(base_dir):
        for file in files:
            file_path = os.path.join(root, file)
            if not _is_deliverable(file_path, base_dir):
                continue
            arcname = os.path.relpath(file_path, base_dir)
            zf.write(file_path, arcname)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_agents.py::test_packaging_agent_with_delivery_map -v`
Expected: PASS

- [ ] **Step 5: Run original packaging test to verify backward compat**

Run: `python -m pytest tests/test_agents.py::test_packaging_agent -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agents/packaging_agent.py tests/test_agents.py
git commit -m "feat: packaging agent uses _delivery_map for file selection"
```

---

### Task 5: Update gumroad agent to use delivery_map

**Files:**
- Modify: `agents/gumroad_agent.py`
- Test: `tests/test_agents.py` (update test_gumroad_agent_publish)

- [ ] **Step 1: Write failing test for delivery-aware gumroad publish**

```python
def test_gumroad_agent_publish_with_delivery_map(tmp_path, monkeypatch):
    from agents import gumroad_agent
    import httpx

    monkeypatch.setenv("GUMROAD_ACCESS_TOKEN", "fake_token")
    monkeypatch.setattr(gumroad_agent, "_get_previous_product_id", lambda *a, **kw: "prod_test456")

    urls = iter([
        "https://s3.example.com/cheatsheet.pdf",
        "https://s3.example.com/package.zip",
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
                    {"id": "f2", "url": "https://s3.example.com/package.zip"},
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

    # ZIP file (package output)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_agents.py::test_gumroad_agent_publish_with_delivery_map -v`
Expected: FAIL — gumroad agent scans filesystem, doesn't use delivery_map

- [ ] **Step 3: Update gumroad agent to use delivery_map**

In `agents/gumroad_agent.py:_run_publish()`, replace the file scanning section (lines 334-343):

```python
    # Scan output directory for files: use delivery_map if available, else fallback
    files_to_upload = []
    delivery_map = context.get("_delivery_map")

    if delivery_map:
        for comp_id, entry in delivery_map.items():
            if "gumroad" not in entry.get("delivery", []):
                continue
            path = entry.get("output")
            if path and os.path.isfile(path):
                files_to_upload.append({"path": path, "name": os.path.basename(path)})
    else:
        # Fallback: scan presentation/*.pdf and root *.zip
        pres_dir = os.path.join(output_dir, "presentation")
        if os.path.isdir(pres_dir):
            for fn in os.listdir(pres_dir):
                if fn.lower().endswith(".pdf"):
                    files_to_upload.append({"path": os.path.join(pres_dir, fn), "name": fn})
        zip_path = os.path.join(output_dir, f"{job_spec.slug}.zip")
        if os.path.isfile(zip_path):
            files_to_upload.append({"path": zip_path, "name": os.path.basename(zip_path)})
```

Also ensure the ZIP file upload (from package component) still works when delivery_map is present. The ZIP file path can be found from the delivery_map:

```python
    # Find ZIP from delivery_map if present
    if delivery_map:
        for comp_id, entry in delivery_map.items():
            if comp_id == "package":
                zip_candidate = entry.get("output")
                if zip_candidate and os.path.isfile(zip_candidate):
                    # Add ZIP if not already in files_to_upload
                    if not any(f["path"] == zip_candidate for f in files_to_upload):
                        files_to_upload.append({"path": zip_candidate, "name": os.path.basename(zip_candidate)})
```

Add this after the delivery_map scan above.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_agents.py::test_gumroad_agent_publish_with_delivery_map -v`
Expected: PASS

- [ ] **Step 5: Run original gumroad publish test to verify backward compat**

Run: `python -m pytest tests/test_agents.py::test_gumroad_agent_publish -v`
Expected: PASS

- [ ] **Step 6: Run all agent tests**

Run: `python -m pytest tests/test_agents.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add agents/gumroad_agent.py tests/test_agents.py
git commit -m "feat: gumroad agent uses _delivery_map for individual file uploads"
```

---

### Task 6: Update schema JSON files with delivery assignments

**Files:**
- Modify: `schemas/research_pack.json`
- Modify: `schemas/blog_kit.json`
- Modify: `schemas/visual_pack.json`
- Modify: `schemas/saas_docs.json`
- Modify: `schemas/course_launch.json`
- Modify: `schemas/operating_system.json`
- Modify: `schemas/workflow_kit.json`

No test needed — config change (TDD exception per skill rule).

- [ ] **Step 1: Update research_pack.json**

```json
{
  "product_type": "research_pack",
  "display_name": "Research Pack",
  "components": [
    {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": [], "delivery": []},
    {"id": "images", "agent": "image_agent", "output": "data/images_generated.json", "depends_on": ["market_research"], "delivery": []},
    {"id": "gumroad_research", "agent": "gumroad_agent", "output": "gumroad/research.json", "depends_on": ["market_research"], "delivery": []},
    {"id": "gumroad_publish", "agent": "gumroad_agent", "output": "gumroad/published.json", "depends_on": ["gumroad_research", "market_research"], "delivery": []},
    {"id": "stitch_download", "agent": "stitch_agent", "output": "stitch/manifest.json", "depends_on": ["market_research"], "delivery": []},
    {"id": "landing_page", "agent": "landing_agent", "output": "landing/deployed.json", "depends_on": ["gumroad_publish", "stitch_download"], "delivery": []},
    {"id": "social_promotion", "agent": "social_agent", "output": "landing/social_results.json", "depends_on": ["landing_page"], "delivery": []},
    {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["market_research"], "delivery": ["zip"]}
  ],
  "notion_sync": false
}
```

- [ ] **Step 2: Update blog_kit.json** (same pattern as research_pack)

Same component delivery values — all internal components get `"delivery": []`, only package gets `"delivery": ["zip"]`.

- [ ] **Step 3: Update visual_pack.json** (same pattern)

- [ ] **Step 4: Update saas_docs.json** (same pattern)

- [ ] **Step 5: Update course_launch.json**

```json
{
  "product_type": "course_launch",
  "display_name": "Course Launch Kit",
  "notion_sync": true,
  "components": [
    {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": [], "delivery": []},
    {"id": "images", "agent": "image_agent", "output": "data/images_generated.json", "depends_on": ["market_research"], "delivery": []},
    {"id": "notion_schema", "agent": "notion_schema_agent", "output": "data/notion_schema.json", "depends_on": ["market_research"], "delivery": []},
    {"id": "notion_tree", "agent": "notion_agent", "output": "notion_sync.json", "depends_on": ["notion_schema"], "delivery": []},
    {"id": "gumroad_research", "agent": "gumroad_agent", "output": "gumroad/research.json", "depends_on": ["market_research"], "delivery": []},
    {"id": "gumroad_publish", "agent": "gumroad_agent", "output": "gumroad/published.json", "depends_on": ["gumroad_research", "market_research"], "delivery": []},
    {"id": "stitch_download", "agent": "stitch_agent", "output": "stitch/manifest.json", "depends_on": ["market_research"], "delivery": []},
    {"id": "landing_page", "agent": "landing_agent", "output": "landing/deployed.json", "depends_on": ["gumroad_publish", "stitch_download"], "delivery": []},
    {"id": "social_promotion", "agent": "social_agent", "output": "landing/social_results.json", "depends_on": ["landing_page"], "delivery": []},
    {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["market_research"], "delivery": ["zip"]}
  ],
  "notion_structure": {
    "type": "functional_workspace",
    "description": "Dynamic student tracker, marketing pipeline, and revenue dashboard generated based on niche + market research"
  }
}
```

- [ ] **Step 6: Update operating_system.json** (same pattern as course_launch)

- [ ] **Step 7: Update workflow_kit.json** (same pattern)

- [ ] **Step 8: Run all tests to verify schema changes don't break anything**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add schemas/
git commit -m "feat: add delivery routing to all schema files"
```

---

### Task 7: Run full test suite and verify

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Run lint**

Run: `ruff check .`
Expected: No errors (or fix any)

- [ ] **Step 3: Push**

```bash
git push
```
