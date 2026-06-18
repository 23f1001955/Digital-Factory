import os
import sys
import csv
import json
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load .env before anything else
load_dotenv()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("main")

from cli.wizard import run_wizard, slugify
from orchestrator.orchestrator import Orchestrator


def process_batch(csv_path: str):
    logger.info(f"Starting batch mode from {csv_path}")
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            product_type = row.get("product_type", "discovery")
            niche = row.get("niche", "default niche")
            theme = row.get("theme", "default")
            slug = row.get("slug", slugify(niche))

            notion_sync = row.get("notion_sync", "false").strip().lower() in (
                "true",
                "yes",
                "1",
                "y",
            )
            job_spec = {
                "slug": slug,
                "product_type": product_type,
                "niche": niche,
                "display_name": row.get("display_name", niche.title()),
                "theme": theme,
                "notion_sync": notion_sync,
                "notion_parent_page_id": (
                    os.getenv("NOTION_PARENT_PAGE_ID") if notion_sync else None
                ),
                "gumroad_enabled": row.get("gumroad_enabled", "false").strip().lower()
                in ("true", "yes", "1", "y"),
                "landing_page_enabled": row.get("landing_page_enabled", "false")
                .strip()
                .lower()
                in ("true", "yes", "1", "y"),
                "social_promotion_enabled": row.get("social_promotion_enabled", "false")
                .strip()
                .lower()
                in ("true", "yes", "1", "y"),
                "call_to_action": row.get("call_to_action", "Buy Now on Gumroad"),
                "created_at": datetime.utcnow().isoformat() + "Z",
            }

            output_dir = os.path.join("outputs", slug)
            os.makedirs(output_dir, exist_ok=True)

            job_spec_path = os.path.join(output_dir, "job_spec.json")
            with open(job_spec_path, "w") as jf:
                json.dump(job_spec, jf, indent=2)

            sys.stderr.write(f"\n{'=' * 60}\n")
            sys.stderr.write(f'  📦 Batch: {product_type} — "{niche}" → {slug}\n')
            sys.stderr.write(f"{'=' * 60}\n")
            sys.stderr.flush()
            logger.info(f"Orchestrating {slug}...")
            orchestrator = Orchestrator(job_spec_path)
            orchestrator.run()

            # Rate-limit between batch runs — respect API free tiers
            time.sleep(3)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--batch" and len(sys.argv) > 2:
        process_batch(sys.argv[2])
    elif len(sys.argv) > 1 and sys.argv[1] == "--resume" and len(sys.argv) > 2:
        job_spec_path = sys.argv[2]
        logger.info(f"Resuming from {job_spec_path}")
        orchestrator = Orchestrator(job_spec_path)
        orchestrator.run()
    elif "--dry-run" in sys.argv:
        _run_dry_run()
    else:
        # First run: start wizard
        job_spec_path = run_wizard()
        if not job_spec_path:
            logger.warning("Wizard aborted.")
            return
        orchestrator = Orchestrator(job_spec_path)
        orchestrator.run()


def _run_dry_run():
    """Run pipeline in dry-run mode: load schema, merge plan, print DAG, exit."""
    from cli.dry_run import print_dry_run
    from orchestrator.component_templates import list_templates

    job_spec_path = run_wizard()
    if not job_spec_path:
        return

    orchestrator = Orchestrator(job_spec_path)

    # Merge pipeline plan if market_research.json exists
    research_path = None
    mr_state = orchestrator.state.components.get("market_research")
    if mr_state and mr_state.status == "done" and mr_state.output_path:
        research_path = mr_state.output_path
    if research_path and os.path.exists(research_path):
        orchestrator._merge_pipeline_plan(research_path)
        logger.info("Pipeline plan merged (dry-run)")

    ordered = orchestrator._get_execution_order()
    templates = list_templates()
    print_dry_run(ordered, templates)


if __name__ == "__main__":
    main()
