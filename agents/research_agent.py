import os
import logging
from jinja2 import Environment, FileSystemLoader
from .llm_client import generate_text

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

PROMPT_DIR = "prompts"
prompt_env = Environment(loader=FileSystemLoader(PROMPT_DIR))


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        template_name = f"{component.id}.j2"
        template = prompt_env.get_template(template_name)

        prompt = template.render(
            niche=job_spec.niche,
            title=job_spec.display_name or job_spec.niche,
        )

        content = generate_text(prompt)

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Research agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
