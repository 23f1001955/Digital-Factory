# Phase 3: Multi-Format Delivery Design

**Date:** 2026-06-16
**Status:** Draft
**Product:** Digital Product Factory
**Prerequisite:** Phase 1 (discovery mode) + Phase 2 (8 new schemas)

## Overview

A digital factory should produce multiple outputs from a single run. Currently each run produces exactly one format per component. Phase 3 enables market_agent to recommend output formats based on niche competition, and the orchestrator routes each component to produce one or more formats simultaneously (CSV + XLSX + PDF + Notion from one pipeline).

## Architecture

```
schema.json (capabilities)
    ↓
market_agent (recommended_formats → per niche)
    ↓
orchestrator (merge: capabilities ∩ recommended_formats)
    ↓
agents (check active_formats → produce multiple files)
    ↓
delivery_map (per-format routing → ZIP / Gumroad / Notion)
```

Each component declares what it *can* produce. Market_agent recommends what it *should* produce for that niche. Orchestrator validates the intersection. Agents produce the active formats.

## 1. Component Capabilities Field

### File: `orchestrator/models.py`

Add `capabilities` to both `ComponentSpec` and `PipelineComponent`:

```python
class ComponentSpec(BaseModel):
    id: str
    agent: str
    output: str
    depends_on: List[str] = Field(default_factory=list)
    uses_renderer: bool = False
    template: Optional[str] = None
    format: Literal["full", "guide", "notion", "prompt", "resource"] = "full"
    delivery: List[str] = Field(default_factory=lambda: ["zip"])
    capabilities: List[str] = Field(default_factory=list)  # NEW
    active_formats: List[str] = Field(default_factory=list)  # NEW — runtime, not serialized in schema
```

**Rules:**
- `capabilities = []` → legacy mode (single output, unchanged behavior)
- `active_formats = []` → legacy mode (no multi-format override)
- Both are empty lists by default, so existing schemas load without errors
- `active_formats` is set by orchestrator at runtime, not stored in schema JSON

### Capability Values

| Format | Meaning |
|---|---|
| `"csv"` | CSV file output |
| `"xlsx"` | Excel spreadsheet (via openpyxl) |
| `"pdf"` | PDF document (via render_agent) |
| `"md"` | Markdown file |
| `"json"` | JSON data file |
| `"notion"` | Notion page sync |

Not all agents support all formats. Each agent validates `active_formats` against its own supported set.

## 2. Market Agent Format Recommendation

### File: `agents/market_agent.py`

Market agent output gains a new field:

```json
{
  "niche": "real estate agents",
  "recommended_product_type": "database",
  "recommendation_confidence": 0.85,
  "recommended_formats": {
    "database_export": ["csv"],
    "market_research": ["pdf"]
  },
  ...
}
```

**Rules:**
- Keys must match component IDs in the schema
- Values must be a subset of each component's `capabilities`
- Orchestrator silently ignores unknown component IDs or unsupported formats
- If `recommended_formats` is absent or empty → legacy mode

### File: `prompts/market_research.j2`

Add format recommendation instruction after the product type catalog. The prompt passes each schema component's ID and capabilities so market_agent knows what's available.

```
## Format Recommendation

The `{recommended_product_type}` schema has these components with their capabilities:

| Component ID | Capabilities |
|---|---|
| database_export | csv, xlsx |
| market_research | md |

For this niche's competitors, determine which FORMATS each component should output.
Consider:
- What formats do top competitors sell? (PDF guides, CSV data, Excel templates?)
- Which formats will the buyer actually use?
- CSV if raw data makes sense; PDF if it needs explanation; XLSX if it needs formulas

Output in "recommended_formats" mapping each component ID to the active format list.
Leave a component OUT if it should produce its default single output.
```

## 3. Orchestrator Merge Logic

### File: `orchestrator/orchestrator.py`

After market_agent completes and schema switch runs, the orchestrator merges format recommendations:

```python
def _merge_format_recommendations(self, research_path: str) -> None:
    """Merge market_agent's recommended_formats into component active_formats."""
    try:
        with open(research_path) as f:
            research = json.load(f)
        fmt_recs = research.get("recommended_formats", {})
        if not fmt_recs:
            return  # legacy mode

        comp_map = {c.id: c for c in self.schema.components}
        for comp_id, formats in fmt_recs.items():
            comp = comp_map.get(comp_id)
            if not comp:
                logger.warning("recommended_formats references unknown component: %s", comp_id)
                continue
            if not comp.capabilities:
                logger.warning(
                    "recommended_formats for %s but component has no capabilities",
                    comp_id,
                )
                continue
            active = [f for f in formats if f in comp.capabilities]
            if active:
                comp.active_formats = active
                logger.info("Component %s active formats: %s", comp_id, active)
    except Exception as e:
        logger.error("Failed to merge format recommendations: %s", e)
```

Called in `run()` after `_switch_schema()`:

```python
if component.id == "market_research" and result.status == "done":
    if self.job_spec.product_type == "discovery":
        # existing schema switch logic...
    self._merge_pipeline_plan(result.output_path)
    self._merge_format_recommendations(result.output_path)  # NEW
    ordered_components = self._get_execution_order()
    ...
```

### Edge Cases

| Scenario | Handling |
|---|---|
| `recommended_formats` missing entirely | Legacy mode — unchanged |
| Component ID in `recommended_formats` not in schema | Silently ignored with warning |
| Format not in component's `capabilities` | Silently filtered out |
| No valid formats after filtering | Legacy mode for that component |
| All components have empty `active_formats` | Full legacy pipeline |
| Resume from pre-Phase-3 job state | No `active_formats` stored → legacy mode |

## 4. Agent Changes

### 4.1 Pattern

Each agent that supports multi-format follows this pattern:

```python
def run(component, job_spec, context):
    active_formats = getattr(component, "active_formats", [])
    if not active_formats:
        # Legacy single-output mode
        return _run_legacy(component, job_spec, context)
    
    outputs = {}
    for fmt in active_formats:
        outputs[fmt] = _run_format(fmt, component, job_spec, context)
    
    primary = list(outputs.values())[0]
    return AgentResult(status="done", output_path=primary, output_paths=outputs)
```

A new optional field `output_paths: Optional[List[str]] = None` on `AgentResult` stores all format paths for delivery routing.

### 4.2 csv_export_agent

Supported formats: `["csv", "xlsx"]`

- `"csv"` → existing behavior (writes CSV)
- `"xlsx"` → write Excel file via openpyxl

When both active, write both files to the same directory using `{component_id}.{ext}` naming.

New dependency: `openpyxl>=3.1.0` in `requirements.txt`.

### 4.3 content_agent

Supported formats: `["md", "pdf", "notion"]`

- `"md"` → existing markdown output
- `"pdf"` → run render_agent after content generation automatically
- `"notion"` → run notion_content_agent after content generation automatically

### 4.4 Other Agents

No changes needed unless they need to support multi-format. Default single-output mode is preserved.

## 5. Delivery Map Extension

### File: `orchestrator/orchestrator.py`

`_delivery_map` extended to track per-format output paths:

```python
delivery_map[comp_id] = {
    "outputs": {
        "csv": "/path/to/file.csv",
        "xlsx": "/path/to/file.xlsx",
    },
    "delivery": ["zip", "gumroad"],
    "primary": "csv",
}
```

- ZIP delivery: includes all output files for the component
- Gumroad: attaches the primary format file (first in `active_formats`, or legacy single file)
- Notion delivery: used when `"notion"` in active_formats or notion-only mode

The `AgentResult` gains an `output_paths: Optional[Dict[str, str]] = None` field for this:

```python
class AgentResult(BaseModel):
    status: Literal["pending", "running", "done", "failed", "skipped"]
    output_path: Optional[str] = None
    error: Optional[str] = None
    output_paths: Optional[Dict[str, str]] = None  # NEW — format → path
```

## 6. Testing Strategy

### File: `tests/test_multi_format.py`

| Test | Description |
|---|---|
| `test_component_spec_capabilities_default` | Existing ComponentSpec loads with empty capabilities |
| `test_orchestrator_merges_format_recs` | orchestrator sets active_formats after market_agent recommends |
| `test_invalid_format_filtered` | Unknown formats in recommended_formats are silently ignored |
| `test_legacy_no_capabilities` | Schema without capabilities runs unchanged |
| `test_csv_agent_multi_format` | csv_export_agent writes both CSV and XLSX when both active |
| `test_delivery_map_per_format` | delivery_map tracks per-format paths |
| `test_market_agent_recommends_formats` | market_agent output includes recommended_formats |
| `test_backward_compat_no_recs` | No recommended_formats → legacy mode |

## 7. Files Changed

| File | Action |
|---|---|
| `orchestrator/models.py` | Add `capabilities`, `active_formats` to ComponentSpec/PipelineComponent; add `output_paths` to AgentResult |
| `orchestrator/orchestrator.py` | Add `_merge_format_recommendations()`, call in `run()`; extend delivery_map |
| `agents/market_agent.py` | Pass component capabilities in prompt, include `recommended_formats` in output |
| `agents/csv_export_agent.py` | Multi-format support: CSV + XLSX |
| `prompts/market_research.j2` | Add format recommendation instruction |
| `requirements.txt` | Add `openpyxl>=3.1.0` |
| `tests/test_multi_format.py` | Integration tests for multi-format delivery |

## 8. Backward Compatibility

| Pre-Phase-3 | Phase 3 | Result |
|---|---|---|
| Schema without `capabilities` | Same schema | Legacy mode — no change |
| Market agent without `recommended_formats` | Same agent output | Legacy mode — no change |
| Job spec with `product_type: "research_pack"` | Same | Legacy mode — no change |
| Resume from pre-Phase-3 state | No `active_formats` in state | Legacy mode — no change |
| Agent that doesn't check `active_formats` | Same code | Legacy mode — no change |
