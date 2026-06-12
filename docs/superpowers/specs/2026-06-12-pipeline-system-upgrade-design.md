# Pipeline System Upgrade — Design Spec

**Date:** 2026-06-12
**Approach:** Context-Driven Pipeline Redesign (Approach B)
**Status:** Draft

---

## 1. Prompt System Redesign

### Current Problem
- `content_agent.py` has 1-2 line prompts per component (e.g. `"Write a comprehensive beginner's guide"`)
- No role/persona, audience, tone, format, or constraints defined
- No cross-component context injection → Guide, SOPs, Templates, Prompts are generated in isolation

### Solution
Each prompt becomes a **structured template** with mandatory fields:

```
[ROLE]       — Specific persona ("You are a senior operations manager in {niche}")
[AUDIENCE]   — Target reader (beginner, professional, hiring manager)
[FORMAT]     — Exact output structure (sections, headings, patterns)
[TONE]       — Professional, conversational, instructional, etc.
[CONTEXT]    — Key takeaways from already-generated dependency components
[CONSTRAINTS]— Min words, style rules, elements to avoid
```

### Implementation Plan
1. Create `prompts/` directory with Jinja2 prompt templates per component:
   - `prompts/report.j2`
   - `prompts/guide.j2`
   - `prompts/sops.j2`
   - `prompts/templates.j2`
   - `prompts/prompts.j2`
   - `prompts/database.j2`
   - `prompts/sources.j2`
   - `prompts/automation_blueprint.j2`
   - `prompts/notion_crm.j2`
   - `prompts/setup_guide.j2`
   - `prompts/image_prompts.j2`
2. Update `content_agent.py` to load prompt templates from `prompts/` directory instead of inline strings
3. Implement context injection — when a component depends on others, extract key themes/points from their output and inject into `{context}` variable
4. Remove `max_tokens=2048` limit → set to 16384 (already done in `llm_client.py`)

---

## 2. Template & Design System Redesign

### Current Problem
- `basic_doc.html.j2` is 22 lines — just `<h1>` title + `{{ content }}` markdown dump
- `base.css` is 88 lines, 5 CSS variables
- Themes are 4-13 lines of color overrides only
- No cover page for operating_system PDFs (only research_pack has one)
- No table of contents, no page numbers, no headers/footers
- Web fonts (Inter, Playfair Display) not available in headless Playwright

### Solution
Implement a proper PDF design system with three visual layers per document:

**Layer 1 — Cover Page:**
- Full-page layout with centered title, subtitle, niche, date
- Optional accent bar/divider
- Different layout per product type (research_pack gets data-focused cover, operating_system gets system-diagram cover)

**Layer 2 — Table of Contents:**
- Auto-generated from markdown headings via `toc` extension
- Dot-leader between section name and page number
- New page per section with section header

**Layer 3 — Content Body:**
- Running header (product name left, page number right)
- Footer with "Digital Product Factory" brand
- Full typography scale: h1-h6, body, lead, small, caption
- Component styles: tables (bordered + striped), code blocks (mono + bg), blockquotes (accent left border), callouts (info/warning/tip styles)
- CSS counters for auto page numbering (`@page` + `counter(page)`)

**Design System (`base.css` upgraded to ~400 lines):**
- CSS custom properties for: typography (font families, sizes, weights, line heights), spacing (section, paragraph, list), colors (text, bg, accent, muted, border, success, warning), layout (page width, margins, cover height)
- Utility classes: `.text-lead`, `.text-caption`, `.callout`, `.callout-warning`, `.code-block`
- `@page` rule for PDF print margins + page numbers

**Themes Upgrade:**
Each theme becomes a full design variant (not just color overrides):

| Theme | Headings | Body | Accent | Vibe |
|-------|----------|------|--------|------|
| default | System sans | System sans | Blue #0066cc | Clean professional |
| luxury-dark | Playfair Display (serif) | System sans | Gold #d4af37 | Premium editorial |
| editorial | Helvetica Neue (sans, uppercase) | Times New Roman (serif) | Firebrick #b22222 | Magazine |
| minimal | Helvetica Neue (light weight) | Same | Black #000000 | Swiss design |

- Font fallback strategy: Bundled fonts via `file://` protocol for Playwright, or system font fallbacks
- Each theme file includes typography scale + spacing + layout vars, not just color

### Implementation Plan
1. Rewrite `templates/shared/base.css` (~400 lines) with full design system
2. Rewrite cover layout with proper full-page design
3. Add TOC template partial (`templates/shared/toc.html.j2`)
4. Add header/footer template partial (`templates/shared/header_footer.html.j2`)
5. Upgrade theme CSS files (luxury-dark.css, editorial.css, minimal.css) with full design tokens
6. Update `basic_doc.html.j2` to include cover + TOC + styled body
7. Update `report.html.j2` with new design system
8. Add page-number CSS (`@page { @bottom-center { content: counter(page) } }`)

---

## 3. Format-Differentiated Content Strategy

### Current Problem
Same markdown goes to 3 places (MD file, PDF, Notion) — redundant, no value add per format.

### Solution
Each format gets a purpose-specific transformation:

| Format | Content | Purpose |
|--------|---------|---------|
| `.md` (raw) | Full comprehensive document | Source of truth, editing, reference |
| `.pdf` | Shorter "How to use / Why / What" guide | Bonus deliverable — actionable, premium design |
| Notion | Working system with databases/properties/relations | Primary product — functional, not textual |

### Mechanism
- Agent gets a new parameter `format` (full/guide/notion):
  - `full`: Current behavior — write complete markdown document
  - `guide`: Takes the full content, asks LLM to create a shorter "Getting Started" version (executive summary + "how to use the Notion template" instructions)
  - `notion`: Takes the full content, asks LLM to generate a JSON database schema blueprint (databases, properties, relations, views)

### Implementation Plan
1. Add `format` field to `ComponentSpec` model in `models.py`
2. Update `content_agent.py` to accept `format` parameter — when `format=guide`, generate condensed version
3. When `format=notion`, generate Notion database blueprint JSON instead of markdown
4. Wire this in `operating_system.json` schema:
   - Existing components stay `full`
   - New `guide_pdf` gets `mode=guide` instead of using same content as `guide`

---

## 4. Notion Agent Upgrade

### Current Problem
- Notion agent creates only **text pages** with raw markdown → block by block
- No database creation, no properties, no relations, no formulas
- Output has page IDs (`37defcc5-d24e...`) instead of clickable URLs

### Solution
Two-phase Notion agent:

**Phase 1 — Schema Generation (new agent or content_agent mode):**
- LLM generates a JSON blueprint describing:
  - Database(s): name, icon, description
  - Properties per database: name, type (title, select, multi_select, number, date, relation, formula, etc.), options, format
  - Relations: which databases link to which, rollup configurations
  - Views: table/kanban/calendar/gallery, filters, sorts
  - Formula definitions as Notion formula syntax

**Phase 2 — Notion API Execution (revised notion_agent.py):**
- `notion.databases.create()` for each database in blueprint
- `notion.databases.update()` to add properties
- `notion.pages.create()` to create relation links
- `notion.databases.create()` for views
- Fetch `url` from response instead of just `id` for clickable links

### Implementation Plan
1. Create `notion_schema_agent.py` — takes niche, generates blueprint JSON via LLM
2. Update `notion_agent.py` — reads blueprint, creates databases + properties + relations + views
3. Store Notion share URLs in `notion_sync.json` (add `url` field)
4. Generate `Notion_Template_Link.md` with proper clickable Notion URLs

---

## 5. Bug Fixes & Technical Debt

| # | Issue | File | Fix |
|---|-------|------|-----|
| 1 | `{slug}.zip` literal filename | `packaging_agent.py:12` | Replace `{slug}` with `job_spec.slug` using string interpolation |
| 2 | Notion page IDs not usable as links | `notion_agent.py:74` | Use `page["url"]` from Notion API response in addition to `page["id"]` |
| 3 | `max_tokens=2048` | `llm_client.py:18` | Changed to `16384` ✅ |
| 4 | No `display_name` on JobSpec | `models.py` | Add `display_name: Optional[str] = None` or use `niche` |
| 5 | `prompts/` dir referenced but missing | AGENTS.md | Create `prompts/` directory with prompt templates |
| 6 | No `__init__.py` files | All packages | Add `__init__.py` for explicit packages |
| 7 | Title fallback to niche | `render_agent.py:42` | Create `display_name` from `product_type` if not set |

---

## 6. Pipeline Architecture (After Upgrade)

```
 USER (niche input)
    │
    ▼
┌─────────────────────────────────────────────────┐
│  SCHEDULER (wizard.py → job_spec.json)           │
│  → slug, niche, product_type, theme              │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│  ORCHESTRATOR (orchestrator.py)                  │
│  → Load schema → Topo sort → Dispatch agents    │
│  → Inject context between deps                   │
│  → Format-aware dispatch (full/guide/notion)     │
└──────────────────────┬──────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
┌─────────────────┐ ┌─────────┐ ┌──────────────┐
│ RESEARCH_AGENT  │ │CONTENT  │ │ NOTION SCHEMA│
│ → database.json │ │_AGENT   │ │ AGENT (new)  │
│ → sources.md    │ │ → .md   │ │ → blueprint  │
└─────────────────┘ │ (format │ │   .json      │
                    │  =full) │ └──────┬───────┘
         ▼          └─────────┘        │
┌─────────────────┐                    │
│ RENDER_AGENT    │                    │
│ → redesigned    │                    │
│   templates     │                    │
│ → premium PDF   │                    │
│ (format=guide)  │                    │
└─────────────────┘                    │
         │                             │
         ▼                             ▼
┌─────────────────┐      ┌─────────────────────┐
│ PACKAGING_AGENT │      │ NOTION_AGENT (v2)   │
│ → {slug}.zip    │      │ → databases create  │
│   (FIXED)       │      │ → properties setup   │
│   → content/    │      │ → relations create   │
│     (raw .md)   │      │ → views configure    │
│   → presentation│      │ → URL output         │
│     (guide PDF) │      │ → share link gen     │
│   → notion_link │      └─────────────────────┘
│     (clickable) │
└─────────────────┘
```

---

## 7. Schema Changes

### `models.py` — JobSpec upgrade
```python
class ComponentSpec(BaseModel):
    id: str
    agent: str
    output: str
    depends_on: List[str] = Field(default_factory=list)
    uses_renderer: bool = False
    template: Optional[str] = None
    format: Literal["full", "guide", "notion"] = "full"  # NEW
```

### Schema JSON files
- Existing schemas unchanged for backward compatibility
- Components with `"format": "guide"` generate condensed content for PDF
- Components with `"format": "notion"` generate database blueprint JSON

---

## 8. Success Criteria

- [ ] Structured prompts produce richer, longer, more specific content (check: avg word count per component > 3x current)
- [ ] PDFs have proper cover pages, TOC, page numbers, and styled content
- [ ] Notion creates actual databases with properties/relations/views, not text dumps
- [ ] Notion output includes clickable URLs
- [ ] ZIP file name resolves `{slug}` correctly
- [ ] Guide and Notion content are meaningfully different (guide = how-to, Notion = working system)
- [ ] All existing product types (research_pack, operating_system, visual_pack, workflow_kit) still work
