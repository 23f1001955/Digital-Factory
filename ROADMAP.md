# Digital Factory — Implementation Roadmap

> Living document. Update status as items are completed.

**Last updated:** 2026-06-17
**Current phase:** Phase 5 completed → Phase 6 recommended

---

## Phase 0 — Architecture Redesign (Foundation)

**Goal:** Decouple product generation from platform-specific publishing. Introduce Channel Layer.

| # | Item | Status | Priority | Est. | Files |
|---|------|--------|----------|------|-------|
| 0.1 | Introduce Channel Layer abstraction | `completed` | P0 | 2d | `orchestrator/models.py`, `orchestrator/orchestrator.py`, new `channels/` |
| 0.2 | Refactor schemas: remove platform-specific components | `completed` | P0 | 1d | All `schemas/*.json` |
| 0.3 | Create `channels/` package with base Channel class | `completed` | P0 | 1d | `channels/__init__.py`, `channels/base.py` |
| 0.4 | Extract Gumroad into `channels/gumroad_channel.py` | `completed` | P0 | 1d | `agents/gumroad_agent.py` → `channels/` |
| 0.5 | Decouple landing page from Gumroad dependency | `completed` | P1 | 1d | `agents/landing_agent.py`, `orchestrator/orchestrator.py` |
| 0.6 | Decouple social promotion from landing page dependency | `completed` | P1 | 0.5d | `agents/social_agent.py`, `orchestrator/orchestrator.py` |

**Why Phase 0 first:** Har future feature (scoring, Etsy channel, analytics) is architecture-dependent. Channel Layer ke bina system tightly coupled rahega.

---

## Phase 1 — Offer Selection Engine (Scoring)

**Goal:** Replace LLM opinion with data-driven product/niche scoring.

| # | Item | Status | Priority | Est. | Files |
|---|------|--------|----------|------|-------|
| 1.1 | Create `offer_scoring_agent` | `completed` | P0 | 1d | `agents/offer_scoring_agent.py`, `agents/registry.py` |
| 1.2 | Build scoring framework with weighted metrics | `completed` | P0 | 1d | `orchestrator/scoring.py` |
| 1.3 | Improve `discovery.json` schema to use scoring | `completed` | P0 | 0.5d | `schemas/discovery.json` |
| 1.4 | Add real demand data sources to scoring | `completed` | P1 | 2d | `agents/offer_scoring_agent.py`, `agents/research_tools.py` |
| 1.5 | Update `_switch_schema` to use scoring output | `completed` | P0 | 0.5d | `orchestrator/orchestrator.py` |

**Scoring data sources to integrate:**

| Source | Signal | Priority |
|--------|--------|----------|
| Google Trends | Search volume over time | P0 |
| Etsy product search | Competitor count, pricing, reviews | P0 |
| Gumroad research | Own portfolio performance | P0 |
| Meta Ads Library | Paid traffic validation (ad spend signal) | P1 |
| Reddit/GDELT/News | Market conversation volume | P1 |
| Keyword CPC data | Commercial intent signal | P2 |

---

## Phase 2 — Quality Validation Layer

**Goal:** Validate content before publishing. Prevent garbage from reaching customers.

| # | Item | Status | Priority | Est. | Files |
|---|------|--------|----------|------|-------|
| 2.1 | Create `evaluation_agent` (QA/Validator) | `completed` | P0 | 1d | New `agents/evaluation_agent.py`, `agents/registry.py` |
| 2.2 | Build content quality scoring criteria | `completed` | P0 | 1d | `agents/evaluation_agent.py` |
| 2.3 | Add validation gate in orchestrator | `completed` | P0 | 0.5d | `orchestrator/orchestrator.py` run loop |
| 2.4 | Add hallucination detection | `completed` | P1 | 1d | `agents/evaluation_agent.py` |
| 2.5 | Create `review_agent` (Human-in-the-loop) | `completed` | P2 | 1d | New `agents/review_agent.py` |
| 2.6 | Wire evaluation into notify/alert system | `completed` | P1 | 0.5d | `orchestrator/orchestrator.py`, `agents/evaluation_agent.py` |

**Quality criteria checklist:**
- [x] Minimum word count per component (configurable per type)
- [x] H1/H2 headings present and non-generic
- [x] No empty sections
- [x] Claims cross-referenced against research data
- [x] Fact-checkable statements flagged for human review
- [x] No templated/AI-ism patterns ("In today's digital landscape...")
- [x] Format compliance (Markdown structure valid)

---

## Phase 3 — Gumroad Channel: Listing Optimization

**Goal:** Maximize conversion from Gumroad traffic. A weak listing kills sales regardless of product quality.

| # | Item | Status | Priority | Est. | Files |
|---|------|--------|----------|------|-------|
| 3.1 | Add pricing optimization | `completed` | P1 | 0.5d | `channels/gumroad_listing.py` |
| 3.2 | Improve listing description generation (AIDA) | `completed` | P1 | 1d | `channels/gumroad_listing.py` |
| 3.3 | Add cover/thumbnail A/B testing support | `completed` | P2 | 1d | `channels/gumroad_ab_testing.py` |
| 3.4 | Improve keyword/tag generation | `completed` | P1 | 0.5d | `channels/gumroad_listing.py` |
| 3.5 | Add Gumroad analytics pull | `completed` | P0 | 1d | `channels/gumroad_analytics.py` |
| 3.6 | Add listing quality score | `completed` | P2 | 0.5d | `channels/gumroad_analytics.py` |

---

## Phase 4 — Social Agent: Broadcasting → Strategy

**Goal:** Move from single posts to multi-post sequences with content strategy.

| # | Item | Status | Priority | Est. | Files |
|---|------|--------|----------|------|-------|
| 4.1 | Add content calendar generation (7–14 day) | `completed` | P1 | 1d | `agents/social/calendar.py` |
| 4.2 | Add multi-post sequences | `completed` | P1 | 1d | `agents/social/sequences.py` |
| 4.3 | Add content repurposing (1 pack → 10 posts) | `completed` | P1 | 1d | `agents/social/repurposing.py` |
| 4.4 | Add engagement tracking | `completed` | P2 | 1d | `agents/social/engagement.py` |
| 4.5 | Add platform-specific content strategy | `completed` | P2 | 1d | `agents/social/platform_strategy.py` |
| 4.6 | Add DM/comment automation hooks | `completed` | P2 | 2d | `agents/social/automation.py` |

---

## Phase 5 — Analytics & Feedback Loop

**Goal:** Close the loop. Sales data → Next product generation learns from past performance.

| # | Item | Status | Priority | Est. | Files |
|---|------|--------|----------|------|-------|
| 5.1 | Create `analytics_agent` | `completed` | P1 | 1d | `agents/analytics_agent.py` |
| 5.2 | Build sales data schema | `completed` | P1 | 0.5d | `orchestrator/analytics_models.py` |
| 5.3 | Add Gumroad analytics pull | `completed` | P0 | 1d | `channels/gumroad_channel.py:get_analytics()` |
| 5.4 | Create feedback loop: analytics → next product | `completed` | P2 | 2d | `orchestrator/feedback_loop.py` |
| 5.5 | Add run-to-run learning | `completed` | P2 | 2d | `orchestrator/feedback_loop.py` |
| 5.6 | Add conversion tracking (landing → Gumroad → purchase) | `completed` | P2 | 1d | `agents/landing_agent.py`, `channels/gumroad_channel.py` |
| 5.7 | Build simple dashboard | `completed` | P2 | 2d | `cli/dashboard.py` |

**Analytics data model (proposed):**

```python
class SalesRecord(BaseModel):
    product_slug: str
    channel: str  # "gumroad" | "etsy" | "shopify" | "store"
    date: datetime
    views: int
    sales: int
    revenue: float
    refunds: int
    conversion_rate: float
    traffic_source: Optional[str]
```

---

## Phase 6 — Dynamic Pipeline Safety

**Goal:** LLM suggests, system decides. Prevent cascading failures from bad LLM output.

| # | Item | Status | Priority | Est. | Files |
|---|------|--------|----------|------|-------|
| 6.1 | Restrict dynamic pipeline: LLM suggests → system maps to templates | `pending` | P2 | 1d | `orchestrator/orchestrator.py:_merge_pipeline_plan` |
| 6.2 | Build component template registry | `pending` | P2 | 1d | New `orchestrator/component_templates.py` |
| 6.3 | Add circuit breaker for dynamic components | `pending` | P2 | 0.5d | `orchestrator/orchestrator.py` |
| 6.4 | Improve error messages | `pending` | P2 | 0.5d | `orchestrator/orchestrator.py` |
| 6.5 | Add dry-run mode for pipeline plans | `pending` | P2 | 1d | `cli/dry_run.py` or `cli/wizard.py` |

**Component template registry:**

| Template | Description | Agent | Output format |
|----------|-------------|-------|---------------|
| `case_study` | Real-world use case | content_agent | Markdown |
| `comparison_table` | Tool/method comparison | content_agent | Markdown table |
| `faq_section` | Frequently asked questions | content_agent | Markdown |
| `resource_list` | Curated resource collection | content_agent | Markdown |
| `step_by_step_guide` | Tutorial/how-to | content_agent | Markdown |
| `checklist` | Actionable checklist | content_agent | Markdown |

---

## Phase 7 — Platform Expansion (Channel Layer)

**Goal:** Ship to multiple platforms from same product output.

| # | Item | Status | Priority | Est. | Files |
|---|------|--------|----------|------|-------|
| 7.1 | Create Etsy channel | `pending` | P2 | 3d | New `channels/etsy_channel.py` |
| 7.2 | Create Shopify channel | `pending` | P3 | 3d | New `channels/shopify_channel.py` |
| 7.3 | Create Own Store channel (Stripe) | `pending` | P2 | 1d | New `channels/store_channel.py` |
| 7.4 | Add channel configuration UI | `pending` | P2 | 1d | `cli/wizard.py`, `orchestrator/models.py` |
| 7.5 | Standardize channel output format | `pending` | P1 | 0.5d | `channels/base.py` |

**Channel interface (proposed):**

```python
class BaseChannel(ABC):
    @abstractmethod
    def validate(self) -> bool  # Check credentials + quota
    @abstractmethod
    def publish(self, product: ProductArtifact) -> PublishResult
    @abstractmethod
    def update(self, product_id: str, product: ProductArtifact) -> PublishResult
    @abstractmethod
    def get_analytics(self, product_id: str) -> AnalyticsData
```

---

## Phase 8 — Production System Hardening

**Goal:** Make the system production-ready with monitoring, rate limits, and reliability.

| # | Item | Status | Priority | Est. | Files |
|---|------|--------|----------|------|-------|
| 8.1 | Add landing page vs direct Gumroad A/B test | `pending` | P2 | 2d | New `tests/conversion_test.py` |
| 8.2 | Add distribution bottleneck analysis | `pending` | P2 | 1d | `agents/analytics_agent.py` |
| 8.3 | Add product categorization by value | `pending` | P2 | 1d | `agents/offer_scoring_agent.py` |
| 8.4 | Add rate-limit aware scheduling | `pending` | P2 | 1d | `orchestrator/orchestrator.py` |
| 8.5 | Add batch run concurrency control | `pending` | P2 | 1d | `main.py:process_batch` |
| 8.6 | Improve CLI wizard | `pending` | P3 | 2d | `cli/wizard.py` |

---

## Discovery Mode — Data Sources (Cross-cutting)

These data sources feed into the Offer Scoring Engine (Phase 1) and Market Research:

| Source | Purpose | Integration method | API Key needed | Priority |
|--------|---------|-------------------|----------------|----------|
| Google Trends | Search volume signal | `pytrends` (existing) | No | P0 |
| Gumroad search | Competitor + pricing | API (existing) | `GUMROAD_ACCESS_TOKEN` | P0 |
| Etsy product search | Sales data + reviews | Scrape / Etsy API v3 | `ETSY_API_KEY` | P0 |
| Meta Ads Library | Paid traffic validation | Scrape `facebook.com/ads/library` | No (public) | P1 |
| Reddit | Conversation volume | PRAW (existing) | Reddit API | P1 |
| GDELT / NewsAPI | News trends | Existing | Optional | P2 |
| Ahrefs / SEMrush | Keyword difficulty + CPC | API | Paid | P3 |

---

## How to use this roadmap

1. **Pick one item** from current phase based on priority
2. Read the item's reasoning + files to touch
3. Implement
4. Update status from `pending` → `in_progress` → `completed`
5. Move to next item

**Recommended start order:**

```
0.1 → 0.2 → 0.3 → 0.4  (Channel Layer — foundation)
1.1 → 1.2 → 1.3 → 1.5  (Offer Scoring — core moat)
2.1 → 2.2 → 2.3        (Validation — prevents garbage)
3.5 → 5.1 → 5.2 → 5.3  (Analytics — visibility)
0.5 → 0.6               (Decouple remaining)
4.1 → 4.2 → 4.3        (Social strategy)
5.4 → 5.5               (Feedback loop — self-improvement)
6.1 → 6.2               (Pipeline safety)
```

---

## Progress Summary

| Phase | Total | Pending | In Progress | Completed |
|-------|-------|---------|-------------|-----------|
| 0 — Architecture Redesign | 6 | 0 | 0 | 6 |
| 1 — Offer Selection Engine | 5 | 0 | 0 | 5 |
| 2 — Quality Validation | 6 | 0 | 0 | 6 |
| 3 — Gumroad Listing Opt. | 6 | 0 | 0 | 6 |
| 4 — Social Strategy | 6 | 0 | 0 | 6 |
| 5 — Analytics & Feedback | 7 | 0 | 0 | 7 |
| 6 — Dynamic Pipeline Safety | 5 | 5 | 0 | 0 |
| 7 — Platform Expansion | 5 | 5 | 0 | 0 |
| 8 — Production Hardening | 6 | 6 | 0 | 0 |
| **Total** | **52** | **16** | **0** | **36** |
