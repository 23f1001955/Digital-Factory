# Digital Product Factory

An automated AI pipeline that researches market niches, generates complete digital products (reports, templates, courses, databases, prompt packs, and more), packages them, publishes to Gumroad, deploys landing pages to Vercel, promotes on social media, and syncs to Notion — all from a single CLI command.

## Architecture

```
User Input (CLI wizard / batch CSV)
         │
         ▼
    Orchestrator ─── loads Product Schema → component DAG
         │
         ├── market_agent      → Real-time web research + competitor analysis
         ├── image_agent       → Cover, thumbnail, & section images (Imagen/Gemini/SVG)
         ├── notion_schema_agent → Notion database blueprint (LLM-generated)
         ├── notion_agent      → Creates Notion workspace with databases & relations
         ├── content_agent     → Markdown content via LLM + Jinja2 prompts
         ├── render_agent      → Markdown → HTML → PDF (Playwright Chromium)
         ├── csv_export_agent  → JSON → CSV / XLSX
         ├── catalog_agent     → Prompt/resource catalogs as JSON
         ├── diagram_agent     → Mermaid.js diagrams
         ├── gumroad_agent     → Research → Publish to Gumroad (files, images, rich content)
         ├── landing_agent     → Design Intelligence + LLM → HTML → ZIP → Vercel deploy
         ├── social_agent      → Copy + images → Facebook / Instagram / Threads / Pinterest
         └── packaging_agent   → ZIP all deliverables
```

## Key Features

- **Discovery Mode** — Enter just a niche; the system researches and recommends the best product type
- **16 Product Schemas** — Research Pack, Blog Kit, Visual Pack, SaaS Docs, Course Launch Kit, Operating System, Workflow Kit, Curated Database, SOP Pack, Prompt Pack, Resource Pack, Swipe File, Checklist, Excel Template, Boilerplate, and discovery
- **Design Intelligence** — Landing pages generated via LLM + curated design skill rules (6 rule files, 12 design vibes, 12 layout patterns) — no external design service dependency
- **Multi-Format Delivery** — Agents produce CSV + XLSX, recommended formats based on niche analysis
- **Dynamic Pipeline** — Market research LLM generates custom pipeline components per niche
- **Notion-Only Mode** — Generate standalone Notion template products
- **Resumable** — Failed pipelines resume from last successful component
- **Batch Mode** — Process multiple products from a CSV file

## Requirements

- Python 3.10+
- [Playwright Chromium](https://playwright.dev/python/) (for PDF generation)
- API keys (see [Environment Variables](#environment-variables))

## Quick Start

```bash
# Clone and enter
git clone <repo-url>
cd digital-factory

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser for PDF rendering
python -m playwright install chromium

# Set up environment
cp .env.example .env
# Edit .env with your API keys (at minimum: ANTHROPIC_API_KEY or OPENAI_API_KEY)

# Run interactive wizard
python main.py
```

## Usage

### Interactive Mode
```bash
python main.py
```
Prompts for: niche, display name, product type, theme, Notion sync, Gumroad publishing, landing page, social media promotion.

### Batch Mode
```bash
python main.py --batch products.csv
```
CSV columns: `product_type, niche, theme, slug, notion_sync, gumroad_enabled, landing_page_enabled, social_promotion_enabled, call_to_action`

### Resume Mode
```bash
python main.py --resume outputs/my-slug/job_spec.json
```
Continues a previously interrupted pipeline from its last successful component.

## Environment Variables

### Required
| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | LLM calls (primary) |
| `OPENAI_API_KEY` | LLM calls (fallback) |

### Conditional (based on features enabled)
| Variable | Feature | Purpose |
|----------|---------|---------|
| `NOTION_API_KEY` | Notion sync | Notion API access |
| `NOTION_PARENT_PAGE_ID` | Notion sync | Parent page for workspace |
| `GUMROAD_ACCESS_TOKEN` | Gumroad publish | Gumroad API |
| `GEMINI_API_KEY` | Image gen / Landing | Image generation |
| `IMAGEN_API_KEY` | Image gen | Alternative image gen |
| `IMAGEN_API_URL` | Image gen | Cloudflare Worker URL |
| `VERCEL_TOKEN` | Landing deploy | Vercel deployment |
| `FIRECRAWL_API_KEY` | Market research | Full page scraping |
| `BRAVE_API_KEY` | Market research | Brave Search API |
| `REDDIT_CLIENT_ID` | Market research | Reddit OAuth |
| `REDDIT_CLIENT_SECRET` | Market research | Reddit OAuth |
| `NEWSAPI_KEY` | Market research | NewsAPI |
| `FACEBOOK_PAGE_TOKEN` | Social promo | Facebook posting |
| `FACEBOOK_PAGE_ID` | Social promo | Facebook page |
| `INSTAGRAM_USER_ID` | Social promo | Instagram posting |
| `THREADS_USER_ID` | Social promo | Threads posting |
| `PINTEREST_TOKEN` | Social promo | Pinterest posting |
| `PINTEREST_BOARD_ID` | Social promo | Pinterest board |

## Product Schemas

| Schema | Components | Best For |
|--------|-----------|----------|
| `discovery` | market only | Product type discovery |
| `research_pack` | all standard | Reports, guides, white papers |
| `blog_kit` | all standard | Blog content packages |
| `visual_pack` | all standard | Design templates, graphics |
| `saas_docs` | all standard | Software documentation |
| `course_launch` | standard + notion | Online courses, workshops |
| `operating_system` | standard + notion | Business OS, templates |
| `workflow_kit` | standard + notion | Automation workflows |
| `database` | market → csv_export | Curated resource databases |
| `sop_pack` | market → content → render | Standard operating procedures |
| `prompt_pack` | market → catalog | AI prompt collections |
| `resource_pack` | market → catalog | Curated resource lists |
| `swipe_file` | market → content → render | Copywriting examples |
| `checklist` | market → content → render + notion | Action checklists |
| `excel_template` | market → content → csv_export | Spreadsheet templates |
| `boilerplate` | market → content → package | Code/contract templates |

## Project Structure

```
digital-factory/
├── main.py                      # Entry point
├── requirements.txt             # Dependencies
├── .env                         # Runtime secrets (gitignored)
├── .env.example                 # Environment template
│
├── cli/
│   └── wizard.py                # Interactive CLI wizard
│
├── orchestrator/
│   ├── models.py                # Pydantic models (ComponentSpec, JobSpec, etc.)
│   ├── orchestrator.py          # Core pipeline engine
│   └── state.py                 # Job state persistence
│
├── agents/
│   ├── registry.py              # Agent function registry
│   ├── llm_client.py            # Unified LLM caller (OpenAI SDK)
│   ├── market_agent.py          # Market research (web, Reddit, news, trends)
│   ├── research_tools.py        # Research data source library
│   ├── research_agent.py        # Legacy research
│   ├── content_agent.py         # Markdown content generation
│   ├── render_agent.py          # PDF rendering (Playwright)
│   ├── packaging_agent.py       # ZIP packaging
│   ├── csv_export_agent.py      # CSV/XLSX export
│   ├── catalog_agent.py         # Prompt/resource catalogs
│   ├── image_agent.py           # Image management
│   ├── visual_agent.py          # Pre-prompted image generation
│   ├── notion_agent.py          # Notion workspace creator
│   ├── notion_content_agent.py  # Notion content writer
│   ├── notion_schema_agent.py   # Notion blueprint generator
│   ├── diagram_agent.py         # Mermaid diagram generator
│   ├── gumroad_agent.py         # Gumroad research + publish
│   ├── landing_agent.py         # Landing page HTML + deploy
│   └── social_agent.py          # Social media promotion
│
├── design_intelligence/
│   ├── models.py                # LandingPattern, DesignBrief
│   ├── registry.py              # Vibe-to-rules mapping
│   ├── brief.py                 # Design brief generator (deterministic)
│   ├── rules/                   # 6 design skill rule files
│   │   ├── impeccable.md
│   │   ├── frontend-design.md
│   │   ├── frontend-design2.md
│   │   ├── design-taste-frontend.md
│   │   ├── gpt-taste.md
│   │   └── ui-ux-pro-max.md
│   └── data/
│       └── landing_patterns.csv # 12 layout patterns
│
├── schemas/                     # 16 JSON product schemas
├── prompts/                     # 33 Jinja2 prompt templates
├── templates/                   # HTML/CSS render templates
├── renderers/                   # PDF rendering engines
├── tests/                       # 30+ pytest tests
└── docs/superpowers/            # Design specs & implementation plans
```

## Testing

```bash
pytest tests/ -v
```

Test coverage includes: orchestrator logic (execution order, error isolation, schema switching, notion-only), all agents (with API mocks), schema validation (all 16 schemas), multi-format delivery, pipeline plan merging.

## Output Structure

Each run produces files under `outputs/{slug}/`:

```
outputs/{slug}/
├── job_spec.json                # Original run configuration
├── job_state.json               # Pipeline state (resumable)
├── run_summary.md               # Component status report
├── data/
│   ├── market_research.json     # Competitors, pricing, design recs, pipeline plan
│   └── images_generated.json    # Image URLs
├── assets/
│   ├── cover.png                # Product cover image
│   └── thumbnail.png            # Product thumbnail
├── content/*.md                 # Generated markdown content
├── content/*.pdf                # Rendered PDF documents
├── data/*.csv / *.xlsx          # CSV/Excel exports
├── gumroad/
│   ├── research.json            # Gumroad competitor analysis
│   └── published.json           # Gumroad publish results
├── landing/
│   ├── index.html               # Landing page HTML
│   └── images/                  # Landing page images
├── presentation/
│   └── Notion_Template_Link.md  # Notion template link
└── social_results.json          # Social media post results
```

## License

MIT
