import json
import os
import logging

from orchestrator.models import ComponentSpec, JobSpec, AgentResult
from orchestrator.scoring import run as run_scoring

logger = logging.getLogger(__name__)


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
            scored_data.append({
                "product_type": offer.product_type,
                "display_name": offer.display_name,
                "total_score": offer.total_score,
                "confidence": offer.confidence,
                "reasoning": offer.reasoning,
            })

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
