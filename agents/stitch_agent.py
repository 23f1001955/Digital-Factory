import os
import json
import time
import logging

import httpx

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

STITCH_MCP_URL = "https://stitch.googleapis.com/mcp"
MCP_TIMEOUT = 300.0
DOWNLOAD_TIMEOUT = 120.0
POLL_INTERVAL = 15
MAX_POLL_SECONDS = 600


def _mcp_call(method: str, arguments: dict | None = None) -> dict:
    api_key = os.getenv("STITCH_API_KEY")
    if not api_key:
        raise ValueError("STITCH_API_KEY not set in .env")
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": method, "arguments": arguments or {}},
    }
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": api_key}
    resp = httpx.post(
        STITCH_MCP_URL, json=payload, headers=headers, timeout=MCP_TIMEOUT
    )
    resp.raise_for_status()
    data = resp.json()
    content = data.get("result", {}).get("content", [])
    for item in content:
        if item.get("type") == "text":
            return json.loads(item["text"])
    structured = data.get("result", {}).get("structuredContent", {})
    if structured:
        return structured
    return data.get("result", {})


def _download_file(url: str, save_path: str) -> bool:
    try:
        resp = httpx.get(url, timeout=DOWNLOAD_TIMEOUT)
        resp.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(resp.content)
        return True
    except Exception as e:
        logger.warning(f"Download failed for {url}: {e}")
        return False


def _extract_screens(screen_result: dict) -> list[dict]:
    screens = []
    if isinstance(screen_result, dict):
        content_list = screen_result.get("content", [])
        for item in content_list:
            if item.get("type") == "text":
                screens_data = json.loads(item["text"])
                screens = screens_data.get("screens", [])
                break
        if not screens:
            structured = screen_result.get("structuredContent", {})
            screens = structured.get("screens", [])
    return screens


def _poll_screen_until_done(
    project_id: str, screen_name: str, project_title: str
) -> dict | None:
    started = time.time()
    while time.time() - started < MAX_POLL_SECONDS:
        try:
            result = _mcp_call(
                "get_screen",
                {
                    "name": screen_name,
                    "projectId": project_id,
                    "screenId": screen_name.split("/")[-1],
                },
            )
        except Exception as e:
            logger.warning(f"Poll get_screen failed for {screen_name}: {e}")
            time.sleep(POLL_INTERVAL)
            continue

        screens_list = result.get("screens", [result])
        screen_obj = screens_list[0] if screens_list else result
        metadata = screen_obj.get("screenMetadata") or {}
        status = (
            metadata.get("status", "IN_PROGRESS")
            if isinstance(metadata, dict)
            else "IN_PROGRESS"
        )

        elapsed = int(time.time() - started)
        if status == "COMPLETE":
            logger.info(f"Screen {screen_name} ready after {elapsed}s")
            return screen_obj
        if status == "FAILED":
            msg = (
                metadata.get("statusMessage", "unknown")
                if isinstance(metadata, dict)
                else "unknown"
            )
            logger.warning(f"Screen {screen_name} failed after {elapsed}s: {msg}")
            return None

        logger.info(f"Screen {screen_name} still generating ({elapsed}s)...")
        time.sleep(POLL_INTERVAL)

    logger.warning(
        f"Screen {screen_name} not ready after {MAX_POLL_SECONDS}s, giving up"
    )
    return None


def _download_screens_from_project(
    output_base: str, pid: str, project_title: str
) -> list[dict]:
    manifest = []
    safe_title = project_title.replace(" ", "_").replace("/", "_")
    proj_dir = os.path.join(output_base, safe_title)
    os.makedirs(proj_dir, exist_ok=True)

    try:
        screens_result = _mcp_call("list_screens", {"projectId": pid})
    except Exception as e:
        logger.warning(f"Failed to list screens for {project_title}: {e}")
        return manifest

    screens = screens_result.get("screens", [])
    for screen in screens:
        screen_title = screen.get("title", "Untitled_Screen")
        safe_name = screen_title.replace(" ", "_").replace("/", "_")

        html_info = screen.get("htmlCode", {})
        html_url = html_info.get("downloadUrl")
        html_path = None
        if html_url:
            html_path = os.path.join(proj_dir, f"{safe_name}.html")
            ok = _download_file(html_url, html_path)
            if ok:
                logger.info(f"Downloaded HTML: {html_path}")

        screenshot_info = screen.get("screenshot", {})
        img_url = screenshot_info.get("downloadUrl")
        img_path = None
        if img_url:
            img_path = os.path.join(proj_dir, f"{safe_name}.jpeg")
            ok = _download_file(img_url, img_path)
            if ok:
                logger.info(f"Downloaded image: {img_path}")

        manifest.append(
            {
                "project": project_title,
                "project_id": pid,
                "screen": screen_title,
                "screen_id": screen.get("name", ""),
                "html": str(html_path) if html_path else None,
                "image": str(img_path) if img_path else None,
            }
        )

    return manifest


def _generate_and_poll_landing(pid: str, prompt: str, project_name: str) -> dict | None:
    logger.info("Sending landing page prompt to Stitch AI (may take 2-5 minutes)...")

    try:
        result = _mcp_call(
            "generate_screen_from_text",
            {
                "projectId": pid,
                "prompt": prompt,
                "deviceType": "DESKTOP",
                "modelId": "GEMINI_3_FLASH",
            },
        )
    except httpx.TimeoutException:
        logger.info(
            "generate_screen_from_text timed out (expected — generation continues in background)"
        )
        result = None
    except Exception as e:
        logger.warning(f"generate_screen_from_text error: {e}")
        result = None

    if result:
        screens = _extract_screens(result)
        for screen in screens:
            metadata = screen.get("screenMetadata") or {}
            status = metadata.get("status", "") if isinstance(metadata, dict) else ""
            screen_name = screen.get("name", "")
            if status == "COMPLETE":
                return screen
            if screen_name and status in ("IN_PROGRESS", "", "UPSCALING"):
                screen_id = screen_name.split("/")[-1] if "/" in screen_name else ""
                project_id = pid
                if screen_id:
                    full_name = f"projects/{project_id}/screens/{screen_id}"
                    logger.info(
                        f"Polling screen {full_name} (initial status: {status})..."
                    )
                    return _poll_screen_until_done(project_id, full_name, project_name)

    # If generate timed out or returned no screens, find screens via list_screens
    logger.info("Polling project for newly created screens...")
    started = time.time()
    while time.time() - started < MAX_POLL_SECONDS:
        try:
            screens_result = _mcp_call("list_screens", {"projectId": pid})
        except Exception:
            time.sleep(POLL_INTERVAL)
            continue

        screens = screens_result.get("screens", [])
        for screen in screens:
            metadata = screen.get("screenMetadata") or {}
            status = metadata.get("status", "") if isinstance(metadata, dict) else ""
            screen_name = screen.get("name", "")
            if status == "COMPLETE" and screen_name:
                return screen
            if status in ("FAILED",):
                msg = (
                    metadata.get("statusMessage", "unknown")
                    if isinstance(metadata, dict)
                    else "unknown"
                )
                logger.warning(f"Screen failed: {msg}")

        elapsed = int(time.time() - started)
        if elapsed % 60 == 0:
            logger.info(f"Still waiting for Stitch generation ({elapsed}s)...")
        time.sleep(POLL_INTERVAL)

    logger.warning("Stitch generation did not complete within the time limit")
    return None


def _noop_result(output_base: str) -> AgentResult:
    """Return a valid done result when Stitch is not configured."""
    os.makedirs(output_base, exist_ok=True)
    result = {
        "status": "done",
        "screens_total": 0,
        "screens": [],
        "landing_page_html": None,
        "output_dir": output_base,
    }
    output_path = os.path.join(output_base, "manifest.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return AgentResult(status="done", output_path=output_path, error=None)


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        slug = job_spec.slug
        output_base = os.path.join("outputs", slug, component.output)
        os.makedirs(output_base, exist_ok=True)

        if not os.getenv("STITCH_API_KEY"):
            logger.info("STITCH_API_KEY not set — using LLM-only landing page")
            return _noop_result(output_base)

        manifest = []
        landing_page_html = None
        runtime_screens = []

        # Phase 1: Download from existing Stitch projects
        if os.getenv("STITCH_API_KEY"):
            try:
                projects_result = _mcp_call("list_projects")
                projects = projects_result.get("projects", [])
                project_ids_env = os.getenv("STITCH_PROJECT_IDS", "")
                if project_ids_env:
                    allowed = {
                        pid.strip() for pid in project_ids_env.split(",") if pid.strip()
                    }
                    projects = [
                        p for p in projects if p["name"].split("/")[1] in allowed
                    ]

                for project in projects:
                    pid = project["name"].split("/")[1]
                    title = project.get("title", "Untitled")
                    screens = _download_screens_from_project(output_base, pid, title)
                    manifest.extend(screens)
            except Exception as e:
                logger.warning(f"Existing project download failed: {e}")

        # Phase 2: Create landing page in Stitch from pipeline content
        content_summary_parts = []
        for dep_key, dep_path in context.items():
            if dep_key == "renderer":
                continue
            if dep_path and os.path.exists(dep_path):
                try:
                    with open(dep_path, encoding="utf-8") as f:
                        text = f.read()
                    label = dep_key.replace("_", " ").title()
                    content_summary_parts.append(f"=== {label} ===\n{text[:3000]}")
                except Exception:
                    pass
        content_summary = "\n\n".join(content_summary_parts)

        if content_summary.strip():
            project_name = f"DF-{slug[:30]}".replace(" ", "_")
            product_label = job_spec.display_name or job_spec.niche
            cta = getattr(job_spec, "call_to_action", "Buy Now on Gumroad")

            try:
                proj_result = _mcp_call("create_project", {"title": project_name})
                proj_name = proj_result.get("name", "")
                pid = proj_name.split("/")[1] if "/" in proj_name else ""
                if not pid:
                    logger.warning(
                        "Failed to create Stitch project for runtime landing page"
                    )
                else:
                    logger.info(f"Created Stitch project '{project_name}' (ID: {pid})")

                    landing_prompt = (
                        f"Design a complete, premium landing page for '{product_label}'. "
                        f"This is a {job_spec.product_type.replace('_', ' ')} product in the {job_spec.niche} niche. "
                        f"Include: hero section with headline '{product_label}' and CTA '{cta}', "
                        f"features section, benefits section, pricing/cta section, and footer. "
                        f"DESKTOP. Light mode. Editorial premium aesthetic. Full page design. "
                        f"Context: {content_summary[:2000]}"
                    )

                    screen = _generate_and_poll_landing(
                        pid, landing_prompt, project_name
                    )
                    if screen:
                        safe_name = (
                            screen.get("title", "Landing_Page")
                            .replace(" ", "_")
                            .replace("/", "_")
                        )
                        html_info = screen.get("htmlCode", {})
                        html_url = html_info.get("downloadUrl")
                        html_path = None
                        if html_url and html_url != "UPLOADING":
                            html_path = os.path.join(output_base, f"{safe_name}.html")
                            ok = _download_file(html_url, html_path)
                            if ok:
                                logger.info(
                                    f"Landing page HTML from Stitch: {html_path}"
                                )
                                landing_page_html = str(html_path)

                        screenshot_info = screen.get("screenshot", {})
                        img_url = screenshot_info.get("downloadUrl")
                        img_path = None
                        if img_url:
                            img_path = os.path.join(output_base, f"{safe_name}.jpeg")
                            ok = _download_file(img_url, img_path)
                            if ok:
                                logger.info(
                                    f"Landing page image from Stitch: {img_path}"
                                )

                        runtime_screens.append(
                            {
                                "project": project_name,
                                "project_id": pid,
                                "screen": screen.get("title", "Landing_Page"),
                                "screen_id": screen.get("name", ""),
                                "html": str(html_path) if html_path else None,
                                "image": str(img_path) if img_path else None,
                            }
                        )

            except Exception as e:
                logger.warning(f"Runtime landing page creation in Stitch failed: {e}")

        manifest.extend(runtime_screens)

        result = {
            "status": "done",
            "screens_total": len(manifest),
            "screens": manifest,
            "landing_page_html": landing_page_html,
            "output_dir": output_base,
        }
        output_path = os.path.join(output_base, "manifest.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        if landing_page_html:
            logger.info(f"Stitch landing page ready at {landing_page_html}")
        else:
            logger.info(
                "No Stitch landing page created — landing_agent will use LLM fallback"
            )
        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Stitch agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
