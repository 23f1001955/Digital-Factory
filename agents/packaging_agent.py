import os
import zipfile
import logging

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        base_dir = os.path.join("outputs", job_spec.slug)
        output_path_resolved = component.output.replace("{slug}", job_spec.slug)
        output_zip = os.path.join("outputs", job_spec.slug, output_path_resolved)
        
        exclude_files = {"job_spec.json", "job_state.json", os.path.basename(output_zip)}
        
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(base_dir):
                for file in files:
                    if file in exclude_files and root == base_dir:
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, base_dir)
                    zf.write(file_path, arcname)
                    
        return AgentResult(status="done", output_path=output_zip, error=None)
        
    except Exception as e:
        logger.error(f"Packaging agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
