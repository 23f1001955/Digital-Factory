import os
import json
import re
import urllib.parse
import logging

import httpx

from channels.base import BaseChannel, ProductArtifact, PublishResult, AnalyticsData, ListingQualityScore
from channels.gumroad_listing import generate_optimized_tags, suggest_price, generate_aida_description
from channels.gumroad_analytics import pull_analytics, score_listing_quality
from channels.gumroad_ab_testing import VariantSet, save_variant_state, upload_variants

logger = logging.getLogger(__name__)

GUMROAD_API_BASE = "https://api.gumroad.com/v2"


def _gumroad_form_api(method: str, path: str, data: dict | None = None) -> dict | None:
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
    token = os.getenv("GUMROAD_ACCESS_TOKEN")
    if not token:
        logger.warning("GUMROAD_ACCESS_TOKEN not set for file upload")
        return None
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    try:
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
    username = os.getenv("GUMROAD_USERNAME")
    if username:
        return username
    user_data = _gumroad_form_api("GET", "user")
    if user_data and "user" in user_data:
        return user_data["user"].get("subdomain", "")
    return ""


class GumroadChannel(BaseChannel):
    name = "gumroad"

    def validate(self) -> bool:
        token = os.getenv("GUMROAD_ACCESS_TOKEN")
        if not token:
            return False
        user_data = _gumroad_form_api("GET", "user")
        return user_data is not None and "user" in user_data

    def publish(self, artifact: ProductArtifact) -> PublishResult:
        research_data = None
        if artifact.research_data_path:
            try:
                with open(artifact.research_data_path) as f:
                    research_data = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load research data: {e}")

        artifact.tags = generate_optimized_tags(
            artifact.niche, artifact.product_type, research_data
        )
        artifact.price_cents = suggest_price(
            artifact.product_type, research_data, artifact.price_cents
        )
        artifact.description = generate_aida_description(
            artifact.niche, artifact.product_type, research_data
        )

        result = _publish_to_gumroad(artifact)

        if result.product_id and (artifact.cover_variants or artifact.thumbnail_variants):
            try:
                vs = VariantSet(
                    covers=artifact.cover_variants,
                    thumbnails=artifact.thumbnail_variants,
                )
                state_dir = os.path.join(
                    os.path.dirname(
                        os.path.dirname(artifact.research_data_path or "")
                    ) if artifact.research_data_path else "outputs",
                    artifact.slug, "gumroad"
                )
                state_path = os.path.join(state_dir, "variant_state.json")
                upload_variants(result.product_id, vs, artifact.slug)
                os.makedirs(state_dir, exist_ok=True)
                save_variant_state(vs, state_path)
            except Exception as e:
                logger.warning(f"Variant upload failed: {e}")

        quality = score_listing_quality(artifact, research_data)
        if not quality.passed:
            logger.warning(
                f"Listing quality score: {quality.overall_score:.2f} — issues: {quality.issues}"
            )
        else:
            logger.info(f"Listing quality score: {quality.overall_score:.2f} — PASS")

        return result

    def update(self, product_id: str, artifact: ProductArtifact) -> PublishResult:
        research_data = None
        if artifact.research_data_path:
            try:
                with open(artifact.research_data_path) as f:
                    research_data = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load research data: {e}")

        artifact.tags = generate_optimized_tags(
            artifact.niche, artifact.product_type, research_data
        )
        artifact.price_cents = suggest_price(
            artifact.product_type, research_data, artifact.price_cents
        )
        artifact.description = generate_aida_description(
            artifact.niche, artifact.product_type, research_data
        )

        return _publish_to_gumroad(artifact, existing_id=product_id)

    def get_analytics(self, product_id: str) -> AnalyticsData:
        return pull_analytics(product_id)


def _publish_to_gumroad(
    artifact: ProductArtifact, existing_id: str | None = None
) -> PublishResult:
    token = os.getenv("GUMROAD_ACCESS_TOKEN")
    if not token:
        return PublishResult(status="failed", error="GUMROAD_ACCESS_TOKEN not set")

    product_name = (
        f"{artifact.display_name or artifact.niche}"
        f" - {artifact.product_type.replace('_', ' ').title()}"
    )
    description = (
        artifact.description
        or f"A premium {artifact.product_type.replace('_', ' ')} for {artifact.niche}."
    )
    custom_summary = (
        f"{product_name} — a premium"
        f" {artifact.product_type.replace('_', ' ')} for {artifact.niche}."
    )
    custom_receipt = (
        f"Thank you for purchasing {product_name}! Your download links are below."
    )
    tags = artifact.tags if artifact.tags else _generate_tags(artifact.niche, artifact.product_type)

    product_id = existing_id
    product_url = ""

    if not product_id:
        create_data = {
            "name": product_name,
            "custom_permalink": artifact.slug,
            "price": str(artifact.price_cents),
            "description": description,
            "custom_receipt": custom_receipt,
            "custom_summary": custom_summary,
            "tags": tags,
        }
        create_result = _gumroad_form_api("POST", "products", create_data)
        if create_result and create_result.get("success"):
            product_id = create_result["product"]["id"]
            product_url = create_result["product"].get("short_url", "")
        else:
            return PublishResult(
                status="failed", error="Failed to create Gumroad product"
            )

    file_urls = []
    for f in artifact.files:
        if os.path.isfile(f.path):
            file_url = _gumroad_upload_file(f.path)
            if file_url:
                file_urls.append({"url": file_url, "name": f.name})

    cover_image_url = None
    thumbnail_image_url = None
    if artifact.cover_image and os.path.isfile(artifact.cover_image):
        url = _gumroad_upload_file(artifact.cover_image)
        if url:
            cover_image_url = url
            file_urls.append({"url": url, "name": os.path.basename(artifact.cover_image)})
    if artifact.thumbnail and os.path.isfile(artifact.thumbnail):
        url = _gumroad_upload_file(artifact.thumbnail)
        if url:
            thumbnail_image_url = url
            file_urls.append({"url": url, "name": os.path.basename(artifact.thumbnail)})

    existing_file_ids = []
    if token and product_id:
        try:
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
                if not product_url:
                    product_url = prod.get("short_url", "")
        except Exception as e:
            logger.warning(f"Failed to fetch existing product: {e}")

    attach_body = {
        "name": product_name,
        "price": str(artifact.price_cents),
        "description": description,
        "custom_receipt": custom_receipt,
        "custom_permalink": artifact.slug,
        "custom_summary": custom_summary,
        "tags": tags,
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
        if not product_url:
            product_url = updated_product.get("short_url", "") or product_url

        updated_files = updated_product.get("files", [])

        for f in file_urls:
            for uf in updated_files:
                if uf.get("url") and uf["url"] == f["url"]:
                    f["id"] = uf["id"]
                    break

        cover_file_url = None
        thumb_file_url = None
        if cover_image_url:
            for uf in updated_files:
                if uf.get("url") == cover_image_url:
                    cover_file_url = uf["url"]
                    break
        if thumbnail_image_url:
            for uf in updated_files:
                if uf.get("url") == thumbnail_image_url:
                    thumb_file_url = uf["url"]
                    break

        if cover_file_url and token:
            try:
                resp = httpx.post(
                    f"{GUMROAD_API_BASE}/products/{product_id}/covers",
                    data={"access_token": token, "url": cover_file_url},
                    timeout=60.0,
                )
                if resp.status_code == 200:
                    logger.info("Cover image set")
            except Exception as e:
                logger.warning(f"Cover upload error: {e}")

        if thumb_file_url and token:
            try:
                resp = httpx.post(
                    f"{GUMROAD_API_BASE}/products/{product_id}/thumbnail",
                    data={"access_token": token, "url": thumb_file_url},
                    timeout=60.0,
                )
                if resp.status_code == 200:
                    logger.info("Thumbnail set")
            except Exception as e:
                logger.warning(f"Thumbnail upload error: {e}")

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
            _gumroad_put_with_rails_params(
                product_id,
                {
                    "rich_content": [
                        {"description": {"type": "doc", "content": rc_content}}
                    ]
                },
            )
    else:
        logger.warning(
            f"Product update failed: {attach_result.get('message', 'unknown') if attach_result else 'no response'}"
        )

    if token and product_id:
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
        except Exception as e:
            logger.warning(f"Publish call failed: {e}")

    if not product_url:
        username = _get_gumroad_username() or "yourusername"
        product_url = f"https://{username}.gumroad.com/l/{artifact.slug}"

    return PublishResult(
        status="published",
        product_id=product_id,
        product_url=product_url,
        price_cents=artifact.price_cents,
    )
