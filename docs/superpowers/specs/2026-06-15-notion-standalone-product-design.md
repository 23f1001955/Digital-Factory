# Notion Standalone Product — Design Spec

## Problem

Currently Notion integration has two issues:
1. **No wizard gate.** When user selects a notion_sync product type but declines Notion sync, `notion_schema` and `notion_tree` components still run — orchestrator doesn't skip them.
2. **No standalone Notion product.** Notion workspace is always a bonus bundled with ZIP content. Cannot sell the Notion workspace as a standalone product (with content rendered as Notion pages, no ZIP).

## Product Modes

Two distinct modes, each a separate pipeline run:

| Feature | Combo Mode (existing + fix) | Standalone Notion Mode (new) |
|---------|-----------------------------|------------------------------|
| Deliverable | ZIP + optional Notion link | Only Notion link |
| Notion contains | Action databases only (CRM, trackers, dashboards) | Action databases + content pages (guides, docs, templates) |
| ZIP contains | PDFs, markdown, assets, Notion link | Nothing — no ZIP created |
| Gumroad upload | ZIP + PDF files + cover/thumbnail | No files — rich_content with link |
| Landing page | ✅ If wizard enabled | ✅ If wizard enabled |
| Social promotion | ✅ If wizard enabled | ✅ If wizard enabled |
| Package agent | ✅ Creates ZIP | ❌ Skipped |
| Product types | Only notion_sync=true (OS, Workflow Kit, Course Launch) | All 7 types |
| Gumroad slug | `{slug}` | `{slug}-notion` |

## Architecture Changes

### 1. New Agent: `notion_content_agent`

Purpose: Create content pages in Notion instead of writing `.md` files to disk.

```
Signature: run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult
```

Flow:
1. Resolve `.j2` prompt by `component.id` (same as content_agent)
2. Call LLM with prompt to generate content
3. Call Notion API to create a page under the product root workspace
4. Return output pointing to `notion_content/{component.id}.json` (contains page URL + ID)

Prompts loaded from `prompts/{component.id}.j2` — no new prompt infrastructure needed.

### 2. Automatic Agent Substitution

In `notion_only=True` mode, orchestrator substitutes file-based agents with notion_content_agent:

| pipeline_plan assigns | Combo mode runs | Standalone mode runs |
|---|---|---|
| `content_agent` | `content_agent` (writes `.md`) | `notion_content_agent` (creates page) |
| `csv_export_agent` | `csv_export_agent` (writes `.csv`) | `notion_content_agent` (creates database rows) |
| `render_agent` | `render_agent` (writes `.pdf`) | `notion_content_agent` (creates formatted page) |
| `diagram_agent` | `diagram_agent` (writes `.mmd`) | `notion_content_agent` (creates page with diagram) |
| `packaging_agent` | `packaging_agent` (creates ZIP) | **Skipped entirely** |
| `notion_schema_agent` | `notion_schema_agent` (blueprint) | `notion_schema_agent` (same) |
| `notion_agent` | `notion_agent` (databases) | `notion_agent` (databases) |

The substitution happens after pipeline_plan merge, before execution loop starts processing components.

For `notion_agent` in standalone mode: it also needs to create/import content from `notion_content_agent` outputs into the workspace. This could mean:
- notion_agent creates databases (existing behavior)
- notion_content_agent creates content pages under the root page
- The workspace has both: databases (top section) + content pages (under a "Content" parent)

### 3. Schema Changes

**JobSpec** (`orchestrator/models.py`) — new field:
```python
notion_only: bool = False  # new — wizard sets this
```

### 4. Market Agent Integration

**market_research.j2** — add notion_only recommendation field:
```json
"market_insights": {
  ...
  "recommends_notion_only": bool,  // new — true if niche has demand for standalone Notion templates
  "notion_price_suggestion": number  // new — suggested price for standalone Notion product
}
```

The market agent, based on competitor and Reddit research, decides if standalone Notion templates sell well for this niche.

### 5. Wizard Changes

When notion_only feature is active:
- After product type selection, wizard asks: "Notion-only template bhi bechein?" (y/n, default n)
- If y: `job_spec.notion_only = True`
- The main product type + niche remains same — only delivery format changes

### 6. Wizard Gate Bug Fix (Combo Mode)

In `orchestrator/orchestrator.py`, add skip logic for notion_schema/notion_tree:

```python
# Skip notion_schema/notion_tree if notion_sync not enabled
if component.id in ("notion_schema", "notion_tree") and not self.job_spec.notion_sync:
    self.state.components[component.id] = AgentResult(status="skipped", error="notion sync not enabled")
    save_job_state(self.state, self.state_path)
    done_count += 1
    logger.warning("%s/%s %s (disabled)", done_count, total, component.id)
    continue
```

### 7. Orchestrator Changes

In `run()` method, after pipeline_plan merge:

```python
# If notion_only mode, substitute file agents with notion_content_agent
if self.job_spec.notion_only:
    # Mark package as skipped — no ZIP needed
    for c in self.schema.components:
        if c.id == "package":
            self.state.components[c.id] = AgentResult(status="skipped", error="notion_only mode: no ZIP")
            break
    # In execution loop, substitute agents:
    # content_agent → notion_content_agent
    # csv_export_agent → notion_content_agent
    # render_agent → notion_content_agent
    # diagram_agent → notion_content_agent
```

The substitution works by overriding `agent_func` in the execution loop when `notion_only=True` and component uses a file-based agent.

### 8. Gumroad Distribution

For standalone Notion mode in `gumroad_agent`:
- `_run_publish()` scans for files — none will exist (no ZIP, no PDFs)
- The API call proceeds without `files` parameter
- `custom_receipt` includes Notion workspace link
- `rich_content` shows: "Thank you! Your workspace is ready at [LINK]"
- Price: `notion_price_suggestion` from market research (typically lower than combo)
- Product slug: `{job_spec.slug}-notion` (prevent collision with combo product)

## Files Changed

| File | Change |
|------|--------|
| `orchestrator/models.py` | Add `notion_only` to JobSpec |
| `orchestrator/orchestrator.py` | Wizard gate fix + notion_only agent substitution + package skip |
| `agents/notion_content_agent.py` | **New file** — creates Notion pages from prompts |
| `agents/registry.py` | Add `notion_content_agent` |
| `cli/wizard.py` | Add "Notion-only?" question |
| `prompts/market_research.j2` | Add `recommends_notion_only` + `notion_price_suggestion` |
| `schemas/*.json` | Optionally add `notion_only` flag (future) |

## Pipeline Flow

### Combo Mode (notion_sync=true)
```
market_research → notion_schema → notion_tree (databases)
                → images
                → [dynamic: content_agent → .md]
                → [dynamic: csv_export → .csv]
                → [dynamic: render → .pdf]     (if template set)
                → package → {slug}.zip
                → gumroad_publish → upload ZIP + PDFs
                → landing_page (optional)
                → social_promotion (optional)
```

### Standalone Notion Mode (notion_only=true)
```
market_research → notion_schema → notion_tree (databases)
                → images (for cover/thumb)
                → [dynamic: notion_content_agent → Notion page]
                → [dynamic: notion_content_agent → Notion page]
                → [dynamic: notion_content_agent → Notion page]
                → gumroad_publish → link-only product
                → landing_page (optional)
                → social_promotion (optional)
                → [package: SKIPPED]
```

## Error Handling

- notion_content_agent fails gracefully if Notion API unavailable (returns `status: "failed"`)
- Agents missing in standalone mode: handled per existing error isolation
- If market_research fails: no pipeline_plan → core components only
- If notion_only + no notion_schema: fail early (log + skip notion_content)

## Testing

- `tests/test_notion_content_agent.py` — mock Notion API, verify page creation
- `tests/test_orchestrator.py` — test notion_only substitution logic
- `tests/test_wizard.py` — test notion_only gate in wizard
