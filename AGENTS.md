# Digital Factory - Agents Documentation
This document provides a comprehensive overview of all the autonomous agents operating within the Digital Factory ecosystem. The system is orchestrated by a DAG-based engine, where each agent acts as a specialized node responsible for a specific stage of the product lifecycle.
---
## 1. Research & Scoring Agents
These agents run at the very beginning of the pipeline. They research the niche, generate the core strategy, score product opportunities, and dynamically expand the orchestrator's execution graph.
* **`market_agent.py`**
  * **Role**: The brain of the operation. Conducts deep market analysis for the given niche using 10+ data sources (Google Trends, Etsy, Gumroad, Reddit, Brave, NewsAPI, GDelt, Firecrawl).
  * **Outputs**: `market_research.json` (Includes a `pipeline_plan` that the orchestrator uses to dynamically add new PDF generation or content tasks to the DAG).
* **`research_agent.py`**
  * **Role**: Conducts deeper, specialized research utilizing external search tools (web scraping, API calls) as needed.
* **`offer_scoring_agent.py`** (Scoring Engine)
  * **Role**: Deterministically scores all available product types against the niche research data using 6 weighted metrics. Replaces LLM opinion with data-driven recommendations.
  * **How it works**: Reads `market_research.json`, runs `orchestrator/scoring.py`, enriches the file with `scored_recommendations[]` sorted by total score.
  * **Metrics**: Search demand (25%), Competition (25%), Market viability (20%), Content fit (15%), Trend momentum (10%), Community signals (5%).
  * **Outputs**: Enriched `market_research.json` with `scored_recommendations[]`, `recommended_product_type`, and `recommendation_confidence`.
---
## 2. Content Generation Agents
Responsible for writing the actual text and structured data for the digital products.
* **`content_agent.py`**
  * **Role**: Uses LLMs to generate extensive Markdown content (guides, cheat sheets, reports) based on the market research.
  * **Outputs**: Various `*.md` files.
* **`catalog_agent.py`**
  * **Role**: Generates structured, list-based content (e.g., resource lists, directories) based on the niche.
  * **Outputs**: Structured JSON/MD catalogs.
---
## 3. Media & Visual Agents
Handles the generation of images, graphics, and diagrams.
* **`image_agent.py`**
  * **Role**: Interacts with Image Generation APIs (like Stable Diffusion or DALL-E) to create cover art, thumbnails, and internal asset images.
  * **Outputs**: `assets/*.png` and `images_generated.json`.
* **`visual_agent.py`**
  * **Role**: Post-processes or handles secondary visual generation tasks.
* **`diagram_agent.py`**
  * **Role**: Uses LLMs to write Mermaid or SVG code to visually represent concepts from the content generation phase.
  * **Outputs**: `*.mmd` or SVG files.
---
## 4. Rendering & Formatting Agents
Converts raw generated data into final, polished file formats.
* **`render_agent.py`**
  * **Role**: Takes generated Markdown, injects it into Jinja2 HTML/CSS templates, and uses a headless browser (Playwright/Antigravity) to render beautiful PDF files.
  * **Outputs**: `presentation/*.pdf`.
* **`csv_export_agent.py`**
  * **Role**: Converts tabular or catalog data into downloadable CSV files.
  * **Outputs**: `*.csv` files.
---
## 5. Notion Integration Agents
A specialized suite of agents for syncing digital products directly into a user's Notion Workspace.
* **`notion_schema_agent.py`**
  * **Role**: Uses an LLM to design the database architecture required in Notion (properties, relations, page structures).
  * **Outputs**: `notion_schema.json`.
* **`notion_agent.py`** (Notion Tree Agent)
  * **Role**: Talks to the Notion API to construct the empty databases, parent pages, and relational structure designed by the schema agent.
* **`notion_content_agent.py`**
  * **Role**: Swaps in for `content_agent` / `render_agent` when `notion_only` mode is active. Pushes the raw markdown content as Notion blocks directly into the previously created pages.
---
## 6. Quality Validation Agents
Runs automatically after each content-producing agent to prevent garbage from reaching customers.
* **`evaluation_agent.py`**
  * **Role**: Evaluates output quality using pattern-based checks (word count, headings, AI-isms, empty sections) and LLM-based hallucination cross-referencing against research data. Generates fix prompts for auto-retry.
  * **Outputs**: `quality-report.json`.
* **`review_agent.py`**
  * **Role**: Creates human-in-the-loop review logs when content has hallucination flags or missing citations. Generates structured markdown with issue details and verdict checklist.
  * **Outputs**: `outputs/{slug}/review/*_review.md`.
---
## 7. Analytics & Feedback Loop Agents
Agents responsible for collecting sales data, computing insights, and closing the feedback loop so future runs learn from past performance.
* **`analytics_agent.py`**
  * **Role**: Post-pipeline analytics collector. Iterates all channels in `CHANNEL_REGISTRY`, calls `get_analytics()` per channel, converts `AnalyticsData` into `SalesRecord`, merges with existing records (dedup by product_slug+channel+date), and computes `Insights` (top products, avg conversion, best channel, monthly revenue trends).
  * **Inputs**: `channel_results` from orchestrator context, `outputs/_analytics/sales_records.json`.
  * **Outputs**: Enriched `outputs/_analytics/` (`sales_records.json`, `insights.json`).
* **`orchestrator/analytics_models.py`**
  * **Role**: Pydantic models (`SalesRecord`, `Insights`) and JSON persistence helpers (`load_sales_records`, `save_sales_records`, `load_insights`, `save_insights`). Dedup by `(product_slug, channel, date)`, monthly revenue trend grouping.
* **`orchestrator/feedback_loop.py`**
  * **Role**: Pipeline feedback engine. `build_past_performance()` summarizes historical data, `generate_prompt_section()` creates a research-prompt appendix, `inject_feedback()` merges into market_agent context, `compute_score_adjustment()` boosts scoring weights for high-conversion product types, `apply_score_adjustments()` modifies the scoring run. Wired into orchestrator before market_agent and before offer_scoring_agent.
* **`cli/dashboard.py`**
  * **Role**: CLI dashboard. `format_summary()` produces a table + ASCII bar chart of sales data, `format_insights()` displays best channel, top products, and monthly revenue trend. Usage: `python -m cli.dashboard --slug <slug>`.
  * **Outputs**: Formatted terminal output (no file persistence).
## 8. Frontend & Web Agents
Creates and deploys live web interfaces for the generated products.
* **`landing_agent.py`**
  * **Role**: Takes the product copy and Design Intelligence brief, generates a landing page HTML, and deploys it to Vercel.
  * **Outputs**: `landing/deployed.json`.
---
## 9. Packaging, Publishing & Promotion Agents
The final stages of the pipeline: bundling the product, selling it, and marketing it.
* **`packaging_agent.py`**
  * **Role**: Reads the orchestrator's `_delivery_map` to collect all PDFs, images, and data files designated for the final bundle and compresses them.
  * **Outputs**: `{slug}.zip`.
* **`gumroad_agent.py`**
  * **Role**: Handles `gumroad_research` — competitor analysis, pricing data, and product type recommendations from Gumroad market data.
  * **Outputs**: `gumroad/research.json`.
  * **Note**: Publishing logic moved to `channels/gumroad_channel.py` as part of the Channel Layer.
* **`social_agent.py`**
  * **Role**: Orchestrates social media promotion with multi-post sequences, content calendar, and repurposing. Reads URLs from orchestrator-injected context (no direct file coupling).
  * **Outputs**: `landing/social_results.json` (includes `scheduled_posts`, `dispatch_results`, `automation`).
* **`social/__init__.py`**
  * **Role**: Package init exporting all social strategy modules.
* **`social/models.py`**
  * **Role**: Data models: `SocialPost`, `ContentCalendar`, `PostResult`, `EngagementMetrics`, `PlatformConfig`.
* **`social/calendar.py`**
  * **Role**: Generates 7–14 day content calendars with teaser→launch→followup→testimonial→repurpose cadence across 4 platforms (Facebook, Instagram, Threads, Pinterest).
  * **Outputs**: `ContentCalendar` with scheduled `SocialPost` objects.
* **`social/sequences.py`**
  * **Role**: Multi-post sequence templates (`teaser`, `launch`, `followup`, `testimonial`, `repurpose`) with platform-adapted content.
* **`social/repurposing.py`**
  * **Role**: Content repurposing engine. Extracts 10+ social-ready posts from generated markdown by mining statistics, bullet points, and blockquotes.
* **`social/engagement.py`**
  * **Role**: Post-performance tracking. Fetches likes, comments, shares, impressions via Graph API. Calculates engagement rate.
  * **Fallback**: Returns zeros when API unavailable.
* **`social/platform_strategy.py`**
  * **Role**: Platform-specific content rules (character limits, hashtag caps, image requirements, best posting times) for Instagram, Facebook, Threads, Pinterest.
* **`social/automation.py`**
  * **Role**: DM and comment webhook registration for Facebook/Instagram. Auto-reply with trigger phrase detection. Threads/Pinterest stubbed (no API).
* **`social/scheduler.py`**
  * **Role**: JSON-based post queue. `queue_posts()` persists calendar, `dequeue_due()` returns ready posts, `dispatch()` routes to existing `_post_to_facebook/instagram/threads/pinterest` API clients.
---
## 10. Channel Layer
The channel layer is a post-pipeline abstraction for publishing generated products to external platforms. Channels run **after** the main pipeline DAG completes, consuming artifacts instead of being embedded in the product schemas.
* **`channels/base.py`**
  * **Role**: Defines the `BaseChannel` abstract base class with `validate()`, `publish()`, `update()`, and `get_analytics()` interface. Also provides `ProductArtifact`, `PublishResult`, `ArtifactFile`, `AnalyticsData`, and `ListingQualityScore` data models.
  * **Design**: Each channel extends `BaseChannel` and implements the publish flow for its platform. The orchestrator calls channel publish after pipeline completion.
* **`channels/gumroad_channel.py`**
  * **Role**: Implements full Gumroad publishing: product creation/update, file upload via presigned URLs, cover/thumbnail images, and rich content (thank-you page). Extracted from the legacy `gumroad_agent.py`. Wires listing optimization (tags, pricing, AIDA description) before publish.
  * **Outputs**: `PublishResult` with status, product URL, and product ID.
* **`channels/gumroad_listing.py`**
  * **Role**: Listing optimization module: `generate_optimized_tags()` extracts competitor tags from market research, `suggest_price()` calculates median competitor pricing, `generate_aida_description()` produces AIDA-format product descriptions via LLM with fallback. Consumes `market_research.json`.
  * **Design**: Pure functions with graceful fallback — no research data = deterministic defaults.
* **`channels/gumroad_analytics.py`**
  * **Role**: Analytics module: `pull_analytics()` fetches product stats (views, sales, revenue, refunds, conversion rate) from Gumroad API into `AnalyticsData`. `score_listing_quality()` evaluates listing quality across 5 weighted dimensions (description, tags, cover, price, research alignment) and returns `ListingQualityScore`.
* **`channels/gumroad_ab_testing.py`**
  * **Role**: Cover/thumbnail A/B testing module: `VariantSet` dataclass for managing multiple variants, `save_variant_state()`/`load_variant_state()` for persistence, `upload_variants()` for deploying the active variant to Gumroad.
* **`channels/__init__.py`**
  * **Role**: Exports `CHANNEL_REGISTRY` — a dict mapping channel names to channel classes. Also re-exports all data models from `base.py`.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
