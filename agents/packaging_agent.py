import os
import zipfile
import logging

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

DELIVERABLE_EXTENSIONS = {".pdf", ".zip", ".md", ".jpg", ".jpeg", ".png", ".svg", ".html"}
DELIVERABLE_PREFIXES = {"content", "presentation", "assets", "gumroad"}


def _is_deliverable(file_path: str, base_dir: str) -> bool:
    rel = os.path.relpath(file_path, base_dir)
    parts = rel.replace("\\", "/").split("/")

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in DELIVERABLE_EXTENSIONS:
        return False

    skip_prefixes = ("data", "gumroad_review", "run_summary", "job_", "notion_")
    file_name = os.path.basename(file_path).lower()
    if any(file_name.startswith(p) for p in skip_prefixes):
        return False

    return True


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        base_dir = os.path.join("outputs", job_spec.slug)
        output_path_resolved = component.output.replace("{slug}", job_spec.slug)
        output_zip = os.path.join("outputs", job_spec.slug, output_path_resolved)

        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(base_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if not _is_deliverable(file_path, base_dir):
                        continue
                    arcname = os.path.relpath(file_path, base_dir)
                    zf.write(file_path, arcname)

        return AgentResult(status="done", output_path=output_zip, error=None)

    except Exception as e:
        logger.error(f"Packaging agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
