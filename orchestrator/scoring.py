import math
import os
import json
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class ScoringMetric(BaseModel):
    name: str
    weight: float
    score: float
    reasoning: str
    data: dict = Field(default_factory=dict)

    @property
    def weighted_score(self) -> float:
        return round(self.weight * self.score, 4)


class ScoredOffer(BaseModel):
    product_type: str
    display_name: str
    total_score: float
    confidence: float
    metrics: List[ScoringMetric]
    reasoning: str


class ScoringFramework(BaseModel):
    offers: List[ScoredOffer]
    source_data: dict = Field(default_factory=dict)


def _calc_search_demand(research: dict) -> ScoringMetric:
    weight = 0.25
    trends = research.get("google_trends", {})
    interest = trends.get("interest_over_time")

    if not interest:
        return ScoringMetric(
            name="search_demand",
            weight=weight,
            score=0.5,
            reasoning="No Google Trends data available",
        )

    values = list(interest.values())
    avg = sum(values) / len(values)
    normalized = avg / 100.0

    direction = trends.get("trend_direction", "stable")
    bonus = {"rising": 0.1, "declining": -0.1, "stable": 0.0}.get(direction, 0.0)

    score = max(0.0, min(1.0, normalized + bonus))

    return ScoringMetric(
        name="search_demand",
        weight=weight,
        score=round(score, 4),
        reasoning=f"Avg interest {avg:.1f}, trend {direction}, normalized to {score:.2f}",
        data={"avg_interest": avg, "trend_direction": direction},
    )


def _calc_competition(research: dict) -> ScoringMetric:
    weight = 0.25
    landscape = research.get("competitor_landscape", {})
    competitors = landscape.get("direct_competitors", [])

    if len(competitors) == 0:
        return ScoringMetric(
            name="competition",
            weight=weight,
            score=0.9,
            reasoning="No direct competitors found — blue ocean",
            data={"competitor_count": 0},
        )

    count = len(competitors)
    score = max(0.1, 1.0 - math.log(count + 1) * 0.2)

    return ScoringMetric(
        name="competition",
        weight=weight,
        score=round(score, 4),
        reasoning=f"{count} direct competitors found, competition score {score:.2f}",
        data={"competitor_count": count},
    )


def _calc_market_viability(research: dict) -> ScoringMetric:
    weight = 0.20
    landscape = research.get("competitor_landscape", {})

    signals = 0
    if landscape.get("quality_gaps"):
        signals += 1
    if landscape.get("recommended_price"):
        signals += 1
    if landscape.get("pricing_tiers"):
        signals += 1

    base = 0.4 + (signals * 0.2)
    score = min(1.0, base)

    return ScoringMetric(
        name="market_viability",
        weight=weight,
        score=round(score, 4),
        reasoning=f"{signals} market viability signals found, score {score:.2f}",
        data={"signals": signals, "recommended_price": landscape.get("recommended_price")},
    )


def _calc_content_fit(research: dict, product_type: str) -> ScoringMetric:
    weight = 0.15
    content = research.get("content_recommendations", {})

    themes = content.get("key_themes", [])
    keywords = content.get("seo_keywords", [])
    signal_count = len(themes) + len(keywords)

    score = min(1.0, 0.3 + signal_count * 0.07)

    return ScoringMetric(
        name="content_fit",
        weight=weight,
        score=round(score, 4),
        reasoning=f"{signal_count} content signals (themes+keywords) for {product_type}, score {score:.2f}",
        data={"themes": len(themes), "keywords": len(keywords)},
    )


def _calc_trend_momentum(research: dict) -> ScoringMetric:
    weight = 0.10
    trends = research.get("google_trends", {})
    direction = trends.get("trend_direction", "stable")

    score = {"rising": 0.8, "stable": 0.5, "declining": 0.2}.get(direction, 0.5)

    return ScoringMetric(
        name="trend_momentum",
        weight=weight,
        score=score,
        reasoning=f"Trend direction is {direction}, momentum score {score}",
        data={"trend_direction": direction},
    )


def _calc_community_signals(research: dict) -> ScoringMetric:
    weight = 0.05
    discussions = research.get("reddit_discussions", [])

    if not discussions:
        return ScoringMetric(
            name="community_signals",
            weight=weight,
            score=0.5,
            reasoning="No Reddit discussion data available",
        )

    total_score = sum(d.get("score", 0) for d in discussions)
    total_comments = sum(d.get("num_comments", 0) for d in discussions)

    score = min(1.0, 0.3 + (total_score / 500) * 0.4 + (total_comments / 100) * 0.3)

    return ScoringMetric(
        name="community_signals",
        weight=weight,
        score=round(score, 4),
        reasoning=f"Reddit discussions: {total_score} total score, {total_comments} total comments",
        data={"total_reddit_score": total_score, "total_reddit_comments": total_comments},
    )


PRODUCT_TYPE_MAP = {
    "blog_kit": "Blog Kit",
    "boilerplate": "Boilerplate",
    "checklist": "Checklist",
    "course_launch": "Course Launch Kit",
    "database": "Database",
    "excel_template": "Excel Template",
    "operating_system": "Operating System",
    "prompt_pack": "Prompt Pack",
    "research_pack": "Research Pack",
    "resource_pack": "Resource Pack",
    "saas_docs": "SaaS Docs",
    "sop_pack": "SOP Pack",
    "swipe_file": "Swipe File",
    "visual_pack": "Visual Pack",
    "workflow_kit": "Workflow Kit",
}

ALL_METRICS = [
    _calc_search_demand,
    _calc_competition,
    _calc_market_viability,
    _calc_content_fit,
    _calc_trend_momentum,
    _calc_community_signals,
]


METRIC_DATA_KEYS = {
    _calc_search_demand: "google_trends",
    _calc_competition: "competitor_landscape",
    _calc_market_viability: "competitor_landscape",
    _calc_content_fit: "content_recommendations",
    _calc_trend_momentum: "google_trends",
    _calc_community_signals: "reddit_discussions",
}


def run(research_data: dict, schemas_dir: Optional[str] = None) -> ScoringFramework:
    product_types = dict(PRODUCT_TYPE_MAP)

    if schemas_dir and os.path.isdir(schemas_dir):
        for fname in os.listdir(schemas_dir):
            if fname.endswith(".json"):
                schema_path = os.path.join(schemas_dir, fname)
                try:
                    with open(schema_path, encoding="utf-8") as f:
                        schema = json.load(f)
                    pt = schema.get("product_type")
                    dn = schema.get("display_name")
                    if pt and dn:
                        product_types[pt] = dn
                except (json.JSONDecodeError, IOError):
                    pass

    offers = []
    total_metrics = len(ALL_METRICS)

    for pt, dn in product_types.items():
        metrics = []
        null_count = 0
        for metric_fn in ALL_METRICS:
            if metric_fn is _calc_content_fit:
                m = metric_fn(research_data, pt)
            else:
                m = metric_fn(research_data)
            metrics.append(m)
            required_key = METRIC_DATA_KEYS.get(metric_fn)
            if required_key and required_key not in research_data:
                null_count += 1

        total_score = sum(m.weighted_score for m in metrics) * 100
        confidence = 1.0 - (null_count / total_metrics) * 0.5

        offers.append(
            ScoredOffer(
                product_type=pt,
                display_name=dn,
                total_score=round(total_score, 2),
                confidence=round(confidence, 4),
                metrics=metrics,
                reasoning=f"Scored {total_score:.1f}/100 across {total_metrics} metrics with confidence {confidence:.2f}",
            )
        )

    offers.sort(key=lambda o: o.total_score, reverse=True)

    return ScoringFramework(offers=offers, source_data=research_data)
