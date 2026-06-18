import json
import os
import logging

from orchestrator.models import ComponentSpec, JobSpec, AgentResult
from orchestrator.scoring import run as run_scoring

logger = logging.getLogger(__name__)


def compute_value_tier(content_fit: float = 0.5, word_count: int = 0, page_count: int = 0, competitor_median: float = 0, product_type: str = "") -> str:
    low_ticket_types = {"checklist", "prompt_pack", "swipe_file", "excel_template"}
    mid_ticket_types = {"research_pack", "blog_kit", "visual_pack", "sop_pack", "resource_pack", "boilerplate"}
    high_ticket_types = {"course_launch", "operating_system", "workflow_kit", "database", "saas_docs"}

    if content_fit < 0.3 and word_count < 500:
        return "free"
    if page_count > 80 or content_fit > 0.7 or competitor_median > 45:
        return "high_ticket"
    if product_type in high_ticket_types:
        return "high_ticket"
    if page_count > 20 or competitor_median > 15 or product_type in mid_ticket_types:
        return "mid_ticket"
    return "low_ticket"


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    """Read market_research.json, score offers, write enriched output."""
    try:
        research_path = context.get("market_research")
        if not research_path or not os.path.exists(research_path):
            return AgentResult(
                status="failed",
                error=f"market_research.json not found at {research_path}",
            )

        with open(research_path, "r", encoding="utf-8") as f:
            research = json.load(f)

        adjustments = context.get("_scoring_adjustments", {})
        framework = run_scoring(research, schemas_dir="schemas", adjustments=adjustments)

        scored_data = []
        for offer in framework.offers:
            rec = {
                "product_type": offer.product_type,
                "display_name": offer.display_name,
                "total_score": offer.total_score,
                "confidence": offer.confidence,
                "reasoning": offer.reasoning,
            }
            rec["value_tier"] = compute_value_tier(
                content_fit=rec.get("content_fit", 0.5),
                word_count=research.get("estimated_word_count", 0),
                page_count=research.get("estimated_page_count", 0),
                competitor_median=rec.get("competitor_median_price", 0),
                product_type=rec.get("product_type", ""),
            )
            scored_data.append(rec)

        research["scored_recommendations"] = scored_data

        if scored_data:
            best = scored_data[0]
            research["recommended_product_type"] = best["product_type"]
            research["recommendation_confidence"] = best["confidence"]
            research["recommendation_reasoning"] = best["reasoning"]
            logger.info(
                "Scoring complete: best offer is '%s' (score=%.1f, confidence=%.2f)",
                best["product_type"], best["total_score"], best["confidence"],
            )

        with open(research_path, "w", encoding="utf-8") as f:
            json.dump(research, f, indent=2)

        return AgentResult(status="done", output_path=str(research_path))

    except Exception as e:
        logger.error(f"Offer scoring agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
