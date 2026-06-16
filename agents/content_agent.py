import os
import logging
from jinja2 import Environment, FileSystemLoader
from .llm_client import generate_text

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

PROMPT_DIR = "prompts"

prompt_env = Environment(loader=FileSystemLoader(PROMPT_DIR))

CONTEXT_EXTRACT_PROMPT = """
Given the following document, extract 3-5 key themes, concepts, or takeaways that would help align another document on the same topic.

Document:
{doc_text}

Return only a bullet list of 3-5 key points, each 1 sentence.
"""


def _extract_context(doc_path: str) -> str:
    """Extract key themes from a dependency document for cross-component context."""
    try:
        with open(doc_path, "r", encoding="utf-8") as f:
            text = f.read()
        excerpt = text[:3000]
        prompt = CONTEXT_EXTRACT_PROMPT.format(doc_text=excerpt)
        return generate_text(prompt)
    except Exception as e:
        logger.warning(f"Context extraction failed for {doc_path}: {e}")
        return ""


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        template_name = f"{component.id}.j2"
        template_path = os.path.join(PROMPT_DIR, template_name)

        if not os.path.exists(template_path):
            prompt = f'You are an expert content creator for the niche: "{job_spec.niche}".\n'
            prompt += f"Write a comprehensive document (Markdown) covering {component.id}. Must start with an H1 title."
            content = generate_text(prompt)
        else:
            template = prompt_env.get_template(template_name)

            render_context = {
                "niche": job_spec.niche,
                "title": job_spec.display_name or job_spec.niche,
                "context": "",
            }

            for dep in component.depends_on:
                dep_path = context.get(dep)
                if dep_path and os.path.exists(dep_path):
                    extracted = _extract_context(dep_path)
                    render_context["context"] += f"\n### From {dep}:\n{extracted}\n"

            for data_key in ("database", "sources"):
                data_path = context.get(data_key)
                if data_path and os.path.exists(data_path):
                    with open(data_path, "r", encoding="utf-8") as f:
                        render_context[data_key] = f.read()
                else:
                    render_context[data_key] = ""

            content_mode = getattr(component, "format", "full")

            if content_mode == "guide":
                render_context["mode"] = "guide"
            elif content_mode == "notion":
                render_context["mode"] = "notion"
            else:
                render_context["mode"] = "full"

            prompt = template.render(**render_context)
            content = generate_text(prompt)

        for attempt in range(2):
            if content.startswith("#"):
                break
            logger.warning(
                "Component %s missing H1, retrying (attempt %s)...",
                component.id,
                attempt + 1,
            )
            prompt += "\n\nCRITICAL: Start the response with an # H1 Title."
            content = generate_text(prompt)

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Content agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
