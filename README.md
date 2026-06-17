# Digital Product Factory

An automated AI pipeline that researches market niches, generates complete digital products (reports, templates, courses, databases, prompt packs, and more), packages them, publishes to Gumroad via a pluggable Channel Layer, deploys landing pages to Vercel, promotes on social media, and syncs to Notion — all from a single CLI command.

## Architecture

```
User Input (CLI wizard / batch CSV)
         │
         ▼
    Orchestrator ─── loads Product Schema → component DAG
         │
          ├── market_agent      → Real-time web research + competitor analysis
          ├── offer_scoring_agent → Deterministic scoring across 15+ product types
         ├── image_agent       → Cover, thumbnail, & section images (Imagen/Gemini/SVG)
         ├── notion_schema_agent → Notion database blueprint (LLM-generated)
         ├── notion_agent      → Creates Notion workspace with databases & relations
         ├── content_agent     → Markdown content via LLM + Jinja2 prompts
         ├── render_agent      → Markdown → HTML → PDF (Playwright Chromium)
         ├── csv_export_agent  → JSON → CSV / XLSX
         ├── catalog_agent     → Prompt/resource catalogs as JSON
         ├── diagram_agent     → Mermaid.js diagrams
         ├── evaluation_agent → Quality validation (pattern checks + LLM hallucination detection)
         ├── review_agent     → Human-in-the-loop review logs for flagged content
          ├── packaging_agent   → ZIP all deliverables
          ├── landing_agent     → Design Intelligence + LLM → HTML → ZIP → Vercel deploy
          ├── social_agent      → Calendar + sequences + repurposing + platform adaptation
          └── analytics_agent   → Sales records + insights + feedback loop
              └── social/       → models, calendar, sequences, repurposing, engagement,
                                  platform_strategy, automation, scheduler
                                  → Facebook / Instagram / Threads / Pinterest
                                  │
                                  ▼
     Channel Layer ──── runs after pipeline, consumes artifacts
          │
          ├── gumroad_listing  → Tag/pricing/AIDA optimization from market research
          ├── gumroad_analytics → Analytics pull + listing quality scoring
          ├── gumroad_ab_testing → Cover/thumbnail variant management
          └── gumroad_channel  → Publish product + files to Gumroad API
```

## Key Features

- **Channel Layer** — Pluggable publishing abstraction: `BaseChannel` ABC, `GumroadChannel`, `CHANNEL_REGISTRY`. Channels run after the pipeline, consuming artifacts instead of being embedded in schemas. Easy to add new channels (Etsy, Shopify).
- **Listing Optimization** — Auto-optimizes Gumroad tags (from competitor research), pricing (median from marketplace data), and descriptions (AIDA framework via LLM) before publishing.
- **Listing Quality Score** — Post-publish quality check across 5 weighted dimensions (description, tags, cover, price, research alignment) with pass/fail gate.
- **Analytics Pull** — `get_analytics()` on `GumroadChannel` returns structured `AnalyticsData` (views, sales, revenue, refunds, conversion rate).
- **Cover/Thumbnail A/B Testing** — Multiple variant support with persistence and round-robin cycling on publish runs.
- **Discovery Mode** — Enter just a niche; the system researches and recommends the best product type via data-driven scoring (6 weighted metrics, 15+ product types)
- **Offer Scoring Engine** — Deterministic scoring framework (`orchestrator/scoring.py`) evaluates niche data against weighted metrics using real marketplace signals from Etsy and Gumroad — no LLM opinion, pure data
- **16 Product Schemas** — Research Pack, Blog Kit, Visual Pack, SaaS Docs, Course Launch Kit, Operating System, Workflow Kit, Curated Database, SOP Pack, Prompt Pack, Resource Pack, Swipe File, Checklist, Excel Template, Boilerplate, and discovery
- **Design Intelligence** — Landing pages generated via LLM + curated design skill rules (6 rule files, 12 design vibes, 12 layout patterns) — no external design service dependency
- **Multi-Format Delivery** — Agents produce CSV + XLSX, recommended formats based on niche analysis
- **Quality Validation** — Pattern-based checks (AI-isms, word count, empty sections) + LLM hallucination cross-referencing with auto-retry on failure
- **Social Strategy** — Multi-post sequences with 7–14 day content calendars per launch; content repurposing extracts 10+ posts from one pack; platform-specific adaptation per platform rules
- **Engagement Tracking** — Post-performance metrics (likes, comments, shares, impressions) via Graph API with engagement rate calculation
- **DM/Comment Automation** — Webhook-based auto-reply for Facebook/Instagram with trigger phrase detection
- **Cross-Product Analytics** — Post-pipeline analytics agent aggregates sales data from all channels, deduplicates, and computes insights (top products, best channel, monthly revenue trends)
- **Feedback Loop** — Past performance data injected into market research prompts and scoring weight adjustments; each run learns from previous runs
- **CLI Dashboard** — `python -m cli.dashboard` displays sales summary with ASCII bar charts and formatted insights
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
│   ├── wizard.py                # Interactive CLI wizard
│   └── dashboard.py             # Analytics dashboard (Phase 5)
│
├── orchestrator/
│   ├── models.py                # Pydantic models (ComponentSpec, JobSpec, QualityReport, etc.)
│   ├── orchestrator.py          # Core pipeline engine + quality validation gate
│   ├── scoring.py               # Offer scoring engine (6 weighted metrics, deterministic)
│   ├── quality.py               # Quality scoring criteria (word count, AI-isms, headings, etc.)
│   ├── notify.py                # Alert dispatch (log + optional webhook)
│   ├── state.py                 # Job state persistence
│   ├── analytics_models.py      # SalesRecord + Insights models, JSON persistence (Phase 5)
│   └── feedback_loop.py         # Past perf → market prompts + scoring adjustments (Phase 5)
│
├── agents/
│   ├── registry.py              # Agent function registry
│   ├── llm_client.py            # Unified LLM caller (OpenAI SDK)
│   ├── market_agent.py          # Market research (web, Reddit, news, trends, Etsy, Gumroad)
│   ├── offer_scoring_agent.py   # Deterministic product type scoring
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
│   ├── evaluation_agent.py      # Quality validation + hallucination detection
│   ├── review_agent.py          # Human-in-the-loop review logs
│   ├── gumroad_agent.py         # Gumroad market research (publish → channels/)
│   ├── landing_agent.py         # Landing page HTML + deploy
 │   ├── social_agent.py          # Social media promotion (Phase 4: strategy)
 │   ├── analytics_agent.py       # Analytics collection + insights (Phase 5)
 │   └── social/                  # Social strategy modules
 │       ├── __init__.py
 │       ├── models.py            # SocialPost, ContentCalendar, PostResult, etc.
 │       ├── calendar.py          # 7-14 day content calendars
 │       ├── sequences.py         # Multi-post sequence templates
 │       ├── repurposing.py       # 1 pack → 10+ social posts
 │       ├── engagement.py        # Post-performance tracking
 │       ├── platform_strategy.py # Platform-specific content rules
 │       ├── automation.py        # DM/comment webhooks
 │       └── scheduler.py         # Post queue + dispatch
│
├── channels/
│   ├── __init__.py              # CHANNEL_REGISTRY + model exports
│   ├── base.py                  # BaseChannel ABC, ProductArtifact, PublishResult, AnalyticsData, ListingQualityScore
│   ├── gumroad_channel.py       # GumroadChannel (publish via presigned uploads)
│   ├── gumroad_listing.py       # Tag/pricing/AIDA optimization (consumes market_research.json)
│   ├── gumroad_analytics.py     # Analytics pull + listing quality scoring
│   └── gumroad_ab_testing.py    # Cover/thumbnail A/B variant management
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
├── tests/                       # 230+ pytest tests (70 added in Phase 4-5)
└── docs/superpowers/            # Design specs & implementation plans
```

## Testing

```bash
pytest tests/ -v
```

Test coverage includes: orchestrator logic (execution order, error isolation, schema switching, notion-only, channel publishing), all agents (with API mocks), channel base ABC + GumroadChannel, schema validation (all 16 schemas), scoring engine (14 tests across 6 weighted metrics), multi-format delivery, pipeline plan merging, listing optimization (tags, pricing, AIDA), analytics pull + quality scoring, A/B variant management, social strategy (60 tests across calendar, sequences, repurposing, engagement, platform strategy, automation, scheduler modules), analytics models (9 tests), analytics agent (5 tests), dashboard (5 tests), feedback loop (14 tests).

## Output Structure

Pipeline-wide analytics are stored in `outputs/_analytics/` (aggregated across all runs). Each run produces files under `outputs/{slug}/`:

```
outputs/_analytics/
├── sales_records.json           # Aggregated sales from all channels (deduped)
└── insights.json                # Top products, avg conversion, best channel, trends

outputs/{slug}/
├── job_spec.json                # Original run configuration
├── job_state.json               # Pipeline state (resumable)
├── run_summary.md               # Component status report
├── quality-report.json          # Quality evaluation results per component
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
│   └── research.json            # Gumroad competitor analysis (publish results stored by channel)
├── landing/
│   ├── index.html               # Landing page HTML
│   └── images/                  # Landing page images
├── review/
│   └── *._review.md             # Human-in-the-loop review logs
├── presentation/
│   └── Notion_Template_Link.md  # Notion template link
└── social_results.json          # Social media post results
```

## License

MIT
