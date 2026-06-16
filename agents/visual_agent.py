import os
import json
import logging

from orchestrator.models import ComponentSpec, JobSpec, AgentResult
from agents.image_agent import generate_from_prompt

logger = logging.getLogger(__name__)


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        if "image_prompts" not in context:
            raise ValueError("image_prompts dependency not met")

        with open(context["image_prompts"], "r") as f:
            prompts = json.load(f)

        if isinstance(prompts, list) and all(isinstance(p, str) for p in prompts):
            prompt_list = prompts
        elif isinstance(prompts, list) and all(isinstance(p, dict) for p in prompts):
            prompt_list = [p.get("prompt", str(p)) for p in prompts]
        else:
            prompt_list = list(prompts) if isinstance(prompts, list) else [str(prompts)]

        output_dir = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(output_dir, exist_ok=True)

        aspect_ratios = ["16:9", "1:1", "2:3", "4:5"]
        results = {}

        for i, prompt_text in enumerate(prompt_list):
            img_id = f"image_{i+1}"
            ar = aspect_ratios[i % len(aspect_ratios)]
            output_path = os.path.join(output_dir, f"{img_id}.png")

            file_path = generate_from_prompt(prompt_text, output_path, ar)
            results[img_id] = file_path
            logger.info(f"Generated {img_id} -> {file_path}")

        output_path = os.path.join(
            "outputs", job_spec.slug, component.output.rstrip("/"), "_manifest.json"
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"images": results, "count": len(results)}, f, indent=2)

        return AgentResult(status="done", output_path=output_dir, error=None)

    except Exception as e:
        logger.error(f"Visual agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
