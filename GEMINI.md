# Digital Factory - Gemini Context Guide
This document serves as a contextual guide for Gemini (or any AI assistant) working on the **Digital Product Factory** codebase. It synthesizes the core architecture from the `README.md` and the specific agent roles from the `AGENTS.md` documentation.
## Project Overview
**Digital Product Factory** is an automated AI pipeline that researches market niches, generates complete digital products (reports, templates, courses, databases, prompt packs, etc.), packages them, publishes to Gumroad, deploys landing pages to Vercel, promotes on social media, and syncs to Notion — all from a single CLI command or batch CSV.
### Core Architecture
The system is built on a **DAG-based, Dynamic AI Orchestrator**. 
1. **Input**: `main.py` takes user input (interactive wizard or CSV batch) and generates a `job_spec.json`.
2. **Orchestrator**: Reads a Product Schema (e.g., `research_pack.json`) to build a Directed Acyclic Graph (DAG) of tasks (components).
3. **Offer Scoring**: In discovery mode, `offer_scoring_agent` runs after `market_agent`, evaluating all 15+ product types against 6 weighted metrics (search demand, competition, market viability, content fit, trend momentum, community signals) using real marketplace data from Etsy and Gumroad.
4. **Dynamic Expansion**: The `market_agent` can return a `pipeline_plan` that dynamically injects new components into the DAG at runtime.
4. **Execution**: The orchestrator runs through the DAG topologically, invoking specialized agents for content generation, rendering, packaging, and publishing.
5. **Channel Publishing**: After the DAG completes, the orchestrator runs configured channels (e.g., `GumroadChannel`) to publish artifacts to external platforms. The `product_url` from channel results is injected back into the DAG context for downstream agents (landing page, social promotion).
## Key Capabilities & Features
- **16 Product Schemas**: Support for various products like Blog Kits, Course Launches, SaaS Docs, Operating Systems, and Boilerplates.
- **Multi-Format Delivery**: Generates Markdown, PDFs (via Playwright HTML printing), CSV/XLSX, Mermaid diagrams, and native Notion workspaces.
- **Channel Layer**: Decoupled publishing via `channels/` package — `BaseChannel` ABC, `GumroadChannel`, and `CHANNEL_REGISTRY`. Channels run **after** the pipeline, consuming artifacts instead of being embedded in the DAG.
- **Listing Optimization**: Gumroad channel auto-optimizes tags (research-sourced), pricing (median competitor), and descriptions (AIDA framework via LLM) before publishing.
- **Listing Quality Scoring**: Post-publish quality check scores description length, tag count, cover image, price alignment, and research claim alignment.
- **Analytics Pull**: `get_analytics()` on `GumroadChannel` returns structured `AnalyticsData` (views, sales, revenue, refunds, conversion rate) from the Gumroad API.
- **Cross-Product Analytics**: `analytics_agent` aggregates sales records from all channels into persistent JSON, computes insights (top products, best channel, monthly revenue trends).
- **Feedback Loop**: `orchestrator/feedback_loop.py` injects past performance data into market research prompts and adjusts scoring weights — each run learns from previous runs.
- **CLI Dashboard**: `cli/dashboard.py` displays sales summary with ASCII bar charts and formatted insights (`python -m cli.dashboard --slug <slug>`).
- **Cover/Thumbnail A/B Testing**: `GumroadChannel` supports multiple cover/thumbnail variants with round-robin cycling across publish runs.
- **Design Intelligence**: Deploys landing pages using LLM-generated UI combined with curated design patterns and rules.
- **Resumable State**: Uses `job_state.json` to resume failed pipelines gracefully without re-running successful agents.
## Agent Roster
The system uses a variety of specialized agents to execute the DAG components:
### 1. Research & Planning
- **`market_agent.py`**: Conducts niche research, competitor analysis, and dynamically expands the execution graph. Gathers data from 10+ sources including Etsy and Gumroad marketplace data.
- **`research_agent.py`**: Deep specialized research via web scraping and external APIs (Brave, Reddit, NewsAPI).
- **`offer_scoring_agent.py`**: Enriches `market_research.json` with `scored_recommendations[]` — a deterministic, data-driven evaluation of which product type best fits the researched niche. Runs after market_agent in discovery mode.
### 2. Content Generation
- **`content_agent.py`**: Generates extensive Markdown content (guides, reports) via LLM based on market research.
- **`catalog_agent.py`**: Creates structured, list-based content (JSON/MD catalogs).
### 3. Media & Visuals
- **`image_agent.py`**: Interacts with Image Generation APIs (Stable Diffusion/DALL-E) to create cover art and assets.
- **`diagram_agent.py`**: Writes Mermaid or SVG code for visual representation of concepts.
- **`visual_agent.py`**: Secondary visual generation and post-processing.
### 4. Rendering & Export
- **`render_agent.py`**: Injects Markdown into Jinja2 templates and prints to PDF using Playwright/Chromium.
- **`csv_export_agent.py`**: Converts tabular JSON data into CSV/XLSX formats.
### 5. Notion Integration
- **`notion_schema_agent.py`**: Designs Notion database architecture (properties, relations).
- **`notion_agent.py`**: Constructs the empty databases and relational structure via Notion API.
- **`notion_content_agent.py`**: Pushes Markdown content directly into Notion blocks (swaps in for standard content agents during Notion-only mode).
### 6. Quality Validation
- **`evaluation_agent.py`**: Evaluates output quality using pattern-based checks (AI-isms, word count, headings) and LLM-based hallucination cross-referencing.
- **`review_agent.py`**: Creates human-in-the-loop review logs when content is flagged for hallucination or missing citations.
### 7. Analytics & Feedback Loop (Phase 5)
- **`analytics_agent.py`**: Post-pipeline analytics collector. Iterates `CHANNEL_REGISTRY`, calls `get_analytics()` per channel, converts `AnalyticsData` to `SalesRecord`, merges with existing records, computes `Insights` (top products, best channel, monthly revenue trends). Persists to `outputs/_analytics/sales_records.json` and `outputs/_analytics/insights.json`.
- **`orchestrator/analytics_models.py`**: Pydantic models (`SalesRecord`, `Insights`) with JSON persistence functions (load/save with dedup by product_slug+channel+date).
- **`orchestrator/feedback_loop.py`**: Pipeline feedback engine. `build_past_performance()` summarizes historical data, `generate_prompt_section()` creates a research-prompt appendix, `inject_feedback()` merges into market_agent context, `compute_score_adjustment()` boosts future runs by past conversion rates, `apply_score_adjustments()` modifies scoring runs. The orchestrator wires both before market_agent and before offer_scoring_agent.
- **`cli/dashboard.py`**: CLI dashboard with `--slug` and `--days` args, `format_summary()` (table + ASCII bar chart), `format_insights()` (best channel, top products, trend).
### 8. Frontend & Web
- **`landing_agent.py`**: Deploys a live landing page (Next.js/Vercel) using product copy and generated designs.
### 9. Packaging, Publishing & Promotion
- **`packaging_agent.py`**: Compresses all designated deliverables into a `{slug}.zip` based on the orchestrator's `_delivery_map`.
- **`gumroad_agent.py`**: Conducts Gumroad market research (competitor pricing, product type distribution). Publishing logic moved to `channels/gumroad_channel.py`.
- **`social_agent.py`**: Promotes the live product on social media platforms (Facebook, Instagram, Threads, Pinterest). Orchestrates multi-post sequences with content calendar, repurposing, and platform adaptation. Reads URLs from orchestrator-injected context.
### 9a. Social Strategy Modules (Phase 4)
- **`social/calendar.py`**: Generates 7–14 day content calendars with teaser→launch→followup→testimonial→repurpose cadence across 4 platforms.
- **`social/sequences.py`**: Multi-post sequence templates (teaser, launch, followup, testimonial, repurpose) with platform-specific formatting.
- **`social/repurposing.py`**: Extracts 10+ social posts from a single content pack by mining statistics, bullet points, blockquotes from generated markdown.
- **`social/engagement.py`**: Post-performance tracking via Graph API insights, engagement rate calculation, fallback to zeros.
- **`social/platform_strategy.py`**: Platform-specific content rules (character limits, hashtag caps, best posting times) for Instagram, Facebook, Threads, Pinterest.
- **`social/automation.py`**: DM/comment webhook registration and auto-reply with trigger phrase detection.
- **`social/scheduler.py`**: JSON-based post queue with time-based dequeue and dispatch via existing `_post_to_*` API clients.
### 10. Channel Layer
- **`channels/base.py`**: `BaseChannel` ABC defining `validate()`, `publish()`, `update()`, `get_analytics()` interface. Also provides `AnalyticsData`, `ListingQualityScore` data models.
- **`channels/gumroad_channel.py`**: `GumroadChannel` implementing full Gumroad publish flow (create/update product, file upload, cover/thumbnail, rich content). Wires listing optimization (tags, pricing, AIDA) from market research before publishing.
- **`channels/gumroad_listing.py`**: Listing optimization: tag extraction from competitor data, median pricing, AIDA description generation via LLM with deterministic fallback.
- **`channels/gumroad_analytics.py`**: Analytics pull from Gumroad API + listing quality scoring across 5 weighted dimensions.
- **`channels/gumroad_ab_testing.py`**: Cover/thumbnail variant management with persistence and round-robin cycling.
## AI Assistant Guidelines
When assisting with this codebase:
- Respect the DAG structure in `orchestrator.py` and the JSON configurations in `schemas/`.
- Maintain the separation of concerns between agents. Do not mix responsibilities.
- **Channels run after the pipeline.** The DAG produces artifacts; channels consume them. Do not embed channel publish steps in schemas.
- Ensure that delivery routing (`_delivery_map`) correctly links `packaging_agent` outputs to channel uploads.
- Any new agent created must be registered in `agents/registry.py` and adhere to the `AgentResult` return type.
- New channels must implement `channels/base.py:BaseChannel` and be registered in `channels/__init__.py:CHANNEL_REGISTRY`.
- PDF designs are controlled by `templates/shared/base.css` and Jinja2 templates.
- Quality validation runs as an orchestrator hook after each content-producing agent. New agents added to `EVALUATION_TARGETS` in `agents/evaluation_agent.py` will be automatically validated.
## Graphify Auto-Activation
This project uses **graphify** for a persistent knowledge graph. At the start of every session, the knowledge graph in `graphify-out/` is the primary reference for codebase questions.
1. **Before answering any codebase question**, check if `graphify-out/graph.json` exists and use `graphify query "<question>"` (or inline NetworkX traversal via `graphify-out/graph.json`) instead of grepping raw files.
2. **Atomic unit**: the knowledge graph — one entity per node, with `source_location` citations. Prefer the graph over raw file grep.
3. **If `graphify-out/` is missing or outdated**, rebuild: run the full graphify pipeline (extract → cluster → label → export).
4. **After any code changes**, rebuild graph via `graphify --update` so the graph stays current.
