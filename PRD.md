# PRD — Digital Product Factory (DOE Architecture)

## 0. Reality Check (read before building)

Three assumptions in the original idea need correction before this spec is usable:

1. **"Directly make Notion workspace" is not possible via API.** The Notion API cannot create a new workspace. It can only create pages/databases as children of a page that has already been shared with your integration. The system therefore creates a **page tree under a pre-shared root page**, which functions as the deliverable's "workspace." This must be set up once by the human (share one page with the integration, copy its ID into config).

2. **"Antigravity inbuilt browser automation"** is an unverified capability. The system does not gate functionality on it. A `Renderer` interface is defined; Playwright is the default/guaranteed implementation (auto-installed on first run if missing); an Antigravity-backed renderer is an optional adapter that can be added later without changing any agent code.

3. **"Premium/high-end quality" is a design-system problem, not an orchestration problem.** The DOE pipeline only gets you correct, repeatable assembly. Perceived quality comes from the Jinja2/HTML/CSS templates, typography, and layout — this PRD allocates an explicit phase for that and does not let it be skipped.

The MVP below is deliberately narrow (one product type, no Notion, no image generation) to prove the pipeline mechanics before the schema system is asked to support four product categories.

---

## 1. Overview

**Digital Product Factory** is a local, CLI-driven, agentic pipeline that turns `(niche + product type)` into a packaged, sellable digital product (research data, guides, SOPs, templates, prompts, Notion structure, rendered PDFs), using a schema-driven template system so each product category has a fixed, predictable set of components.

It is **not** a web app, SaaS, or hosted service. It is a script you run locally (or in a CI job / scheduled task later), producing a folder + ZIP per run.

## 2. Goals

### Explicit goals (from user)
- Agentic workflow following a **Directive → Orchestration → Execution (DOE)** pattern.
- Produces "high-end premium" digital products made of multiple components.
- Can generate a Notion workspace/structure directly.
- First run: agent asks the user what product type / components they want.
- Browser automation: use Antigravity's built-in browser tool if available; otherwise install and use Playwright.
- Not a full web app.
- Deliverables: PRD (this doc), `CLAUDE.md`, three prompt files (planning / build / review).

### Inferred goals
- A reusable **factory**, not a one-off script — adding a 5th product category later should not require rewriting the orchestrator.
- Output quality must be good enough to sell on Gumroad/similar (i.e., design system matters as much as code).
- Minimize manual work per product: ideally `run.py` → review output → package → upload.
- Avoid re-running expensive LLM calls on every retry (resumable jobs).

### Non-goals (v1–v2)
- No multi-user accounts, auth, or hosted dashboard.
- No payment processing or storefront integration.
- No fully autonomous "discover niche → publish → market" loop (that's Phase 3 distribution, explicitly out of scope here).
- No database server (Postgres/Mongo) — local JSON/SQLite files are sufficient at this scale.

## 3. Architecture — DOE

```
┌─────────────────────────────────────────────────────────────┐
│ DIRECTIVE LAYER  (cli/wizard.py)                              │
│  - First run: interactive Q&A                                │
│    1. Product type? (research_pack | operating_system |      │
│       visual_pack | workflow_kit)                             │
│    2. Niche / topic?                                          │
│    3. Output name / slug?                                     │
│    4. Sync to Notion? (y/n) -> if y, parent page ID           │
│    5. (Phase 2+) Brand/style preset?                          │
│  - Writes a single `job_spec.json` — the contract for the run │
│  - Loads matching schema from /schemas/{product_type}.json    │
└───────────────────────────┬───────────────────────────────────┘
                             │ job_spec.json + schema
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ ORCHESTRATION LAYER  (orchestrator/orchestrator.py)            │
│  - Reads schema -> builds dependency graph of components      │
│  - Topologically sorts components (some depend on others)     │
│  - Maintains job_state.json (per-component status:            │
│    pending/running/done/failed) for resumability               │
│  - Dispatches each component to its agent via a registry       │
│  - Catches per-agent exceptions -> marks component failed,     │
│    continues with independent branches, surfaces a summary     │
│  - Selects Renderer implementation (Antigravity if available,  │
│    else Playwright) and injects it into render-capable agents  │
│  - On completion, triggers packaging agent                      │
└───────────────────────────┬───────────────────────────────────┘
                             │ per-component calls
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ EXECUTION LAYER  (agents/*.py — plain functions, no UI)        │
│  research_agent        -> data/database.json, content/sources.md │
│  csv_export_agent       -> data/export.csv (from database.json)   │
│  content_agent          -> content/*.md (report, guide, SOP, etc) │
│  prompts_agent          -> content/prompts/*.md                   │
│  catalog_agent           -> content/catalog.json                  │
│  visual_agent (Phase 3) -> assets/images/*, image_prompts.md       │
│  notion_agent (Phase 2) -> pushes page tree under shared parent    │
│  render_agent            -> presentation/*.pdf (via Renderer)      │
│  packaging_agent          -> outputs/{slug}/{slug}.zip              │
└─────────────────────────────────────────────────────────────┘
```

**Architectural style:** single-process, schema-driven pipeline (not microservices, not event bus). Justification: run frequency is low (manual/batch), no concurrent users, no need for network boundaries between "agents" — they're functions. A message queue or service mesh here would be pure overhead.

**Key patterns:**
- **Strategy pattern** for `Renderer` (Playwright vs Antigravity vs future).
- **Registry pattern** for agent dispatch (`AGENT_REGISTRY: dict[str, Callable]`), so adding a component = adding one entry, no orchestrator edits.
- **Schema-driven configuration** — product "shape" lives in JSON, not code branches.
- **Checkpointed pipeline** — `job_state.json` enables resume-after-failure without redoing completed (and LLM-costly) components.

## 4. Product Taxonomy & Component Layers

Per the earlier design discussion, every component belongs to one of three layers, and "PDF" is an output format of the presentation layer only — not a property of every component.

| Layer | Components | Format |
|---|---|---|
| Data | Database, CSV, Sources | JSON / CSV / MD |
| Content | Report, Guide, SOP, Prompts, Catalog | Markdown / JSON |
| Presentation | PDF Showcase, Images, Notion page tree | PDF / PNG / Notion API |

Product types select a **fixed** component list (Level 2 consistency from the earlier discussion — same category, any niche, same components):

| Product Type | Components | Notion Sync | Phase |
|---|---|---|---|
| `research_pack` | database, csv, sources, report (PDF) | No | **MVP (Phase 1)** |
| `operating_system` | guide (PDF), sops (PDF), templates (MD), prompts (MD), notion page tree | Yes | Phase 2 |
| `visual_pack` | images, image_prompts, reference_board, catalog, pdf_showcase | No | Phase 3 |
| `workflow_kit` | workflow_diagram, prompts, setup_guide (PDF), notion_crm, automation_blueprint | Yes | Phase 4 |

## 5. Schema File Format

`/schemas/{product_type}.json` — orchestrator reads this; nothing about product structure is hardcoded in Python.

```json
{
  "product_type": "research_pack",
  "display_name": "Research Pack",
  "components": [
    {
      "id": "database",
      "agent": "research_agent",
      "output": "data/database.json",
      "depends_on": []
    },
    {
      "id": "sources",
      "agent": "research_agent",
      "output": "content/sources.md",
      "depends_on": []
    },
    {
      "id": "csv",
      "agent": "csv_export_agent",
      "output": "data/export.csv",
      "depends_on": ["database"]
    },
    {
      "id": "report",
      "agent": "content_agent",
      "output": "content/report.md",
      "depends_on": ["database", "sources"]
    },
    {
      "id": "report_pdf",
      "agent": "render_agent",
      "output": "presentation/report.pdf",
      "depends_on": ["report"],
      "uses_renderer": true,
      "template": "research_pack/report.html.j2"
    }
  ],
  "notion_sync": false
}
```

`operating_system.json` (Phase 2) adds a `"notion_sync": true` flag and a `notion_structure` block describing the page tree (mirrors the component list: one page per component, nested under the run's root page).

## 6. First-Run / Directive Wizard Spec

On `python main.py` with no `job_spec.json` argument:

1. Detect `.env` — if `ANTHROPIC_API_KEY` (or chosen LLM key) missing, prompt for it and write to `.env` (never commit `.env`).
2. Ask product type (numbered list from `/schemas/*.json`).
3. Ask niche/topic (free text).
4. Ask output slug (default: slugified niche).
5. If schema's `notion_sync` is true (or user opts in): ask for `NOTION_PARENT_PAGE_ID`; if not set, print the one-time setup instructions (create integration, share a page, paste its ID) and skip Notion for this run rather than failing.
6. Write `outputs/{slug}/job_spec.json`.
7. Hand off to orchestrator.

`job_spec.json`:
```json
{
  "slug": "ai-tools-2026-research-pack",
  "product_type": "research_pack",
  "niche": "AI productivity tools for solo founders",
  "notion_sync": false,
  "notion_parent_page_id": null,
  "created_at": "2026-06-12T10:00:00Z"
}
```

Re-running with `python main.py --resume outputs/{slug}/job_spec.json` skips the wizard and resumes from `job_state.json`.

## 7. Renderer Strategy (Browser Automation)

```python
# renderers/base.py
class Renderer(Protocol):
    def render_pdf(self, html: str, output_path: str) -> None: ...

# orchestrator selects implementation at startup:
def get_renderer() -> Renderer:
    if antigravity_browser_available():   # capability probe, never assumed
        return AntigravityRenderer()
    if not playwright_installed():
        run_playwright_install()          # `python -m playwright install chromium`
    return PlaywrightRenderer()
```

- `antigravity_browser_available()` is a single probe function isolated in `renderers/antigravity_renderer.py`. If the hook doesn't exist or raises, it returns `False` — system falls through to Playwright with **no error surfaced to the user**.
- Playwright is installed lazily (only when a `render_agent` component is actually reached), not as part of `pip install` — keeps install time down for Notion-only or data-only runs.
- All templates render to HTML first (Jinja2), then to PDF — the renderer never touches Markdown directly.

## 8. Notion Integration Spec (Phase 2)

**Setup (one-time, manual, documented in README):**
1. Create a Notion integration, get `NOTION_API_KEY`.
2. Create one page in Notion called e.g. "Digital Product Factory Root".
3. Share that page with the integration.
4. Copy the page ID into `.env` as `NOTION_PARENT_PAGE_ID`.

**Per run (operating_system / workflow_kit):**
- `notion_agent` creates a new child page under `NOTION_PARENT_PAGE_ID` named after the product (`job_spec.slug`).
- Under that, creates one child page/database per component per the schema's `notion_structure` block (e.g., Guide page, SOPs page with toggle blocks per SOP, Templates database, Prompts database).
- Content is converted from the agent-generated Markdown to Notion blocks via a minimal MD→blocks mapper (headings, paragraphs, bullet lists, code blocks, dividers — not a full Markdown spec).
- If `NOTION_API_KEY` or `NOTION_PARENT_PAGE_ID` is missing, this component is marked `skipped` (not `failed`) in `job_state.json`, and the rest of the pipeline proceeds.

## 9. Tech Stack

- **Language:** Python 3.11+ (single language across orchestrator + agents — avoids polyglot overhead for a local tool).
- **LLM access:** Anthropic API (`anthropic` SDK), model configurable via `.env`.
- **Templating:** Jinja2 (HTML templates) → Playwright (Chromium headless) → PDF.
- **Schema validation:** Pydantic models for `job_spec.json`, `job_state.json`, and each schema file — fail fast on malformed config.
- **Notion:** `notion-client` (official SDK) for Phase 2.
- **CLI:** `typer` or `argparse` (no framework needed beyond stdlib + typer for the wizard).
- **Packaging:** stdlib `zipfile`.
- **Config:** `.env` + `python-dotenv`.
- **Testing:** `pytest` with mocked LLM/Notion/renderer calls.

No frontend framework, no database server, no Docker required for v1 (Dockerfile optional, for Phase 5 reproducibility only).

## 10. Folder Structure

```
digital-product-factory/
├── CLAUDE.md
├── PRD.md
├── prompts/
│   ├── 01_planning_prompt.md
│   ├── 02_implementation_prompt.md
│   └── 03_review_prompt.md
├── main.py                      # entrypoint: wizard -> orchestrator
├── .env.example
├── requirements.txt
├── cli/
│   └── wizard.py                # Directive layer
├── orchestrator/
│   ├── orchestrator.py          # Orchestration layer
│   ├── models.py                # Pydantic: JobSpec, JobState, Schema
│   └── state.py                 # load/save job_state.json
├── agents/
│   ├── registry.py               # AGENT_REGISTRY dict
│   ├── research_agent.py
│   ├── csv_export_agent.py
│   ├── content_agent.py
│   ├── catalog_agent.py
│   ├── visual_agent.py          # Phase 3 stub in MVP
│   ├── notion_agent.py          # Phase 2 stub in MVP
│   ├── render_agent.py
│   └── packaging_agent.py
├── renderers/
│   ├── base.py
│   ├── playwright_renderer.py
│   └── antigravity_renderer.py
├── schemas/
│   ├── research_pack.json
│   ├── operating_system.json
│   ├── visual_pack.json
│   └── workflow_kit.json
├── templates/
│   ├── research_pack/
│   │   └── report.html.j2
│   └── shared/
│       ├── base.css
│       └── partials/
├── outputs/
│   └── {slug}/
│       ├── job_spec.json
│       ├── job_state.json
│       ├── data/
│       ├── content/
│       ├── presentation/
│       ├── assets/
│       └── {slug}.zip
└── tests/
    ├── test_orchestrator.py
    ├── test_agents.py
    └── fixtures/
```

## 11. MVP Definition (Phase 1)

**In scope:**
- Directive wizard (product type + niche + slug only; Notion question skipped/hardcoded `false`).
- Orchestrator with dependency resolution + `job_state.json` checkpointing.
- `research_pack` schema fully working end-to-end: `research_agent` → `database.json` + `sources.md` → `csv_export_agent` → `export.csv`, `content_agent` → `report.md` → `render_agent` → `report.pdf` (Playwright) → `packaging_agent` → `{slug}.zip`.
- One real Jinja2/CSS template for the report — must look deliberately designed (typography, spacing, cover section), not a default browser-print stylesheet. This is the Phase 1 "design system" deliverable, scoped to one template.
- Renderer fallback logic implemented (Antigravity probe + Playwright auto-install), even though Antigravity adapter itself can be a `NotImplementedError` stub in v1.
- Basic error isolation: one failed component doesn't crash the whole run.
- `pytest` suite covering orchestrator dependency resolution and at least one agent with mocked LLM calls.

**Explicitly deferred (Phase 2+):**
- `operating_system`, `visual_pack`, `workflow_kit` schemas and their agents.
- Notion integration.
- Image generation.
- Multiple design themes/presets.
- Batch/multi-niche runs.

## 12. Roadmap

| Phase | Scope | Size |
|---|---|---|
| 0 | Repo scaffold, `.env`, Pydantic models, schema loader, orchestrator skeleton with dependency graph + state file | M |
| 1 (MVP) | `research_pack` end-to-end, Playwright renderer + fallback probe, one polished template, tests | L |
| 2 | `operating_system` schema + agents, Notion integration (page tree under shared root), MD→Notion-blocks mapper | L |
| 3 | `visual_pack` schema, image-generation agent (pluggable provider), reference-board + showcase templates | M |
| 4 | `workflow_kit` schema, Notion CRM template, workflow diagram (Mermaid → SVG), automation blueprint generator | M |
| 5 (Advanced) | Theme/preset system (e.g. "luxury dark", "editorial", "minimal") applied across all templates; multi-niche batch mode (`--batch niches.csv`); Antigravity renderer adapter (if/when capability confirmed); structured logging + run summary report | L |

## 13. Risks & Open Questions

| Risk | Mitigation |
|---|---|
| LLM output quality varies by niche, breaking template assumptions (missing sections) | `content_agent` validates generated Markdown structure against expected headings before render; on mismatch, retries with a stricter prompt once, then fails that component only |
| Playwright/Chromium download size/time on first run | Lazy install, only when a render component is reached; document expected ~150–200MB download |
| Notion API rate limits on large page trees | Batch block-append calls (100-block max per request per Notion limits); back off on 429 |
| "Premium" is subjective — templates may still look generic | Phase 1 ships exactly one template but it is reviewed against a named visual reference (e.g., a specific Stripe/Apple-style report) before sign-off; this review gate is mandatory, not optional |
| Antigravity browser hook may not exist at all | Probe function returns `False` safely; entire feature is additive, never blocking |
