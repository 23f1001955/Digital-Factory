import os
import csv
import json
import logging

from orchestrator.models import ComponentSpec, JobSpec, AgentResult
from typing import Dict

logger = logging.getLogger(__name__)


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        data_path = context.get("database")
        if not data_path:
            research_path = context.get("market_research")
            if not research_path:
                raise ValueError("Neither 'database' nor 'market_research' found in context")
            with open(research_path, "r") as f:
                research = json.load(f)
            data = research.get("database")
            if data is None:
                raise ValueError("'database' key not found in market research output")
        else:
            with open(data_path, "r") as f:
                data = json.load(f)

        if not data:
            raise ValueError("No data to export")

        base_dir = os.path.join("outputs", job_spec.slug)
        output_dir = os.path.dirname(os.path.join(base_dir, component.output))
        os.makedirs(output_dir, exist_ok=True)

        active_formats = getattr(component, "active_formats", []) or []
        output_paths: Dict[str, str] = {}

        if not active_formats or "csv" in active_formats:
            csv_path = os.path.join(output_dir, f"{component.id}.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            output_paths["csv"] = csv_path

        if "xlsx" in active_formats:
            import openpyxl
            xlsx_path = os.path.join(output_dir, f"{component.id}.xlsx")
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = component.id
            if data:
                ws.append(list(data[0].keys()))
                for row in data:
                    ws.append(list(row.values()))
            wb.save(xlsx_path)
            output_paths["xlsx"] = xlsx_path

        if not output_paths:
            raise ValueError("No formats produced")

        primary_path = list(output_paths.values())[0]
        return AgentResult(
            status="done",
            output_path=primary_path,
            output_paths=output_paths,
        )

    except Exception as e:
        logger.error(f"CSV export agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
