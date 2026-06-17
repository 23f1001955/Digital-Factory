import os
import json
import re
import logging
from typing import Optional

from orchestrator.models import ComponentSpec, JobSpec, QualityReport, QualityIssue
from orchestrator.quality import run_quality_checks
from .llm_client import generate_text

logger = logging.getLogger(__name__)

HALLUCINATION_CHECK_PROMPT = """
You are a fact-checking AI. Given a research context and a piece of content, identify any statements in the content that are NOT supported by or CONTRADICT the research context.

Research context:
{research_context}

Content to check:
{content}

Return a JSON object with:
- "unsupported_claims": list of strings, each an unsupported or contradictory statement found. Empty list if all claims are supported.
- "hallucination_risk": "low" | "medium" | "high"
- "explanation": brief explanation of your assessment

Only flag claims that can be checked against the provided research context. Do not flag opinions, hypotheticals, or obviously reasonable statements.
"""

FIX_PROMPT_TEMPLATE = """
The previous version of this content had quality issues. Please rewrite it, fixing ALL of the following issues:

{issues_summary}

Original content was about: {niche}
Title: {title}
"""

EVALUATION_TARGETS = {
    "content_agent",
    "catalog_agent",
    "market_agent",
    "research_agent",
    "render_agent",
    "notion_content_agent",
    "diagram_agent",
}


def _read_file(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.warning(f"Failed to read {path}: {e}")
        return None


def _llm_hallucination_check(content: str, research_context: str) -> tuple:
    if not research_context:
        return [], "unknown"

    try:
        prompt = HALLUCINATION_CHECK_PROMPT.format(
            research_context=research_context[:5000],
            content=content[:4000],
        )
        result = generate_text(prompt)
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[1]
            result = result.rsplit("\n", 1)[0] if result.endswith("```") else result
        parsed = json.loads(result)
        flags = parsed.get("unsupported_claims", [])
        risk = parsed.get("hallucination_risk", "low")
        return flags, risk
    except Exception as e:
        logger.warning(f"LLM hallucination check failed: {e}")
        return [], "unknown"


def _detect_missing_citations(content: str) -> list:
    issues = []
    factual_patterns = re.findall(
        r"according to|studies show|research indicates|data shows|statistics show|\d+% of",
        content,
        re.IGNORECASE,
    )
    if factual_patterns:
        has_citations = bool(re.search(r"\[.+?\]\(.+?\)|\b\d{4}\b|source|citation|reference", content, re.IGNORECASE))
        if not has_citations:
            issues.append({
                "category": "missing_citation",
                "severity": "warning",
                "message": f"Content makes factual claims ({len(factual_patterns)} markers) without citations",
            })
    return issues


def _build_issues_summary(issues: list) -> str:
    lines = []
    for i, issue in enumerate(issues, 1):
        lines.append(f"{i}. [{issue['severity'].upper()}] {issue['category']}: {issue['message']}")
    return "\n".join(lines)


def evaluate(
    component: ComponentSpec,
    job_spec: JobSpec,
    context: dict,
    agent_output_path: str,
) -> QualityReport:
    content = _read_file(agent_output_path)
    if content is None:
        return QualityReport(
            component_id=component.id,
            score=0.0,
            threshold=0.6,
            issues=[QualityIssue(category="read_error", severity="error", message=f"Cannot read output: {agent_output_path}")],
        )

    # Skip quality checks for JSON outputs (structured data, not content)
    if agent_output_path.endswith(".json"):
        return QualityReport(
            component_id=component.id,
            score=1.0,
            threshold=0.6,
        )

    format_type = getattr(component, "format", "full")
    score, pattern_issues = run_quality_checks(content, format_type)

    all_issues = pattern_issues.copy()
    all_issues.extend(_detect_missing_citations(content))

    hallucination_flags = []
    if pattern_issues and any(i["severity"] == "error" for i in pattern_issues):
        research_path = context.get("market_research")
        if research_path and os.path.exists(research_path):
            research_content = _read_file(research_path)
            if research_content:
                flags, risk = _llm_hallucination_check(content, research_content)
                hallucination_flags = flags
                if flags:
                    all_issues.append({
                        "category": "hallucination",
                        "severity": "error" if risk == "high" else "warning",
                        "message": f"LLM flagged {len(flags)} unsupported claims",
                    })

    passed = score >= 0.6
    needs_human_review = bool(hallucination_flags) or any(
        i["category"] == "missing_citation" for i in all_issues
    )

    fix_prompt = None
    if not passed:
        fix_prompt = FIX_PROMPT_TEMPLATE.format(
            issues_summary=_build_issues_summary(all_issues),
            niche=job_spec.niche,
            title=job_spec.display_name or job_spec.niche,
        )

    quality_issues = [
        QualityIssue(**i) if isinstance(i, dict) else i for i in all_issues
    ]

    return QualityReport(
        component_id=component.id,
        score=score,
        threshold=0.6,
        issues=quality_issues,
        hallucination_flags=hallucination_flags,
        needs_human_review=needs_human_review,
        fix_prompt=fix_prompt,
    )


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> dict:
    """Standalone run entry point if evaluation_agent is called as a DAG node."""
    output_path = context.get("input_path")
    if not output_path:
        return {"error": "No input_path in context"}
    report = evaluate(component, job_spec, context, output_path)
    return report.model_dump(mode="json")
