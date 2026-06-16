import os
import csv
import json
import logging

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        data_path = context.get("database")
        if not data_path:
            # Fallback: read from market_research output
            research_path = context.get("market_research")
            if not research_path:
                raise ValueError("Neither 'database' nor 'market_research' found in context")
            with open(research_path, "r") as f:
                research = json.load(f)
            data = research.get("database")
            if data is None:
                raise ValueError("'database' key not found in market research output")
        else:
            with open(data_path, "r") as f:
                data = json.load(f)

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        if not data:
            raise ValueError("Database is empty")

        keys = data[0].keys()

        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"CSV export agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
