import os
import json
import re
import unicodedata
import logging
import markdown
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

from orchestrator.models import ComponentSpec, JobSpec, AgentResult
from renderers.base import Renderer

logger = logging.getLogger(__name__)


def _parse_toc_items(md_text: str) -> list[dict]:
    items: list[dict] = []
    in_code_block = False

    for line in md_text.splitlines():
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            if in_code_block:
                continue

        if in_code_block:
            continue

        m = re.match(r'^(#{2,3})\s+(.+)$', stripped)
        if not m:
            continue

        level = len(m.group(1))
        title = m.group(2).strip()
        folded = unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode('ascii')
        anchor_id = re.sub(r'[^a-zA-Z0-9]+', '-', folded.lower()).strip('-')
        items.append({
            "level": level,
            "id": anchor_id,
            "title": title,
            "page": "",
        })

    return items


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        renderer: Renderer = context.get("renderer")
        if not renderer:
            raise ValueError("Renderer instance not injected into context")

        if not component.template:
            raise ValueError("No template specified for render_agent")

        html_content = ""
        mermaid_src = ""
        md_text = ""

        md_file = None
        if component.depends_on:
            for dep in component.depends_on:
                dep_path = context.get(dep)
                if dep_path and dep_path.endswith(".md") and os.path.exists(dep_path):
                    md_file = dep_path
                    break
        if not md_file:
            md_file = context.get("report")
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

            # Convert fenced mermaid code blocks to mermaid-renderable elements
            html_content = re.sub(
                r'<pre><code class="language-mermaid">(.*?)</code></pre>',
                r'<pre class="mermaid">\1</pre>',
                html_content,
                flags=re.DOTALL,
            )

        if md_file and md_file.endswith(".mmd") and os.path.exists(md_file):
            with open(md_file, "r", encoding="utf-8") as f:
                mermaid_src = f.read()

        toc_items = _parse_toc_items(md_text)

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
            "toc_items": toc_items,
        }

        # Inject cover image from context if available
        if "images" in context:
            try:
                with open(context["images"], "r", encoding="utf-8") as imf:
                    images_data = json.load(imf)
                cover_path = images_data.get("images", {}).get("cover", "")
                if cover_path and os.path.exists(cover_path):
                    template_vars["cover_image"] = os.path.abspath(cover_path).replace("\\", "/")
            except Exception as e:
                logger.warning(f"Failed to load cover image for template: {e}")

        if "catalog" in context:
            with open(context["catalog"], "r", encoding="utf-8") as cf:
                catalog_data = json.load(cf)
            if "visual_assets" in context:
                images_dir = os.path.abspath(context["visual_assets"])
                for i, item in enumerate(catalog_data):
                    item["image_path"] = os.path.join(images_dir, f"image_{i+1}.png").replace('\\', '/')
            template_vars["catalog"] = catalog_data

        final_html = template.render(**template_vars)

        if 'class="mermaid"' in final_html:
            local_mermaid = os.path.join("templates", "shared", "mermaid.min.js")
            mermaid_src = (
                f'file:///{os.path.abspath(local_mermaid).replace(chr(92), "/")}'
                if os.path.exists(local_mermaid) else
                "https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"
            )
            mermaid_script = (
                f'<script src="{mermaid_src}"></script>\n'
                '<script>mermaid.initialize({startOnLoad:true,theme:"default"});</script>\n'
            )
            idx = final_html.rfind("</body>")
            if idx != -1:
                final_html = final_html[:idx] + mermaid_script + final_html[idx:]

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        renderer.render_pdf(final_html, output_path)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Render agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
