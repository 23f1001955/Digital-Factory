import os
import zipfile
import logging

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

DELIVERABLE_EXTENSIONS = {
    ".pdf",
    ".zip",
    ".md",
    ".jpg",
    ".jpeg",
    ".png",
    ".svg",
    ".html",
}


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

        delivery_map = context.get("_delivery_map")

        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            if delivery_map:
                _add_delivery_map_files(zf, delivery_map, base_dir)
            else:
                _walk_filesystem(zf, base_dir)

        return AgentResult(status="done", output_path=output_zip, error=None)

    except Exception as e:
        logger.error(f"Packaging agent failed: {e}")
        return AgentResult(status="failed", error=str(e))


def _add_delivery_map_files(zf, delivery_map, base_dir):
    """Add files from delivery_map entries with 'zip' delivery to ZIP archive."""
    added = set()
    for comp_id, entry in delivery_map.items():
        if "zip" not in entry.get("delivery", []):
            continue
        path = entry.get("output")
        if not path or not os.path.exists(path):
            continue
        if os.path.isfile(path):
            rel = os.path.relpath(path, base_dir)
            if rel.startswith("..") or os.path.isabs(rel):
                logger.warning("Skipping path outside base_dir: %s", path)
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext in DELIVERABLE_EXTENSIONS:
                zf.write(path, rel)
                added.add(rel)
        elif os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                for file in files:
                    fpath = os.path.join(root, file)
                    frel = os.path.relpath(fpath, base_dir)
                    if frel.startswith("..") or os.path.isabs(frel):
                        continue
                    if frel in added:
                        continue
                    ext = os.path.splitext(file)[1].lower()
                    if ext in DELIVERABLE_EXTENSIONS:
                        zf.write(fpath, frel)
                        added.add(frel)


def _walk_filesystem(zf, base_dir):
    """Fallback: walk filesystem and filter by _is_deliverable."""
    for root, _dirs, files in os.walk(base_dir):
        for file in files:
            file_path = os.path.join(root, file)
            if not _is_deliverable(file_path, base_dir):
                continue
            arcname = os.path.relpath(file_path, base_dir)
            zf.write(file_path, arcname)
