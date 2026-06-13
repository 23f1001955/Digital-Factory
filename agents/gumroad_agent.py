import os
import sys
import json
import logging
from datetime import datetime, timedelta

import httpx

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

GUMROAD_API_BASE = "https://api.gumroad.com/v2"


def _gumroad_api(method: str, path: str, data: dict | None = None) -> dict | None:
    token = os.getenv("GUMROAD_ACCESS_TOKEN")
    if not token:
        logger.warning("GUMROAD_ACCESS_TOKEN not set")
        return None
    url = f"{GUMROAD_API_BASE}/{path.lstrip('/')}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = httpx.request(method, url, headers=headers, json=data, timeout=15.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Gumroad API call failed ({method} {path}): {e}")
        return None


def _gumroad_upload_asset(product_id: str, file_path: str) -> dict | None:
    token = os.getenv("GUMROAD_ACCESS_TOKEN")
    if not token:
        logger.warning("GUMROAD_ACCESS_TOKEN not set for asset upload")
        return None
    url = f"{GUMROAD_API_BASE}/products/{product_id}/asset"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        with open(file_path, "rb") as f:
            resp = httpx.post(url, headers=headers, files={"file": f}, timeout=30.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Failed to upload asset {file_path} to Gumroad product {product_id}: {e}")
        return None


def _run_research(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    niche = job_spec.niche

    products_data = _gumroad_api("GET", "products")
    niche_products = []
    if products_data and "products" in products_data:
        for p in products_data["products"]:
            name = (p.get("name") or "").lower()
            desc = (p.get("description") or "").lower()
            if any(kw in name or kw in desc for kw in niche.lower().split()):
                niche_products.append(p)

    type_keywords = {
        "operating_system": ["operating system", "os", "workflow system", "dashboard"],
        "research_pack": ["research", "report", "market analysis", "guide"],
        "visual_pack": ["visual", "design", "template pack", "assets", "graphics"],
        "workflow_kit": ["workflow", "automation", "pipeline", "sop"],
        "blog_kit": ["blog", "content pack", "article", "seo"],
        "course_launch": ["course", "training", "workshop", "masterclass", "curriculum"],
        "saas_docs": ["documentation", "api docs", "developer", "technical"],
    }
    type_distribution = {}
    for p in niche_products:
        name = (p.get("name") or "").lower()
        matched = False
        for ptype, kws in type_keywords.items():
            if any(kw in name for kw in kws):
                type_distribution[ptype] = type_distribution.get(ptype, 0) + 1
                matched = True
                break
        if not matched:
            type_distribution["research_pack"] = type_distribution.get("research_pack", 0) + 1

    recommended_type = max(type_distribution, key=type_distribution.get) if type_distribution else "research_pack"

    research = {
        "niche": niche,
        "products_analyzed": len(niche_products),
        "product_type_distribution": type_distribution,
        "recommended_product_type": recommended_type,
        "top_products": [
            {
                "name": p.get("name", ""),
                "price": p.get("price", 0),
                "sales": p.get("sales_count", 0),
                "description_length": len(p.get("description", "") or ""),
            }
            for p in niche_products[:10]
        ],
        "competitor_count": len(niche_products),
    }

    try:
        from agents.llm_client import generate_text as llm_call
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader("prompts"))
        template = env.get_template("gumroad_research.j2")
        llm_prompt = template.render(
            gumroad_data_json=json.dumps(products_data, indent=2)[:8000] if products_data else "No products found",
            niche=niche,
            product_type=job_spec.product_type.replace("_", " ").title(),
        )
        llm_analysis = llm_call(llm_prompt)
        research["llm_analysis"] = llm_analysis
        logger.info("LLM-powered Gumroad research analysis completed")
    except Exception as e:
        logger.warning(f"LLM research analysis failed (non-blocking): {e}")
        research["llm_analysis"] = None

    output_path = os.path.join("outputs", job_spec.slug, component.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(research, f, indent=2)

    logger.info(f"Gumroad research: {len(niche_products)} products found, recommended type: {recommended_type}")
    return AgentResult(status="done", output_path=output_path, error=None)


def _run_publish(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    output_dir = os.path.join("outputs", job_spec.slug)

    files_to_upload = []
    research_data = None
    for key, path in context.items():
        if path and os.path.exists(path):
            if path.endswith(".pdf") or path.endswith(".zip"):
                files_to_upload.append({"key": key, "path": path, "name": os.path.basename(path)})
            elif path.endswith(".json") and "gumroad_research" in path:
                with open(path, "r", encoding="utf-8") as f:
                    research_data = json.load(f)

    suggested_price = 29
    if research_data:
        prices = [p.get("price", 0) for p in research_data.get("top_products", []) if p.get("price", 0) > 0]
        if prices:
            suggested_price = round(sum(prices) / len(prices))

    review_path = os.path.join(output_dir, "gumroad_review.md")
    with open(review_path, "w", encoding="utf-8") as f:
        f.write(f"# Gumroad Product Review\n\n")
        f.write(f"**Niche:** {job_spec.niche}\n")
        f.write(f"**Product Type:** {job_spec.product_type}\n")
        f.write(f"**Suggested Price:** ${suggested_price}\n\n")
        f.write(f"## Files to Upload\n\n")
        for fobj in files_to_upload:
            fobj_size = os.path.getsize(fobj["path"])
            f.write(f"- `{fobj['name']}` ({fobj_size / 1024:.1f} KB)\n")
        f.write(f"\n---\n")
        f.write(f"\nPublish to Gumroad? (y/N): ")

    logger.info(f"Gumroad publish: {len(files_to_upload)} files, suggested price ${suggested_price}")
    logger.info(f"Review written to {review_path}")

    product_name = f"{job_spec.display_name or job_spec.niche} - {job_spec.product_type.replace('_', ' ').title()}"
    product_data = {
        "name": product_name,
        "price": suggested_price * 100,
        "description": f"A premium {job_spec.product_type.replace('_', ' ')} for {job_spec.niche}.",
    }
    try:
        from agents.llm_client import generate_text as llm_call
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader("prompts"))
        template = env.get_template("gumroad_listing.j2")
        research_output_path = context.get("gumroad_research", "")
        listing_prompt = template.render(
            niche=job_spec.niche,
            product_type=job_spec.product_type.replace("_", " ").title(),
            call_to_action=getattr(job_spec, "call_to_action", "Buy Now on Gumroad"),
            research_output_path=research_output_path,
        )
        listing_result = llm_call(listing_prompt)
        import json as _json
        import re as _re
        match = _re.search(r'\{.*\}', listing_result, _re.DOTALL)
        if match:
            listing_data = _json.loads(match.group())
            if "product_name" in listing_data and listing_data["product_name"]:
                product_name = listing_data["product_name"]
            if "description" in listing_data and listing_data["description"]:
                product_data["description"] = listing_data["description"]
            logger.info(f"LLM-generated listing: {product_name}")
    except Exception as e:
        logger.warning(f"LLM listing generation failed (non-blocking): {e}")
    result = _gumroad_api("POST", "products", data=product_data)

    if not result or "product" not in result:
        logger.error("Failed to create Gumroad product")
        return AgentResult(status="failed", error="Gumroad API product creation failed")

    product_id = result["product"]["id"]
    product_url = result["product"].get("short_url", result["product"].get("url", ""))

    logger.info(f"Gumroad product created: {product_url} (ID: {product_id})")

    # Upload cover + thumbnail images to Gumroad product
    images_path = context.get("images")
    if images_path and os.path.exists(images_path):
        try:
            with open(images_path, "r", encoding="utf-8") as f:
                images_data = json.load(f)
            product_images = images_data.get("images", {})
            for img_type in ("cover", "thumbnail"):
                img_path = product_images.get(img_type)
                if img_path and os.path.exists(img_path):
                    asset_result = _gumroad_upload_asset(product_id, img_path)
                    if asset_result:
                        logger.info(f"Uploaded {img_type} image to Gumroad product {product_id}")
                    else:
                        logger.warning(f"Failed to upload {img_type} image to Gumroad product {product_id}")
        except Exception as e:
            logger.warning(f"Image upload to Gumroad failed (non-blocking): {e}")

    publish_result = {
        "status": "published",
        "product_id": product_id,
        "product_url": product_url,
        "price": suggested_price,
    }

    output_path = os.path.join(output_dir, component.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(publish_result, f, indent=2)

    link_dir = os.path.join(output_dir, "presentation")
    os.makedirs(link_dir, exist_ok=True)
    link_path = os.path.join(link_dir, "Gumroad_Product_Link.md")
    with open(link_path, "w", encoding="utf-8") as f:
        f.write(f"# Gumroad Product Published\n\n")
        f.write(f"## [View on Gumroad]({product_url})\n\n")
        f.write(f"- **Product ID:** {product_id}\n")
        f.write(f"- **Price:** ${suggested_price}\n")

    return AgentResult(status="done", output_path=output_path, error=None)


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    if component.id == "gumroad_research":
        return _run_research(component, job_spec, context)
    elif component.id == "gumroad_publish":
        return _run_publish(component, job_spec, context)
    raise ValueError(f"Unknown gumroad component id: {component.id}")
