import os
import sys
import csv
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load .env before anything else
load_dotenv()

# Configure structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("main")

from cli.wizard import run_wizard, slugify
from orchestrator.orchestrator import Orchestrator

def process_batch(csv_path: str):
    logger.info(f"Starting batch mode from {csv_path}")
    with open(csv_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            product_type = row.get("product_type", "research_pack")
            niche = row.get("niche", "default niche")
            theme = row.get("theme", "default")
            slug = row.get("slug", slugify(niche))
            
            job_spec = {
                "slug": slug,
                "product_type": product_type,
                "niche": niche,
                "theme": theme,
                "notion_sync": False,
                "notion_parent_page_id": None,
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
            
            output_dir = os.path.join("outputs", slug)
            os.makedirs(output_dir, exist_ok=True)
            
            job_spec_path = os.path.join(output_dir, "job_spec.json")
            with open(job_spec_path, "w") as jf:
                json.dump(job_spec, jf, indent=2)
                
            logger.info(f"Orchestrating {slug}...")
            orchestrator = Orchestrator(job_spec_path)
            orchestrator.run()

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--batch" and len(sys.argv) > 2:
        process_batch(sys.argv[2])
    elif len(sys.argv) > 1 and sys.argv[1] == "--resume" and len(sys.argv) > 2:
        job_spec_path = sys.argv[2]
        logger.info(f"Resuming from {job_spec_path}")
        orchestrator = Orchestrator(job_spec_path)
        orchestrator.run()
    else:
        # First run: start wizard
        job_spec_path = run_wizard()
        if not job_spec_path:
            logger.warning("Wizard aborted.")
            return
        orchestrator = Orchestrator(job_spec_path)
        orchestrator.run()

if __name__ == "__main__":
    main()
