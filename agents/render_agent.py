import os
import json
import logging
import markdown
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

from orchestrator.models import ComponentSpec, JobSpec, AgentResult
from renderers.base import Renderer

logger = logging.getLogger(__name__)


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        renderer: Renderer = context.get("renderer")
        if not renderer:
            raise ValueError("Renderer instance not injected into context")

        if not component.template:
            raise ValueError("No template specified for render_agent")

        html_content = ""
        mermaid_src = ""

        md_file = context.get(component.depends_on[0]) if component.depends_on else context.get("report")
        if md_file and md_file.endswith(".md") and os.path.exists(md_file):
            with open(md_file, "r", encoding="utf-8") as f:
                md_text = f.read()

            if getattr(component, "format", "full") == "guide":
                guide_prompt = (
                    f"Rewrite the following document as a concise, actionable guide "
                    f"focused on 'how to use, what to do, why to do it'. "
                    f"Keep it under 1000 words. Make it skimmable with bold key points.\n\n{md_text[:5000]}"
                )
                from .llm_client import generate_text
                md_text = generate_text(guide_prompt)

            html_content = markdown.markdown(md_text, extensions=['extra', 'toc'])

        if md_file and md_file.endswith(".mmd") and os.path.exists(md_file):
            with open(md_file, "r", encoding="utf-8") as f:
                mermaid_src = f.read()

        env = Environment(loader=FileSystemLoader("templates"))
        template = env.get_template(component.template)

        template_vars = {
            "title": job_spec.display_name or job_spec.niche,
            "subtitle": getattr(job_spec, "niche", ""),
            "niche": job_spec.niche,
            "product_type": job_spec.product_type.replace("_", " ").title(),
            "date": datetime.now().strftime("%B %d, %Y"),
            "content": html_content,
            "mermaid_src": mermaid_src,
            "theme": getattr(job_spec, "theme", "default"),
            "toc_items": [],
        }

        if "catalog" in context:
            with open(context["catalog"], "r", encoding="utf-8") as cf:
                catalog_data = json.load(cf)
            if "images" in context:
                images_dir = os.path.abspath(context["images"])
                for i, item in enumerate(catalog_data):
                    item["image_path"] = os.path.join(images_dir, f"image_{i+1}.png").replace('\\', '/')
            template_vars["catalog"] = catalog_data

        final_html = template.render(**template_vars)

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        renderer.render_pdf(final_html, output_path)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Render agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
