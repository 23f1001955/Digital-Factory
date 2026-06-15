# Market Research Agent Design

**Date:** 2026-06-13
**Status:** Draft
**Product:** Digital Product Factory

## Overview

A specialized agent that performs deep market research *before* content creation, using Gumroad API data + LLM analysis to produce structured competitive intelligence that feeds into all downstream agents (content, visual, render, publish).

## Motivation

The existing `gumroad_research` component runs **after** content generation, meaning content cannot benefit from market data. The Market Research Agent runs **before** content, so every product is informed by real competitor analysis.

## Architecture

```
market_research (runs first, depends_on: [])
         │
         ├──→ content_agent (uses competitor gaps, keywords)
         ├──→ visual_agent (uses trending keywords for image prompts)
         ├──→ render_agent (uses pricing for cover design)
         └──→ gumroad_publish (uses price recommendations)
```

## Agent: `market_agent`

### Signature

```python
def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
```

### Process

1. **Fetch seller's Gumroad products** via `GET /v2/products` (reuses existing `_gumroad_api` helper or its own httpx call)
2. **Build LLM prompt** with niche, seller products, and product type
3. **Call LLM** to generate structured analysis covering:
   - Competitor landscape (direct competitors, their pricing, strengths, weaknesses)
   - Pricing analysis (budget/mid/premium tiers, sweet spot)
   - Quality gaps (what competitors are missing)
   - Trending keywords and SEO terms
   - Content recommendations (tone, themes, key messages)
4. **Write output** to `outputs/{slug}/data/market_research.json`
5. **Graceful degradation** — if Gumroad API fails, LLM works from training knowledge alone

### Output Schema

```json
{
  "niche": "AI Writing Tools",
  "seller_products_count": 3,
  "seller_products": [
    {"name": "...", "price": 29, "sales": 150}
  ],
  "competitor_landscape": {
    "direct_competitors": [
      {"name": "Competitor X", "price": 19, "strengths": ["strong marketing"], "weaknesses": ["thin content"]}
    ],
    "pricing_tiers": {"budget": "$5-15", "mid": "$15-35", "premium": "$35-100"},
    "recommended_price": 29,
    "quality_gaps": ["Competitors lack onboarding", "No automation features"],
    "trending_keywords": ["AI writing", "content automation", "prompt engineering"]
  },
  "content_recommendations": {
    "tone": "professional but approachable",
    "key_themes": ["productivity", "time-saving", "quality"],
    "seo_keywords": ["best AI writing tools", "content workflow automation"]
  }
}
```

### Graceful Degradation

- No `GUMROAD_ACCESS_TOKEN` → LLM performs research from training knowledge
- API call fails → same fallback
- LLM call fails → minimal output with just niche + current time

## Prompt Template

`prompts/market_research.j2` — structured prompt for LLM:

```
You are a digital product market analyst. Analyze the niche "{{ niche }}"
for a {{ product_type }} product.

{{ seller_products_section }}

Generate a comprehensive market analysis in JSON format:
- competitor_landscape: direct competitors with pricing, strengths, weaknesses
- pricing_tiers: budget/mid/premium ranges
- recommended_price: optimal price point
- quality_gaps: 3-5 things competitors are missing
- trending_keywords: 5-10 keywords trending in this niche
- content_recommendations: tone, key themes, SEO keywords

Return ONLY valid JSON, no markdown, no code blocks.
```

## Schema Changes

Add `market_research` as the first component in all 7 schemas (`depends_on: []`), and add `"market_research"` to the `depends_on` array of every content component.

### Pattern

```json
{
  "id": "market_research",
  "agent": "market_agent",
  "output": "data/market_research.json",
  "depends_on": []
},
```

Content components (report, guide, post_draft, etc.) get `"market_research"` prepended to their `depends_on`:

```json
"depends_on": ["market_research", "database", "sources"]
```

## Files to Create

| File | Purpose |
|------|---------|
| `agents/market_agent.py` | Market research agent implementation |
| `prompts/market_research.j2` | LLM prompt template |

## Files to Modify

| File | Changes |
|------|---------|
| `agents/registry.py` | Add `market_agent` entry |
| `schemas/*.json` (x7) | Add `market_research` component + update content depends_on |

## Constraints

1. No hardcoded secrets — `GUMROAD_ACCESS_TOKEN` from `.env`
2. Graceful degradation — API failures → LLM-only research
3. Runs first in all schemas — all content agents depend on it
4. Resumability — tracked in `job_state.json` like all other components

## Self-Review Notes

- Scope: focused on market research agent only. No unrelated features.
- Consistent with existing patterns: registry, schema-driven, agent contract
- Content agents already use context dict — market_research output flows naturally
