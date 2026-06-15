import os
import logging
from jinja2 import Environment, FileSystemLoader
from .llm_client import generate_text

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

PROMPT_DIR = "prompts"
prompt_env = Environment(loader=FileSystemLoader(PROMPT_DIR))


def _web_search(query: str, max_results: int = 5) -> str:
    """Search the web for real URLs and data about a niche. Returns markdown or empty string."""
    try:
        import httpx
        url = "https://html.duckduckgo.com/html/"
        data = {"q": f"{query} tools resources platforms"}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = httpx.post(url, data=data, headers=headers, timeout=10.0)
        resp.raise_for_status()

        import re
        results = []
        for match in re.finditer(
            r'<a rel="nofollow" class="result__a" href="([^"]+)".*?>(.*?)</a>',
            resp.text, re.DOTALL
        ):
            href = match.group(1)
            if href.startswith("//"):
                href = "https:" + href
            title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            if title and href:
                results.append(f"- [{title}]({href})")
            if len(results) >= max_results:
                break

        if results:
            enriched = "## Web Search Results\n\nHere are real URLs and resources found online:\n\n"
            enriched += "\n".join(results)
            enriched += "\n\nUse these to make your output more accurate and real."
            logger.info(f"Web search returned {len(results)} results for: {query}")
            return enriched
        return ""
    except Exception as e:
        logger.debug(f"Web search failed (non-critical): {e}")
        return ""


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        template_name = f"{component.id}.j2"
        template = prompt_env.get_template(template_name)

        web_results = _web_search(job_spec.niche)

        prompt = template.render(
            niche=job_spec.niche,
            title=job_spec.display_name or job_spec.niche,
            web_results=web_results,
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
