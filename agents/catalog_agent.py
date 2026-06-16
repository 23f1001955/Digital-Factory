import os
import json
import logging
from .llm_client import generate_text

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        if "image_prompts" not in context:
            raise ValueError("image_prompts dependency not met")

        with open(context["image_prompts"], "r") as f:
            prompts = json.load(f)

        prompt_text = f"You are a catalog curator for the niche: {job_spec.niche}.\n"
        prompt_text += f"For the following {len(prompts)} image prompts, generate a JSON array of objects. Each object should have a 'title' (max 5 words) and a 'description' (1 short sentence).\n\nPrompts:\n"
        for i, p in enumerate(prompts):
            prompt_text += f"{i+1}. {p}\n"
        prompt_text += "\nReturn ONLY raw JSON."

        content = generate_text(prompt_text)

        try:
            catalog_data = json.loads(content)
        except json.JSONDecodeError:
            # fallback if it's wrapped in markdown
            content = content.replace("```json\n", "").replace("\n```", "")
            catalog_data = json.loads(content)

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(catalog_data, f, indent=2)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Catalog agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
