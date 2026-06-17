# Digital Factory - Gemini Context Guide
This document serves as a contextual guide for Gemini (or any AI assistant) working on the **Digital Product Factory** codebase. It synthesizes the core architecture from the `README.md` and the specific agent roles from the `AGENTS.md` documentation.
## Project Overview
**Digital Product Factory** is an automated AI pipeline that researches market niches, generates complete digital products (reports, templates, courses, databases, prompt packs, etc.), packages them, publishes to Gumroad, deploys landing pages to Vercel, promotes on social media, and syncs to Notion — all from a single CLI command or batch CSV.
### Core Architecture
The system is built on a **DAG-based, Dynamic AI Orchestrator**. 
1. **Input**: `main.py` takes user input (interactive wizard or CSV batch) and generates a `job_spec.json`.
2. **Orchestrator**: Reads a Product Schema (e.g., `research_pack.json`) to build a Directed Acyclic Graph (DAG) of tasks (components).
3. **Dynamic Expansion**: The `market_agent` can return a `pipeline_plan` that dynamically injects new components into the DAG at runtime.
4. **Execution**: The orchestrator runs through the DAG topologically, invoking specialized agents for content generation, rendering, packaging, and publishing.
## Key Capabilities & Features
- **16 Product Schemas**: Support for various products like Blog Kits, Course Launches, SaaS Docs, Operating Systems, and Boilerplates.
- **Multi-Format Delivery**: Generates Markdown, PDFs (via Playwright HTML printing), CSV/XLSX, Mermaid diagrams, and native Notion workspaces.
- **Design Intelligence**: Deploys landing pages using LLM-generated UI combined with curated design patterns and rules.
- **Resumable State**: Uses `job_state.json` to resume failed pipelines gracefully without re-running successful agents.
## Agent Roster
The system uses a variety of specialized agents to execute the DAG components:
### 1. Research & Planning
- **`market_agent.py`**: Conducts niche research, competitor analysis, and dynamically expands the execution graph.
- **`research_agent.py`**: Deep specialized research via web scraping and external APIs (Brave, Reddit, NewsAPI).
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
### 7. Frontend & Web
- **`landing_agent.py`**: Deploys a live landing page (Next.js/Vercel) using product copy and generated designs.
### 8. Packaging, Publishing & Promotion
- **`packaging_agent.py`**: Compresses all designated deliverables into a `{slug}.zip` based on the orchestrator's `_delivery_map`.
- **`gumroad_agent.py`**: Writes sales copy, uploads the ZIP + images, and publishes a live Gumroad product via API.
- **`social_agent.py`**: Promotes the live product on social media platforms (Twitter, Instagram, Facebook, Pinterest).
## AI Assistant Guidelines
When assisting with this codebase:
- Respect the DAG structure in `orchestrator.py` and the JSON configurations in `schemas/`.
- Maintain the separation of concerns between agents. Do not mix responsibilities.
- Ensure that delivery routing (`_delivery_map`) correctly links `packaging_agent` outputs to `gumroad_agent` uploads.
- Any new agent created must be registered in `agents/registry.py` and adhere to the `AgentResult` return type.
- PDF designs are controlled by `templates/shared/base.css` and Jinja2 templates.
- Quality validation runs as an orchestrator hook after each content-producing agent. New agents added to `EVALUATION_TARGETS` in `agents/evaluation_agent.py` will be automatically validated.
