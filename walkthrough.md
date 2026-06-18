# Digital Factory — Walkthrough

## What We've Built

An automated AI pipeline that researches market niches, generates complete digital products (reports, templates, courses, databases, prompt packs, and more), packages them, publishes to Gumroad, deploys landing pages to Vercel, promotes on social media, and syncs to Notion — all from a single CLI command.

---

## Pipeline Flow

```mermaid
flowchart TB
    subgraph Input["Input Layer"]
        A1["CLI Wizard<br/><i>interactive Typer prompts</i>"]
        A2["Batch CSV<br/><i>multi-product via --batch</i>"]
        A3["Resume Mode<br/><i>--resume from last state</i>"]
    end

    subgraph Core["Orchestrator Engine"]
        B["Orchestrator<br/><i>DAG topological sort<br/>error isolation • resumable state<br/>dynamic pipeline expansion</i>"]
        C["Product Schema<br/><i>16 JSON schemas define<br/>component DAG per product type</i>"]
        D["Job State<br/><i>JSON persistence per component<br/>enables resume on failure</i>"]
    end

    subgraph Research["Research & Scoring"]
        E["market_agent<br/><i>Web • Reddit • News • Trends • GDelt • Etsy • Gumroad<br/>Firecrawl deep scrape • competitor analysis<br/>→ market_research.json</i>"]
        E2["offer_scoring_agent<br/><i>6 weighted metrics • deterministic scoring<br/>Etsy/Gumroad marketplace data<br/>→ scored_recommendations[]</i>"]
        F["research_agent<br/><i>legacy research agent</i>"]
    end

    subgraph Content["Content Generation"]
        G["content_agent<br/><i>LLM + Jinja2 prompt templates<br/>→ extensive Markdown</i>"]
        H["catalog_agent<br/><i>prompt/resource collections<br/>→ structured JSON catalogs</i>"]
        I["csv_export_agent<br/><i>tabular data → CSV / XLSX</i>"]
    end

    subgraph Visuals["Media & Visuals"]
        J["image_agent<br/><i>Imagen → Gemini → SVG fallback<br/>→ cover.png, thumbnail.png</i>"]
        K["visual_agent<br/><i>secondary image generation</i>"]
        L["diagram_agent<br/><i>Mermaid.js code generation<br/>→ *.mmd diagrams</i>"]
    end

    subgraph Rendering["Rendering & Formatting"]
        M["render_agent<br/><i>Markdown → Jinja2 HTML/CSS<br/>→ Playwright PDF → *.pdf</i>"]
        N["renderers/<br/><i>PlaywrightRenderer (active)<br/>AntigravityRenderer (stub)</i>"]
    end

    subgraph Quality["Quality Validation"]
        QA["evaluation_agent<br/><i>pattern checks • AI-ism detection<br/>LLM hallucination cross-ref<br/>→ quality-report.json</i>"]
        QB["review_agent<br/><i>human-in-the-loop review logs<br/>when hallucination flags found</i>"]
        QC["orchestrator/quality.py<br/><i>scoring criteria • thresholds<br/>25 AI-ism patterns</i>"]
        QD["orchestrator/notify.py<br/><i>alert dispatch • optional<br/>QUALITY_WEBHOOK_URL</i>"]
    end

    subgraph Notion["Notion Integration"]
        O["notion_schema_agent<br/><i>LLM designs database architecture<br/>→ notion_schema.json</i>"]
        P["notion_agent<br/><i>Notion API: creates databases,<br/>properties, relations, pages</i>"]
        Q["notion_content_agent<br/><i>pushes markdown as Notion blocks<br/>used in notion_only mode</i>"]
    end

    subgraph Publishing["Packaging, Publishing & Promotion"]
        R["packaging_agent<br/><i>collects all deliverables from<br/>_delivery_map → {slug}.zip</i>"]
        S["gumroad_agent<br/><i>Gumroad market research only<br/>(publish moved to channel layer)</i>"]
        T["landing_agent<br/><i>Design Intelligence brief →<br/>LLM HTML → Vercel deploy</i>"]
        U["social_agent + social/ package<br/><i>Phase 4 strategy: calendar → sequences<br/>→ repurpose → adapt → schedule → dispatch<br/>social/ (models, calendar, sequences,<br/>repurposing, engagement, platform_strategy,<br/>automation, scheduler)</i>"]
    end

    subgraph Channels["Channel Layer (post-pipeline)"]
        X["gumroad_channel<br/><i>GumroadChannel extends BaseChannel<br/>product create/update → presigned<br/>file upload → cover + thumbnail<br/>→ rich content → publish</i>"]
        Y["channels/base.py<br/><i>BaseChannel ABC with<br/>validate/publish/update/get_analytics</i>"]
    end

    subgraph DesignIntelligence["Design Intelligence"]
        V["design_intelligence/<br/><i>6 design skill rules • 12 vibes<br/>12 layout patterns • brief generator</i>"]
    end

    subgraph Outputs["Output Artifacts"]
        W1["outputs/{slug}/<br/>market_research.json"]
        W2["outputs/{slug}/<br/>content/*.md"]
        W3["outputs/{slug}/<br/>content/*.pdf"]
        W4["outputs/{slug}/<br/>assets/cover.png"]
        W5["outputs/{slug}/<br/>data/*.csv/*.xlsx"]
        W6["outputs/{slug}/<br/>{slug}.zip"]
        W7["outputs/{slug}/<br/>gumroad/research.json"]
        W8["outputs/{slug}/<br/>landing/index.html"]
        W9["PublishResult<br/><i>status • product_url • product_id</i>"]
    end

    A1 --> B
    A2 --> B
    A3 --> B
    B --> C
    B --> D

    B --> E
    E -->|"pipeline plan merge<br/>format recommendations"| B
    E2 -->|"schema switch<br/>(scored_recommendations)"| B
    E --> E2
    E --> F
    E --> S
    E2 --> G
    E --> H
    E --> I

    G --> J
    G --> L
    G --> M
    M --> N
    H --> M

    G -.->|"quality gate"| QA
    H -.->|"quality gate"| QA
    I -.->|"quality gate"| QA
    J -.->|"quality gate"| QA
    L -.->|"quality gate"| QA
    M -.->|"quality gate"| QA
    E -.->|"quality gate"| QA
    QA -->|"score < 0.6 → fix prompt → retry (max 2)"| G
    QA -->|"needs_human_review → log"| QB
    QA --> QC
    QA --> QD

    E --> O
    O --> P
    P --> Q

    J --> R
    G --> R
    M --> R
    I --> R
    L --> R
    Q --> R

    G --> T
    V --> T
    T --> U

    R -.->|"post-pipeline"| X
    Y -.->|"BaseChannel"| X
    U -.->|"post-pipeline"| X

    B --> W1
    S --> W7
    G --> W2
    M --> W3
    J --> W4
    I --> W5
    R --> W6
    T --> W8
    X --> W9
```

---

## Execution Order (Typical Research Pack)

```
market_research ──→ images ──→ content ──→ render ──→ package
                      │                      │
                      ├── csv_export ─────────┘
                      ├── diagram ─────────────┘
                      └── catalog ─────────────┘

notion_schema ──→ notion_tree ──→ notion_content  (parallel branch)

gumroad_research  (research only — publish via channel layer)
landing_page  (after content)
social_promotion  (after landing_page)

[Pipeline Complete]
       │
       ▼
Channel Layer ──→ gumroad_channel.publish(artifacts)
                   → product_url injected into context
                     (consumed by landing/social if not already set)
```

### Discovery Mode Execution

```
market_research ──→ offer_scoring ──→ _switch_schema (picks best product type)
                                         │
                                         ▼
                              rest of pipeline (dynamic, based on chosen schema)
```

In discovery mode, the orchestrator runs `offer_scoring` after `market_research`. The scoring engine evaluates 15+ product types against 6 weighted metrics and the orchestrator switches to the highest-scored schema (threshold ≥ 50/100) before continuing the pipeline.

---

## 16 Product Schemas

| Schema | Key Path | Notion Sync |
|--------|----------|-------------|
| `discovery` | market → switch | ❌ |
| `research_pack` | market → content → render → package | optional |
| `blog_kit` | market → content → render → package | optional |
| `visual_pack` | market → image → render → package | optional |
| `saas_docs` | market → content → render → package | optional |
| `course_launch` | market → content → render → notion → package | ✅ |
| `operating_system` | market → content → render → notion → package | ✅ |
| `workflow_kit` | market → image → content → render → notion → package | ✅ |
| `database` | market → csv_export → package | optional |
| `sop_pack` | market → content → render → package | optional |
| `prompt_pack` | market → catalog → package | optional |
| `resource_pack` | market → catalog → package | optional |
| `swipe_file` | market → content → render → package | optional |
| `checklist` | market → content → render + notion | ✅ |
| `excel_template` | market → csv_export → package | optional |
| `boilerplate` | market → content → package | optional |

---

## Agents Implemented (20 agents + 7 social modules + 6 channel components + 3 analytics modules + 2 pipeline safety modules)

| Agent | File | Lines | Role |
|-------|------|-------|------|
| `market_agent` | `agents/market_agent.py` | 151 | Deep market analysis with 10+ real-time data sources (incl. Etsy, Gumroad) |
| `offer_scoring_agent` | `agents/offer_scoring_agent.py` | 55 | Deterministic scoring: 6 weighted metrics, 15+ product types |
| `research_agent` | `agents/research_agent.py` | 81 | Legacy content research (fallback) |
| `content_agent` | `agents/content_agent.py` | 102 | LLM-driven Markdown content generation |
| `catalog_agent` | `agents/catalog_agent.py` | 70 | Prompt/resource catalog generation |
| `image_agent` | `agents/image_agent.py` | 299 | 3-tier image generation with SVG fallback |
| `visual_agent` | `agents/visual_agent.py` | 52 | Secondary pre-prompted image gen |
| `diagram_agent` | `agents/diagram_agent.py` | 34 | Mermaid diagram code generation |
| `render_agent` | `agents/render_agent.py` | 172 | Markdown → HTML → PDF via Playwright |
| `csv_export_agent` | `agents/csv_export_agent.py` | 71 | CSV + XLSX multi-format export |
| `packaging_agent` | `agents/packaging_agent.py` | 110 | ZIP bundling via _delivery_map |
| `evaluation_agent` | `agents/evaluation_agent.py` | 177 | Quality validation: pattern checks + LLM hallucination detection |
| `review_agent` | `agents/review_agent.py` | 73 | Human-in-the-loop review logs |
| `notion_schema_agent` | `agents/notion_schema_agent.py` | 71 | LLM-generated Notion database blueprints |
| `notion_agent` | `agents/notion_agent.py` | 566 | Notion API: databases, relations, pages |
| `notion_content_agent` | `agents/notion_content_agent.py` | 127 | Notion block content writer |
| `gumroad_agent` | `agents/gumroad_agent.py` | 134 | Gumroad market research (publish → channels/) |
| `landing_agent` | `agents/landing_agent.py` | 204 | Design Intelligence + Vercel deploy |
| `social_agent` | `agents/social_agent.py` | 355 | Social promotion with strategy (calendar, sequences, repurposing) |
| `social_scheduler` | `agents/social/scheduler.py` | 127 | JSON post queue + dispatch to API clients |
| `social_calendar` | `agents/social/calendar.py` | 90 | 7-14 day content calendar generation |
| `social_sequences` | `agents/social/sequences.py` | 45 | Multi-post sequence templates |
| `social_repurposing` | `agents/social/repurposing.py` | 83 | 1 pack → 10+ posts via content mining |
| `social_engagement` | `agents/social/engagement.py` | 79 | Post-performance tracking via Graph API |
| `social_platform_strategy` | `agents/social/platform_strategy.py` | 63 | Platform-specific content rules |
| `social_automation` | `agents/social/automation.py` | 86 | DM/comment webhooks + auto-reply |
| `analytics_agent` | `agents/analytics_agent.py` | 85 | Post-pipeline analytics: collects from all channels, deduplicates, computes insights |
| `analytics_models` | `orchestrator/analytics_models.py` | 102 | SalesRecord + Insights Pydantic models with JSON persistence |
| `feedback_loop` | `orchestrator/feedback_loop.py` | 157 | Past performance → market prompts + scoring weight adjustments |
| `dashboard` | `cli/dashboard.py` | 120 | CLI sales dashboard with ASCII bar charts |
| `BaseChannel` | `channels/base.py` | 76 | ABC: validate, publish, update, get_analytics; AnalyticsData, ListingQualityScore models |
| `GumroadChannel` | `channels/gumroad_channel.py` | 436 | Full Gumroad publish with listing optimization, quality scoring, A/B variants |
| `gumroad_listing` | `channels/gumroad_listing.py` | 147 | Tag/pricing/AIDA description optimization (consumes market_research.json) |
| `gumroad_analytics` | `channels/gumroad_analytics.py` | 165 | Analytics pull (views, sales, revenue) + listing quality scoring |
| `gumroad_ab_testing` | `channels/gumroad_ab_testing.py` | 80 | Cover/thumbnail A/B variant management |
| `CHANNEL_REGISTRY` | `channels/__init__.py` | 8 | Channel name → class mapping |
| `component_templates` | `orchestrator/component_templates.py` | 55 | Frozen template registry: validate, resolve, list templates |
| `dry_run` | `cli/dry_run.py` | 20 | Print DAG tree for `--dry-run` mode |

---

## Key Infrastructure

### Orchestrator (`orchestrator/orchestrator.py` — ~700 lines)
- DAG topological sort from product schema components
- Dynamic pipeline expansion: `market_agent` returns a `pipeline_plan` that adds new components (restricted to validated template registry in Phase 6)
- Circuit breaker: per-template failure tracking blocks templates after 3 failures, prevents cascading failures
- Discovery mode: auto-detects product type via `offer_scoring_agent` (6 weighted metrics, Etsy/Gumroad marketplace data)
- Format recommendations: market LLM recommends CSV/XLSX per component
- Quality validation gate: auto-evaluates each agent's output, retries with fix prompt if score < 0.6
- Wizardskip-gating for optional features (landing, social, gumroad, notion)
- `notion_only` mode substitutes file-agent outputs with Notion content
- Resumable state: failed pipelines pick up from last successful component
- `_delivery_map`: built from all schema components for packaging/gumroad

### Design Intelligence (`design_intelligence/`)
- Replaces the removed StitchMCP dependency
- 6 design skill rule files (impeccable, frontend-design, frontend-design2, design-taste-frontend, gpt-taste, ui-ux-pro-max)
- 12 design vibes mapped to rule combinations
- 12 landing layout patterns from CSV
- Deterministic brief generator creates structured DesignBrief for landing agent

### LLM Client (`agents/llm_client.py`)
- Unified OpenAI SDK wrapper
- Endpoint: `opencode.ai/zen/v1` — model: `mimo-v2.5-free`
- Consistent interface for all agents

### Research Tools (`agents/research_tools.py`)
- 10 data sources: Brave Search, DuckDuckGo, Reddit, Google Trends, GDelt, Firecrawl, NewsAPI, PyTrends, Etsy, Gumroad
- Etsy + Gumroad provide real marketplace competitor counts and pricing for scoring metrics

### State Management (`orchestrator/state.py`)
- JSON file persistence per job
- Per-component status tracking (pending/running/done/failed/skipped)
- Enables `--resume` mode

---

## Testing (254 tests — 60 added in Phase 4, 33 added in Phase 5, 20 added in Phase 6)

```
tests/
├── test_quality.py               # 18 tests — quality checks, evaluation agent, scoring
├── test_orchestrator.py          # 12 tests — execution, isolation, pipeline plan, schema switching, scoring-based discovery, notion-only, channels
├── test_scoring.py               # 14 tests — scoring models, 6 metric functions, integration, empty data
├── test_offer_scoring_agent.py   # 3 tests — enrichment, missing file, mocked scoring
├── test_agents.py                # 16 tests — all agents with mocked LLM/API
├── test_channel_base.py          # 8 tests — base channel ABC, models, analytics defaults, quality score
├── test_gumroad_channel.py       # 13 tests — gumroad channel, tags, rails, variants, research data
├── test_gumroad_analytics.py     # 6 tests — analytics pull, quality scoring (5 dimensions)
├── test_gumroad_listing.py       # 7 tests — tag optimization, pricing, AIDA description
├── test_csv_export_agent.py      # 3 tests — CSV/XLSX generation
├── test_multi_format.py          # 7 tests — multi-format delivery, format recs, delivery_map
├── test_catalog_agent.py         # 1 test — prompt mode
├── test_notion_content_agent.py  # 2 tests — notion content + file fallback
├── test_schemas_phase2.py        # 9 tests — schema validation (Phase 2 schemas)
├── test_social_models.py         # 9 tests — SocialPost, ContentCalendar, PostResult, etc.
├── test_social_calendar.py       # 7 tests — calendar generation, day count, platform allocation
├── test_social_sequences.py      # 8 tests — all 5 sequence types, platform adaptation
├── test_social_repurposing.py    # 5 tests — content mining from markdown
├── test_social_engagement.py     # 7 tests — Graph API insights, fallback, rate calc
├── test_social_platform_strategy.py     # 10 tests — platform rules, hashtag/content adaptation
├── test_social_automation.py     # 8 tests — webhook registration, auto-reply, trigger phrases
├── test_social_scheduler.py      # 5 tests — queue, dequeue, dispatch
├── test_analytics_models.py      # 9 tests — SalesRecord, Insights, dedup, monthly trends, persistence
├── test_analytics_agent.py       # 5 tests — analytics collection, channel iteration, dedup, empty, insights
├── test_dashboard.py             # 5 tests — format_summary, format_insights, empty data, slug filter, bar chart
├── test_feedback_loop.py         # 7 tests — build_past_performance, prompt section, injection, adjustments
└── test_scoring_feedback.py      # 7 tests — score adjustment application, empty history, normalization
```

Run with: `pytest tests/ -v`

---

## Git History (140+ commits)

All commits by Kundan Kumar on `main` branch.

Key milestones in order:
1. Initial scaffolding — project structure, `__init__.py`, basic packaging
2. PDF rendering — Playwright-based HTML→PDF with design system (base.css, cover, TOC)
3. Notion integration v2 — databases, properties, relations, sample entries
4. Landing pages — StitchMCP → Vercel landing page deployment
5. Social promotion — Facebook, Instagram, Threads, Pinterest
6. Market agent — pre-content competitive intelligence with 8 real data sources
7. Image generation — unified `image_agent` with Imagen→Gemini→SVG fallback chain
8. Gumroad publishing — full presign-upload-complete flow with rich content
9. Delivery routing — `_delivery_map`, packaging/gumroad use delivery tags
10. Pipeline plans — LLM dynamically injects new components into DAG
11. Schema expansion — 8 more product schemas (Phase 2)
12. Discovery mode — auto-detect product type from market research
13. Notion-only mode — standalone Notion template products
14. Design Intelligence — 6 design rules, 12 vibes, 12 patterns, brief generator
15. Stitch removal — removed StitchMCP dependency, replaced with Design Intelligence
16. **Phase 0: Channel Layer** — extracted Gumroad publishing from `gumroad_agent` into `channels/gumroad_channel.py` with `BaseChannel` ABC; decoupled landing/social from file coupling; removed `gumroad_publish` from all 15 schemas
17. Multi-format delivery — CSV+XLSX, format recommendations, output_paths dict
18. Cleanup — removed stitch_agent, old plans/specs
19. **Phase 1: Offer Scoring Engine** — scoring framework with 6 weighted metrics, `offer_scoring_agent`, Etsy/Gumroad marketplace data sources, orchestrator scoring-based schema switching (126+ tests)
20. Quality Validation — evaluation_agent, pattern + LLM checks, auto-retry, review_agent, alerts
21. **Phase 3: Listing Optimization** — analytics pull (`gumroad_analytics.py`), listing quality scoring, AIDA description generation, research-driven tags/pricing, cover/thumbnail A/B variant management (`gumroad_ab_testing.py`)
22. **Phase 4: Social Strategy** — multi-post sequences, 7-14 day content calendars, content repurposing engine (1 pack → 10+ posts), platform-specific adaptation, engagement tracking, DM/comment automation, post scheduler with dispatch; `agents/social/` package with 7 submodules (60 tests)
23. **Phase 5: Analytics & Feedback Loop** — `analytics_models.py` (SalesRecord, Insights with JSON persistence), `analytics_agent` (post-pipeline collector across all channels), `feedback_loop.py` (past performance → market prompts + scoring adjustments), `cli/dashboard.py` (table + ASCII bar chart + insights); wired into orchestrator before market_agent and before offer_scoring_agent (33 new tests)
24. **Phase 6: Dynamic Pipeline Safety** — component template registry (`orchestrator/component_templates.py`) with 6 validated templates and LOCKED_FIELDS security; `_merge_pipeline_plan` rejects components without/with unknown templates; circuit breaker blocks templates after 3 consecutive failures; structured error messages with template registry reference; `--dry-run` CLI mode prints DAG without execution (20 new tests)

---

## 52 Roadmap Items

9 phases across: Channel Layer, Offer Scoring, Quality Validation, Analytics, Platform Expansion, Advanced Delivery, AI Improvements, Enterprise Features, Monitoring.

**Completed:** Phase 0 — Channel Layer (6/6). Phase 1 — Offer Selection Engine (5/5). Phase 2 — Quality Validation Layer (6/6). Phase 3 — Gumroad Listing Optimization (6/6). Phase 4 — Social Strategy (6/6). **Phase 5 — Analytics & Feedback Loop (7/7). Phase 6 — Dynamic Pipeline Safety (5/5).**
