import os
import logging
from .llm_client import generate_text

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        prompt = f"You are a systems architect for the niche: {job_spec.niche}.\n"
        prompt += "Generate a Mermaid.js diagram (e.g. flowchart or state diagram) mapping out the core workflow or funnel for this niche.\n"
        prompt += "Return ONLY the raw Mermaid syntax. Do not wrap it in markdown code blocks. Start with 'graph TD' or 'flowchart TD'."

        content = generate_text(prompt)

        # Strip code blocks if LLM still returned them
        if content.startswith("```"):
            lines = content.split("\n")
            if len(lines) > 2:
                content = "\n".join(lines[1:-1])

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Diagram agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
