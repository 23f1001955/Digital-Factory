import os
import json
import logging
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

from orchestrator.models import QualityReport, JobSpec

logger = logging.getLogger(__name__)


def _write_quality_report(report: QualityReport, slug: str) -> str:
    out_dir = os.path.join("outputs", slug)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "quality-report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(mode="json"), f, indent=2)
    logger.info("Quality report written to %s", path)
    return path


def _dispatch_webhook(report: QualityReport, slug: str, component_id: str) -> None:
    webhook_url = os.getenv("QUALITY_WEBHOOK_URL")
    if not webhook_url:
        return

    payload = json.dumps({
        "event": "quality_evaluation",
        "slug": slug,
        "component_id": component_id,
        "score": report.score,
        "passed": report.passed,
        "threshold": report.threshold,
        "issues_count": len(report.issues),
        "needs_human_review": report.needs_human_review,
    }).encode("utf-8")

    try:
        req = Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})
        urlopen(req, timeout=10)
        logger.info("Webhook dispatched to %s", webhook_url)
    except URLError as e:
        logger.warning("Webhook dispatch failed: %s", e)
    except Exception as e:
        logger.warning("Webhook error: %s", e)


def dispatch_alert(
    report: QualityReport,
    job_spec: JobSpec,
    component_id: str,
) -> None:
    if not report.passed:
        logger.warning(
            "Quality check FAILED for %s/%s (score=%.2f, threshold=%.2f)",
            job_spec.slug, component_id, report.score, report.threshold,
        )
    elif report.score < 0.8:
        logger.info(
            "Quality check borderline for %s/%s (score=%.2f)",
            job_spec.slug, component_id, report.score,
        )
    else:
        logger.info(
            "Quality check PASSED for %s/%s (score=%.2f)",
            job_spec.slug, component_id, report.score,
        )

    report_path = _write_quality_report(report, job_spec.slug)
    _dispatch_webhook(report, job_spec.slug, component_id)

    for issue in report.issues:
        logger.log(
            logging.WARNING if issue.severity in ("error", "warning") else logging.INFO,
            "  [%s] %s: %s",
            issue.severity.upper(),
            issue.category,
            issue.message,
        )
