import os
import json
import logging
from .llm_client import generate_text

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

SCHEMA_PROMPT = """You are a Notion database architect specializing in {niche}.

Design a complete Notion workspace blueprint for a "{niche}" professional or team.

Generate a JSON object with a 'databases' array. Each database has:

{{
  "databases": [
    {{
      "name": "Database Name",
      "description": "What this database tracks",
      "icon": "emoji (e.g. 📁)",
      "properties": {{
        "Property Name": {{"type": "title", "options": []}},
        "Status": {{"type": "select", "options": ["Option 1", "Option 2", "Option 3"]}},
        "Date": {{"type": "date"}},
        "Related": {{"type": "relation", "target": "Other Database Name"}},
        "Formula": {{"type": "formula", "expression": "prop(\\"Property Name\\")"}},
        "Number": {{"type": "number", "format": "number"}},
        "URL": {{"type": "url"}},
        "Email": {{"type": "email"}},
        "Phone": {{"type": "phone"}},
        "Checkbox": {{"type": "checkbox"}},
        "Files": {{"type": "files"}}
      }}
    }}
  ]
}}

Supported property types: title, text, number, select, multi_select, date, person, files, checkbox, url, email, phone, formula, relation, rollup, created_time, created_by, last_edited_time, last_edited_by, status

Relations: use 'target' field to match database name. Use 'type': 'rollup' with 'rollup_property', 'rollup_function' for rollups.

Create 3-5 databases that form a connected system. Use relations to link them.

Return ONLY raw JSON — no markdown, no explanation, no code block wrapping.
"""


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        prompt = SCHEMA_PROMPT.format(niche=job_spec.niche)

        context_text = ""
        for dep in component.depends_on:
            dep_path = context.get(dep)
            if dep_path and os.path.exists(dep_path):
                with open(dep_path, "r", encoding="utf-8") as f:
                    excerpt = f.read()[:2000]
                context_text += f"\n\nContent from {dep}:\n{excerpt[:2000]}"

        if context_text:
            prompt += f"\n\nUse this context to inform the database design:\n{context_text}"

        content = generate_text(prompt)

        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])

        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from LLM: {e}")
            return AgentResult(status="failed", error=f"Invalid schema JSON: {e}")

        output_path = os.path.join("outputs", job_spec.slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Notion schema agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
