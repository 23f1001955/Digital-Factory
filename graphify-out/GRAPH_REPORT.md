# Graph Report - .  (2026-06-15)

## Corpus Check
- 47 files · ~82,392 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 112 nodes · 144 edges · 22 communities (16 shown, 6 thin omitted)
- Extraction: 58% EXTRACTED · 42% INFERRED · 0% AMBIGUOUS · INFERRED: 60 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Agent Contract & Dispatch|Agent Contract & Dispatch]]
- [[_COMMUNITY_Market Research Pipeline|Market Research Pipeline]]
- [[_COMMUNITY_Orchestrator Core|Orchestrator Core]]
- [[_COMMUNITY_Landing Page & Stitch|Landing Page & Stitch]]
- [[_COMMUNITY_Image Generation|Image Generation]]
- [[_COMMUNITY_Product Schemas|Product Schemas]]
- [[_COMMUNITY_Renderer Fallback Chain|Renderer Fallback Chain]]
- [[_COMMUNITY_Gumroad Publishing|Gumroad Publishing]]
- [[_COMMUNITY_Social Media Posting|Social Media Posting]]
- [[_COMMUNITY_CLI & DOE Architecture|CLI & DOE Architecture]]
- [[_COMMUNITY_Product Types Overview|Product Types Overview]]
- [[_COMMUNITY_Image Requirement Spec|Image Requirement Spec]]
- [[_COMMUNITY_Stitch MCP Dispatcher|Stitch MCP Dispatcher]]
- [[_COMMUNITY_Renderer Strategy|Renderer Strategy]]
- [[_COMMUNITY_Dynamic Pipeline Spec|Dynamic Pipeline Spec]]

## God Nodes (most connected - your core abstractions)
1. `Agent Contract (run signature)` - 16 edges
2. `market_agent.run()` - 13 edges
3. `ProductSchema` - 9 edges
4. `generate_text()` - 8 edges
5. `Orchestrator` - 8 edges
6. `generate_images()` - 7 edges
7. `notion_agent.run()` - 7 edges
8. `social_agent.run()` - 7 edges
9. `Research Pack` - 7 edges
10. `gather_all()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `Agent Catalog for market_agent` --semantically_similar_to--> `AGENT_REGISTRY dict`  [INFERRED] [semantically similar]
  docs/superpowers/specs/2026-06-15-dynamic-pipeline-design.md → agents/registry.py
- `Resumability via job_state.json` --conceptually_related_to--> `market_agent.run()`  [INFERRED]
  AGENTS.md → agents/market_agent.py
- `Agent Contract (run signature)` --conceptually_related_to--> `catalog_agent.run()`  [INFERRED]
  AGENTS.md → agents/catalog_agent.py
- `Agent Contract (run signature)` --conceptually_related_to--> `diagram_agent.run()`  [INFERRED]
  AGENTS.md → agents/diagram_agent.py
- `Agent Contract (run signature)` --conceptually_related_to--> `gumroad_agent.run()`  [INFERRED]
  AGENTS.md → agents/gumroad_agent.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **DOE Architecture Pipeline** — doe_architecture, cli_wizard_run_wizard, agents_registry_agent_registry, agents_market_agent_run, agents_content_agent_run, agents_render_agent_run, agents_packaging_agent_run [INFERRED 0.95]
- **Market Research Data Gathering** — agents_market_agent_run, agents_research_tools_brave_search, agents_research_tools_duckduckgo_search, agents_research_tools_reddit_search, agents_research_tools_gdelt_news, agents_research_tools_newsapi_headlines, agents_research_tools_pytrends_data, agents_research_tools_firecrawl_scrape, agents_llm_client_generate_text [INFERRED 0.95]
- **Image Generation Chain with Fallback** — agents_image_agent_call_imagen, agents_image_agent_call_gemini, agents_image_agent_generate_placeholder, agents_image_agent_generate_images, agents_image_agent_generate_from_prompt, image_fallback_chain [INFERRED 0.95]
- **Renderer Selection with Graceful Degradation** — renderers_base_get_renderer, renderers_antigravity_renderer_antigravity_browser_available, renderers_antigravity_renderer_antigravity_renderer, renderers_playwright_renderer_playwright_installed, renderers_playwright_renderer_run_playwright_install, renderers_playwright_renderer_playwright_renderer, orchestrator_renderer_fallback_chain [EXTRACTED 1.00]
- **Error Isolation Mechanism — One Failed Component Doesn't Abort the Run** — orchestrator_orchestrator_run, orchestrator_models_agent_result, orchestrator_models_job_state, orchestrator_state_save_job_state, orchestrator_error_isolation_pattern [EXTRACTED 1.00]
- **Schema-Driven Pipeline Construction** — orchestrator_orchestrator_orchestrator, orchestrator_models_product_schema, orchestrator_models_component_spec, orchestrator_schema_driven_pipeline, schemas_research_pack_research_pack, schemas_blog_kit_blog_kit, schemas_course_launch_course_launch, schemas_operating_system_operating_system, schemas_saas_docs_saas_docs, schemas_visual_pack_visual_pack, schemas_workflow_kit_workflow_kit [EXTRACTED 1.00]

## Communities (22 total, 6 thin omitted)

### Community 0 - "Agent Contract & Dispatch"
Cohesion: 0.13
Nodes (16): Agent Contract (run signature), catalog_agent.run(), content_agent.run(), csv_export_agent.run(), diagram_agent.run(), generate_text(), _build_property_config(), NOTION_PROPERTY_CREATORS dict (+8 more)

### Community 1 - "Market Research Pipeline"
Cohesion: 0.18
Nodes (14): Agent Catalog for market_agent, market_agent.run(), AGENT_REGISTRY dict, brave_search(), firecrawl_scrape(), gather_all(), gdelt_news(), newsapi_headlines() (+6 more)

### Community 2 - "Orchestrator Core"
Cohesion: 0.21
Nodes (14): Error Isolation Pattern, AgentResult, ComponentSpec, JobSpec, JobState, _generate_run_summary, _get_execution_order, Orchestrator (+6 more)

### Community 3 - "Landing Page & Stitch"
Cohesion: 0.28
Nodes (5): landing_agent.run(), _download_screens_from_project(), _generate_and_poll_landing(), _mcp_call(), stitch_agent.run()

### Community 4 - "Image Generation"
Cohesion: 0.46
Nodes (8): _call_gemini(), _call_imagen(), generate_from_prompt(), generate_images(), _generate_placeholder(), image_agent.run(), visual_agent.run(), Image Generation Fallback Chain (Imagen→Gemini→SVG)

### Community 5 - "Product Schemas"
Cohesion: 0.46
Nodes (8): ProductSchema, Blog Kit, Course Launch Kit, Operating System, Research Pack, SaaS Documentation, Visual Pack, Workflow Kit

### Community 6 - "Renderer Fallback Chain"
Cohesion: 0.39
Nodes (8): Renderer Fallback Chain, antigravity_browser_available, AntigravityRenderer, get_renderer, Renderer, playwright_installed, PlaywrightRenderer, run_playwright_install

### Community 7 - "Gumroad Publishing"
Cohesion: 0.40
Nodes (6): _gumroad_form_api(), _gumroad_upload_file(), gumroad_agent.run(), _run_publish(), _run_research(), Gumroad File Upload Flow (presign→upload→complete→attach)

### Community 9 - "CLI & DOE Architecture"
Cohesion: 0.50
Nodes (3): run_wizard(), DOE Architecture (Directive-Orchestration-Execution), main()

## Knowledge Gaps
- **9 isolated node(s):** `Dynamic Pipeline System Spec`, `Dynamic pipeline_plan by market_agent`, `7 Product Types`, `ImageRequirement TypedDict`, `NOTION_PROPERTY_CREATORS dict` (+4 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Agent Contract (run signature)` connect `Agent Contract & Dispatch` to `Market Research Pipeline`, `Landing Page & Stitch`, `Image Generation`, `Gumroad Publishing`, `Social Media Posting`?**
  _High betweenness centrality (0.231) - this node is a cross-community bridge._
- **Why does `market_agent.run()` connect `Market Research Pipeline` to `Agent Contract & Dispatch`?**
  _High betweenness centrality (0.135) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `Agent Contract (run signature)` (e.g. with `catalog_agent.run()` and `content_agent.run()`) actually correct?**
  _`Agent Contract (run signature)` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `market_agent.run()` (e.g. with `Agent Contract (run signature)` and `generate_text()`) actually correct?**
  _`market_agent.run()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `generate_text()` (e.g. with `_run_publish()` and `_run_research()`) actually correct?**
  _`generate_text()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Dynamic Pipeline System Spec`, `DOE Architecture (Directive-Orchestration-Execution)`, `Registry Pattern for Agent Dispatch` to the rest of the system?**
  _17 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Agent Contract & Dispatch` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._