# Notion Standalone Product Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add standalone Notion product mode alongside existing combo mode, plus fix the missing wizard gate for notion_sync.

**Architecture:** JobSpec gets `notion_only` flag. Orchestrator skips notion_schema/notion_tree when `notion_sync=False`, skips package + substitutes file agents with `notion_content_agent` when `notion_only=True`. New `notion_content_agent` creates Notion pages instead of writing `.md` files. Market agent recommends notion_only viability. Wizard gates both modes.

**Tech Stack:** Python 3.11+, Notion API, Jinja2, Pydantic v2

---

### Task 1: Add notion_only to JobSpec

**Files:**
- Modify: `orchestrator/models.py:21-34`

- [ ] **Step 1: Add notion_only field**

In `orchestrator/models.py`, add `notion_only: bool = False` to `JobSpec`:

```python
class JobSpec(BaseModel):
    slug: str
    product_type: str
    niche: str
    display_name: Optional[str] = None
    theme: str = "default"
    notion_sync: bool = False
    notion_only: bool = False  # new — standalone Notion product mode
    notion_parent_page_id: Optional[str] = None
    landing_page_enabled: bool = False
    social_promotion_enabled: bool = False
    gumroad_enabled: bool = False
    landing_page_url: Optional[str] = None
    call_to_action: str = "Buy Now on Gumroad"
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 2: Commit**

```bash
git add orchestrator/models.py
git commit -m "feat: add notion_only flag to JobSpec"
```

---

### Task 2: Fix Wizard Gate — notion_schema/notion_tree skip

**Files:**
- Modify: `orchestrator/orchestrator.py:166-196`

- [ ] **Step 1: Add notion skip logic to run() loop**

In `orchestrator/orchestrator.py`, after the gumroad skip block (after line 188), add:

```python
            # Skip notion_schema/notion_tree if notion_sync not enabled
            if component.id in ("notion_schema", "notion_tree") and not self.job_spec.notion_sync:
                self.state.components[component.id] = AgentResult(status="skipped", error="notion sync not enabled")
                save_job_state(self.state, self.state_path)
                done_count += 1
                logger.warning("%s/%s %s (disabled)", done_count, total, component.id)
                continue
```

- [ ] **Step 2: Commit**

```bash
git add orchestrator/orchestrator.py
git commit -m "fix: add wizard gate for notion_schema/notion_tree"
```

---

### Task 3: Wizard — Notion-only Question

**Files:**
- Modify: `cli/wizard.py:77-108`

- [ ] **Step 1: Add notion_only question to wizard**

After the notion_sync block (after line 108), add:

```python
    notion_only = False
    if not notion_sync:
        notion_only_prompt = typer.prompt(
            "Notion-only template bechein? (y/n)", default="n"
        )
        if notion_only_prompt.lower() == "y":
            notion_only = True
            notion_api_key = os.getenv("NOTION_API_KEY")
            if not notion_api_key or notion_api_key == "your_notion_api_key_here":
                notion_api_key = typer.prompt("Notion API Key missing. Please enter it")
                set_key(env_path, "NOTION_API_KEY", notion_api_key)
            notion_parent_page_id = os.getenv("NOTION_PARENT_PAGE_ID")
            if not notion_parent_page_id or notion_parent_page_id == "your_notion_parent_page_id_here":
                notion_parent_page_id = typer.prompt("Notion Parent Page ID missing. Please enter it")
                set_key(env_path, "NOTION_PARENT_PAGE_ID", notion_parent_page_id)
```

- [ ] **Step 2: Add notion_only to job_spec dict**

In the `job_spec` dict (line 199-212), add `notion_only`:

```python
    job_spec = {
        "slug": slug,
        "product_type": product_type,
        "niche": niche,
        "display_name": display_name,
        "theme": theme,
        "notion_sync": notion_sync,
        "notion_only": notion_only,
        "notion_parent_page_id": notion_parent_page_id,
        "gumroad_enabled": gumroad_enabled,
        "landing_page_enabled": landing_page_enabled,
        "social_promotion_enabled": social_promotion_enabled,
        "call_to_action": cta_text,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
```

- [ ] **Step 3: Auto-set notion_sync when notion_only=True**

In the wizard, when `notion_only=True`, also set `notion_sync=True` (because standalone mode needs Notion sync):

```python
    if notion_only_prompt.lower() == "y":
        notion_only = True
        notion_sync = True  # standalone mode requires notion sync
        ...
```

- [ ] **Step 4: Commit**

```bash
git add cli/wizard.py
git commit -m "feat: add notion_only question to wizard"
```

---

### Task 4: Market Agent — recommends_notion_only

**Files:**
- Modify: `prompts/market_research.j2:68-74`

- [ ] **Step 1: Add recommends_notion_only + notion_price_suggestion to prompt**

In `prompts/market_research.j2`, add to the market_insights section (after line 73):

```json
  - "recommends_notion_only" (boolean — true if this niche has demand for standalone Notion templates based on competitor analysis)
  - "notion_price_suggestion" (number — suggested price for standalone Notion product, typically 30-50% of full product price)
```

The full section should look like:

```jinja2
- "market_insights": object with:
  - "total_competitors_found" (integer)
  - "avg_competitor_price" (number or null)
  - "sentiment_summary" (string — from Reddit/user discussions)
  - "news_headline" (most relevant news story summary)
  - "trend_insight" (what's gaining/losing traction)
  - "recommends_notion_only" (boolean)
  - "notion_price_suggestion" (number)
```

- [ ] **Step 2: Commit**

```bash
git add prompts/market_research.j2
git commit -m "feat: add notion_only recommendation to market research prompt"
```

---

### Task 5: notion_content_agent — New Agent

**Files:**
- Create: `agents/notion_content_agent.py`

- [ ] **Step 1: Write the agent**

Create `agents/notion_content_agent.py`:

```python
import os
import json
import logging
from jinja2 import Environment, FileSystemLoader

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

PROMPT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        notion_api_key = os.getenv("NOTION_API_KEY")
        notion_parent_id = os.getenv("NOTION_PARENT_PAGE_ID")

        if not notion_api_key or not notion_parent_id:
            logger.warning("Notion not configured. Falling back to file output.")
            return _file_fallback(component, job_spec, context)

        from notion_client import Client
        notion = Client(auth=notion_api_key, notion_version="2022-06-28")

        # Find root page ID from notion_tree output in context
        root_page_id = None
        for key, path in context.items():
            if path and os.path.exists(path) and key == "notion_tree":
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                root_page_id = data.get("root_page_id")
                break

        if not root_page_id:
            logger.warning("No root page ID found in context. Falling back to file output.")
            return _file_fallback(component, job_spec, context)

        # Load and render prompt
        env = Environment(loader=FileSystemLoader(PROMPT_DIR))
        template_path = f"{component.id}.j2"
        if not os.path.exists(os.path.join(PROMPT_DIR, template_path)):
            logger.warning(f"Prompt {template_path} not found. Falling back to file output.")
            return _file_fallback(component, job_spec, context)

        template = env.get_template(template_path)

        # Build context from market_research if available
        research_data = {}
        for key, path in context.items():
            if path and os.path.exists(path) and "market_research" in key:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        research_data = json.load(f)
                except (json.JSONDecodeError, Exception):
                    pass
                break

        prompt = template.render(
            niche=job_spec.niche,
            product_type=job_spec.product_type,
            market_research=research_data,
        )

        from agents.llm_client import generate_text
        content = generate_text(prompt)

        # Create Notion page under root workspace
        page = notion.pages.create(
            parent={"page_id": root_page_id},
            properties={
                "title": {
                    "title": [{"text": {"content": component.id.replace("_", " ").title()}}]
                }
            },
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content[:2000]}}]
                    },
                }
            ],
        )

        result = {
            "page_id": page["id"],
            "page_url": page.get("url", ""),
            "component_id": component.id,
        }

        output_path = os.path.join("outputs", job_spec.slug, f"notion_content_{component.id}.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Notion content agent failed for {component.id}: {e}")
        return _file_fallback(component, job_spec, context)


def _file_fallback(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    """Fallback: write content as .md file when Notion unavailable."""
    try:
        from agents.content_agent import run as content_run
        return content_run(component, job_spec, context)
    except Exception as e:
        return AgentResult(status="failed", error=f"Notion content + fallback failed: {e}")
```

- [ ] **Step 2: Commit**

```bash
git add agents/notion_content_agent.py
git commit -m "feat: add notion_content_agent for Notion page creation"
```

---

### Task 6: Register notion_content_agent

**Files:**
- Modify: `agents/registry.py:18`, `agents/registry.py:36`

- [ ] **Step 1: Add import + registry entry**

```python
from . import (
    ...
    notion_content_agent,  # add
)

AGENT_REGISTRY = {
    ...
    "notion_content_agent": notion_content_agent.run,  # add
}
```

- [ ] **Step 2: Commit**

```bash
git add agents/registry.py
git commit -m "feat: register notion_content_agent in registry"
```

---

### Task 7: Orchestrator — notion_only Agent Substitution + Package Skip

**Files:**
- Modify: `orchestrator/orchestrator.py:120-225`

- [ ] **Step 1: Add agent substitution map + logic**

In `orchestrator/orchestrator.py`, after `_merge_pipeline_plan` (after line 118), add:

```python
    FILE_AGENT_SUBSTITUTIONS = {
        "content_agent": "notion_content_agent",
        "csv_export_agent": "notion_content_agent",
        "render_agent": "notion_content_agent",
        "diagram_agent": "notion_content_agent",
    }
```

In the `run()` method, after the pipeline_plan merge block (after line 217), add package skip logic:

```python
            # If notion_only mode: skip package, substitute file agents
            if self.job_spec.notion_only:
                if component.id == "package":
                    self.state.components[component.id] = AgentResult(status="skipped", error="notion_only mode: no ZIP")
                    save_job_state(self.state, self.state_path)
                    done_count += 1
                    logger.warning("%s/%s %s (notion_only — skipped)", done_count, total, component.id)
                    continue

                # Substitute file agent with notion_content_agent
                original_agent = component.agent
                substituted = FILE_AGENT_SUBSTITUTIONS.get(original_agent)
                if substituted:
                    agent_func = AGENT_REGISTRY.get(substituted)
                    logger.info("%s/%s %s (%s → %s)", done_count, total, component.id, original_agent, substituted)
```

Also add the import for the substitution map at the top of the class or after `_merge_pipeline_plan`. Actually let me put it as a class attribute or module-level constant.

Let me put it as a module-level constant after the imports:

```python
FILE_AGENT_SUBSTITUTIONS = {
    "content_agent": "notion_content_agent",
    "csv_export_agent": "notion_content_agent",
    "render_agent": "notion_content_agent",
    "diagram_agent": "notion_content_agent",
}
```

And the full run() block integration. After the existing `agent_func = AGENT_REGISTRY.get(component.agent)` line (currently line 164), add:

```python
            # notion_only mode: substitute file agents + skip package
            if self.job_spec.notion_only:
                if component.id == "package":
                    self.state.components[component.id] = AgentResult(status="skipped", error="notion_only mode: no ZIP")
                    save_job_state(self.state, self.state_path)
                    done_count += 1
                    logger.warning("%s/%s %s (notion_only — skipped)", done_count, total, component.id)
                    continue
                substituted = FILE_AGENT_SUBSTITUTIONS.get(component.agent)
                if substituted:
                    agent_func = AGENT_REGISTRY.get(substituted)
                    logger.info("%s/%s %s (%s → %s)", done_count, total, component.id, component.agent, substituted)
```

Wait, but `agent_func` is already defined at line 164. The substitution should happen BEFORE the `agent_func` lookup. Let me re-read the current orchestrator code...

Looking at orchestrator/orchestrator.py lines 160-196:

```python
            # Inject renderer if needed
            if component.uses_renderer:
                context["renderer"] = self.renderer
                
            agent_func = AGENT_REGISTRY.get(component.agent)

            # Skip landing_page if not enabled
            ...
```

So `agent_func` is defined at line 164, then the skip blocks check gates. The actual execution is at line 203: `result = agent_func(component, self.job_spec, context)`.

I should add the substitution AFTER the gate blocks (after line 188, before the agent_func check at line 190), or more specifically, replace the `agent_func` value after the gate blocks check. Let me place it right after the notion gate block:

```python
            # notion_only mode: substitute file agents + skip package
            if self.job_spec.notion_only:
                if component.id == "package":
                    self.state.components[component.id] = AgentResult(status="skipped", error="notion_only mode: no ZIP")
                    save_job_state(self.state, self.state_path)
                    done_count += 1
                    logger.warning("%s/%s %s (notion_only — skipped)", done_count, total, component.id)
                    continue
                substituted = FILE_AGENT_SUBSTITUTIONS.get(component.agent)
                if substituted:
                    agent_func = AGENT_REGISTRY.get(substituted)
```

This goes after the `if not agent_func:` check (line 190). No wait, actually `agent_func` is currently checked for None at line 190. If I'm substituting, `agent_func` should already be set to the substituted function. So the substitution should go BEFORE the `if not agent_func:` check.

Looking at the flow again:
1. Line 164: `agent_func = AGENT_REGISTRY.get(component.agent)` — gets by original agent name
2. Lines 166-188: gate checks (landing, social, gumroad) — these skip the component entirely
3. Line 190: `if not agent_func:` — checks if agent exists

If I add substitution after the gate checks but before the agent_func check, it would look like:

```python
            agent_func = AGENT_REGISTRY.get(component.agent)

            # Skip landing_page if not enabled
            ...
            # Skip social_promotion if not enabled
            ...
            # Skip gumroad if not enabled
            ...
            # Skip notion_schema/notion_tree if not enabled
            ... (Task 2)

            # notion_only mode: substitute file agents + skip package
            if self.job_spec.notion_only:
                if component.id == "package":
                    ...
                    continue
                substituted = FILE_AGENT_SUBSTITUTIONS.get(component.agent)
                if substituted:
                    agent_func = AGENT_REGISTRY.get(substituted)

            if not agent_func:
                ...
```

That works.

- [ ] **Step 2: Commit**

```bash
git add orchestrator/orchestrator.py
git commit -m "feat: notion_only agent substitution + package skip in orchestrator"
```

---

### Task 8: Gumroad — Slug Suffix for Notion-Only Products

**Files:**
- Modify: `agents/gumroad_agent.py:362-363`

- [ ] **Step 1: Add custom_permalink suffix when notion_only**

In `agents/gumroad_agent.py`, in `_run_publish()`, find the product_data dict (around line 362-367) and the custom_permalink assignment (line 471). For notion_only mode, append `-notion` to the slug:

```python
    custom_permalink = f"{job_spec.slug}-notion" if getattr(job_spec, 'notion_only', False) else job_spec.slug
```

Then use `custom_permalink` in the attach_body (line 471):

```python
        "custom_permalink": custom_permalink,
```

Also update the product name to indicate it's a Notion template:

```python
    product_name = (
        f"{job_spec.display_name or job_spec.niche} - {job_spec.product_type.replace('_', ' ').title()} Notion Template"
        if getattr(job_spec, 'notion_only', False)
        else f"{job_spec.display_name or job_spec.niche} - {job_spec.product_type.replace('_', ' ').title()}"
    )
```

- [ ] **Step 2: Commit**

```bash
git add agents/gumroad_agent.py
git commit -m "feat: notion_only slug suffix for Gumroad products"
```

---

### Task 9: Tests

**Files:**
- Create: `tests/test_notion_content_agent.py`

- [ ] **Step 1: Write test for notion_content_agent fallback**

Create `tests/test_notion_content_agent.py`:

```python
import pytest
from unittest import mock
from orchestrator.models import ComponentSpec, JobSpec, AgentResult


@pytest.fixture
def mock_job_spec():
    return JobSpec(
        slug="test-niche",
        product_type="blog_kit",
        niche="Test Niche",
        notion_only=True,
    )


def test_notion_content_agent_fallback(tmp_path, monkeypatch, mock_job_spec):
    """Test that notion_content_agent falls back to content_agent when Notion unavailable."""
    from agents.notion_content_agent import run

    component = ComponentSpec(
        id="test_content",
        agent="notion_content_agent",
        output="content/test_content.md",
        depends_on=["market_research"],
    )

    # Mock content_agent to return success
    mock_content = mock.Mock(return_value=AgentResult(status="done", output_path="content/test_content.md"))
    monkeypatch.setattr("agents.content_agent.run", mock_content)

    result = run(component, mock_job_spec, {})

    assert result.status == "done"
    mock_content.assert_called_once_with(component, mock_job_spec, {})


def test_notion_content_agent_no_context(tmp_path, monkeypatch, mock_job_spec):
    """Test fallback when notion_tree not in context."""
    from agents.notion_content_agent import run

    component = ComponentSpec(
        id="test_content",
        agent="notion_content_agent",
        output="content/test_content.md",
        depends_on=["market_research"],
    )

    # Set NOTION_API_KEY but no notion_tree in context → fallback
    monkeypatch.setenv("NOTION_API_KEY", "test-key")
    monkeypatch.setenv("NOTION_PARENT_PAGE_ID", "test-page")

    mock_content = mock.Mock(return_value=AgentResult(status="done", output_path="content/test_content.md"))
    monkeypatch.setattr("agents.content_agent.run", mock_content)

    result = run(component, mock_job_spec, {"market_research": "some_path.json"})

    assert result.status == "done"
    mock_content.assert_called_once()
```

- [ ] **Step 2: Write orchestrator notion_only test**

Add to `tests/test_orchestrator.py`:

```python
def test_notion_only_skips_package(tmp_path, monkeypatch):
    """Test that notion_only mode skips package component."""
    schema_path = _make_schema(tmp_path, [
        {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
        {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["market_research"]},
    ])

    mock_market = mock.Mock(return_value=AgentResult(status="done", output_path="data/market_research.json"))
    mock_package = mock.Mock()
    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market)
    monkeypatch.setitem(AGENT_REGISTRY, "packaging_agent", mock_package)

    job_spec_path = _make_job_spec(tmp_path, overrides={"notion_only": True})
    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = __import__("orchestrator.models", fromlist=["ProductSchema"]).ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-slug" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-slug")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    assert orc.state.components["package"].status == "skipped"
    assert orc.state.components["package"].error == "notion_only mode: no ZIP"
    mock_package.assert_not_called()


def test_notion_only_substitutes_content_agent(tmp_path, monkeypatch):
    """Test that notion_only substitutes content_agent with notion_content_agent."""
    schema_path = _make_schema(tmp_path, [
        {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
        {"id": "test_content", "agent": "content_agent", "output": "content/test_content.md", "depends_on": ["market_research"]},
    ])

    mock_market = mock.Mock(return_value=AgentResult(status="done", output_path="data/market_research.json"))
    mock_notion_content = mock.Mock(return_value=AgentResult(status="done"))
    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market)
    monkeypatch.setitem(AGENT_REGISTRY, "content_agent", mock.Mock())  # should NOT be called
    monkeypatch.setitem(AGENT_REGISTRY, "notion_content_agent", mock_notion_content)

    job_spec_path = _make_job_spec(tmp_path, overrides={"notion_only": True})
    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = __import__("orchestrator.models", fromlist=["ProductSchema"]).ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-slug" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-slug")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    assert orc.state.components["test_content"].status == "done"
    mock_notion_content.assert_called_once()
```

Also need to update `_make_job_spec` to accept overrides. In the existing test file, `_make_job_spec` is defined. Let me check what it looks like:

From the existing code, I need to read the test file to see the exact helper signature. Actually, the new tests use `overrides={"notion_only": True}` — but the existing `_make_job_spec` may not support that. Let me add an overrides parameter to it.

In `tests/test_orchestrator.py`, update `_make_job_spec`:

```python
def _make_job_spec(tmp_path, overrides=None):
    """Create a job_spec.json for testing."""
    spec = {
        "slug": "test-slug",
        "product_type": "research_pack",
        "niche": "test niche",
        "display_name": "Test",
        "theme": "default",
        "notion_sync": False,
        "notion_only": False,
        "landing_page_enabled": False,
        "social_promotion_enabled": False,
        "gumroad_enabled": False,
        "call_to_action": "",
        "created_at": "2026-01-01T00:00:00Z",
    }
    if overrides:
        spec.update(overrides)
    path = tmp_path / "outputs" / "test-slug" / "job_spec.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    import json
    with open(path, "w") as f:
        json.dump(spec, f)
    return path
```

- [ ] **Step 3: Run all tests**

Run: `python -m pytest tests/ -v --ignore-glob="*market*" -k "not test_market_agent"`
Expected: 20+ passed (existing 18 + 2 new orchestrator + 2 new notion_content_agent)

- [ ] **Step 4: Commit**

```bash
git add tests/test_notion_content_agent.py tests/test_orchestrator.py
git commit -m "test: add notion_only and notion_content_agent tests"
```

---

### Task 10: Final Verification

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v --ignore-glob="*market*" -k "not test_market_agent"`
Expected: All pass

- [ ] **Step 2: Verify imports**

Run: `python -c "from agents.notion_content_agent import run; from orchestrator.models import JobSpec; s = JobSpec(slug='t', product_type='t', niche='t', notion_only=True); print(f'notion_only={s.notion_only}'); print('All imports OK')"`
Expected: `notion_only=True` + `All imports OK`

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: standalone Notion product mode"
```
