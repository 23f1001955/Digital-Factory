# Market Research Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a market research agent that runs before content creation, using Gumroad API + LLM to produce competitive intelligence that informs all downstream agents.

**Architecture:** New `market_agent.py` sits at the top of every schema (`depends_on: []`). All content components get `"market_research"` added to their `depends_on`. The agent fetches the seller's Gumroad products, then uses the LLM to produce a structured analysis (competitors, pricing, gaps, keywords). Graceful degradation: no Gumroad token → LLM-only research.

**Tech Stack:** Python 3.11+, httpx (Gumroad API), LLM via `agents/llm_client.py`

---

### File Structure Map

| File | Action | Purpose |
|------|--------|---------|
| `agents/market_agent.py` | Create | Market research agent |
| `prompts/market_research.j2` | Create | LLM prompt for market analysis |
| `agents/registry.py` | Modify | Add `market_agent` entry |
| `schemas/research_pack.json` | Modify | Add market_research component + update content depends_on |
| `schemas/operating_system.json` | Modify | Same |
| `schemas/visual_pack.json` | Modify | Same |
| `schemas/workflow_kit.json` | Modify | Same |
| `schemas/blog_kit.json` | Modify | Same |
| `schemas/course_launch.json` | Modify | Same |
| `schemas/saas_docs.json` | Modify | Same |

---

### Task 1: Create `prompts/market_research.j2`

**Files:**
- Create: `prompts/market_research.j2`

- [ ] **Step 1: Write the prompt template**

```jinja2
You are a digital product market analyst. Analyze the niche "{{ niche }}" for a {{ product_type }} product.

{% if seller_products %}
Your current Gumroad catalog in this space:
{% for p in seller_products %}
- {{ p.name }} (${{ p.price }}, {{ p.sales }} sales)
{% endfor %}
{% endif %}

Generate a comprehensive market analysis in JSON format with these keys:
- "competitor_landscape": object with "direct_competitors" (array of {name, price, strengths:[], weaknesses:[]}), "pricing_tiers" ({budget, mid, premium} as strings), "recommended_price" (integer), "quality_gaps" (array of 3-5 strings), "trending_keywords" (array of 5-10 strings)
- "content_recommendations": object with "tone" (string), "key_themes" (array of strings), "seo_keywords" (array of strings)

Base your analysis on:
1. What sells well on Gumroad for this niche
2. Common quality gaps in competitor products
3. Pricing psychology for digital products ($5-15 budget, $15-35 mid, $35+ premium)
4. SEO and discoverability keywords

Return ONLY valid JSON. No markdown, no code blocks, no text outside the JSON.
```

- [ ] **Step 2: Commit**

```bash
git add prompts/market_research.j2
git commit -m "feat: add market research prompt template"
```

---

### Task 2: Create `agents/market_agent.py`

**Files:**
- Create: `agents/market_agent.py`

- [ ] **Step 1: Write the agent**

```python
import os
import json
import logging
from typing import Optional

import httpx

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

GUMROAD_API_BASE = "https://api.gumroad.com/v2"


def _fetch_seller_products() -> list:
    """Fetch the authenticated seller's products from Gumroad API."""
    token = os.getenv("GUMROAD_ACCESS_TOKEN")
    if not token:
        logger.warning("GUMROAD_ACCESS_TOKEN not set — skipping API fetch")
        return []
    try:
        url = f"{GUMROAD_API_BASE}/products"
        headers = {"Authorization": f"Bearer {token}"}
        resp = httpx.get(url, headers=headers, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        products = data.get("products", [])
        logger.info(f"Fetched {len(products)} seller products from Gumroad")
        return [
            {
                "name": p.get("name", ""),
                "price": p.get("price", 0),
                "sales": p.get("sales_count", 0),
                "url": p.get("short_url", ""),
            }
            for p in products
        ]
    except Exception as e:
        logger.warning(f"Gumroad API fetch failed: {e}")
        return []


def _generate_research(niche: str, product_type: str, seller_products: list) -> dict:
    """Generate market research using LLM."""
    from agents.llm_client import generate_text as llm_call
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader("prompts"))
    template = env.get_template("market_research.j2")
    prompt = template.render(
        niche=niche,
        product_type=product_type,
        seller_products=seller_products,
    )

    try:
        result = llm_call(prompt)
        import re
        match = re.search(r'\{.*\}', result, re.DOTALL)
        if match:
            research = json.loads(match.group())
            logger.info(f"Market research generated: {len(research.get('competitor_landscape', {}).get('direct_competitors', []))} competitors found")
            return research
    except Exception as e:
        logger.warning(f"LLM market research failed: {e}")

    return _fallback_research(niche, product_type)


def _fallback_research(niche: str, product_type: str) -> dict:
    """Minimal fallback when LLM is unavailable."""
    return {
        "niche": niche,
        "product_type": product_type,
        "competitor_landscape": {
            "direct_competitors": [],
            "pricing_tiers": {"budget": "$5-15", "mid": "$15-35", "premium": "$35-100"},
            "recommended_price": 29,
            "quality_gaps": ["Research this niche for specific gaps"],
            "trending_keywords": [niche.lower().replace(" ", "_")],
        },
        "content_recommendations": {
            "tone": "professional",
            "key_themes": ["quality", "expertise", "results"],
            "seo_keywords": [niche.lower()],
        },
    }


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        niche = job_spec.niche
        product_type = job_spec.product_type

        seller_products = _fetch_seller_products()
        research = _generate_research(niche, product_type, seller_products)

        research["niche"] = niche
        research["product_type"] = product_type
        research["seller_products"] = seller_products

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(research, f, indent=2)

        logger.info(f"Market research written to {output_path}")
        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Market agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
```

- [ ] **Step 2: Verify it compiles**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python -c "import ast; ast.parse(open('agents/market_agent.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add agents/market_agent.py
git commit -m "feat: add market_agent for pre-content competitive intelligence"
```

---

### Task 3: Update `agents/registry.py`

**Files:**
- Modify: `agents/registry.py`

- [ ] **Step 1: Add import and registry entry**

Current imports:
```python
from . import (
    research_agent,
    csv_export_agent,
    content_agent,
    render_agent,
    packaging_agent,
    notion_agent,
    catalog_agent,
    visual_agent,
    diagram_agent,
    notion_schema_agent,
    gumroad_agent,
    landing_agent,
    social_agent,
)
```

Add `market_agent,` after `social_agent,`:

```python
from . import (
    research_agent,
    csv_export_agent,
    content_agent,
    render_agent,
    packaging_agent,
    notion_agent,
    catalog_agent,
    visual_agent,
    diagram_agent,
    notion_schema_agent,
    gumroad_agent,
    landing_agent,
    social_agent,
    market_agent,
)
```

Current registry:
```python
AGENT_REGISTRY = {
    "research_agent": research_agent.run,
    "csv_export_agent": csv_export_agent.run,
    "content_agent": content_agent.run,
    "render_agent": render_agent.run,
    "packaging_agent": packaging_agent.run,
    "notion_agent": notion_agent.run,
    "catalog_agent": catalog_agent.run,
    "visual_agent": visual_agent.run,
    "diagram_agent": diagram_agent.run,
    "notion_schema_agent": notion_schema_agent.run,
    "gumroad_agent": gumroad_agent.run,
    "landing_agent": landing_agent.run,
    "social_agent": social_agent.run,
}
```

Add `"market_agent": market_agent.run,` after `social_agent`:

```python
AGENT_REGISTRY = {
    "research_agent": research_agent.run,
    "csv_export_agent": csv_export_agent.run,
    "content_agent": content_agent.run,
    "render_agent": render_agent.run,
    "packaging_agent": packaging_agent.run,
    "notion_agent": notion_agent.run,
    "catalog_agent": catalog_agent.run,
    "visual_agent": visual_agent.run,
    "diagram_agent": diagram_agent.run,
    "notion_schema_agent": notion_schema_agent.run,
    "gumroad_agent": gumroad_agent.run,
    "landing_agent": landing_agent.run,
    "social_agent": social_agent.run,
    "market_agent": market_agent.run,
}
```

- [ ] **Step 2: Verify file compiles**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python -c "import ast; ast.parse(open('agents/registry.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add agents/registry.py
git commit -m "feat: register market_agent in registry"
```

---

### Task 4: Update All 7 Schemas

**Files:**
- Modify: `schemas/research_pack.json`
- Modify: `schemas/operating_system.json`
- Modify: `schemas/visual_pack.json`
- Modify: `schemas/workflow_kit.json`
- Modify: `schemas/blog_kit.json`
- Modify: `schemas/course_launch.json`
- Modify: `schemas/saas_docs.json`

Each schema gets:
1. `market_research` component at position 0 (before all others) with `depends_on: []`
2. All content components get `"market_research"` added to their `depends_on` array

- [ ] **Step 1: research_pack.json**

Add `market_research` before `database`. Update `report`'s depends_on from `["database", "sources"]` to `["market_research", "database", "sources"]`.

The components array starts:
```json
{
  "id": "market_research",
  "agent": "market_agent",
  "output": "data/market_research.json",
  "depends_on": []
},
```

Report depends_on becomes:
```json
"depends_on": ["market_research", "database", "sources"]
```

- [ ] **Step 2: operating_system.json**

Add `market_research` first. Update `guide`, `sops`, `templates`, `prompts` depends_on:

```json
"depends_on": ["market_research"]
```

- [ ] **Step 3: visual_pack.json**

Add `market_research` first. Update `image_prompts` depends_on:

```json
"depends_on": ["market_research"]
```

- [ ] **Step 4: workflow_kit.json**

Add `market_research` first. Update `setup_guide`, `prompts`, `automation_blueprint`, `notion_crm` depends_on:

```json
"depends_on": ["market_research"]
```

- [ ] **Step 5: blog_kit.json**

Add `market_research` first. Update `database`, `sources` depends_on:

```json
"depends_on": ["market_research"]
```
```json
"depends_on": ["market_research"]
```
And `post_draft` depends_on from `["database", "sources"]` to `["market_research", "database", "sources"]`.

- [ ] **Step 6: course_launch.json**

Add `market_research` first. Update `course_outline`, `marketing_copy` depends_on:

```json
"depends_on": ["market_research"]
```

- [ ] **Step 7: saas_docs.json**

Add `market_research` first. Update `api_reference`, `user_guide`, `changelog` depends_on:

```json
"depends_on": ["market_research"]
```

- [ ] **Step 8: Validate all schemas**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
foreach ($f in Get-ChildItem schemas/*.json) { try { $null = Get-Content $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json; Write-Output "OK: $($f.Name)" } catch { Write-Output "FAIL: $($f.Name): $_" } }
```

- [ ] **Step 9: Commit**

```bash
git add schemas/
git commit -m "feat: add market_research to all 7 schemas and update content depends_on"
```

---

### Task 5: Integration Test

- [ ] **Step 1: Verify the agent works standalone**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python -c "from agents.market_agent import _fallback_research; r = _fallback_research('AI Writing Tools', 'research_pack'); print('OK:', r['competitor_landscape']['recommended_price'])"
```

Expected: `OK: 29`

- [ ] **Step 2: Run existing tests to ensure nothing broken**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python -m pytest tests/ -v --tb=short
```

Expected: All existing tests pass.

---

## Self-Review Checklist

- [ ] Spec coverage: All spec requirements have corresponding tasks
- [ ] No placeholders: All code blocks are complete
- [ ] Type consistency: Agent signature matches existing pattern
- [ ] Schema pattern: market_research first in all 7 schemas
- [ ] Content depends_on updated correctly for each product type
