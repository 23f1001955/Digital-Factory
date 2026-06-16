import os
import json
import logging
from jinja2 import Environment, FileSystemLoader
from .llm_client import generate_text

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

PROMPT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        env = Environment(loader=FileSystemLoader(PROMPT_DIR))
        template = env.get_template("notion_schema.j2")

        market_research_json = ""
        for dep in component.depends_on:
            dep_path = context.get(dep)
            if dep_path and os.path.exists(dep_path):
                try:
                    with open(dep_path, "r", encoding="utf-8") as f:
                        research_data = json.load(f)
                    essential = {
                        k: research_data[k]
                        for k in (
                            "competitor_landscape",
                            "content_recommendations",
                            "market_insights",
                            "pipeline_plan",
                        )
                        if k in research_data
                    }
                    market_research_json = json.dumps(essential, indent=2)
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"Could not load {dep} as JSON: {e}")
                    market_research_json = ""
                break

        prompt = template.render(
            niche=job_spec.niche,
            product_type=job_spec.product_type,
            market_research_json=market_research_json,
        )

        content = generate_text(prompt)

        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from LLM: {e}")
            return AgentResult(status="failed", error=f"Invalid schema JSON: {e}")

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Notion schema agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
