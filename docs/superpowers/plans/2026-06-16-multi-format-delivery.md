# Phase 3: Multi-Format Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable market_agent to recommend output formats per component, orchestrator to route multi-format output, and agents to produce multiple formats simultaneously.

**Architecture:** Add `capabilities` field to ComponentSpec (declares what each component *can* produce). Market_agent recommends `recommended_formats` per component. Orchestrator validates intersection and sets `active_formats`. Agents check `active_formats` to decide what to produce. Delivery map extended to track per-format paths.

**Tech Stack:** Python, Pydantic, openpyxl>=3.1.0

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `orchestrator/models.py` | **Modify** | Add `capabilities`, `active_formats` to `ComponentSpec` + `PipelineComponent`; add `output_paths` to `AgentResult` |
| `orchestrator/orchestrator.py` | **Modify** | Add `_merge_format_recommendations()`, call in `run()`; extend `_delivery_map` for per-format paths |
| `agents/market_agent.py` | **Modify** | Include `recommended_formats` in output, pass component capabilities in prompt context |
| `agents/csv_export_agent.py` | **Modify** | Support multi-format: CSV + XLSX based on `active_formats` |
| `prompts/market_research.j2` | **Modify** | Add format recommendation instruction block |
| `requirements.txt` | **Modify** | Add `openpyxl>=3.1.0` |
| `tests/test_multi_format.py` | **Create** | All multi-format integration tests |

---

### Task 1: Update models with capabilities/active_formats/output_paths

**Files:**
- Modify: `orchestrator/models.py`

**Context:** Add `capabilities: List[str]` and `active_formats: List[str]` to both `ComponentSpec` and `PipelineComponent`. Add `output_paths: Optional[Dict[str, str]]` to `AgentResult`. All default to empty/None for backward compatibility.

- [ ] **Step 1: Add fields to ComponentSpec**

In `orchestrator/models.py`, add two fields to `ComponentSpec`:

```python
class ComponentSpec(BaseModel):
    id: str
    agent: str
    output: str
    depends_on: List[str] = Field(default_factory=list)
    uses_renderer: bool = False
    template: Optional[str] = None
    format: Literal["full", "guide", "notion", "prompt", "resource"] = "full"
    delivery: List[str] = Field(default_factory=lambda: ["zip"])
    capabilities: List[str] = Field(default_factory=list)
    active_formats: List[str] = Field(default_factory=list)
```

- [ ] **Step 2: Add same fields to PipelineComponent**

In `orchestrator/models.py`, add the same two fields to `PipelineComponent`:

```python
class PipelineComponent(BaseModel):
    id: str
    agent: str
    output: str
    depends_on: List[str] = Field(default_factory=list)
    uses_renderer: bool = False
    template: Optional[str] = None
    format: Literal["full", "guide", "notion", "prompt", "resource"] = "full"
    delivery: List[str] = Field(default_factory=lambda: ["zip"])
    capabilities: List[str] = Field(default_factory=list)
    active_formats: List[str] = Field(default_factory=list)
```

- [ ] **Step 3: Add output_paths to AgentResult**

In `orchestrator/models.py`, add to `AgentResult`:

```python
class AgentResult(BaseModel):
    status: Literal["pending", "running", "done", "failed", "skipped"]
    output_path: Optional[str] = None
    error: Optional[str] = None
    output_paths: Optional[Dict[str, str]] = None
```

Add `from typing import Dict` at the top if not already imported (currently it has `from typing import List, Literal, Dict, Optional` — confirm).

- [ ] **Step 4: Verify models still load existing schemas**

Run: `python -c "from orchestrator.models import ProductSchema, ComponentSpec; c = ComponentSpec(id='test', agent='test', output='out'); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add orchestrator/models.py
git commit -m "feat: add capabilities, active_formats, output_paths to models"
```

---

### Task 2: Install openpyxl

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add openpyxl dependency**

Add to `requirements.txt`:
```
openpyxl>=3.1.0
```

- [ ] **Step 2: Install**

Run: `pip install openpyxl`
Expected: Successfully installed openpyxl

- [ ] **Step 3: Verify install**

Run: `python -c "import openpyxl; print(openpyxl.__version__)"`
Expected: version number printed

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add openpyxl dependency for xlsx generation"
```

---

### Task 3: csv_export_agent multi-format support (CSV + XLSX)

**Files:**
- Modify: `agents/csv_export_agent.py`
- Test: `tests/test_multi_format.py`

**Context:** csv_export_agent currently reads `database` key from context and writes a single CSV. When `component.active_formats` contains `["csv", "xlsx"]`, it should write both files side by side.

- [ ] **Step 1: Write failing test for multi-format CSV+XLSX**

Create `tests/test_multi_format.py`:

```python
import json
import os
import pytest
from agents.csv_export_agent import run
from orchestrator.models import ComponentSpec, JobSpec


def test_csv_export_agent_multi_format(tmp_path):
    """csv_export_agent writes both CSV and XLSX when active_formats has both."""
    output_dir = tmp_path / "outputs" / "test-multi" / "data"
    output_dir.mkdir(parents=True)

    research_data = {
        "niche": "real estate agents",
        "database": [
            {"name": "Agent A", "city": "NYC", "phone": "555-0101"},
            {"name": "Agent B", "city": "LA", "phone": "555-0102"},
        ]
    }
    research_path = tmp_path / "research.json"
    with open(research_path, "w") as f:
        json.dump(research_data, f)

    comp = ComponentSpec(
        id="database_export",
        agent="csv_export_agent",
        output="data/test_multi_db.csv",
        depends_on=["market_research"],
        delivery=["zip"],
        capabilities=["csv", "xlsx"],
        active_formats=["csv", "xlsx"],
    )
    job = JobSpec(slug="test-multi", product_type="database", niche="real estate")
    context = {"market_research": str(research_path)}

    result = run(comp, job, context)
    assert result.status == "done"
    assert result.output_paths is not None
    assert "csv" in result.output_paths
    assert "xlsx" in result.output_paths

    # Verify CSV content
    with open(result.output_paths["csv"]) as f:
        content = f.read()
    assert "Agent A" in content
    assert "NYC" in content

    # Verify XLSX exists
    assert os.path.exists(result.output_paths["xlsx"])
    assert result.output_paths["xlsx"].endswith(".xlsx")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_multi_format.py::test_csv_export_agent_multi_format -v`
Expected: FAIL — csv_export_agent doesn't check active_formats or write xlsx yet

- [ ] **Step 3: Update csv_export_agent with multi-format support**

Read the current `agents/csv_export_agent.py` first. Replace the run() function body to check `active_formats`:

```python
def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        data_path = context.get("database")
        if not data_path:
            research_path = context.get("market_research")
            if not research_path:
                raise ValueError("Neither 'database' nor 'market_research' found in context")
            with open(research_path, "r") as f:
                research = json.load(f)
            data = research.get("database")
            if not data:
                raise ValueError("'database' key not found in market research output")
        else:
            with open(data_path, "r") as f:
                data = json.load(f)

        if not data:
            raise ValueError("No data to export")

        base_dir = os.path.join("outputs", job_spec.slug)
        output_dir = os.path.dirname(os.path.join(base_dir, component.output))
        os.makedirs(output_dir, exist_ok=True)

        active_formats = getattr(component, "active_formats", []) or []
        output_paths = {}

        if not active_formats or "csv" in active_formats:
            csv_path = os.path.join(output_dir, f"{component.id}.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            output_paths["csv"] = csv_path

        if "xlsx" in active_formats:
            import openpyxl
            xlsx_path = os.path.join(output_dir, f"{component.id}.xlsx")
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = component.id
            if data:
                ws.append(list(data[0].keys()))
                for row in data:
                    ws.append(list(row.values()))
            wb.save(xlsx_path)
            output_paths["xlsx"] = xlsx_path

        if not output_paths:
            raise ValueError("No formats produced")

        primary_path = list(output_paths.values())[0]
        return AgentResult(
            status="done",
            output_path=primary_path,
            output_paths=output_paths,
        )

    except Exception as e:
        logger.error(f"CSV export agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
```

Ensure `import csv` and `import os` are at the top. Add `import openpyxl` at the top or import inline in the xlsx block.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_multi_format.py::test_csv_export_agent_multi_format -v`
Expected: PASS

- [ ] **Step 5: Run existing csv_export tests**

Run: `python -m pytest tests/test_csv_export_agent.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add agents/csv_export_agent.py tests/test_multi_format.py
git commit -m "feat: csv_export_agent multi-format CSV+XLSX support"
```

---

### Task 4: Update market agent prompt for format recommendation

**Files:**
- Modify: `prompts/market_research.j2`

**Context:** Add format recommendation instruction to the prompt template so market_agent knows to output `recommended_formats`. The prompt must tell it which components and capabilities are available.

- [ ] **Step 1: Read current prompt template**

Run: `cat prompts/market_research.j2` to see current structure.

- [ ] **Step 2: Add format recommendation block**

Insert this block before the `## Rules` section (or at the end, before the final instruction):

```jinja2
## Format Recommendation

Based on your recommended product type, determine which OUTPUT FORMATS each component of the schema should produce.

Each schema component has CAPABILITIES — the formats it *can* produce. Select the best subset for this specific niche.

Consider:
- What formats do top competitors sell? (PDF guides, CSV data, Excel files, Notion workspaces?)
- Buyers in this niche — will they use raw CSV, a formatted PDF, an Excel sheet with formulas?
- If the niche needs actionable data → include "csv" or "xlsx"
- If the niche needs explanation/guidance → include "pdf"
- If the niche needs organization/tracking → include "notion"

Output your recommendation in the "recommended_formats" field — a JSON object mapping component IDs to arrays of format strings.

Example:
```json
{
  "recommended_formats": {
    "database_export": ["csv", "xlsx"],
    "market_research": ["pdf"]
  }
}
```

Only include a component if you want to change its output from the default single format. Leave it out for default behavior.
```

- [ ] **Step 3: Verify prompt loads**

Run: `python -c "from jinja2 import Template; open('prompts/market_research.j2').read(); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add prompts/market_research.j2
git commit -m "feat: add format recommendation instruction to market research prompt"
```

---

### Task 5: Update market_agent to include recommended_formats in output

**Files:**
- Modify: `agents/market_agent.py`
- Test: `tests/test_multi_format.py`

**Context:** Market_agent needs to pass `recommended_formats` through from the LLM output. The prompt (Task 4) tells the LLM to generate it — we just need to ensure the agent doesn't strip it.

- [ ] **Step 1: Write failing test for recommended_formats**

Add to `tests/test_multi_format.py`:

```python
def test_market_agent_recommends_formats(monkeypatch):
    """Test that market_agent returns recommended_formats in output."""
    from agents import market_agent
    from orchestrator.models import ComponentSpec, JobSpec

    monkeypatch.setattr(
        "agents.llm_client.generate_text",
        lambda p: json.dumps({
            "competitor_landscape": {"direct_competitors": [], "pricing_tiers": {}, "recommended_price": 29, "quality_gaps": [], "trending_keywords": []},
            "content_recommendations": {"tone": "professional", "key_themes": [], "seo_keywords": []},
            "market_insights": {},
            "recommended_product_type": "database",
            "recommendation_confidence": 0.85,
            "recommendation_reasoning": "High demand for lead lists",
            "recommended_formats": {
                "database_export": ["csv", "xlsx"],
                "market_research": ["pdf"],
            },
            "pipeline_plan": {"components": []},
        }),
    )

    monkeypatch.setattr("agents.research_tools.brave_search", lambda q, n: [])
    monkeypatch.setattr("agents.research_tools.duckduckgo_search", lambda q, n: [])
    monkeypatch.setattr("agents.research_tools.reddit_search", lambda q, n: [])
    monkeypatch.setattr("agents.research_tools.gdelt_news", lambda q, n: [])
    monkeypatch.setattr("agents.research_tools.newsapi_headlines", lambda q, n: [])
    monkeypatch.setattr("agents.research_tools.pytrends_data", lambda q: {})
    monkeypatch.setattr("agents.research_tools.firecrawl_scrape", lambda u: None)

    job_spec = JobSpec(slug="test-format-rec", product_type="database", niche="real estate")
    comp = ComponentSpec(id="market_research", agent="market_agent", output="data/market_research.json", depends_on=[])
    context = {}

    result = market_agent.run(comp, job_spec, context)
    assert result.status == "done"

    with open(result.output_path) as f:
        research = json.load(f)

    assert "recommended_formats" in research
    assert "database_export" in research["recommended_formats"]
    assert "xlsx" in research["recommended_formats"]["database_export"]
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `python -m pytest tests/test_multi_format.py::test_market_agent_recommends_formats -v`

If it fails: market_agent strips the field somewhere. If it passes: the field already passes through (the LLM response is written as-is). Expected behavior depends on current agent implementation.

- [ ] **Step 3: If test fails — update market_agent.py**

Read the current `agents/market_agent.py` to find where research dict is constructed. Ensure `recommended_formats` is not filtered out. The `_fallback_research` function should also include it:

```python
def _fallback_research(niche: str, product_type: str) -> dict:
    return {
        "niche": niche,
        "product_type": product_type,
        "recommended_product_type": "research_pack",
        "recommendation_confidence": 0.3,
        "recommendation_reasoning": "Insufficient data — falling back to research_pack",
        "recommended_formats": {},
        ...
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_multi_format.py::test_market_agent_recommends_formats -v`
Expected: PASS

- [ ] **Step 5: Run existing agent tests**

Run: `python -m pytest tests/test_agents.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add agents/market_agent.py tests/test_multi_format.py
git commit -m "feat: market_agent outputs recommended_formats"
```

---

### Task 6: Orchestrator merge format recommendations

**Files:**
- Modify: `orchestrator/orchestrator.py`
- Test: `tests/test_multi_format.py`

**Context:** After market_agent completes, orchestrator reads `recommended_formats` and merges them into component `active_formats`, validating against `capabilities`.

- [ ] **Step 1: Write failing test for format merge**

Add to `tests/test_multi_format.py`:

```python
def test_orchestrator_merges_format_recs(tmp_path, monkeypatch):
    """Orchestrator sets active_formats after market_agent recommends."""
    from orchestrator.orchestrator import Orchestrator
    from orchestrator.state import load_job_state
    from orchestrator.models import AgentResult, ProductSchema
    from agents.registry import AGENT_REGISTRY
    from unittest import mock
    import json, os, shutil

    slug = "test-merge-fmts"

    def _write_json(path, data):
        path = tmp_path / path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f)

    # Create job spec
    _write_json("job_spec.json", {
        "slug": slug, "product_type": "discovery", "niche": "test",
        "notion_sync": False, "notion_parent_page_id": None,
        "created_at": "2026-06-16T10:00:00Z",
    })

    # Create discovery schema
    _write_json("discovery.json", {
        "product_type": "discovery", "display_name": "Discovery",
        "components": [{"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []}],
    })

    # Create database schema with capabilities
    _write_json("database.json", {
        "product_type": "database", "display_name": "Database",
        "components": [
            {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
            {"id": "database_export", "agent": "csv_export_agent", "output": "data/{slug}_database.csv", "depends_on": ["market_research"], "delivery": ["zip"], "capabilities": ["csv", "xlsx"]},
        ],
    })

    def mock_market(comp, js, ctx):
        out_dir = os.path.join("outputs", js.slug, "data")
        os.makedirs(out_dir, exist_ok=True)
        research = {
            "niche": "test",
            "recommended_product_type": "database",
            "recommendation_confidence": 0.9,
            "recommendation_reasoning": "test",
            "recommended_formats": {"database_export": ["csv", "xlsx"]},
            "pipeline_plan": {"components": []},
        }
        path = os.path.join(out_dir, "market_research.json")
        with open(path, "w") as f:
            json.dump(research, f)
        return AgentResult(status="done", output_path=path)

    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market)
    monkeypatch.setitem(AGENT_REGISTRY, "csv_export_agent", mock.Mock(return_value=AgentResult(status="done")))

    job_spec_path = str(tmp_path / "job_spec.json")
    orc = Orchestrator(job_spec_path)
    with open(tmp_path / "discovery.json") as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.schema_path = str(tmp_path / "discovery.json")
    orc.state_path = os.path.join("outputs", slug, "job_state.json")
    orc.state = load_job_state(orc.state_path, slug)
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    # Schema should have switched
    assert orc.schema.product_type == "database"

    # database_export component should have active_formats
    export_comp = [c for c in orc.schema.components if c.id == "database_export"]
    assert len(export_comp) == 1
    assert "csv" in export_comp[0].active_formats
    assert "xlsx" in export_comp[0].active_formats
```

Also add a test for invalid format filtering:

```python
def test_invalid_format_filtered(tmp_path, monkeypatch):
    """Unknown formats in recommended_formats are silently ignored."""
    from orchestrator.orchestrator import Orchestrator
    from orchestrator.state import load_job_state
    from orchestrator.models import AgentResult, ProductSchema
    from agents.registry import AGENT_REGISTRY
    from unittest import mock
    import json, os

    slug = "test-filter-fmts"

    def _write_json(path, data):
        path = tmp_path / path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f)

    _write_json("job_spec.json", {
        "slug": slug, "product_type": "discovery", "niche": "test",
        "notion_sync": False, "notion_parent_page_id": None,
        "created_at": "2026-06-16T10:00:00Z",
    })

    _write_json("discovery.json", {
        "product_type": "discovery", "display_name": "Discovery",
        "components": [{"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []}],
    })

    _write_json("database.json", {
        "product_type": "database", "display_name": "Database",
        "components": [
            {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
            {"id": "database_export", "agent": "csv_export_agent", "output": "data/{slug}_database.csv", "depends_on": ["market_research"], "delivery": ["zip"], "capabilities": ["csv"]},
        ],
    })

    def mock_market(comp, js, ctx):
        out_dir = os.path.join("outputs", js.slug, "data")
        os.makedirs(out_dir, exist_ok=True)
        research = {
            "niche": "test",
            "recommended_product_type": "database",
            "recommendation_confidence": 0.9,
            "recommendation_reasoning": "test",
            "recommended_formats": {"database_export": ["csv", "xlsx", "pdf"]},
            "pipeline_plan": {"components": []},
        }
        path = os.path.join(out_dir, "market_research.json")
        with open(path, "w") as f:
            json.dump(research, f)
        return AgentResult(status="done", output_path=path)

    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market)
    monkeypatch.setitem(AGENT_REGISTRY, "csv_export_agent", mock.Mock(return_value=AgentResult(status="done")))

    job_spec_path = str(tmp_path / "job_spec.json")
    orc = Orchestrator(job_spec_path)
    with open(tmp_path / "discovery.json") as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.schema_path = str(tmp_path / "discovery.json")
    orc.state_path = os.path.join("outputs", slug, "job_state.json")
    orc.state = load_job_state(orc.state_path, slug)
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    # database_export only has "csv" capability, so xlsx and pdf should be filtered
    export_comp = [c for c in orc.schema.components if c.id == "database_export"]
    assert len(export_comp) == 1
    assert export_comp[0].active_formats == ["csv"]
```

Also add backward compatibility test:

```python
def test_no_recs_legacy_mode(tmp_path, monkeypatch):
    """No recommended_formats means legacy mode — no active_formats set."""
    from orchestrator.orchestrator import Orchestrator
    from orchestrator.state import load_job_state
    from orchestrator.models import AgentResult, ProductSchema
    from agents.registry import AGENT_REGISTRY
    from unittest import mock
    import json, os

    slug = "test-legacy-fmts"

    def _write_json(path, data):
        path = tmp_path / path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f)

    _write_json("job_spec.json", {
        "slug": slug, "product_type": "discovery", "niche": "test",
        "notion_sync": False, "notion_parent_page_id": None,
        "created_at": "2026-06-16T10:00:00Z",
    })

    _write_json("discovery.json", {
        "product_type": "discovery", "display_name": "Discovery",
        "components": [{"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []}],
    })

    _write_json("database.json", {
        "product_type": "database", "display_name": "Database",
        "components": [
            {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
            {"id": "database_export", "agent": "csv_export_agent", "output": "data/{slug}_database.csv", "depends_on": ["market_research"], "delivery": ["zip"], "capabilities": ["csv", "xlsx"]},
        ],
    })

    def mock_market(comp, js, ctx):
        out_dir = os.path.join("outputs", js.slug, "data")
        os.makedirs(out_dir, exist_ok=True)
        research = {
            "niche": "test",
            "recommended_product_type": "database",
            "recommendation_confidence": 0.9,
            "recommendation_reasoning": "test",
            "pipeline_plan": {"components": []},
        }
        path = os.path.join(out_dir, "market_research.json")
        with open(path, "w") as f:
            json.dump(research, f)
        return AgentResult(status="done", output_path=path)

    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market)
    monkeypatch.setitem(AGENT_REGISTRY, "csv_export_agent", mock.Mock(return_value=AgentResult(status="done")))

    job_spec_path = str(tmp_path / "job_spec.json")
    orc = Orchestrator(job_spec_path)
    with open(tmp_path / "discovery.json") as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.schema_path = str(tmp_path / "discovery.json")
    orc.state_path = os.path.join("outputs", slug, "job_state.json")
    orc.state = load_job_state(orc.state_path, slug)
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    # No active_formats should be set (legacy mode)
    export_comp = [c for c in orc.schema.components if c.id == "database_export"]
    assert len(export_comp) == 1
    assert export_comp[0].active_formats == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_multi_format.py::test_orchestrator_merges_format_recs tests/test_multi_format.py::test_invalid_format_filtered tests/test_multi_format.py::test_no_recs_legacy_mode -v`
Expected: FAIL — no `_merge_format_recommendations` method exists

- [ ] **Step 3: Add `_merge_format_recommendations` to orchestrator**

In `orchestrator/orchestrator.py`, add after the existing `_merge_pipeline_plan` method:

```python
def _merge_format_recommendations(self, research_path: str) -> None:
    """Merge market_agent's recommended_formats into component active_formats."""
    try:
        with open(research_path) as f:
            research = json.load(f)
        fmt_recs = research.get("recommended_formats", {})
        if not fmt_recs:
            return  # legacy mode

        comp_map = {c.id: c for c in self.schema.components}
        for comp_id, formats in fmt_recs.items():
            comp = comp_map.get(comp_id)
            if not comp:
                logger.warning(
                    "recommended_formats references unknown component: %s", comp_id
                )
                continue
            if not comp.capabilities:
                logger.warning(
                    "recommended_formats for %s but component has no capabilities",
                    comp_id,
                )
                continue
            active = [f for f in formats if f in comp.capabilities]
            if active:
                comp.active_formats = active
                logger.info(
                    "Component %s active formats: %s", comp_id, active
                )
    except Exception as e:
        logger.error("Failed to merge format recommendations: %s", e)
```

- [ ] **Step 4: Call `_merge_format_recommendations` in `run()`**

Find the block in `run()` where `_merge_pipeline_plan` is called (around the `component.id == "market_research"` block). Add the new call right after:

```python
if component.id == "market_research" and result.status == "done":
    if self.job_spec.product_type == "discovery":
        try:
            with open(result.output_path) as f:
                research = json.load(f)
            recommended = research.get("recommended_product_type")
            confidence = research.get("recommendation_confidence", 0)
            if recommended and confidence >= 0.5:
                self._switch_schema(recommended)
            elif recommended:
                logger.warning(
                    "Low confidence (%.2f) for '%s' — falling back to research_pack",
                    confidence, recommended,
                )
                self._switch_schema("research_pack")
            else:
                logger.warning("No product type recommendation — falling back to research_pack")
                self._switch_schema("research_pack")
        except Exception as e:
            logger.error("Failed to read market_research.json for schema switch: %s", e)
            self._switch_schema("research_pack")

    self._merge_pipeline_plan(result.output_path)
    self._merge_format_recommendations(result.output_path)  # NEW
    ordered_components = self._get_execution_order()
    idx = 0
    total = len(ordered_components)
    logger.info("Pipeline re-planned: %s total components", total)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_multi_format.py::test_orchestrator_merges_format_recs tests/test_multi_format.py::test_invalid_format_filtered tests/test_multi_format.py::test_no_recs_legacy_mode -v`
Expected: All PASS

- [ ] **Step 6: Run all orchestrator tests**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: All PASS (backward compatibility maintained)

- [ ] **Step 7: Commit**

```bash
git add orchestrator/orchestrator.py tests/test_multi_format.py
git commit -m "feat: orchestrator merges format recommendations from market_agent"
```

---

### Task 7: Extend delivery map for multi-format

**Files:**
- Modify: `orchestrator/orchestrator.py`
- Test: `tests/test_multi_format.py`

**Context:** The delivery map currently stores `component_id → {"outputs": [...], "delivery": [...]}`. Extend to support per-format output paths from `agent_result.output_paths`.

- [ ] **Step 1: Write failing test for multi-format delivery**

Add to `tests/test_multi_format.py`:

```python
def test_delivery_map_per_format(tmp_path, monkeypatch):
    """delivery_map stores per-format paths from agent_result.output_paths."""
    from orchestrator.orchestrator import Orchestrator
    from orchestrator.state import load_job_state
    from orchestrator.models import AgentResult, ProductSchema
    from agents.registry import AGENT_REGISTRY
    from unittest import mock
    import json, os

    slug = "test-delivery-fmts"

    def _write_json(path, data):
        path = tmp_path / path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f)

    _write_json("job_spec.json", {
        "slug": slug, "product_type": "database", "niche": "test",
        "notion_sync": False, "notion_parent_page_id": None,
        "created_at": "2026-06-16T10:00:00Z",
    })

    _write_json("database.json", {
        "product_type": "database", "display_name": "Database",
        "components": [
            {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
            {"id": "database_export", "agent": "csv_export_agent", "output": "data/{slug}_database.csv", "depends_on": ["market_research"], "delivery": ["zip"], "capabilities": ["csv", "xlsx"], "active_formats": ["csv", "xlsx"]},
        ],
    })

    def mock_market(comp, js, ctx):
        out_dir = os.path.join("outputs", js.slug, "data")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "market_research.json")
        with open(path, "w") as f:
            json.dump({"niche": "test", "pipeline_plan": {"components": []}}, f)
        return AgentResult(status="done", output_path=path)

    def mock_csv(comp, js, ctx):
        out_dir = os.path.join("outputs", js.slug, "data")
        os.makedirs(out_dir, exist_ok=True)
        csv_path = os.path.join(out_dir, "database_export.csv")
        xlsx_path = os.path.join(out_dir, "database_export.xlsx")
        with open(csv_path, "w") as f:
            f.write("name,city\nA,NYC\n")
        return AgentResult(
            status="done",
            output_path=csv_path,
            output_paths={"csv": csv_path, "xlsx": xlsx_path},
        )

    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market)
    monkeypatch.setitem(AGENT_REGISTRY, "csv_export_agent", mock_csv)

    job_spec_path = str(tmp_path / "job_spec.json")
    orc = Orchestrator(job_spec_path)
    with open(tmp_path / "database.json") as f:
        orc.schema = ProductSchema(**json.load(f))
    orc.state_path = os.path.join("outputs", slug, "job_state.json")
    orc.state = load_job_state(orc.state_path, slug)
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    # delivery_map should track per-format paths for database_export
    dm = orc._delivery_map
    assert "database_export" in dm
    outputs = dm["database_export"].get("outputs", {})
    assert "csv" in outputs
    assert "xlsx" in outputs
    assert outputs["csv"].endswith(".csv")
    assert outputs["xlsx"].endswith(".xlsx")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_multi_format.py::test_delivery_map_per_format -v`
Expected: FAIL — delivery_map doesn't capture output_paths yet

- [ ] **Step 3: Extend delivery map in orchestrator**

In `orchestrator/orchestrator.py`, find where `_delivery_map` is populated (likely after each component runs). Extend it to capture `agent_result.output_paths`:

```python
# In the component execution loop, after agent runs:
if result.status == "done":
    entry = self._delivery_map.setdefault(component.id, {
        "outputs": {},
        "delivery": component.delivery,
    })
    # Store per-format outputs
    if result.output_paths:
        entry["outputs"] = result.output_paths
    else:
        entry["outputs"] = {component.id: result.output_path}
    entry["delivery"] = component.delivery
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_multi_format.py::test_delivery_map_per_format -v`
Expected: PASS

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add orchestrator/orchestrator.py tests/test_multi_format.py
git commit -m "feat: extend delivery_map for per-format output paths"
```

---

### Task 8: Final verification

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests pass (Phase 1 + Phase 2 + Phase 3)

- [ ] **Step 2: Verify models backward compat**

Run: `python -c "from orchestrator.models import ProductSchema, ComponentSpec; c = ComponentSpec(id='test', agent='test', output='out'); print('capabilities:', c.capabilities); print('active_formats:', c.active_formats)"`
Expected: `capabilities: []` `active_formats: []`

- [ ] **Step 3: Verify openpyxl works**

Run: `python -c "import openpyxl; wb = openpyxl.Workbook(); wb.save('test.xlsx'); import os; os.remove('test.xlsx'); print('openpyxl OK')"`
Expected: `openpyxl OK`

- [ ] **Step 4: Push**

```bash
git push
```
