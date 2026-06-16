# Dynamic Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all 7 product types generate their component pipelines dynamically from market research instead of hardcoded schema lists.

**Architecture:** Schema files stripped to core components only. market_agent generates a `pipeline_plan` in `market_research.json`. Orchestrator merges core + dynamic components after market_agent runs, then validates and executes.

**Tech Stack:** Python 3.11+, Jinja2, Pydantic v2

---

### Task 1: Update market_research.j2 Prompt

**Files:**
- Modify: `prompts/market_research.j2`
- Modify: `agents/market_agent.py`

- [ ] **Step 1: Add `notion_sync` to template render call in market_agent.py**

In `agents/market_agent.py` line 22, add `notion_sync` parameter:

```python
prompt = template.render(
    niche=niche,
    product_type=product_type,
    seller_products=[],
    notion_sync=job_spec.notion_sync,
    real_data=real_data,
)
```

- [ ] **Step 2: Add pipeline_plan section to prompt**

In `prompts/market_research.j2`, before the "Rules:" line, add:

```jinja2
{% if notion_sync %}Note: This product includes Notion workspace sync (CRM, dashboards, trackers).{% endif %}

- "pipeline_plan": object with a "components" array. Design a custom pipeline for this specific niche. Each component:
  - "id": unique, descriptive (e.g., lead_tracker, email_templates, churn_analysis)
  - "agent": from catalog below
  - "output": "data/<id>.csv" for csv_export, "content/<id>.md" for content, "content/<id>.mmd" for diagram
  - "depends_on": ["market_research"] or ["<other_dynamic_component_id>"]

AVAILABLE AGENTS CATALOG — use only these:
- research_agent: Database + source compilation. Output .json or .md.
- content_agent: Markdown content generation. Prompt loaded by component.id + ".j2". Output .md
- render_agent: HTML → PDF rendering. Add "template": "shared/basic_doc.html.j2". Output .pdf
- csv_export_agent: JSON → CSV. Output .csv
- diagram_agent: Mermaid architecture diagrams. Output .mmd
- catalog_agent: Product catalog. Output .json
- stitch_agent: Stitch AI design screens. Output varies

RULES for pipeline_plan:
1. Generate DIFFERENT components per niche — real estate needs CRM + lead_tracker, SaaS needs churn_analysis + onboarding, coaching needs student_tracker + session_scheduler.
2. Do NOT use these reserved IDs: images, package, notion_schema, notion_tree, gumroad_research, gumroad_publish, landing_page, social_promotion.
3. Every component must depend on "market_research" or another component in this same plan.
4. For render_agent: always include "template": "shared/basic_doc.html.j2".
5. Generate 2-6 components based on niche complexity.
```

- [ ] **Step 3: Commit**

```bash
git add prompts/market_research.j2 agents/market_agent.py
git commit -m "feat: add pipeline_plan to market research prompt + notion_sync context"
```

---

### Task 2: Add PipelinePlan Model

**Files:**
- Modify: `orchestrator/models.py`

- [ ] **Step 1: Add PipelineComponent and PipelinePlan models**

After `AgentResult` class (line 39), add:

```python
class PipelineComponent(BaseModel):
    id: str
    agent: str
    output: str
    depends_on: List[str] = Field(default_factory=list)
    template: Optional[str] = None
    format: Literal["full", "guide", "notion"] = "full"

class PipelinePlan(BaseModel):
    components: List[PipelineComponent]
```

- [ ] **Step 2: Commit**

```bash
git add orchestrator/models.py
git commit -m "feat: add PipelinePlan models for dynamic pipeline"
```

---

### Task 3: Update Orchestrator — Pipeline Merge

**Files:**
- Modify: `orchestrator/orchestrator.py`

- [ ] **Step 1: Add import for PipelinePlan**

Change line 6 from:
```python
from .models import JobSpec, ProductSchema, ComponentSpec, AgentResult
```
to:
```python
from .models import JobSpec, ProductSchema, ComponentSpec, AgentResult, PipelinePlan
```

- [ ] **Step 2: Add _merge_pipeline_plan method to Orchestrator**

After `_get_execution_order()` method (after line 50), add:

```python
def _merge_pipeline_plan(self, research_path: str) -> None:
    """Load market_research.json, extract pipeline_plan, validate, merge into schema."""
    if not os.path.exists(research_path):
        logger.warning("No market_research.json found — running with core components only")
        return

    with open(research_path, "r") as f:
        research = json.load(f)

    raw_plan = research.get("pipeline_plan")
    if not raw_plan or "components" not in raw_plan:
        logger.info("No pipeline_plan in market research — running with core components only")
        return

    plan = PipelinePlan(**raw_plan)

    RESERVED_IDS = {
        "market_research", "images", "package",
        "notion_schema", "notion_tree",
        "gumroad_research", "gumroad_publish",
        "landing_page", "social_promotion",
    }

    existing_ids = {c.id for c in self.schema.components}
    allowed_agents = set(AGENT_REGISTRY.keys())

    added = 0
    for comp in plan.components:
        if comp.id in RESERVED_IDS:
            logger.warning(f"Pipeline plan uses reserved ID '{comp.id}' — skipping")
            continue
        if comp.id in existing_ids:
            logger.warning(f"Pipeline plan component '{comp.id}' already exists — skipping")
            continue
        if comp.agent not in allowed_agents:
            logger.warning(f"Pipeline plan uses unknown agent '{comp.agent}' — skipping")
            continue

        all_valid_ids = existing_ids | {c.id for c in plan.components}
        deps_ok = all(dep in all_valid_ids for dep in comp.depends_on)
        if not deps_ok:
            logger.warning(f"Pipeline plan component '{comp.id}' has invalid dependencies — skipping")
            continue

        spec = ComponentSpec(
            id=comp.id,
            agent=comp.agent,
            output=comp.output,
            depends_on=comp.depends_on,
            template=comp.template,
            format=comp.format,
        )
        self.schema.components.append(spec)
        existing_ids.add(comp.id)
        added += 1
        logger.info(f"Added dynamic component: {comp.id} ({comp.agent})")

    logger.info(f"Pipeline plan merged: {added} dynamic components added")
```

- [ ] **Step 3: Integrate merge into run() loop**

In `run()`, after line 139 (`save_job_state(self.state, self.state_path)`), add:

```python
# After market_agent completes, merge pipeline_plan
if component.id == "market_research" and result.status == "done":
    self._merge_pipeline_plan(result.output_path)
    ordered_components = self._get_execution_order()
    total = len(ordered_components)
    logger.info("Pipeline re-planned: %s total components", total)
```

- [ ] **Step 4: Commit**

```bash
git add orchestrator/orchestrator.py
git commit -m "feat: add pipeline_plan merge to orchestrator"
```

---

### Task 4: Strip Schema Files to Core Components

**Files:**
- Modify: `schemas/operating_system.json`
- Modify: `schemas/workflow_kit.json`
- Modify: `schemas/course_launch.json`
- Modify: `schemas/blog_kit.json`
- Modify: `schemas/saas_docs.json`
- Modify: `schemas/research_pack.json`
- Modify: `schemas/visual_pack.json`

For each schema, keep only:
- market_research
- images (depends on market_research)
- notion_schema (only if notion_sync: true, depends on market_research)
- notion_tree (only if notion_sync: true, depends on notion_schema)
- gumroad_research (depends on market_research)
- gumroad_publish (depends on gumroad_research + market_research)
- landing_page (depends on gumroad_publish)
- social_promotion (depends on landing_page)
- package (depends on all)

Package depends on notion_tree only (if notion_sync) or market_research only (if not). gumroad/landing/social gates are handled by orchestrator's existing wizard gates.

Gumroad components depend on market_research (not specific PDFs) because the dynamic components that PDFs come from may not exist yet.

- [ ] **Step 1: operating_system.json**

```json
{
  "product_type": "operating_system",
  "display_name": "Operating System",
  "notion_sync": true,
  "components": [
    {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
    {"id": "images", "agent": "image_agent", "output": "data/images_generated.json", "depends_on": ["market_research"]},
    {"id": "notion_schema", "agent": "notion_schema_agent", "output": "data/notion_schema.json", "depends_on": ["market_research"]},
    {"id": "notion_tree", "agent": "notion_agent", "output": "notion_sync.json", "depends_on": ["notion_schema"]},
    {"id": "gumroad_research", "agent": "gumroad_agent", "output": "gumroad/research.json", "depends_on": ["market_research"]},
    {"id": "gumroad_publish", "agent": "gumroad_agent", "output": "gumroad/published.json", "depends_on": ["gumroad_research", "market_research"]},
    {"id": "landing_page", "agent": "landing_agent", "output": "landing/deployed.json", "depends_on": ["gumroad_publish"]},
    {"id": "social_promotion", "agent": "social_agent", "output": "landing/social_results.json", "depends_on": ["landing_page"]},
    {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["notion_tree"]}
  ],
  "notion_structure": {
    "type": "functional_workspace",
    "description": "Business management OS — Client CRM, Revenue Dashboard, Project Tracker, Content Calendar, SOP Manager"
  }
}
```

Fixes needed: gumroad's old dependency was on specific PDFs. Changed to `market_research`. Package depends on notion_tree only (which transitively depends on everything via its chain). The wizard gates handle the skipping.

Wait — this creates a problem. If gumroad/landing/social are disabled by wizard, and package depends on notion_tree which depends on notion_schema which depends on market_research — that chain works. But the dynamic components also need to be dependencies of package. Currently package only depends on notion_tree. But we need to add dynamic component outputs to the ZIP.

Actually the packaging agent scans `outputs/{slug}/` for files matching deliverable prefixes and extensions. It doesn't depend on specific component outputs — it just ZIPs everything. So as long as dynamic components write to `content/` or `data/` directories, they'll be included automatically.

But there's a sequencing problem: package needs to run AFTER all dynamic components finish. Currently package depends on notion_tree. notion_tree runs after notion_schema → market_research. But dynamic components also run after market_research. Since package runs after notion_tree which runs after notion_schema → market_research, and dynamic components also start after market_research, package could run BEFORE some dynamic components finish.

We need package to depend on all components, including dynamic ones. But in the static schema, we can't list dynamic components. So how to handle this?

Option 1: package dependency becomes `["market_research"]` and we make packaging agent smarter to wait for all job_state components to finish.

Option 2: Add a dependency on `images` which is always present and runs at the end... no, images depends on market_research and runs early.

Option 3: Dynamic components are added to the schema after market_agent runs. After merging, we should also update package's dependencies. But package is in the schema before merge.

This is actually a problem. Let me think...

The execution order is computed after merge. So if I update the execution order after merge, and the execution loop processes them in order, the loop continues from where it was. After market_research finishes:
1. Merge pipeline_plan into schema
2. Recompute execution order (now includes dynamic components + remaining core ones)
3. Continue loop — next component in new order

Since market_research is the first component, after it finishes:
- Loop iteration for market_research ends
- Next iteration picks the next component from the new ordered_components list

If package is in the new order AFTER all dynamic components (because package depends on them via transitive deps), then package runs last as needed.

But in the stripped schemas, package depends on `notion_tree` or `market_research`. It doesn't depend on dynamic components. So it could run before them.

To fix: make package depend on `images` + `notion_tree` + `market_research`. Actually that still doesn't help because dynamic components also depend on market_research.

The real solution: after merging, rebuild package's depends_on to include all dynamic component IDs. That way topo-sort puts package after everything.

Let me add this to the _merge_pipeline_plan method. After adding all dynamic components, find the package component and update its depends_on to include all dynamic component IDs.

Actually, the simplest approach: make package depend on nothing and put it at the end. The packaging agent scans the filesystem, so it just needs to run last. I can set package.depends_on to all non-wizard-gated component IDs after merge.

Let me just add this logic to _merge_pipeline_plan.

No wait, simpler: after merging, find `package` component, set its `depends_on` to all components. That way topo-sort puts it last.

```python
# After merge, ensure package runs last
for c in self.schema.components:
    if c.id == "package":
        c.depends_on = [comp.id for comp in self.schema.components if comp.id != "package"]
        break
```

This is clean. Let me include it in the plan.

Actually, let me reconsider. The gumroad/landing/social components are wizard-gated (might be skipped). Package should NOT depend on those. So:

```python
for c in self.schema.components:
    if c.id == "package":
        c.depends_on = [
            comp.id for comp in self.schema.components 
            if comp.id != "package" 
            and comp.id not in ("gumroad_research", "gumroad_publish", "landing_page", "social_promotion")
        ]
        break
```

This way package depends on everything non-wizard-gated, guaranteeing it runs last. Good.

Let me update the plan with this.

- [ ] **Step 1-7: Update all schema files**

OK let me just write the plan file now with all the corrections.<｜end▁of▁thinking｜>Plan likhne se pehle ek design flaw fix karna hoga. Package ko sab dynamic components ke baad run hona chahiye. Spec mein yeh miss ho gaya. Fix include karunga plan mein.

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="write">
<｜｜DSML｜｜parameter name="content" string="true"># Dynamic Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all 7 product types generate their component pipelines dynamically from market research instead of hardcoded schema lists.

**Architecture:** Schema files stripped to core components. market_agent generates `pipeline_plan` in `market_research.json`. Orchestrator merges core + dynamic components after market_agent runs, then updates package deps, topo-sorts, and executes.

**Tech Stack:** Python 3.11+, Jinja2, Pydantic v2

---

### Task 1: Update market_agent.py — Pass notion_sync

**Files:**
- Modify: `agents/market_agent.py`

- [ ] **Step 1: Add notion_sync to template render**

In `agents/market_agent.py` line 18, change:

```python
prompt = template.render(
    niche=niche,
    product_type=product_type,
    seller_products=[],
    real_data=real_data,
)
```

to:

```python
prompt = template.render(
    niche=niche,
    product_type=product_type,
    seller_products=[],
    notion_sync=job_spec.notion_sync,
    real_data=real_data,
)
```

- [ ] **Step 2: Commit**

```bash
git add agents/market_agent.py
git commit -m "feat: pass notion_sync to market research prompt"
```

---

### Task 2: Update market_research.j2 Prompt

**Files:**
- Modify: `prompts/market_research.j2`

- [ ] **Step 1: Add notion_sync note after line 20**

After `{% endif %}` at line 20, add:

```jinja2
{% if notion_sync %}Note: This product includes a Notion workspace (CRM, dashboards, trackers).{% endif %}
```

- [ ] **Step 2: Add pipeline_plan section before "Rules:"**

Before line 73 `Rules:`, add:

```jinja2
- "pipeline_plan": object with a "components" array. Design a custom pipeline for THIS specific niche. Each component:
  - "id" (string, unique, descriptive — e.g., lead_tracker, email_templates, churn_analysis)
  - "agent" (string, from catalog below)
  - "output" (string, use convention: "data/<id>.csv" for csv_export, "content/<id>.md" for content, "content/<id>.mmd" for diagram)
  - "depends_on" (array, ["market_research"] or ["<other_component_id>"])

AVAILABLE AGENTS CATALOG — use only these:
- research_agent: Database + source compilation. Output .json or .md.
- content_agent: Markdown content. Prompt loaded by component.id + ".j2". Output .md
- render_agent: HTML → PDF. Requires "template": "shared/basic_doc.html.j2". Output .pdf
- csv_export_agent: JSON → CSV. Output .csv
- diagram_agent: Mermaid diagrams. Output .mmd
- catalog_agent: Product catalog. Output .json
- stitch_agent: Stitch AI design screens. Output varies

RULES for pipeline_plan:
1. Generate DIFFERENT components per niche — real estate needs CRM + lead_tracker, SaaS needs churn_analysis + onboarding, coaching needs student_tracker + session_scheduler.
2. Do NOT use reserved IDs: images, package, notion_schema, notion_tree, gumroad_research, gumroad_publish, landing_page, social_promotion.
3. Every component must depend on "market_research" or another component in this same plan.
4. Generate 2-6 components based on niche complexity. Simple niche = fewer.
5. Output paths must not overlap — each must be unique.
```
```

- [ ] **Step 3: Commit**

```bash
git add prompts/market_research.j2
git commit -m "feat: add pipeline_plan instructions + notion_sync to market research prompt"
```

---

### Task 3: Add PipelinePlan Model

**Files:**
- Modify: `orchestrator/models.py`

- [ ] **Step 1: Add PipelineComponent and PipelinePlan models**

After `AgentResult` class (line 39), add:

```python
class PipelineComponent(BaseModel):
    id: str
    agent: str
    output: str
    depends_on: List[str] = Field(default_factory=list)
    template: Optional[str] = None
    format: Literal["full", "guide", "notion"] = "full"

class PipelinePlan(BaseModel):
    components: List[PipelineComponent]
```

- [ ] **Step 2: Commit**

```bash
git add orchestrator/models.py
git commit -m "feat: add PipelinePlan model"
```

---

### Task 4: Update Orchestrator Logic

**Files:**
- Modify: `orchestrator/orchestrator.py`

- [ ] **Step 1: Add PipelinePlan import**

Change line 6:
```python
from .models import JobSpec, ProductSchema, ComponentSpec, AgentResult
```
to:
```python
from .models import JobSpec, ProductSchema, ComponentSpec, AgentResult, PipelinePlan
```

- [ ] **Step 2: Add _merge_pipeline_plan method**

After `_get_execution_order()` method (after line 50), add:

```python
def _merge_pipeline_plan(self, research_path: str) -> None:
    """Load market_research.json, extract pipeline_plan, merge into schema."""
    if not os.path.exists(research_path):
        logger.warning("No market_research.json found — core components only")
        return

    with open(research_path, "r") as f:
        research = json.load(f)

    raw_plan = research.get("pipeline_plan")
    if not raw_plan or "components" not in raw_plan:
        logger.info("No pipeline_plan in research — core components only")
        return

    plan = PipelinePlan(**raw_plan)

    RESERVED_IDS = {
        "market_research", "images", "package",
        "notion_schema", "notion_tree",
        "gumroad_research", "gumroad_publish",
        "landing_page", "social_promotion",
    }

    existing_ids = {c.id for c in self.schema.components}
    allowed_agents = set(AGENT_REGISTRY.keys())

    added = 0
    for comp in plan.components:
        if comp.id in RESERVED_IDS:
            logger.warning(f"Skipping reserved ID '{comp.id}'")
            continue
        if comp.id in existing_ids:
            logger.warning(f"Skipping duplicate '{comp.id}'")
            continue
        if comp.agent not in allowed_agents:
            logger.warning(f"Skipping unknown agent '{comp.agent}' for '{comp.id}'")
            continue

        all_valid_ids = existing_ids | {c.id for c in plan.components}
        if not all(dep in all_valid_ids for dep in comp.depends_on):
            logger.warning(f"Skipping '{comp.id}' — invalid dependencies")
            continue

        spec = ComponentSpec(
            id=comp.id,
            agent=comp.agent,
            output=comp.output,
            depends_on=comp.depends_on,
            template=comp.template,
            format=comp.format,
        )
        self.schema.components.append(spec)
        existing_ids.add(comp.id)
        added += 1
        logger.info(f"Added dynamic component: {comp.id} ({comp.agent})")

    # Ensure package runs last — depends on all non-wizard-gated components
    for c in self.schema.components:
        if c.id == "package":
            c.depends_on = [
                comp.id for comp in self.schema.components
                if comp.id != "package"
                and comp.id not in ("gumroad_research", "gumroad_publish", "landing_page", "social_promotion")
            ]
            break

    logger.info(f"Pipeline plan merged: {added} dynamic components")
```

- [ ] **Step 3: Integrate merge into run() loop**

In `run()` method, after line 139 (`save_job_state(self.state, self.state_path);`), add:

```python
            # After market_agent completes, merge pipeline_plan
            if component.id == "market_research" and result.status == "done":
                self._merge_pipeline_plan(result.output_path)
                ordered_components = self._get_execution_order()
                total = len(ordered_components)
                logger.info("Pipeline re-planned: %s total components", total)
```

- [ ] **Step 4: Commit**

```bash
git add orchestrator/orchestrator.py
git commit -m "feat: add pipeline_plan merge to orchestrator"
```

---

### Task 5: Strip Schema Files to Core Components

**Files:**
- Modify: `schemas/operating_system.json`
- Modify: `schemas/workflow_kit.json`
- Modify: `schemas/course_launch.json`
- Modify: `schemas/blog_kit.json`
- Modify: `schemas/saas_docs.json`
- Modify: `schemas/research_pack.json`
- Modify: `schemas/visual_pack.json`

Core components per product type:

**notion_sync: true** (operating_system, workflow_kit, course_launch):
```json
{
  "components": [
    {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
    {"id": "images", "agent": "image_agent", "output": "data/images_generated.json", "depends_on": ["market_research"]},
    {"id": "notion_schema", "agent": "notion_schema_agent", "output": "data/notion_schema.json", "depends_on": ["market_research"]},
    {"id": "notion_tree", "agent": "notion_agent", "output": "notion_sync.json", "depends_on": ["notion_schema"]},
    {"id": "gumroad_research", "agent": "gumroad_agent", "output": "gumroad/research.json", "depends_on": ["market_research"]},
    {"id": "gumroad_publish", "agent": "gumroad_agent", "output": "gumroad/published.json", "depends_on": ["gumroad_research", "market_research"]},
    {"id": "landing_page", "agent": "landing_agent", "output": "landing/deployed.json", "depends_on": ["gumroad_publish"]},
    {"id": "social_promotion", "agent": "social_agent", "output": "landing/social_results.json", "depends_on": ["landing_page"]},
    {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["market_research"]}
  ]
}
```

**notion_sync: false** (blog_kit, saas_docs, research_pack, visual_pack):
```json
{
  "components": [
    {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
    {"id": "images", "agent": "image_agent", "output": "data/images_generated.json", "depends_on": ["market_research"]},
    {"id": "gumroad_research", "agent": "gumroad_agent", "output": "gumroad/research.json", "depends_on": ["market_research"]},
    {"id": "gumroad_publish", "agent": "gumroad_agent", "output": "gumroad/published.json", "depends_on": ["gumroad_research", "market_research"]},
    {"id": "landing_page", "agent": "landing_agent", "output": "landing/deployed.json", "depends_on": ["gumroad_publish"]},
    {"id": "social_promotion", "agent": "social_agent", "output": "landing/social_results.json", "depends_on": ["landing_page"]},
    {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["market_research"]}
  ]
}
```

Note: image_agent for non-notion-sync products: images depend on market_research. The image_agent is included in all as a core component because it provides images for PDF rendering and landing pages.

- [ ] **Step 1: operating_system.json** — Replace components array with 9 core components + keep notion_structure

- [ ] **Step 2: workflow_kit.json** — Same as Step 1

- [ ] **Step 3: course_launch.json** — Same as Step 1

- [ ] **Step 4: blog_kit.json** — Replace with 7 core components (no notion)

- [ ] **Step 5: saas_docs.json** — Same as Step 4

- [ ] **Step 6: research_pack.json** — Same as Step 4

- [ ] **Step 7: visual_pack.json** — Same as Step 4

- [ ] **Step 8: Verify all JSON is valid**

Run: `python -c "import json; [json.load(open(f'schemas/{f}')) for f in ['operating_system.json','workflow_kit.json','course_launch.json','blog_kit.json','saas_docs.json','research_pack.json','visual_pack.json']]; print('All valid')"`
Expected: `All valid`

- [ ] **Step 9: Commit**

```bash
git add schemas/
git commit -m "refactor: strip schemas to core components, rest is dynamic"
```

---

### Task 6: Update Tests

**Files:**
- Modify: `tests/test_orchestrator.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Add pipeline_plan merge test to test_orchestrator.py**

Add this test to `tests/test_orchestrator.py`:

```python
def test_pipeline_plan_merge(tmp_path, monkeypatch):
    """Test that orchestrator merges pipeline_plan from market_research.json."""
    schema_path = _make_schema(tmp_path, [
        {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
        {"id": "images", "agent": "image_agent", "output": "data/images_generated.json", "depends_on": ["market_research"]},
        {"id": "package", "agent": "packaging_agent", "output": "{slug}.zip", "depends_on": ["market_research"]},
    ])

    # Mock market_agent to return a result that writes market_research.json with pipeline_plan
    def mock_market_agent(component, job_spec, context):
        output_dir = os.path.join("outputs", job_spec.slug)
        os.makedirs(output_dir, exist_ok=True)
        research = {
            "niche": "test niche",
            "pipeline_plan": {
                "components": [
                    {"id": "lead_tracker", "agent": "csv_export_agent", "output": "data/lead_tracker.csv", "depends_on": ["market_research"]},
                    {"id": "email_templates", "agent": "content_agent", "output": "content/email_templates.md", "depends_on": ["market_research"]},
                ]
            }
        }
        research_path = os.path.join(output_dir, "data", "market_research.json")
        os.makedirs(os.path.dirname(research_path), exist_ok=True)
        with open(research_path, "w") as f:
            json.dump(research, f)
        return AgentResult(status="done", output_path=research_path)

    mock_image = mock.Mock(return_value=AgentResult(status="done"))
    mock_csv = mock.Mock(return_value=AgentResult(status="done"))
    mock_content = mock.Mock(return_value=AgentResult(status="done"))
    mock_packaging = mock.Mock(return_value=AgentResult(status="done"))

    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market_agent)
    monkeypatch.setitem(AGENT_REGISTRY, "image_agent", mock_image)
    monkeypatch.setitem(AGENT_REGISTRY, "csv_export_agent", mock_csv)
    monkeypatch.setitem(AGENT_REGISTRY, "content_agent", mock_content)
    monkeypatch.setitem(AGENT_REGISTRY, "packaging_agent", mock_packaging)

    job_spec_path = _make_job_spec(tmp_path)

    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = __import__("orchestrator.models", fromlist=["ProductSchema"]).ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-slug" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-slug")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    assert orc.state.components["market_research"].status == "done"
    assert orc.state.components["images"].status == "done"
    assert orc.state.components["lead_tracker"].status == "done"
    assert orc.state.components["email_templates"].status == "done"
    assert orc.state.components["package"].status == "done"
    mock_csv.assert_called_once()
    mock_content.assert_called_once()
```

- [ ] **Step 2: Add test for pipeline_plan validation (invalid dependencies)**

```python
def test_pipeline_plan_invalid_deps_skipped(tmp_path, monkeypatch):
    """Test that components with invalid deps in pipeline_plan are skipped."""
    schema_path = _make_schema(tmp_path, [
        {"id": "market_research", "agent": "market_agent", "output": "data/market_research.json", "depends_on": []},
    ])

    def mock_market_agent(component, job_spec, context):
        output_dir = os.path.join("outputs", job_spec.slug)
        os.makedirs(output_dir, exist_ok=True)
        research = {
            "niche": "test",
            "pipeline_plan": {
                "components": [
                    {"id": "bad_comp", "agent": "csv_export_agent", "output": "data/bad.csv", "depends_on": ["nonexistent_dep"]},
                ]
            }
        }
        research_path = os.path.join(output_dir, "data", "market_research.json")
        os.makedirs(os.path.dirname(research_path), exist_ok=True)
        with open(research_path, "w") as f:
            json.dump(research, f)
        return AgentResult(status="done", output_path=research_path)

    monkeypatch.setitem(AGENT_REGISTRY, "market_agent", mock_market_agent)
    monkeypatch.setitem(AGENT_REGISTRY, "csv_export_agent", mock.Mock())

    job_spec_path = _make_job_spec(tmp_path)
    orc = Orchestrator(str(job_spec_path))
    with open(schema_path) as f:
        orc.schema = __import__("orchestrator.models", fromlist=["ProductSchema"]).ProductSchema(**json.load(f))
    orc.state_path = str(tmp_path / "outputs" / "test-slug" / "job_state.json")
    orc.state = load_job_state(orc.state_path, "test-slug")
    monkeypatch.setattr(orc, "_generate_run_summary", lambda: None)

    orc.run()

    # bad_comp should not be in state at all (never added to schema)
    assert "bad_comp" not in orc.state.components
```

- [ ] **Step 3: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: 19 passed (2 new + 17 existing)

- [ ] **Step 4: Commit**

```bash
git add tests/test_orchestrator.py
git commit -m "test: add pipeline_plan merge tests"
```

---

### Task 7: Full Verification

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 2: Verify JSON schemas**

Run: `python -c "import json; [json.load(open(f'schemas/{f}')) for f in __import__('os').listdir('schemas') if f.endswith('.json')]; print('all valid')"`
Expected: `all valid`

- [ ] **Step 3: Verify imports**

Run: `python -c "from orchestrator.models import PipelinePlan, PipelineComponent; print('imports OK')"`
Expected: `imports OK`

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: dynamic pipeline from market research"
```
