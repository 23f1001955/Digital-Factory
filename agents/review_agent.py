import os
import logging
from datetime import datetime, timezone

from orchestrator.models import ComponentSpec, JobSpec, AgentResult, QualityReport

logger = logging.getLogger(__name__)


def write_review_log(
    component: ComponentSpec,
    job_spec: JobSpec,
    report: QualityReport,
) -> str:
    slug = job_spec.slug
    review_dir = os.path.join("outputs", slug, "review")
    os.makedirs(review_dir, exist_ok=True)

    path = os.path.join(review_dir, f"{component.id}_review.md")
    lines = []
    lines.append(f"# Human Review: {component.id}")
    lines.append(f"**Slug:** {slug}")
    lines.append(f"**Date:** {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}")
    lines.append(f"**Quality Score:** {report.score}")
    lines.append(f"**Threshold:** {report.threshold}")
    lines.append("")
    lines.append("## Quality Issues")
    lines.append("")

    for issue in report.issues:
        lines.append(f"- **[{issue.severity.upper()}]** {issue.category}: {issue.message}")
        if issue.location:
            lines.append(f"  - Location: {issue.location}")

    lines.append("")
    lines.append("## Hallucination Flags")
    if report.hallucination_flags:
        for flag in report.hallucination_flags:
            lines.append(f"- {flag}")
    else:
        lines.append("- None flagged")

    lines.append("")
    lines.append("## Review Verdict")
    lines.append("")
    lines.append("- [ ] **Approved** — content is acceptable as-is")
    lines.append("- [ ] **Needs edits** — see notes above")
    lines.append("- [ ] **Reject** — content needs full rewrite")
    lines.append("")
    lines.append("## Reviewer Notes")
    lines.append("")
    lines.append("*(Add your notes here)*")

    content = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info("Review log written to %s", path)
    return path


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        report_data = context.get("_quality_report")
        if not report_data:
            return AgentResult(status="skipped", error="No quality report in context")

        report = QualityReport(**report_data)
        path = write_review_log(component, job_spec, report)
        return AgentResult(status="done", output_path=path)
    except Exception as e:
        logger.error("Review agent failed: %s", e)
        return AgentResult(status="failed", error=str(e))
