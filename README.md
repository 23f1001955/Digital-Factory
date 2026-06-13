# Digital Product Factory

A **local CLI pipeline** that turns a niche + product type into a packaged, sellable digital product — research reports, operating systems, visual packs, blog kits, course launch kits, workflow kits, SaaS documentation, and more.

```bash
python main.py               # Interactive wizard
python main.py --batch jobs.csv   # Batch mode
python main.py --resume outputs/foo/job_spec.json  # Resume
```

---

## Table of Contents

- [What It Does](#what-it-does)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Interactive Wizard](#interactive-wizard)
  - [Batch Mode](#batch-mode)
  - [Resume Mode](#resume-mode)
- [Product Types](#product-types)
  - [1. Research Pack](#1-research-pack)
  - [2. Operating System](#2-operating-system)
  - [3. Visual Pack](#3-visual-pack)
  - [4. Workflow Kit](#4-workflow-kit)
  - [5. Blog Kit](#5-blog-kit)
  - [6. Course Launch Kit](#6-course-launch-kit)
  - [7. SaaS Documentation](#7-saas-documentation)
- [How It Works — End to End](#how-it-works--end-to-end)
- [Agents Reference](#agents-reference)
- [Output Structure](#output-structure)
- [Notion Integration](#notion-integration)
- [Gumroad Publishing](#gumroad-publishing)
- [Templates & Themes](#templates--themes)
- [Tech Stack](#tech-stack)
- [Development](#development)
- [FAQ](#faq)

---

## What It Does

Digital Product Factory is a **schema-driven, agentic pipeline** that:

1. Asks you what kind of product you want and what niche
2. Uses LLM agents to research, write content, generate diagrams, create images, render PDFs
3. Creates databases in Notion with sample entries
4. Packages everything into a zip file ready to sell
5. Optionally publishes to Gumroad with market-researched pricing
6. Optionally generates a landing page (via Google Stitch) and deploys it to Vercel
7. Optionally promotes across Instagram, Threads, Facebook, and Pinterest

All of this runs **locally** on your machine — no web app, no hosted service, no monthly subscription.

---

## Key Features

- **7 Product Types** — Research packs, operating systems, visual packs, blog kits, course launch kits, workflow kits, and SaaS documentation
- **Schema-Driven** — Each product type is defined in `/schemas/*.json`. Adding a new type means adding one JSON file, not rewriting code
- **LLM-Powered Content** — Uses Anthropic Claude to research niches and generate high-quality written content
- **PDF Rendering** — Generates production-quality PDFs via Playwright (Chromium) with Jinja2 HTML templates
- **Notion Sync** — Creates full Notion workspaces with databases, relations, sample entries, icons, and cover images
- **Gumroad Publishing** — Researches competitor pricing on Gumroad, suggests optimal pricing, and publishes with manual approval
- **Landing Page Generation** — Generates premium landing pages via Google Stitch with cover images (Gemini 3.1 Flash), Gumroad CTA button, and deploys to Vercel
- **Social Media Promotion** — Posts product announcements to Instagram, Threads, Facebook, and Pinterest with LLM-generated platform-specific copy
- **Batch Mode** — Process multiple niches from a CSV file in one command
- **Resumable** — If a run fails, resume from where it left off without redoing completed (and LLM-costly) steps
- **Graceful Degradation** — One failed component doesn't crash the whole pipeline; independent branches continue
- **4 Visual Themes** — Default, Luxury Dark, Editorial, Minimal
- **Interactive Progress** — Real-time emoji status for each component during pipeline execution

---

## Architecture

The system follows a three-layer **DOE Architecture** (Directive → Orchestration → Execution):

```
┌──────────────────────────────────────────────────────────────┐
│ DIRECTIVE LAYER (cli/wizard.py)                              │
│  - Interactive Q&A: product type, niche, theme, Notion sync  │
│  - Writes job_spec.json — the contract for a single run      │
└───────────────────────────┬──────────────────────────────────┘
                            │ job_spec.json + schema
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ ORCHESTRATION LAYER (orchestrator/orchestrator.py)           │
│  - Reads schema → builds dependency graph of components      │
│  - Topologically sorts components (respects depends_on)      │
│  - Maintains job_state.json for resumability                 │
│  - Dispatches each component to its agent via a registry     │
│  - Catches exceptions → marks component failed, continues    │
│  - Selects renderer (Playwright) and injects it where needed │
└───────────────────────────┬──────────────────────────────────┘
                            │ per-component calls
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ EXECUTION LAYER (agents/*.py — plain functions, no UI)       │
│  research_agent     → database.json, sources.md              │
│  content_agent      → content reports, guides, blogs, etc.   │
│  csv_export_agent   → export.csv from database.json          │
│  render_agent       → PDFs via Playwright + Jinja2 templates │
│  visual_agent       → image generation via DALL-E / placeholders │
│  catalog_agent      → image catalog JSON                     │
│  diagram_agent      → Mermaid diagrams → SVGs → PDFs         │
│  packaging_agent    → zip archive of all deliverables        │
│  notion_agent       → creates page tree under shared parent  │
│  gumroad_agent      → market research + product publishing   │
│  landing_agent      → cover images → Stitch HTML → Vercel   │
│  social_agent       → copy gen → FB/IG/Threads/Pinterest    │
└──────────────────────────────────────────────────────────────┘
```

### Key Design Patterns

- **Registry Pattern** — `agents/registry.py` maps agent names to functions. Adding a new agent = adding one dict entry
- **Strategy Pattern** — Renderers (Playwright, Antigravity) are interchangeable through a Protocol
- **Schema-Driven Configuration** — Product "shape" lives in JSON files, not Python if/elif chains

---

## Installation

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
# 1. Clone the repository
git clone <repo-url> digital-product-factory
cd digital-product-factory

# 2. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment file
cp .env.example .env

# 5. (Optional, for PDF rendering) Install Playwright Chromium
# This happens automatically on first PDF render, but you can pre-install:
python -m playwright install chromium

# 6. Configure your API keys (see Configuration below)
```

---

## Configuration

All configuration lives in `.env`:

```env
# Required: LLM provider
ANTHROPIC_API_KEY=sk-ant-...

# Optional: OpenAI (for image generation in Visual Pack)
OPENAI_API_KEY=sk-...

# Optional: Notion integration
NOTION_API_KEY=secret_...
NOTION_PARENT_PAGE_ID=your_page_id_here

# Optional: Gumroad publishing
GUMROAD_ACCESS_TOKEN=your_token_here

# Optional: Landing page (Google Stitch + Vercel)
GEMINI_API_KEY=
STITCH_API_KEY=
VERCEL_TOKEN=

# Optional: Social media promotion
FACEBOOK_PAGE_TOKEN=
FACEBOOK_PAGE_ID=
INSTAGRAM_USER_ID=
THREADS_USER_ID=
PINTEREST_TOKEN=
PINTEREST_BOARD_ID=
```

### How to get each key

| Key | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com/ |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `NOTION_API_KEY` | https://www.notion.so/my-integrations (create an internal integration) |
| `NOTION_PARENT_PAGE_ID` | Share a page with your integration, then copy the page URL segment (32 hex chars) |
| `GUMROAD_ACCESS_TOKEN` | https://app.gumroad.com/settings/advanced#application-forms |
| `GEMINI_API_KEY` | https://aistudio.google.com/app/apikey |
| `STITCH_API_KEY` | https://stitch.google.com/ (request access) |
| `VERCEL_TOKEN` | https://vercel.com/account/tokens |
| `FACEBOOK_PAGE_TOKEN` | Meta Business Suite → Page Access Token (requires connected IG + Threads) |
| `PINTEREST_TOKEN` | https://developers.pinterest.com/tokens/ |

---

## Usage

### Interactive Wizard

```bash
python main.py
```

The wizard will ask:

1. **Product type** (1-7) — What kind of product to create
2. **Niche/Topic** — What subject (e.g., "AI tools for freelancers")
3. **Output slug** — Directory name (auto-generated from niche)
4. **Theme** (1-4) — Visual design style
5. **Notion sync?** (y/n) — Whether to create Notion databases
6. **Gumroad validation?** (y/n) — Whether to research competitor pricing
7. **Landing page?** (y/n) — Generate a Stitch-designed landing page + deploy to Vercel (collects Gemini, Stitch, and Vercel API keys)
8. **Social media?** (y/n) — Post product to Instagram, Threads, Facebook, and Pinterest (collects Facebook Page and Pinterest tokens)

After answering, the pipeline runs automatically with real-time progress:

```
── Pipeline: 7 components ──────────────────────
  ▶️  [1/7] database...
  ▶️  [2/7] sources...
  ▶️  [3/7] csv...
  ▶️  [4/7] report...
  ▶️  [5/9] report_pdf...
  ▶️  [6/9] gumroad_research...
  ▶️  [7/9] gumroad_publish...
  ▶️  [8/9] landing_page...   (if enabled)
  ▶️  [9/9] social_promotion... (if enabled)
──────────────────────────────────────────────

  ═══════════════════════════════════════════════
    Gumroad Product Review
    Price: $29
    Files: 2 ready
  ═══════════════════════════════════════════════
  Publish to Gumroad? (y/N):
```

### Batch Mode

Create a CSV file with multiple jobs:

```csv
product_type,niche,theme,slug
research_pack,AI productivity tools for freelancers,default,ai-freelancer-tools
operating_system,Running a remote agency,luxury-dark,remote-agency-os
blog_kit,Minimalist living,editorial,minimalist-living-blog
course_launch,Python for data science,default,python-data-science
saas_docs,SaaS authentication API,minimal,auth-api-docs
```

Then run:

```bash
python main.py --batch jobs.csv
```

Each row is processed sequentially with its own progress output.

### Resume Mode

If a run fails (e.g., API timeout), resume from where it left off:

```bash
python main.py --resume outputs/<slug>/job_spec.json
```

Completed components are skipped; only pending/failed ones re-run.

---

## Product Types

The factory currently supports **7 product types**, each with a fixed set of components:

### 1. Research Pack

Best for: Market research reports, competitive analysis, deep-dive guides

| Component | Agent | Description |
|---|---|---|
| `database` | research_agent | Web research → structured JSON database of findings |
| `sources` | research_agent | Curated list of sources with annotations |
| `csv` | csv_export_agent | CSV export of research database |
| `report` | content_agent | Full written report with analysis and insights |
| `report_pdf` | render_agent | Professionally designed PDF report |
| `gumroad_research` | gumroad_agent | Competitor analysis + pricing recommendation |
| `gumroad_publish` | gumroad_agent | Product listing creation + publish (with approval) |

Outputs: `database.json`, `sources.md`, `export.csv`, `report.md`, `report.pdf`, `gumroad/research.json`

### 2. Operating System

Best for: Business playbooks, SOP collections, complete workflow systems

| Component | Agent | Description |
|---|---|---|
| `guide` | content_agent | Comprehensive guide document |
| `sops` | content_agent | Standard Operating Procedures |
| `templates` | content_agent | Reusable templates and checklists |
| `prompts` | content_agent | Prompt library for AI workflows |
| `guide_pdf` | render_agent | PDF of the guide |
| `sops_pdf` | render_agent | PDF of all SOPs |
| `notion_schema` | notion_schema_agent | Generates Notion database blueprint |
| `notion_tree` | notion_agent | Creates full Notion workspace |
| `package` | packaging_agent | Zip archive of everything |
| `gumroad_research` | gumroad_agent | Market research for pricing |
| `gumroad_publish` | gumroad_agent | Publish to Gumroad |

Outputs: `guide.pdf`, `sops.pdf`, `templates.md`, `prompts.md`, Notion workspace, `{slug}.zip`

### 3. Visual Pack

Best for: Design asset packs, brand kits, social media templates

| Component | Agent | Description |
|---|---|---|
| `image_prompts` | content_agent | AI image generation prompts |
| `catalog` | catalog_agent | Image catalog with metadata |
| `images` | visual_agent | Generated images (DALL-E or placeholders) |
| `reference_board` | render_agent | PDF mood/reference board |
| `showcase_pdf` | render_agent | Product showcase PDF |
| `package` | packaging_agent | Zip archive of all assets |

Outputs: `image_prompts.json`, `catalog.json`, `assets/images/*`, `reference_board.pdf`, `showcase.pdf`, `{slug}.zip`

### 4. Workflow Kit

Best for: Automation blueprints, CRM templates, productivity systems

| Component | Agent | Description |
|---|---|---|
| `setup_guide` | content_agent | Step-by-step setup instructions |
| `prompts` | content_agent | Workflow-specific prompt collection |
| `automation_blueprint` | content_agent | Automation architecture document |
| `workflow_diagram_src` | diagram_agent | Mermaid flowchart diagram |
| `notion_crm` | content_agent | CRM database guide with formulas |
| `setup_guide_pdf` | render_agent | PDF of setup guide |
| `diagram_pdf` | render_agent | Rendered workflow diagram PDF |
| `notion_tree` | notion_agent | Notion workspace with CRM database |
| `package` | packaging_agent | Zip archive |

Outputs: `setup_guide.pdf`, `workflow_diagram.pdf`, `notion_crm.md`, `{slug}.zip`, Notion workspace

### 5. Blog Kit

Best for: SEO-optimized blog posts, content packs, newsletter editions

| Component | Agent | Description |
|---|---|---|
| `database` | research_agent | Topic research and keyword data |
| `sources` | research_agent | Curated reference sources |
| `post_draft` | content_agent | Full blog post with structure |
| `seo_metadata` | content_agent | SEO metadata, keywords, description |
| `compilation_pdf` | render_agent | Formatted blog post PDF |
| `package` | packaging_agent | Zip archive |

Outputs: `database.json`, `sources.md`, `post_draft.md`, `seo_metadata.md`, `compilation.pdf`, `{slug}.zip`

### 6. Course Launch Kit

Best for: Online course materials, workshop curriculum, training programs

| Component | Agent | Description |
|---|---|---|
| `course_outline` | content_agent | Complete course curriculum and structure |
| `lessons` | content_agent | Detailed lesson content |
| `marketing_copy` | content_agent | Sales page copy and promotional content |
| `timeline` | content_agent | Launch timeline and milestones |
| `outline_pdf` | render_agent | PDF of course outline |
| `launch_pdf` | render_agent | PDF of launch plan |
| `notion_tree` | notion_agent | Notion workspace with course databases |
| `package` | packaging_agent | Zip archive |

Outputs: `course_outline.md`, `lessons.md`, `marketing_copy.md`, `timeline.md`, `outline.pdf`, `launch_plan.pdf`, Notion workspace, `{slug}.zip`

### 7. SaaS Documentation

Best for: API documentation, user guides, developer portals

| Component | Agent | Description |
|---|---|---|
| `api_reference` | content_agent | Complete API endpoint reference |
| `user_guide` | content_agent | Getting started guide and tutorials |
| `changelog` | content_agent | Version history and release notes |
| `docs_pdf` | render_agent | Compiled documentation PDF |
| `package` | packaging_agent | Zip archive |

Outputs: `api_reference.md`, `user_guide.md`, `changelog.md`, `docs.pdf`, `{slug}.zip`

---

## How It Works — End to End

### Step-by-step flow of a pipeline run

```
1. WIZARD
   └── User answers questions (product type, niche, theme)
   └── job_spec.json written to outputs/<slug>/

2. ORCHESTRATOR LOADS
   └── Reads job_spec.json
   └── Loads matching schema from schemas/<product_type>.json
   └── Loads job_state.json (for resumability)
   └── Builds dependency DAG, topologically sorts components

3. FOR EACH COMPONENT (in dependency order):
   ├── Check if already done (skip if resuming)
   ├── Check if all dependencies completed successfully
   │   └── If not, mark as failed and move on
   ├── Find agent function from registry
   ├── Inject renderer if component uses one
   ├── Run agent → produce output file
   ├── Save result to job_state.json
   └── Print status (✅ done / ❌ failed / ⚠️ skipped)

4. POST-PROCESSING
   └── Generate run_summary.md with all component statuses
   └── Generate Notion_Template_Link.md (if Notion sync)
   └── Generate Gumroad_Product_Link.md (if published)
   └── Generate landing page via Stitch + deploy to Vercel (if enabled)
   └── Post to social media platforms (if enabled)

5. OUTPUT
   └── All files in outputs/<slug>/
   ├── data/database.json, export.csv
   ├── content/*.md
   ├── presentation/*.pdf
   ├── templates/*.html.j2 → PDF via Playwright
   ├── notion_sync.json (if Notion sync)
   ├── gumroad/published.json (if published)
   ├── landing/index.html + deployed.json (if landing page enabled)
   ├── run_summary.md
   └── <slug>.zip — ready to sell!
```

### Dependency Resolution

The orchestrator builds a dependency graph from each component's `depends_on` field. For example, in the Research Pack, `report` depends on both `database` and `sources`, so it runs only after both are complete. This ensures correct ordering while maximizing parallelism where possible.

### Error Handling

If a component fails:
- Its status is set to `failed` with an error message
- Dependent components are blocked and marked `skipped`
- Independent components continue running
- The pipeline produces a summary of what succeeded and what failed

---

## Agents Reference

| Agent | File | Purpose | Outputs |
|---|---|---|---|---|
| `research_agent` | `agents/research_agent.py` | Web research via LLM + DuckDuckGo web search | `database.json`, `sources.md` |
| `content_agent` | `agents/content_agent.py` | LLM-generated written content via Jinja2 prompts | `*.md` reports, guides, blog posts |
| `csv_export_agent` | `agents/csv_export_agent.py` | Converts database.json to CSV | `export.csv` |
| `catalog_agent` | `agents/catalog_agent.py` | Generates image catalog metadata | `catalog.json` |
| `diagram_agent` | `agents/diagram_agent.py` | Generates Mermaid diagrams | `diagram.mmd` |
| `visual_agent` | `agents/visual_agent.py` | Generates images via DALL-E (or placeholders) | `assets/images/*` |
| `render_agent` | `agents/render_agent.js` | HTML → PDF via Playwright | `*.pdf` |
| `packaging_agent` | `agents/packaging_agent.py` | Zip archive of all outputs | `{slug}.zip` |
| `notion_schema_agent` | `agents/notion_schema_agent.py` | LLM-generated Notion database blueprint | `data/notion_schema.json` |
| `notion_agent` | `agents/notion_agent.py` | Creates databases, sample entries + page tree | Notion workspace |
| `gumroad_agent` | `agents/gumroad_agent.py` | Gumroad market research + product publishing | `gumroad/research.json`, `gumroad/published.json` |
| `landing_agent` | `agents/landing_agent.py` | Gemini image gen → Stitch HTML → Vercel deploy | `landing/index.html`, `landing/deployed.json` |
| `social_agent` | `agents/social_agent.py` | LLM copy gen → FB/IG/Threads/Pinterest posts | `landing/social_results.json` |

### Agent Contract

Every agent follows the same signature:

```python
def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    ...
```

- `component` — What to build, its dependencies, its output path
- `job_spec` — The overall job (slug, niche, product type, theme)
- `context` — Outputs of already-completed dependencies (file paths)
- Returns `AgentResult` with `status`, `output_path`, and optional `error`

---

## Output Structure

Every run produces a folder under `outputs/<slug>/`:

```
outputs/<slug>/
├── job_spec.json          # The run configuration
├── job_state.json         # Per-component status (for resume)
├── run_summary.md         # Summary of what was built
├── data/
│   ├── database.json      # Research data (if applicable)
│   ├── export.csv         # CSV export
│   └── notion_schema.json # Notion blueprint (if generated)
├── content/
│   ├── report.md          # Main report/document
│   ├── sources.md         # Source references
│   ├── seo_metadata.md    # SEO data
│   └── ... (product-specific content)
├── presentation/
│   ├── report.pdf         # Rendered PDF
│   ├── guide.pdf
│   ├── showcase.pdf
│   ├── Notion_Template_Link.md  # Notion workspace link
│   ├── Gumroad_Product_Link.md  # Gumroad product link
│   └── ...
├── gumroad/
│   ├── research.json      # Competitor analysis
│   └── published.json     # Publish result
├── landing/               # Landing page (if enabled)
│   ├── index.html         # Generated landing page HTML
│   ├── deployed.json      # Vercel deploy result
│   ├── social_results.json # Social media post results
│   └── images/            # Gemini-generated cover images
├── assets/                # Images (for Visual Pack)
├── notion_sync.json       # Notion sync result
└── <slug>.zip             # Packaged product, ready to sell
```

---

## Notion Integration

The Notion integration is a key differentiator — it creates a **complete, interactive workspace** in Notion that the product recipient can duplicate into their own account.

### One-time setup

1. Go to https://www.notion.so/my-integrations
2. Create a new "Internal Integration"
3. Copy the `NOTION_API_KEY` (starts with `secret_...`)
4. Create a page in Notion called "Digital Product Factory Root"
5. Share that page with your integration (invite the integration via the Share menu)
6. Copy the page ID from the URL (32-character hex string in the URL after the workspace name)
7. Add both to `.env`

### What gets created

When you run a product with `notion_sync: true`:

```
Notion Parent Page (shared with integration)
└── 📋 AI Tools for Freelancers (Research Pack)
    ├── 🏢 Root workspace page with cover image
    ├── 📦 Template Products (database)
    │   ├── Sample Alpha    ← 4-5 sample entries
    │   ├── Sample Beta
    │   ├── Sample Gamma
    │   ├── Sample Delta
    │   └── Sample Epsilon
    ├── 💰 Sales & Invoices (database) with 5 sample entries
    ├── 🛠️ Development Tasks (database) with 5 sample entries
    ├── 🔍 QA Issue Tracker (database) with 5 sample entries
    └── 🎧 Customer Support (database) with 5 sample entries
    └── 📑 Notion Template — How to Use (instructions page)
        ├── Welcome message
        ├── Database descriptions (bold names)
        ├── How to duplicate the workspace
        └── Sample data explanation
```

### Features

- **Emoji icons** on every database (auto-selected based on database name)
- **Cover images** on the root page and template page
- **Colored select options** (10 colors cycle through options)
- **Relations** between databases (e.g., Sales → Product)
- **Sample entries** (4-5 realistic rows per database)
- **How-to-use guide** page with bold database names and numbered instructions

---

## Gumroad Publishing

The Gumroad integration adds end-to-end publishing capability — from market research to product listing.

### How it works

1. **`gumroad_research`** — After all content is generated, the agent:
   - Fetches the seller's existing products from Gumroad API
   - Analyzes competitor products in the same niche
   - Recommends optimal pricing based on market data
   - Suggests which product type is most likely to sell

2. **`gumroad_publish`** — Before publishing, the agent:
   - Shows a review summary with suggested price and file list
   - **Waits for manual approval** (asks `y/N` on the command line)
   - Creates the product on Gumroad with name, price, and description
   - Saves the published product URL

### Smart product type selection

When Gumroad is enabled and the wizard offers validation:
- User suggests a product type (via wizard)
- The `gumroad_research` agent validates against real Gumroad market data
- If the data suggests a different product type would sell better, it's noted in the research output

### Graceful degradation

If `GUMROAD_ACCESS_TOKEN` is not configured, the gumroad components are skipped with a warning — the rest of the pipeline completes normally.

### Landing Page (Post-Publish)

After Gumroad publishes, if enabled in the wizard, the pipeline generates a **landing page** for the product:

1. **Gemini 3.1 Flash** generates a cover image (16:9, clean product shot)
2. **LLM** writes a design prompt for Google Stitch, embedding the image URL and Gumroad link
3. **Stitch API** (`generate_screen_from_text`) returns HTML for a premium landing page
4. **LLM** refines the HTML — injects a Gumroad "Buy Now" CTA button, fixes responsiveness
5. **Vercel API** deploys the HTML to a Vercel project (`https://df-<slug>.vercel.app`)

If any API key is missing, the agent degrades gracefully: fallback HTML template (if Stitch unavailable), local file save (if Vercel unavailable).

### Social Media Promotion

If social promotion is enabled, the pipeline posts the product to **Instagram, Threads, Facebook, and Pinterest**:

1. **LLM** generates platform-specific copy (captions, hashtags, post text) — different tone per platform
2. **Facebook Graph API** posts to Facebook Page, Instagram Business Account, and Threads
3. **Pinterest API** creates a Pin with product link and description

Each platform is wrapped in try/except — one platform failure doesn't block the others. Requires a Facebook Page connected to Instagram and Threads via Meta Business Suite.

---

## Templates & Themes

### Visual Themes

Four built-in themes change the look and feel of all PDF outputs:

| Theme | Description |
|---|---|
| `default` | Clean, professional design |
| `luxury-dark` | Dark mode with accent colors |
| `editorial` | Magazine-style layout |
| `minimal` | Minimalist, maximum whitespace |

### Template System

PDFs are generated from Jinja2 HTML templates in `/templates/`:

```
templates/
├── research_pack/
│   └── report.html.j2         # Research report layout
├── visual_pack/
│   ├── reference_board.html.j2  # Mood board layout
│   └── showcase.html.j2        # Product showcase layout
├── workflow_kit/
│   └── diagram.html.j2         # Diagram page layout
├── landing/
│   └── basic.html.j2           # Fallback landing page (when Stitch unavailable)
└── shared/
    ├── base.css                 # Global styles (shared across all themes)
    └── basic_doc.html.j2        # Generic document template
```

Features:
- Auto-generated Table of Contents from markdown headings
- Mermaid diagram rendering (injected CDN → Playwright renders to PDF)
- Unicode heading ID normalization
- Code block syntax highlighting

---

## Tech Stack

### Languages & Frameworks

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| LLM Provider | Anthropic Claude (via `anthropic` SDK) |
| Image Generation | Gemini 3.1 Flash / DALL-E 3 |
| Landing Page | Google Stitch (`generate_screen_from_text`) |
| Deployment | Vercel API (`/v12/deployments`) |
| Social API | Facebook Graph API v21.0 + Pinterest REST API v5 |
| PDF Rendering | Playwright (Chromium headless) |
| Templates | Jinja2 |
| CLI | `typer` |
| Notion | `notion-client` SDK |
| Schemas | Pydantic v2 |
| Web Search | DuckDuckGo via `httpx` |
| Diagrams | Mermaid → SVG → PDF |
| Config | `python-dotenv` |

### Key Dependencies

```
pydantic>=2.0.0       # Schema validation
python-dotenv>=1.0.0  # Environment config
typer>=0.9.0          # CLI prompts
anthropic>=0.30.0     # LLM access
jinja2>=3.1.0         # HTML templates
playwright>=1.40.0    # PDF rendering
notion-client>=2.2.1  # Notion API
openai>=1.10.0        # Image generation
markdown>=3.5.0       # Markdown→HTML for PDFs
httpx>=0.25.0         # HTTP for web search
```

---

## Development

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_agents.py -v

# Run with coverage
pytest tests/ --cov=agents --cov=orchestrator
```

### Adding a New Product Type

1. Create `schemas/new_type.json` with component definitions
2. Create Jinja2 templates in `templates/new_type/`
3. Create any needed prompt templates in `prompts/`
4. Register any new agents in `agents/registry.py`

No orchestrator code changes needed — the system reads the schema dynamically.

### Adding a New Agent

1. Create `agents/my_agent.py` with a `run(component, job_spec, context)` function
2. Add `my_agent.run` to `agents/registry.py`
3. Reference it in any schema file as `"agent": "my_agent"`
4. Create corresponding Jinja2 prompt if needed in `prompts/`

### Code Conventions

- Type hints everywhere
- Pydantic v2 for models
- Structured logging (`logging` module, no `print()`)
- All file opens use `encoding="utf-8"`
- Functions are plain functions, not classes (except Orchestrator)
- Follow existing patterns in neighboring files

---

## FAQ

### Do I need an API key to run this?

Yes, you need at minimum an **Anthropic API key** for LLM access. Notion and Gumroad are optional.

### How much does each run cost?

Cost depends on LLM token usage. A typical Research Pack uses ~50K–100K input tokens + ~10K–20K output tokens across all agents. At current Anthropic API pricing, this is roughly $0.50–$1.00 per run.

### Can I sell the outputs?

Yes! That's the purpose of the factory. Everything generated is yours to sell on Gumroad, Notion template marketplaces, or any other platform.

### Does the Notion workspace have sample data?

Yes — each database comes with 4-5 pre-populated example entries so buyers can immediately understand the structure.

### Can I run this without Notion or Gumroad?

Yes. Simply leave those fields blank in `.env` — the pipeline runs fully without them, generating all content, PDFs, and zip packages locally.

### Do I need Stitch, Vercel, or Facebook API keys?

No. Landing page and social promotion are optional — the wizard asks before collecting keys. If you skip them, the pipeline completes without those steps. If you enable them but a key is missing, the agents gracefully degrade (fallback template, local save).

### How are images generated for the landing page?

The landing agent uses **Gemini 3.1 Flash** (image generation modality) to generate a cover image and optional product mockups. This replaces DALL-E for landing page images. The image count is per-run ("kit-wise") — minimum 1 cover image, additional images added if the LLM decides they're needed.

### Which social platforms are supported?

Instagram, Threads, Facebook (via Facebook Graph API v21.0) and Pinterest (via Pinterest REST API v5). Each requires a connected Meta Business Suite setup for IG/Threads posting.

### What if a component fails?

The orchestrator catches the error, marks that component as `failed`, and continues with any components whose dependencies are still satisfied. Run `--resume` after fixing the issue to pick up where you left off.

### Can I run multiple niches at once?

Yes — use `--batch jobs.csv` with a CSV file containing one row per job.

### What does "schema-driven" mean?

Every product type is defined as a JSON file (`schemas/*.json`) that lists all its components, their dependencies, and their output paths. The orchestrator reads this file — there's no hardcoded logic for each product type. To add a new type, you just add a JSON file.
