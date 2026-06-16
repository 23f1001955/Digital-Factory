import os
import json
import logging
from jinja2 import Environment, FileSystemLoader

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

PROMPT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        notion_api_key = os.getenv("NOTION_API_KEY")
        notion_parent_id = os.getenv("NOTION_PARENT_PAGE_ID")

        if not notion_api_key or not notion_parent_id:
            logger.warning("Notion not configured. Falling back to file output.")
            return _file_fallback(component, job_spec, context)

        from notion_client import Client
        notion = Client(auth=notion_api_key, notion_version="2022-06-28")

        # Find root page ID from notion_tree output in context
        root_page_id = None
        for key, path in context.items():
            if path and os.path.exists(path) and key == "notion_tree":
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                root_page_id = data.get("root_page_id")
                break

        if not root_page_id:
            logger.warning("No root page ID found in context. Falling back to file output.")
            return _file_fallback(component, job_spec, context)

        # Load and render prompt
        env = Environment(loader=FileSystemLoader(PROMPT_DIR))
        template_path = f"{component.id}.j2"
        if not os.path.exists(os.path.join(PROMPT_DIR, template_path)):
            logger.warning(f"Prompt {template_path} not found. Falling back to file output.")
            return _file_fallback(component, job_spec, context)

        template = env.get_template(template_path)

        # Build context from market_research if available
        research_data = {}
        for key, path in context.items():
            if path and os.path.exists(path) and "market_research" in key:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        research_data = json.load(f)
                except (json.JSONDecodeError, Exception):
                    pass
                break

        prompt = template.render(
            niche=job_spec.niche,
            product_type=job_spec.product_type,
            market_research=research_data,
        )

        from agents.llm_client import generate_text
        content = generate_text(prompt)

        # Create Notion page under root workspace
        page = notion.pages.create(
            parent={"page_id": root_page_id},
            properties={
                "title": {
                    "title": [{"text": {"content": component.id.replace("_", " ").title()}}]
                }
            },
            children=[
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content[:2000]}}]
                    },
                }
            ],
        )

        result = {
            "page_id": page["id"],
            "page_url": page.get("url", ""),
            "component_id": component.id,
        }

        output_path = os.path.join("outputs", job_spec.slug, f"notion_content_{component.id}.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Notion content agent failed for {component.id}: {e}")
        return _file_fallback(component, job_spec, context)


def _file_fallback(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    """Fallback: write content as .md file when Notion unavailable."""
    try:
        from agents.content_agent import run as content_run
        return content_run(component, job_spec, context)
    except Exception as e:
        return AgentResult(status="failed", error=f"Notion content + fallback failed: {e}")
