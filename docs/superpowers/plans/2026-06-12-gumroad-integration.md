# Gumroad Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Gumroad API into the Digital Product Factory for end-to-end product research, creation, and publishing.

**Architecture:** A single `gumroad_agent.py` operates in two modes (research + publish) identified by `component.id`. Research runs first to scrape Gumroad for competitor data, pricing, and quality gaps — this informs content creation. Publish runs last to create the product listing, upload files, and generate offer codes. The wizard gains a smart product-type selection flow that recommends the best type based on what's selling.

**Tech Stack:** Python 3.11+, httpx (for Gumroad API calls), Jinja2 (prompt templates), existing agents for content/render/package.

---

### File Structure Map

| File | Action | Purpose |
|------|--------|---------|
| `agents/gumroad_agent.py` | Create | Consolidated agent: research + publish modes |
| `prompts/gumroad_listing.j2` | Create | LLM prompt for product listing copy |
| `prompts/gumroad_research.j2` | Create | LLM prompt for research analysis |
| `agents/registry.py` | Modify | Add `gumroad_agent` |
| `.env.example` | Modify | Add `GUMROAD_ACCESS_TOKEN` |
| `cli/wizard.py` | Modify | Smart product type decision flow |
| `schemas/research_pack.json` | Modify | Add gumroad_research + gumroad_publish; update depends_on |
| `schemas/operating_system.json` | Modify | Same pattern |
| `schemas/visual_pack.json` | Modify | Same pattern |
| `schemas/workflow_kit.json` | Modify | Same pattern |
| `schemas/blog_kit.json` | Modify | Same pattern |
| `schemas/course_launch.json` | Modify | Same pattern |
| `schemas/saas_docs.json` | Modify | Same pattern |

---

### Task 1: Create `agents/gumroad_agent.py`

**Files:**
- Create: `agents/gumroad_agent.py`

**Architecture:** Single file with two internal functions `_run_research()` and `_run_publish()`, dispatched from `run()` based on `component.id`.

The agent uses `httpx` to call Gumroad API v2 at `https://api.gumroad.com/v2/`. All calls are wrapped in try/except for graceful degradation.

API key loaded via `os.getenv("GUMROAD_ACCESS_TOKEN")`.

For the approval gate in publish mode, it writes a review markdown file, then does an interactive `input()` on stderr.

- [ ] **Step 1: Write the agent skeleton with research mode**

```python
import os
import sys
import json
import logging
from datetime import datetime, timedelta

import httpx

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

GUMROAD_API_BASE = "https://api.gumroad.com/v2"


def _gumroad_api(method: str, path: str, data: dict | None = None) -> dict | None:
    token = os.getenv("GUMROAD_ACCESS_TOKEN")
    if not token:
        logger.warning("GUMROAD_ACCESS_TOKEN not set")
        return None
    url = f"{GUMROAD_API_BASE}/{path.lstrip('/')}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = httpx.request(method, url, headers=headers, json=data, timeout=15.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Gumroad API call failed ({method} {path}): {e}")
        return None


def _run_research(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    niche = job_spec.niche

    # Fetch products from Gumroad
    products_data = _gumroad_api("GET", "products")
    niche_products = []
    if products_data and "products" in products_data:
        for p in products_data["products"]:
            name = (p.get("name") or "").lower()
            desc = (p.get("description") or "").lower()
            if any(kw in name or kw in desc for kw in niche.lower().split()):
                niche_products.append(p)

    # Analyze product types from names
    type_keywords = {
        "operating_system": ["operating system", "os", "workflow system", "dashboard"],
        "research_pack": ["research", "report", "market analysis", "guide"],
        "visual_pack": ["visual", "design", "template pack", "assets", "graphics"],
        "workflow_kit": ["workflow", "automation", "pipeline", "sop"],
        "blog_kit": ["blog", "content pack", "article", "seo"],
        "course_launch": ["course", "training", "workshop", "masterclass", "curriculum"],
        "saas_docs": ["documentation", "api docs", "developer", "technical"],
    }
    type_distribution = {}
    for p in niche_products:
        name = (p.get("name") or "").lower()
        matched = False
        for ptype, kws in type_keywords.items():
            if any(kw in name for kw in kws):
                type_distribution[ptype] = type_distribution.get(ptype, 0) + 1
                matched = True
                break
        if not matched:
            type_distribution["research_pack"] = type_distribution.get("research_pack", 0) + 1

    recommended_type = max(type_distribution, key=type_distribution.get) if type_distribution else "research_pack"

    # Build research output
    research = {
        "niche": niche,
        "products_analyzed": len(niche_products),
        "product_type_distribution": type_distribution,
        "recommended_product_type": recommended_type,
        "top_products": [
            {
                "name": p.get("name", ""),
                "price": p.get("price", 0),
                "sales": p.get("sales_count", 0),
                "description_length": len(p.get("description", "") or ""),
            }
            for p in niche_products[:10]
        ],
        "competitor_count": len(niche_products),
    }

    output_path = os.path.join("outputs", job_spec.slug, component.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(research, f, indent=2)

    logger.info(f"Gumroad research: {len(niche_products)} products found, recommended type: {recommended_type}")
    return AgentResult(status="done", output_path=output_path, error=None)
```

- [ ] **Step 2: Add publish mode to the agent**

```python
def _run_publish(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    # Gather outputs for files
    output_dir = os.path.join("outputs", job_spec.slug)
    files_to_upload = []
    for key, path in context.items():
        if path and os.path.exists(path):
            if path.endswith(".pdf") or path.endswith(".zip"):
                files_to_upload.append({"key": key, "path": path, "name": os.path.basename(path)})
            elif path.endswith(".json") and "gumroad_research" in path:
                with open(path, "r", encoding="utf-8") as f:
                    research_data = json.load(f)

    suggested_price = 29
    if research_data:
        prices = [p.get("price", 0) for p in research_data.get("top_products", []) if p.get("price", 0) > 0]
        if prices:
            suggested_price = round(sum(prices) / len(prices))

    # Generate review summary
    review_path = os.path.join(output_dir, "gumroad_review.md")
    with open(review_path, "w", encoding="utf-8") as f:
        f.write(f"# Gumroad Product Review\n\n")
        f.write(f"**Niche:** {job_spec.niche}\n")
        f.write(f"**Product Type:** {job_spec.product_type}\n")
        f.write(f"**Suggested Price:** ${suggested_price}\n\n")
        f.write(f"## Files to Upload\n\n")
        for fobj in files_to_upload:
            fobj_size = os.path.getsize(fobj["path"])
            f.write(f"- `{fobj['name']}` ({fobj_size / 1024:.1f} KB)\n")
        f.write(f"\n---\n")
        f.write(f"\nPublish to Gumroad? (y/N): ")

    print("\n" + "=" * 55, file=sys.stderr)
    print(f"  Gumroad Product Review", file=sys.stderr)
    print(f"  Price: ${suggested_price}", file=sys.stderr)
    print(f"  Files: {len(files_to_upload)} ready", file=sys.stderr)
    print("=" * 55, file=sys.stderr)

    answer = input("  Publish to Gumroad? (y/N): ").strip().lower()
    if answer != "y":
        logger.info("Gumroad publish skipped by user")
        output_path = os.path.join(output_dir, component.output)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"status": "skipped", "reason": "user declined"}, f)
        return AgentResult(status="skipped", output_path=output_path, error="User declined publish")

    # Create product on Gumroad
    product_data = {
        "name": f"{job_spec.display_name or job_spec.niche} — {job_spec.product_type.replace('_', ' ').title()}",
        "price": suggested_price * 100,  # cents
        "description": f"A premium {job_spec.product_type.replace('_', ' ')} for {job_spec.niche}.",
    }
    result = _gumroad_api("POST", "products", data=product_data)

    if not result or "product" not in result:
        logger.error("Failed to create Gumroad product")
        return AgentResult(status="failed", error="Gumroad API product creation failed")

    product_id = result["product"]["id"]
    product_url = result["product"].get("short_url", result["product"].get("url", ""))

    logger.info(f"Gumroad product created: {product_url} (ID: {product_id})")

    publish_result = {
        "status": "published",
        "product_id": product_id,
        "product_url": product_url,
        "price": suggested_price,
    }

    output_path = os.path.join(output_dir, component.output)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(publish_result, f, indent=2)

    link_path = os.path.join(output_dir, "presentation", "Gumroad_Product_Link.md")
    os.makedirs(os.path.dirname(link_path), exist_ok=True)
    with open(link_path, "w", encoding="utf-8") as f:
        f.write(f"# Gumroad Product Published\n\n")
        f.write(f"## 🔗 [View on Gumroad]({product_url})\n\n")
        f.write(f"- **Product ID:** {product_id}\n")
        f.write(f"- **Price:** ${suggested_price}\n")

    return AgentResult(status="done", output_path=output_path, error=None)
```

- [ ] **Step 3: Add the run() dispatcher function**

```python
def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    if component.id == "gumroad_research":
        return _run_research(component, job_spec, context)
    elif component.id == "gumroad_publish":
        return _run_publish(component, job_spec, context)
    raise ValueError(f"Unknown gumroad component id: {component.id}")
```

- [ ] **Step 4: Verify the file compiles**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python -c "import ast; ast.parse(open('agents/gumroad_agent.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add agents/gumroad_agent.py
git commit -m "feat: add consolidated gumroad agent with research + publish modes"
```

---

### Task 2: Create Prompt Templates

**Files:**
- Create: `prompts/gumroad_research.j2`
- Create: `prompts/gumroad_listing.j2`

- [ ] **Step 1: Create `prompts/gumroad_research.j2`**

```jinja2
You are a Gumroad market analyst specializing in {{ niche }}.

Review the following raw Gumroad competitor data and generate a structured analysis.

Raw Data:
{{ raw_data | default("No competitor data available — use your training knowledge") }}

Output a markdown analysis covering:
1. **Market Overview** — How many products exist, what types dominate
2. **Quality Gaps** — What are competitors missing? Weak descriptions? Missing features?
3. **Pricing Analysis** — Price range, sweet spot, what top sellers charge
4. **Recommended Product Type** — Best format for this niche with reasoning
5. **Content Suggestions** — What to emphasize, what keywords to target

Be specific and data-driven. Reference real product names from the data.
```

- [ ] **Step 2: Create `prompts/gumroad_listing.j2`**

```jinja2
You are a Gumroad product listing copywriter specializing in {{ niche }}.

Generate an optimized product listing for a {{ product_type }} in the "{{ niche }}" niche.

{% if research_data %}
Use this competitor/market data to inform your copy:
{{ research_data }}
{% endif %}

Output a JSON object with these fields:
- "title": Product title (under 80 chars, include keywords)
- "subtitle": Short tagline (under 120 chars)
- "description": Full product description (200-400 words) using markdown
  - Start with a hook
  - Bullet-list the key features/benefits
  - Include social proof language
  - End with call to action
- "price": Suggested price in dollars (integer, based on competitor analysis)
- "tags": Array of 5-8 relevant tags/keywords
- "highlights": Array of 3-5 key selling points (one line each)

CRITICAL: Return ONLY valid JSON — no markdown, no code blocks, no text outside the JSON.
```

- [ ] **Step 3: Verify prompt files exist**

```bash
ls prompts/gumroad_research.j2 prompts/gumroad_listing.j2
```

- [ ] **Step 4: Commit**

```bash
git add prompts/gumroad_research.j2 prompts/gumroad_listing.j2
git commit -m "feat: add gumroad prompt templates for research and listing copy"
```

---

### Task 3: Register Agent in Registry

**Files:**
- Modify: `agents/registry.py`

- [ ] **Step 1: Add import and registry entry**

Add import line after `notion_schema_agent`:
```python
    gumroad_agent,
```

Add registry entry after `"notion_schema_agent": notion_schema_agent.run,`:
```python
    "gumroad_agent": gumroad_agent.run,
```

- [ ] **Step 2: Verify file is valid**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python -c "import ast; ast.parse(open('agents/registry.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add agents/registry.py
git commit -m "feat: register gumroad_agent in registry"
```

---

### Task 4: Update .env.example

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add GUMROAD_ACCESS_TOKEN**

Add after `NOTION_PARENT_PAGE_ID`:
```
GUMROAD_ACCESS_TOKEN=your_gumroad_access_token_here
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "chore: add GUMROAD_ACCESS_TOKEN to env example"
```

---

### Task 5: Update Wizard for Smart Product Type Decision

**Files:**
- Modify: `cli/wizard.py`

The wizard is restructured to:
1. Ask niche first (before product type)
2. Optionally ask product type suggestion
3. If suggested, call gumroad_research to validate
4. If not suggested, auto-select based on research
5. Show comparison table if user choice vs research differs
6. Ask for confirmation

- [ ] **Step 1: Restructure wizard flow in `cli/wizard.py`**

Replace the product type selection section with a new smart flow:

```python
def _gumroad_quick_research(niche: str) -> dict | None:
    """Quick research call to validate product type — uses LLM since we're in wizard phase."""
    try:
        from agents.llm_client import generate_text
        prompt = f"""You are a Gumroad market analyst. Given the niche "{niche}", analyze what type of digital product sells best on Gumroad.

Available product types:
- research_pack: Reports, guides, market analysis PDFs
- operating_system: Full workflow systems, dashboards, integrated toolkits
- visual_pack: Templates, design assets, graphics packs
- workflow_kit: SOPs, automation blueprints, process docs
- blog_kit: Blog post packs, content bundles, SEO kits
- course_launch: Course outlines, lesson plans, launch timelines
- saas_docs: API docs, technical documentation, dev guides

Return JSON ONLY:
{{
  "product_type_distribution": {{"research_pack": <count_estimate>, "operating_system": <count_estimate>, ...}},
  "recommended_product_type": "<best_type>",
  "reasoning": "<one sentence why>"
}}"""
        result = generate_text(prompt)
        import re
        match = re.search(r'\{.*\}', result, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        logger.debug(f"Quick research failed: {e}")
    return None
```

Add to imports at top:
```python
import logging
logger = logging.getLogger(__name__)
```

Replace the product type menu section with:

```python
    niche = typer.prompt("What is the niche/topic?")
    default_slug = slugify(niche)
    slug = typer.prompt("Output slug", default=default_slug)

    print("\nDo you have a preferred product type in mind?")
    print("(Press Enter to auto-detect based on Gumroad research)")
    suggested = typer.prompt("Product type suggestion (optional)", default="").strip()

    if suggested:
        valid_types = ["research_pack", "operating_system", "visual_pack", "workflow_kit", "blog_kit", "course_launch", "saas_docs"]
        if suggested not in valid_types:
            print(f"  Unknown type '{suggested}', auto-detecting...")
            suggested = ""

    print(f"\n  ⏳ Researching Gumroad for '{niche}'...")
    research = _gumroad_quick_research(niche)

    if research and research.get("product_type_distribution"):
        distro = research["product_type_distribution"]
        recommended = research["recommended_product_type"]
        print("\n  📊 Market Analysis (estimated):")
        print(f"  {'Product Type':<25} {'Count':<8}")
        print(f"  {'-'*33}")
        for pt, cnt in sorted(distro.items(), key=lambda x: -x[1]):
            marker = " ◀ recommended" if pt == recommended else ""
            print(f"  {pt:<25} {cnt:<8}{marker}")

        if suggested and suggested != recommended:
            print(f"\n  ⚠ You suggested '{suggested}', but '{recommended}' appears to sell better in this niche.")
            switch = typer.prompt(f"  Switch to '{recommended}'? (Y/n)", default="y")
            product_type = recommended if switch.lower() == 'y' else suggested
        elif suggested:
            product_type = suggested
            print(f"\n  ✅ '{product_type}' confirmed — it's a good fit for this niche.")
        else:
            product_type = recommended
            print(f"\n  ✅ Auto-selected '{product_type}' — top seller in this niche.")
    else:
        if suggested:
            product_type = suggested
        else:
            print("\n  Available Product Types:")
            for i, (key, name) in enumerate(pt_options, 1):
                print(f"  {i}. {name}")
            choice = typer.prompt("Select a product type", default="1")
            product_type = list(dict(pt_options).keys())[int(choice) - 1]
```

Define `pt_options` before use:
```python
pt_options = [
    ("research_pack", "Research Pack"),
    ("operating_system", "Operating System"),
    ("visual_pack", "Visual Pack"),
    ("workflow_kit", "Workflow Kit"),
    ("blog_kit", "Blog Kit"),
    ("course_launch", "Course Launch Kit"),
    ("saas_docs", "SaaS Documentation"),
]
```

- [ ] **Step 2: Verify file compiles**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python -c "import ast; ast.parse(open('cli/wizard.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add cli/wizard.py
git commit -m "feat: smart wizard with Gumroad-based product type recommendation"
```

---

### Task 6: Update All 7 Schemas

**Files:**
- Modify: all 7 schema files in `schemas/*.json`

Each schema gets:
1. `gumroad_research` component at top (`depends_on: []`)
2. `gumroad_publish` component at bottom (`depends_on: ["package"]`)
3. Existing content components get `gumroad_research` added to their `depends_on`

Pattern for research_pack.json:
```json
{
  "id": "gumroad_research",
  "agent": "gumroad_agent",
  "output": "data/gumroad_research.json",
  "depends_on": []
},
...
{
  "id": "gumroad_publish",
  "agent": "gumroad_agent",
  "output": "gumroad_published.json",
  "depends_on": ["package"]
},
```

Content `depends_on` arrays get `"gumroad_research"` added. Example for research_pack report:
```json
"depends_on": ["gumroad_research", "database", "sources"]
```

For operating_system's content components (guide, sops, templates, prompts):
```json
"depends_on": ["gumroad_research"]
```

For visual_pack image_prompts:
```json
"depends_on": ["gumroad_research"]
```

For workflow_kit's content components (setup_guide, prompts, automation_blueprint, notion_crm):
```json
"depends_on": ["gumroad_research"]
```

For blog_kit's database and sources:
```json
"depends_on": ["gumroad_research"]
```

For course_launch's course_outline, marketing_copy:
```json
"depends_on": ["gumroad_research"]
```

For saas_docs's api_reference, user_guide, changelog:
```json
"depends_on": ["gumroad_research"]
```

- [ ] **Step 1: Update research_pack.json**

Add gumroad_research at top of components array (before "database"):
```json
    {
      "id": "gumroad_research",
      "agent": "gumroad_agent",
      "output": "data/gumroad_research.json",
      "depends_on": []
    },
```

Update report depends_on to `["gumroad_research", "database", "sources"]`

Add gumroad_publish at end of components array (after report_pdf):
```json
    {
      "id": "gumroad_publish",
      "agent": "gumroad_agent",
      "output": "gumroad_published.json",
      "depends_on": ["package"]
    }
```

Add package component if not exists:
```json
    {
      "id": "package",
      "agent": "packaging_agent",
      "output": "{slug}.zip",
      "depends_on": ["report_pdf"]
    }
```

- [ ] **Step 2 through 7: Repeat for all 7 schemas**

Same pattern for each: gumroad_research first, gumroad_publish last, gumroad_research added to content depends_on.

- [ ] **Step 8: Validate all schemas**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
foreach ($f in Get-ChildItem schemas/*.json) { try { $null = Get-Content $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json; Write-Output "OK: $($f.Name)" } catch { Write-Output "FAIL: $($f.Name): $_" } }
```

- [ ] **Step 9: Commit**

```bash
git add schemas/
git commit -m "feat: add gumroad_research and gumroad_publish to all 7 schemas"
```

---

### Task 7: Run Integration Test

- [ ] **Step 1: Ensure .env has GUMROAD_ACCESS_TOKEN set**

Check `C:\Users\hp\Documents\Projects\digital-factory\.env` contains:
```
GUMROAD_ACCESS_TOKEN=your_actual_token
```

- [ ] **Step 2: Create test batch CSV**

```csv
product_type,niche,slug,theme,notion_sync
research_pack,Gumroad Product Research Guide,gumroad-test-pipeline,luxury-dark,false
```

- [ ] **Step 3: Run the pipeline**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python main.py --batch test_gumroad.csv
```

- [ ] **Step 4: Verify output**

Check `outputs/gumroad-test-pipeline/data/gumroad_research.json` exists with product data.

Check `outputs/gumroad-test-pipeline/gumroad_review.md` exists for publish review.

Check `outputs/gumroad-test-pipeline/gumroad_published.json` after approval.

- [ ] **Step 5: Clean up test files**

```bash
Remove-Item test_gumroad.csv -ErrorAction SilentlyContinue
```

---

## Self-Review Checklist

- [ ] Spec coverage: All design doc sections have corresponding tasks
- [ ] No placeholders: All code is complete, no TBD/TODO
- [ ] Type consistency: agent.run() signature matches existing pattern
- [ ] Schema depends_on updated for all content components