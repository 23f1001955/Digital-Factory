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
## 7. Frontend & Web Agents
Creates and deploys live web interfaces for the generated products.
* **`landing_agent.py`**
  * **Role**: Takes the product copy and Design Intelligence brief, generates a landing page HTML, and deploys it to Vercel.
  * **Outputs**: `landing/deployed.json`.
---
## 8. Packaging, Publishing & Promotion Agents
The final stages of the pipeline: bundling the product, selling it, and marketing it.
* **`packaging_agent.py`**
  * **Role**: Reads the orchestrator's `_delivery_map` to collect all PDFs, images, and data files designated for the final bundle and compresses them.
  * **Outputs**: `{slug}.zip`.
* **`gumroad_agent.py`**
  * **Role**: Handles `gumroad_research` — competitor analysis, pricing data, and product type recommendations from Gumroad market data.
  * **Outputs**: `gumroad/research.json`.
  * **Note**: Publishing logic moved to `channels/gumroad_channel.py` as part of the Channel Layer.
* **`social_agent.py`**
  * **Role**: Generates social media posts (e.g., Twitter threads) promoting the newly deployed landing page and Gumroad product, then pushes them via social APIs. Reads URLs from orchestrator-injected context (no direct file coupling).
  * **Outputs**: `landing/social_results.json`.
---
## 9. Channel Layer
The channel layer is a post-pipeline abstraction for publishing generated products to external platforms. Channels run **after** the main pipeline DAG completes, consuming artifacts instead of being embedded in the product schemas.
* **`channels/base.py`**
  * **Role**: Defines the `BaseChannel` abstract base class with `validate()`, `publish()`, `update()`, and `get_analytics()` interface. Also provides `ProductArtifact`, `PublishResult`, and `ArtifactFile` data models.
  * **Design**: Each channel extends `BaseChannel` and implements the publish flow for its platform. The orchestrator calls channel publish after pipeline completion.
* **`channels/gumroad_channel.py`**
  * **Role**: Implements full Gumroad publishing: product creation/update, file upload via presigned URLs, cover/thumbnail images, and rich content (thank-you page). Extracted from the legacy `gumroad_agent.py`.
  * **Outputs**: `PublishResult` with status, product URL, and product ID.
* **`channels/__init__.py`**
  * **Role**: Exports `CHANNEL_REGISTRY` — a dict mapping channel names to channel classes. New channels register here.