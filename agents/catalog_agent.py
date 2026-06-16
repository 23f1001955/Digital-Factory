import os
import json
import logging
from .llm_client import generate_text

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        mode = getattr(component, "format", "catalog")

        if mode in ("prompt", "resource"):
            research_path = context.get("market_research")
            if not research_path:
                raise ValueError("market_research dependency not met")
            with open(research_path, "r") as f:
                research = json.load(f)

            if mode == "prompt":
                prompt_text = (
                    f"You are an AI prompt engineer for the niche: {job_spec.niche}.\n"
                    f"Research context: {json.dumps(research, indent=2)[:2000]}\n\n"
                    "Generate a JSON array of 10-15 AI prompt templates. "
                    "Each object must have: 'prompt' (the template text with {{variables}}), "
                    "'category' (use case category), 'use_case' (1-sentence description). "
                    "Return ONLY raw JSON."
                )
            else:
                prompt_text = (
                    f"You are a resource curator for the niche: {job_spec.niche}.\n"
                    f"Research context: {json.dumps(research, indent=2)[:2000]}\n\n"
                    "Generate a JSON array of 15-20 curated resources. "
                    "Each object must have: 'name', 'url', 'description', 'category'. "
                    "Return ONLY raw JSON."
                )
        else:
            # Default: catalog mode (existing behavior)
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
