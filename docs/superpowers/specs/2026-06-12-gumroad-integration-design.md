# Gumroad Integration Design

**Date:** 2026-06-12  
**Status:** Draft  
**Product:** Digital Product Factory

## Overview

Integrate Gumroad API into the Digital Product Factory pipeline for end-to-end product research, creation, and publishing. The key innovation: product type selection becomes dynamic, driven by real Gumroad market data rather than fixed user selection.

## Core Flow

```
User inputs niche ──► Gumroad Research Phase ──► Product Type Decision ──► Pipeline ──► Gumroad Publish Phase
                          (API: GET products,        (dynamic or                  (API: POST product,
                           GET sales, analyze)         user-confirmed)              PUT files, offers)
```

## Phase 1: Research Mode

### Agent: `gumroad_agent` (research mode)

The single `gumroad_agent.py` operates in two modes identified by `component.id`.

**Research mode** runs first in the pipeline (`id: "gumroad_research"`, `depends_on: []`).

API calls to Gumroad:
| Endpoint | Purpose |
|----------|---------|
| `GET /v2/products` | Fetch products matching the niche (search by name/description) |
| `GET /v2/products/{id}` | Get individual product details, pricing, description length/content |
| `GET /v2/sales` | Fetch sales data for revenue estimation per product type |

Output: `outputs/{slug}/data/gumroad_research.json`

Schema:
```json
{
  "niche": "AI Writing Tools for Content Creators",
  "products_analyzed": 24,
  "product_type_distribution": {
    "operating_system": { "count": 11, "avg_price": 29.00, "total_sales_est": 450 },
    "template_pack": { "count": 7, "avg_price": 19.00, "total_sales_est": 320 },
    "research_pack": { "count": 5, "avg_price": 14.00, "total_sales_est": 180 },
    "workflow_kit": { "count": 1, "avg_price": 39.00, "total_sales_est": 45 }
  },
  "top_products": [
    { "name": "...", "price": 29, "sales": 150, "description_length": 850,
      "key_features": ["...", "..."], "quality_gaps": ["missing X", "weak Y"] }
  ],
  "recommended_product_type": "operating_system",
  "recommended_price_range": { "min": 19, "max": 39, "suggested": 29 },
  "quality_gaps": ["Competitors lack automation features", "No onboarding templates"],
  "pricing_analysis": { "lowest": 9, "highest": 79, "median": 24, "sweet_spot": 29 }
}
```

### Smart Product Type Decision (Wizard)

After research completes, the wizard uses this data to determine product type:

```
User input: niche + optionally suggested product type

IF user suggested a type:
    Look up that type in product_type_distribution
    IF it's the top seller:
        ✅ Auto-confirm, proceed
    ELSE:
        ⚠ Show comparison data
        "You chose '{user_type}' ({share}% market, avg ${price}).
         '{top_type}' is the top seller ({top_share}% market, avg ${top_price}).
         Switch to '{top_type}'? (Y/n):"
        IF yes → switch type
        IF no  → use user's choice
ELSE:
    Auto-select best-selling product type
    Show user with option to change
```

## Phase 2: Content Creation (Existing Pipeline)

Once product type is confirmed, the existing pipeline runs normally with `job_spec.product_type` set to the chosen type.

### Enhanced Context Injection

The `gumroad_research.json` data is injected into all content agents via context:
- `research_agent` gets competitor product names, features, gaps
- `content_agent` gets quality gaps, missing features to emphasize
- `render_agent` gets pricing tier suggestions for cover/title page

This ensures the output content is market-informed and fills real gaps.

## Phase 3: Publish Mode

### Agent: `gumroad_agent` (publish mode)

Runs last in the pipeline (`id: "gumroad_publish"`, depends on all content + render + package components).

#### Steps:

1. **Generate Listing** — LLM prompt (`prompts/gumroad_listing.j2`) creates optimized product listing using:
   - Gumroad research data (competitor descriptions, keywords)
   - Product content (from content_agent output)
   - Best practices (from prompt template)
2. **Generate Review Summary** — Markdown file showing:
   - Product title, price, description preview
   - Files to attach (PDF, ZIP)
   - Offer codes with expiry
   - Variants (if applicable)
3. **Approval Gate** — Pipeline pauses, displays review, waits for "y" input
4. **Publish** — On approval:
   - `POST /v2/products` — create product
   - `PUT /v2/products/{id}` — set description, rich content, price
   - Upload files (PDF, ZIP)
   - `POST /v2/offer_codes` — create launch discount codes
   - `POST /v2/products/{id}/publish` — enable/make live

#### Approval Gate UX

```
═══════════════════════════════════════════════
  Product Review — Ready to Publish

  Title:    AI Writing OS — The Complete Toolkit
  Price:    $29.00
  Type:     Operating System

  Files:
    ✅ guide.pdf (1.2 MB)
    ✅ sops.pdf (890 KB)
    ✅ templates.zip (3.4 MB)
    ✅ prompts.zip (2.1 MB)

  Offer Code: LAUNCH20 — 20% off (expires 7 days)

  Description Preview:
  "The all-in-one operating system for AI writing
   professionals..."

  Publish to Gumroad? (y/N):
═══════════════════════════════════════════════
```

## Gumroad API Reference

Base URL: `https://api.gumroad.com/v2/`
Auth: `Authorization: Bearer <access_token>`

| Method | Endpoint | Use Case |
|--------|----------|----------|
| GET | `/user` | Verify auth, get user info |
| GET | `/products` | List all products (research) |
| GET | `/products/{id}` | Product details (research) |
| POST | `/products` | Create new product (publish) |
| PUT | `/products/{id}` | Update product (set description, price) |
| PUT | `/products/{id}/publish` | Enable product listing |
| POST | `/products/{id}/offer_codes` | Create discount codes |
| DELETE | `/products/{id}/offer_codes/{offer_code}` | Remove offer code |
| GET | `/sales` | Fetch sales data (research) |

## Files to Create

| File | Description |
|------|-------------|
| `agents/gumroad_agent.py` | Consolidated agent with research + publish modes |
| `prompts/gumroad_listing.j2` | LLM prompt for optimized product listing copy |
| `prompts/gumroad_research.j2` | LLM prompt for analyzing Gumroad research data |

## Files to Modify

| File | Changes |
|------|---------|
| `agents/registry.py` | Add `gumroad_agent` entry |
| `cli/wizard.py` | New research-based smart wizard flow |
| `orchestrator/orchestrator.py` | Handle dynamic product type decision from gumroad_research.json; skip gumroad_research if already done on resume |
| `orchestrator/models.py` | Add `GUMROAD_ACCESS_TOKEN` env var reference; no schema change needed |
| `schemas/research_pack.json` | Add gumroad_research + gumroad_publish components |
| `schemas/operating_system.json` | Same |
| `schemas/visual_pack.json` | Same |
| `schemas/workflow_kit.json` | Same |
| `schemas/blog_kit.json` | Same |
| `schemas/course_launch.json` | Same |
| `schemas/saas_docs.json` | Same |
| `.env.example` | Add `GUMROAD_ACCESS_TOKEN` |

## Constraints

1. **No hardcoded secrets** — `GUMROAD_ACCESS_TOKEN` from `.env` only, via `python-dotenv`
2. **Resumability** — `gumroad_research` if done, skip on resume; `gumroad_publish` if done, skip
3. **Approval gate blocks pipeline** — publish phase waits for user input; pipeline does NOT continue until response
4. **Graceful degradation** — if Gumroad API is unreachable at research phase, proceed with LLM-only research (no crash)
5. **All file opens use `encoding="utf-8"`**

## Schema Component Pattern

Each product type schema gets two new components added:

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
}
```

The orchestrator's `_get_execution_order()` topological sort places `gumroad_research` first and `gumroad_publish` last.

## Orchestrator Changes

### Dynamic Product Type

In `orchestrator.py`, after `gumroad_research` completes:

```python
if component.id == "gumroad_research" and result.status == "done":
    research_path = result.output_path
    if os.path.exists(research_path):
        with open(research_path, "r") as f:
            research = json.load(f)
        recommended_type = research.get("recommended_product_type")
        if recommended_type and recommended_type != current_product_type:
            # This should happen in wizard, not orchestrator
            pass  # Decision already made in wizard
```

The dynamic product type decision happens in the **wizard phase** (before pipeline runs), not in the orchestrator. The orchestrator simply runs with whatever `job_spec.product_type` is.

### Agent Mode Detection

```python
def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    if component.id == "gumroad_research":
        return _run_research(component, job_spec, context)
    elif component.id == "gumroad_publish":
        return _run_publish(component, job_spec, context)
    raise ValueError(f"Unknown gumroad component: {component.id}")
```

## Self-Review Notes

- Placeholder-free: all sections complete
- Internal consistency: flow matches from wizard → research → decision → pipeline → publish
- Scope check: focused on Gumroad integration only, no unrelated features
- Ambiguity check: approval gate behavior is explicit (wait for input, don't timeout)
