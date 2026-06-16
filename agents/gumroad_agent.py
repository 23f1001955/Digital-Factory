import os
import json
import re
import urllib.parse
import logging

import httpx

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

GUMROAD_API_BASE = "https://api.gumroad.com/v2"


def _gumroad_form_api(method: str, path: str, data: dict | None = None) -> dict | None:
    """Call Gumroad API with form-encoded data and access_token."""
    token = os.getenv("GUMROAD_ACCESS_TOKEN")
    if not token:
        logger.warning("GUMROAD_ACCESS_TOKEN not set")
        return None
    url = f"{GUMROAD_API_BASE}/{path.lstrip('/')}"
    form_data = {"access_token": token}
    if data:
        form_data.update(data)
    try:
        if method == "GET":
            resp = httpx.request(method, url, params=form_data, timeout=60.0)
        else:
            resp = httpx.request(method, url, data=form_data, timeout=60.0)
        if resp.status_code == 200:
            return resp.json()
        logger.warning(
            f"Gumroad API {method} {path} -> {resp.status_code}: {resp.text[:300]}"
        )
        return None
    except Exception as e:
        logger.warning(f"Gumroad API call failed ({method} {path}): {e}")
        return None


def _to_rails_params(obj, prefix=""):
    """Convert nested dict/list to Rails-style form params list of (key, value) tuples."""
    items = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            new_prefix = f"{prefix}[{key}]" if prefix else key
            items.extend(_to_rails_params(val, new_prefix))
    elif isinstance(obj, list):
        for val in obj:
            items.extend(_to_rails_params(val, f"{prefix}[]"))
    elif obj is None:
        pass
    elif isinstance(obj, bool):
        items.append((prefix, "true" if obj else "false"))
    else:
        items.append((prefix, str(obj)))
    return items


def _gumroad_put_with_rails_params(product_id: str, body_dict: dict) -> dict | None:
    """Send a PUT to /products/:id with Rails-style nested form encoding."""
    token = os.getenv("GUMROAD_ACCESS_TOKEN")
    if not token:
        return None
    params = [("access_token", token)]
    for key, val in body_dict.items():
        if isinstance(val, (dict, list)):
            params.extend(_to_rails_params(val, key))
        else:
            params.append((key, str(val)))
    body = urllib.parse.urlencode(params)
    try:
        resp = httpx.put(
            f"{GUMROAD_API_BASE}/products/{product_id}",
            content=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=120.0,
        )
        return resp.json() if resp.status_code == 200 else None
    except Exception as e:
        logger.warning(f"Rails-encoded PUT failed: {e}")
        return None


def _generate_tags(niche: str, product_type: str) -> list[str]:
    """Generate product tags from niche and product type."""
    tags = set()
    for kw in niche.lower().split():
        cleaned = kw.strip(",.!?")
        if cleaned:
            tags.add(cleaned)
    ptype_readable = product_type.replace("_", " ").title()
    tags.add(ptype_readable)
    tags.add("Digital Product")
    tags.add("Download")
    return sorted(tags)[:8]


def _gumroad_upload_file(file_path: str) -> str | None:
    """Upload a file to Gumroad using presign→upload→complete→attach flow. Returns file_url or None."""
    token = os.getenv("GUMROAD_ACCESS_TOKEN")
    if not token:
        logger.warning("GUMROAD_ACCESS_TOKEN not set for file upload")
        return None
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    try:
        # 1. Presign — only filename + file_size per API docs
        presign_resp = httpx.post(
            f"{GUMROAD_API_BASE}/files/presign",
            data={
                "access_token": token,
                "filename": file_name,
                "file_size": str(file_size),
            },
            timeout=60.0,
        )
        if presign_resp.status_code != 200:
            logger.warning(
                f"/files/presign failed ({presign_resp.status_code}): {presign_resp.text[:300]}"
            )
            return None
        presign_body = presign_resp.json()
        upload_id = presign_body["upload_id"]
        key = presign_body["key"]
        parts = presign_body.get("parts", [])
        file_url = presign_body.get("file_url", "")
        logger.info(f"Presigned: {file_name} ({file_size}b, {len(parts)} part(s))")

        # 2. Upload each part's byte range to S3, capture ETags
        etags = []
        for i, part in enumerate(parts):
            start = i * 100 * 1024 * 1024
            end = min(start + 100 * 1024 * 1024, file_size)
            with open(file_path, "rb") as fh:
                fh.seek(start)
                chunk = fh.read(end - start)
            part_resp = httpx.put(part["presigned_url"], content=chunk, timeout=600.0)
            part_resp.raise_for_status()
            etag = part_resp.headers.get("etag", "")
            etags.append({"part_number": part["part_number"], "etag": etag})
            logger.info(
                f"Uploaded part {part['part_number']} ({len(chunk)}b ETag: {etag[:30]}...)"
            )

        # 3. Complete — submit ETags to finalize
        complete_items = [
            ("access_token", token),
            ("upload_id", upload_id),
            ("key", key),
        ]
        for et in etags:
            complete_items.append(("parts[][part_number]", str(et["part_number"])))
            complete_items.append(("parts[][etag]", et["etag"]))
        complete_resp = httpx.post(
            f"{GUMROAD_API_BASE}/files/complete",
            content=urllib.parse.urlencode(complete_items),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=60.0,
        )
        if complete_resp.status_code == 200:
            complete_body = complete_resp.json()
            file_url = complete_body.get("file_url", file_url)
        else:
            logger.warning(
                f"/files/complete failed ({complete_resp.status_code}): {complete_resp.text[:300]}"
            )
        logger.info(f"Upload complete: {file_name} -> {file_url}")
        return file_url or None
    except Exception as e:
        logger.warning(f"File upload failed for {file_name}: {e}")
        return None


def _get_gumroad_username() -> str:
    """Get Gumroad username from env var or derive from API."""
    username = os.getenv("GUMROAD_USERNAME")
    if username:
        return username
    user_data = _gumroad_form_api("GET", "user")
    if user_data and "user" in user_data:
        return user_data["user"].get("subdomain", "")
    return ""


def _run_research(
    component: ComponentSpec, job_spec: JobSpec, context: dict
) -> AgentResult:
    niche = job_spec.niche

    products_data = _gumroad_form_api("GET", "products")
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
        "course_launch": [
            "course",
            "training",
            "workshop",
            "masterclass",
            "curriculum",
        ],
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
            type_distribution["research_pack"] = (
                type_distribution.get("research_pack", 0) + 1
            )

    recommended_type = (
        max(type_distribution, key=type_distribution.get)
        if type_distribution
        else "research_pack"
    )

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
            gumroad_data_json=(
                json.dumps(products_data, indent=2)[:8000]
                if products_data
                else "No products found"
            ),
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

    logger.info(
        f"Gumroad research: {len(niche_products)} products found, recommended type: {recommended_type}"
    )
    return AgentResult(status="done", output_path=output_path, error=None)


def _get_previous_product_id(output_dir: str, niche: str = "") -> str | None:
    """Find existing product_id — first from cached publish state, then by matching Gumroad products."""
    publish_path = os.path.join(output_dir, "gumroad", "published.json")
    try:
        if os.path.isfile(publish_path):
            with open(publish_path, "r") as f:
                data = json.load(f)
            pid = data.get("product_id")
            if pid:
                logger.info(f"Found cached product ID: {pid}")
                return pid
    except Exception as e:
        logger.warning(f"Could not read previous publish state: {e}")

    # Fallback: find an existing Gumroad product matching this niche
    if niche:
        products_data = _gumroad_form_api("GET", "products")
        if products_data and "products" in products_data:
            niche_kw = niche.lower().split()
            for p in products_data["products"]:
                name = (p.get("name") or "").lower()
                if any(kw in name for kw in niche_kw):
                    pid = p.get("id")
                    logger.info(
                        f"Found matching existing product: {p['name']} (ID: {pid})"
                    )
                    return pid
    return None


def _run_publish(
    component: ComponentSpec, job_spec: JobSpec, context: dict
) -> AgentResult:
    output_dir = os.path.join("outputs", job_spec.slug)

    # Load research data from context
    research_data = None
    for key, path in context.items():
        if (
            path
            and os.path.exists(path)
            and path.endswith(".json")
            and "gumroad_research" in path
        ):
            with open(path, "r", encoding="utf-8") as f:
                research_data = json.load(f)

    # Scan output directory for files: presentation/*.pdf, root *.zip
    files_to_upload = []
    pres_dir = os.path.join(output_dir, "presentation")
    if os.path.isdir(pres_dir):
        for fn in os.listdir(pres_dir):
            if fn.lower().endswith(".pdf"):
                files_to_upload.append({"path": os.path.join(pres_dir, fn), "name": fn})
    zip_path = os.path.join(output_dir, f"{job_spec.slug}.zip")
    if os.path.isfile(zip_path):
        files_to_upload.append({"path": zip_path, "name": os.path.basename(zip_path)})

    suggested_price = 29
    if research_data:
        prices = [
            p.get("price", 0)
            for p in research_data.get("top_products", [])
            if p.get("price", 0) > 0
        ]
        if prices:
            suggested_price = round(sum(prices) / len(prices))

    review_path = os.path.join(output_dir, "gumroad_review.md")
    with open(review_path, "w", encoding="utf-8") as f:
        f.write("# Gumroad Product Review\n\n")
        f.write(f"**Niche:** {job_spec.niche}\n")
        f.write(f"**Product Type:** {job_spec.product_type}\n")
        f.write(f"**Suggested Price:** ${suggested_price}\n\n")
        f.write("## Files to Upload\n\n")
        for fobj in files_to_upload:
            fobj_size = os.path.getsize(fobj["path"])
            f.write(f"- `{fobj['name']}` ({fobj_size / 1024:.1f} KB)\n")
        f.write("\n---\n")
        f.write("\nPublish to Gumroad? (y/N): ")

    logger.info(
        f"Gumroad publish: {len(files_to_upload)} files, suggested price ${suggested_price}"
    )
    logger.info(f"Review written to {review_path}")

    product_name = (
        f"{job_spec.display_name or job_spec.niche} - {job_spec.product_type.replace('_', ' ').title()} Notion Template"
        if getattr(job_spec, 'notion_only', False)
        else f"{job_spec.display_name or job_spec.niche} - {job_spec.product_type.replace('_', ' ').title()}"
    )
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
        match = re.search(r"\{.*\}", listing_result, re.DOTALL)
        if match:
            listing_data = json.loads(match.group())
            if "product_name" in listing_data and listing_data["product_name"]:
                product_name = listing_data["product_name"]
            if "description" in listing_data and listing_data["description"]:
                product_data["description"] = listing_data["description"]
            if "tagline" in listing_data and listing_data["tagline"]:
                custom_summary = listing_data["tagline"][:120]
            logger.info(f"LLM-generated listing: {product_name}")
    except Exception as e:
        logger.warning(f"LLM listing generation failed (non-blocking): {e}")

    token = os.getenv("GUMROAD_ACCESS_TOKEN")

    product_id = _get_previous_product_id(output_dir, niche=job_spec.niche)
    if not product_id:
        logger.info("No existing product found — attempting to create new product")
        create_data = {
            "name": product_name,
            "custom_permalink": f"{job_spec.slug}-notion" if getattr(job_spec, 'notion_only', False) else job_spec.slug,
            "price": str(product_data["price"]),
            "description": product_data["description"],
            "custom_receipt": custom_receipt,
            "custom_summary": custom_summary,
            "tags": tags,
        }
        create_result = _gumroad_form_api("POST", "products", create_data)
        if create_result and create_result.get("success"):
            product_id = create_result["product"]["id"]
            product_url = create_result["product"].get("short_url", "")
            logger.info(f"Created new Gumroad product: {product_id}")
        else:
            msg = "Failed to create product (rate limit: 10/day)"
            logger.error(msg)
            return AgentResult(status="failed", error=msg)

    logger.info(f"Using existing product ID: {product_id}")

    # Upload all files via presign→upload→complete→attach flow
    file_urls = []
    for fobj in files_to_upload:
        file_url = _gumroad_upload_file(fobj["path"])
        if file_url:
            file_urls.append({"url": file_url, "name": fobj["name"]})
            logger.info(f"Uploaded file {fobj['name']} -> {file_url}")
        else:
            logger.warning(f"Failed to upload file {fobj['name']}")

    # Also upload cover + thumbnail images
    assets_dir = os.path.join(output_dir, "assets")
    if os.path.isdir(assets_dir):
        for img_file in os.listdir(assets_dir):
            img_lower = img_file.lower()
            if img_lower.startswith("cover") or img_lower.startswith("thumbnail"):
                img_path = os.path.join(assets_dir, img_file)
                if os.path.isfile(img_path):
                    img_url = _gumroad_upload_file(img_path)
                    if img_url:
                        file_urls.append({"url": img_url, "name": img_file})
                        logger.info(f"Uploaded image {img_file} -> {img_url}")

    # Fetch existing product to get current file IDs (to preserve them)
    existing_file_ids = []
    product_files_gumroad = []
    product_url = None
    if token:
        get_resp = httpx.request(
            "GET",
            f"{GUMROAD_API_BASE}/products/{product_id}",
            params={"access_token": token},
            timeout=60.0,
        )
        if get_resp.status_code == 200:
            prod = get_resp.json().get("product", {})
            for ef in prod.get("files", []):
                if ef.get("id"):
                    existing_file_ids.append(ef["id"])
                if ef.get("url"):
                    product_files_gumroad.append(ef["url"])
            product_url = prod.get("short_url", "")
            if existing_file_ids:
                logger.info(f"Preserving {len(existing_file_ids)} existing file(s)")

    # Build custom_receipt text
    cta = getattr(job_spec, "call_to_action", "Buy Now on Gumroad")
    custom_receipt = (
        f"Thank you for purchasing {product_name}! "
        f"Your download links are below. {cta}"
    )

    # Generate tags from niche + product_type
    tags = _generate_tags(job_spec.niche, job_spec.product_type)

    # Generate custom_summary from LLM tagline or fallback
    custom_summary = (
        f"{product_name} — a standalone Notion workspace template for {job_spec.niche}."
        if getattr(job_spec, 'notion_only', False)
        else f"{product_name} — a premium {job_spec.product_type.replace('_', ' ')} for {job_spec.niche}."
    )

    # First PUT: attach files, set all product fields
    attach_body = {
        "name": product_name,
        "price": str(product_data["price"]),
        "description": product_data["description"],
        "custom_receipt": custom_receipt,
        "custom_permalink": f"{job_spec.slug}-notion" if getattr(job_spec, 'notion_only', False) else job_spec.slug,
        "custom_summary": custom_summary,
        "tags": tags,
        "display_product_reviews": "true",
        "should_show_sales_count": "true",
    }
    files_spec = []
    for fid in existing_file_ids:
        files_spec.append({"id": fid})
    for f in file_urls:
        files_spec.append({"url": f["url"], "name": f["name"]})
    if files_spec:
        attach_body["files"] = files_spec

    attach_result = _gumroad_put_with_rails_params(product_id, attach_body)
    if attach_result and attach_result.get("success"):
        updated_product = attach_result.get("product", {})
        product_url = updated_product.get("short_url", "") or product_url
        logger.info(
            f"Updated product with {len(file_urls)} new file(s) + {len(existing_file_ids)} preserved"
        )

        # Get file IDs from response for rich_content
        updated_files = updated_product.get("files", [])
        for f in file_urls:
            for uf in updated_files:
                if uf.get("url") and uf["url"] == f["url"]:
                    f["id"] = uf["id"]
                    break

        # Upload cover image via POST /products/:id/covers
        cover_url = None
        thumbnail_url = None
        for f in file_urls:
            name_lower = f.get("name", "").lower()
            target_url = None
            for uf in updated_files:
                if uf.get("id") == f.get("id") and uf.get("url"):
                    target_url = uf["url"]
                    break
            if name_lower.startswith("cover"):
                cover_url = target_url
            elif name_lower.startswith("thumbnail"):
                thumbnail_url = target_url

        if cover_url and token:
            try:
                cover_resp = httpx.post(
                    f"{GUMROAD_API_BASE}/products/{product_id}/covers",
                    data={"access_token": token, "url": cover_url},
                    timeout=60.0,
                )
                if cover_resp.status_code == 200:
                    logger.info("Cover image set")
                else:
                    logger.warning(f"Cover upload failed: {cover_resp.text[:200]}")
            except Exception as e:
                logger.warning(f"Cover upload error: {e}")

        # Upload thumbnail via POST /products/:id/thumbnail
        if thumbnail_url and token:
            try:
                thumb_resp = httpx.post(
                    f"{GUMROAD_API_BASE}/products/{product_id}/thumbnail",
                    data={"access_token": token, "url": thumbnail_url},
                    timeout=60.0,
                )
                if thumb_resp.status_code == 200:
                    logger.info("Thumbnail set")
                else:
                    logger.warning(f"Thumbnail upload failed: {thumb_resp.text[:200]}")
            except Exception as e:
                logger.warning(f"Thumbnail upload error: {e}")

        # Build and set rich_content (thank-you page with file download embeds)
        file_embeds = []
        for uf in updated_files:
            if uf.get("id"):
                file_embeds.append(
                    {
                        "type": "fileEmbed",
                        "attrs": {
                            "id": uf["id"],
                            "uid": uf["id"][:32],
                            "collapsed": False,
                        },
                    }
                )
        if file_embeds:
            rc_content = [
                {
                    "type": "heading",
                    "attrs": {"level": 1},
                    "content": [
                        {
                            "text": "Thank you for your purchase!",
                            "type": "text",
                            "marks": [{"type": "bold"}],
                        }
                    ],
                },
                {
                    "type": "paragraph",
                    "content": [
                        {"text": "Your downloads are ready below.", "type": "text"}
                    ],
                },
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "text": "Your Files:",
                            "type": "text",
                            "marks": [{"type": "bold"}],
                        }
                    ],
                },
                *file_embeds,
            ]
            rc_result = _gumroad_put_with_rails_params(
                product_id,
                {
                    "rich_content": [
                        {"description": {"type": "doc", "content": rc_content}}
                    ]
                },
            )
            if rc_result and rc_result.get("success"):
                logger.info("Rich content (thank-you page) set")
            else:
                logger.warning("Rich content setting failed")
    else:
        logger.warning(
            f"Product update failed: {attach_result.get('message', 'unknown') if attach_result else 'no response'}"
        )

    # Publish via the enable endpoint
    if token:
        try:
            enable_resp = httpx.put(
                f"{GUMROAD_API_BASE}/products/{product_id}/enable",
                data={"access_token": token},
                timeout=60.0,
            )
            if enable_resp.status_code == 200:
                enable_result = enable_resp.json()
                if enable_result.get("success"):
                    product_url = (
                        enable_result.get("product", {}).get("short_url", "")
                        or product_url
                    )
                    logger.info(f"Product published: {product_url}")
                else:
                    logger.warning(
                        f"Publish failed: {enable_result.get('errors', 'unknown error')}"
                    )
            else:
                logger.warning(
                    f"Publish HTTP {enable_resp.status_code}: {enable_resp.text[:200]}"
                )
        except Exception as e:
            logger.warning(f"Publish call failed: {e}")

    if not product_url:
        username = _get_gumroad_username() or "yourusername"
        product_url = f"https://{username}.gumroad.com/l/{job_spec.slug}"

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

    # Also save product_id to gumroad/published.json for next-run caching
    cached_publish_path = os.path.join(output_dir, "gumroad", "published.json")
    os.makedirs(os.path.dirname(cached_publish_path), exist_ok=True)
    with open(cached_publish_path, "w", encoding="utf-8") as f:
        json.dump(publish_result, f, indent=2)

    link_dir = os.path.join(output_dir, "presentation")
    os.makedirs(link_dir, exist_ok=True)
    link_path = os.path.join(link_dir, "Gumroad_Product_Link.md")
    with open(link_path, "w", encoding="utf-8") as f:
        f.write("# Gumroad Product Published\n\n")
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
