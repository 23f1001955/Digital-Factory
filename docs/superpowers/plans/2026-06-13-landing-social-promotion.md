# Landing Page + Social Media Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional landing page generation (via Stitch → Vercel) and social media promotion (IG/Threads/FB/Pinterest) as post-publish pipeline steps.

**Architecture:** Two new agents — `landing_agent` uses Gemini 3.1 Flash for images, LLM for Stitch prompt/HTML refinement, Stitch API for HTML generation, Vercel API for deploy. `social_agent` uses Gemini for social images, LLM for per-platform copy, Facebook Graph API + Pinterest API for posting. Both are opt-in via wizard flags and run after `gumroad_publish`.

**Tech Stack:** Python 3.11+, `httpx`, Gemini 3.1 Flash API, Google Stitch SDK (HTTP), Vercel API, Facebook Graph API v21.0, Pinterest REST API v5, Jinja2

---

### File Structure Map

| File | Action | Purpose |
|------|--------|---------|
| `orchestrator/models.py` | Modify | Add landing/social fields to `JobSpec` |
| `orchestrator/orchestrator.py` | Modify | Skip landing/social components when disabled |
| `agents/landing_agent.py` | Create | Image gen → Stitch → HTML refine → Vercel deploy |
| `agents/social_agent.py` | Create | Social image gen → copy gen → multi-platform posting |
| `prompts/landing_stitch.j2` | Create | LLM prompt for Stitch design brief |
| `prompts/landing_refine.j2` | Create | LLM prompt for HTML refinement |
| `prompts/social_copy.j2` | Create | LLM prompt for per-platform social copy |
| `templates/landing/basic.html.j2` | Create | Fallback HTML if Stitch unavailable |
| `agents/registry.py` | Modify | Add both new agents |
| `cli/wizard.py` | Modify | Add landing/social questions + API key collection |
| `schemas/*.json` (x7) | Modify | Add landing_page + social_promotion components |
| `.env.example` | Modify | Add new env vars |

---

### Task 1: Update `orchestrator/models.py`

**Files:**
- Modify: `orchestrator/models.py`

Add `landing_page_enabled`, `social_promotion_enabled`, `landing_page_url`, and `call_to_action` fields to `JobSpec`.

- [ ] **Step 1: Edit `orchestrator/models.py`**

Update the `JobSpec` class:

```python
class JobSpec(BaseModel):
    slug: str
    product_type: str
    niche: str
    display_name: Optional[str] = None
    theme: str = "default"
    notion_sync: bool = False
    notion_parent_page_id: Optional[str] = None
    landing_page_enabled: bool = False
    social_promotion_enabled: bool = False
    landing_page_url: Optional[str] = None
    call_to_action: str = "Buy Now on Gumroad"
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 2: Verify file compiles**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python -c "import ast; ast.parse(open('orchestrator/models.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add orchestrator/models.py
git commit -m "feat: add landing_page_enabled and social_promotion_enabled to JobSpec"
```

---

### Task 2: Update `orchestrator/orchestrator.py`

**Files:**
- Modify: `orchestrator/orchestrator.py`

Add logic to skip `landing_page` and `social_promotion` components if their corresponding flags are `False` in `job_spec`.

- [ ] **Step 1: Edit `orchestrator/orchestrator.py`**

In the `run()` method, after retrieving the component from the registry, add a skip check:

```python
# In run() method, after line: agent_func = AGENT_REGISTRY.get(component.agent)
            # Skip landing_page if not enabled
            if component.id == "landing_page" and not self.job_spec.landing_page_enabled:
                self.state.components[component.id] = AgentResult(status="skipped", error="landing page not enabled")
                save_job_state(self.state, self.state_path)
                done_count += 1
                sys.stderr.write(f"\r  ⏭️  [{done_count}/{total}] {component.id} (disabled)\n")
                sys.stderr.flush()
                continue

            # Skip social_promotion if not enabled
            if component.id == "social_promotion" and not self.job_spec.social_promotion_enabled:
                self.state.components[component.id] = AgentResult(status="skipped", error="social promotion not enabled")
                save_job_state(self.state, self.state_path)
                done_count += 1
                sys.stderr.write(f"\r  ⏭️  [{done_count}/{total}] {component.id} (disabled)\n")
                sys.stderr.flush()
                continue
```

Insert this block right after `agent_func = AGENT_REGISTRY.get(component.agent)` and before `if not agent_func:`.

- [ ] **Step 2: Verify file compiles**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python -c "import ast; ast.parse(open('orchestrator/orchestrator.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add orchestrator/orchestrator.py
git commit -m "feat: skip landing_page/social_promotion when disabled in job spec"
```

---

### Task 3: Create `agents/landing_agent.py`

**Files:**
- Create: `agents/landing_agent.py`

This agent handles the full landing page pipeline: image generation (Gemini 3.1 Flash) → Stitch prompt writing → Stitch API call → HTML refinement → Vercel deploy.

- [ ] **Step 1: Write `agents/landing_agent.py`**

```python
import os
import sys
import json
import time
import base64
import logging
from typing import Optional

import httpx

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODEL = "gemini-2.0-flash-exp"
STITCH_API_URL = "https://stitch.googleapis.com/mcp"
VERCEL_API_BASE = "https://api.vercel.com"


def _call_gemini(prompt: str, api_key: str) -> Optional[bytes]:
    """Generate an image using Gemini 3.1 Flash. Returns PNG bytes or None."""
    url = f"{GEMINI_API_BASE}/{GEMINI_MODEL}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["image"]},
    }
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()
        for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
            if "inlineData" in part and part["inlineData"].get("mimeType", "").startswith("image/"):
                return base64.b64decode(part["inlineData"]["data"])
        logger.warning("Gemini returned no image data")
        return None
    except Exception as e:
        logger.warning(f"Gemini image generation failed: {e}")
        return None


def _generate_images(niche: str, output_dir: str, gemini_key: str) -> dict:
    """Generate cover image + optional mockups. Returns dict of paths."""
    os.makedirs(output_dir, exist_ok=True)
    images = {}

    cover_prompt = (
        f"A premium, professional product cover image for a digital product about '{niche}'. "
        f"Clean white background, minimalist design, 16:9 aspect ratio. "
        f"The composition should feel modern and trustworthy. "
        f"Use a warm, inviting color palette. No text overlay."
    )
    cover_bytes = _call_gemini(cover_prompt, gemini_key)
    if cover_bytes:
        cover_path = os.path.join(output_dir, "cover.png")
        with open(cover_path, "wb") as f:
            f.write(cover_bytes)
        images["cover"] = cover_path
        logger.info(f"Cover image generated: {cover_path}")
    else:
        logger.warning("Cover image generation failed")

    return images


def _build_stitch_prompt(job_spec: JobSpec, images: dict, gumroad_url: str) -> str:
    """Build a Stitch design prompt from product info and image URLs."""
    cover_url = images.get("cover", "")
    parts = [
        f"Design a premium landing page for a digital product called '{job_spec.display_name or job_spec.niche}'.",
        f"Product type: {job_spec.product_type.replace('_', ' ').title()}",
        f"Niche: {job_spec.niche}",
        f"Theme: {getattr(job_spec, 'theme', 'default')}",
        "",
        "Sections:",
        "1. Hero section with the cover image, product title, and a call-to-action button",
        "2. Features section highlighting key benefits",
        "3. Pricing section showing the product price",
        "4. Footer with minimal branding",
        "",
        f"Cover image URL: {cover_url}",
        f"CTA text: {getattr(job_spec, 'call_to_action', 'Buy Now on Gumroad')}",
        f"Gumroad product URL: {gumroad_url}",
        "",
        "Design requirements:",
        "- Clean, modern, professional aesthetic",
        "- Mobile-responsive layout",
        "- Fast loading (minimal external dependencies)",
        "- Use a cohesive color palette appropriate for the niche",
        "- The CTA button should be prominently visible in the hero section",
    ]
    return "\n".join(parts)


def _call_stitch(prompt: str, stitch_key: str) -> Optional[dict]:
    """Call Google Stitch API to generate a landing page. Returns dict with 'html' and 'screenshot_url'."""
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": stitch_key}
    payload = {
        "tool": "generate_screen_from_text",
        "input": {"text": prompt},
    }
    try:
        sys.stderr.write("  ⏳ Calling Stitch API (1-3 minutes)...\n")
        sys.stderr.flush()
        resp = httpx.post(STITCH_API_URL, headers=headers, json=payload, timeout=300.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Stitch API call failed: {e}")
        return None


def _refine_html(raw_html: str, gumroad_url: str, cta_text: str) -> str:
    """Basic HTML refinement: inject Gumroad CTA button if not present."""
    if 'href="' not in raw_html and gumroad_url:
        cta_button = (
            f'<a href="{gumroad_url}" '
            f'style="display:inline-block;padding:16px 32px;background-color:#000;color:#fff;'
            f'text-decoration:none;border-radius:8px;font-size:18px;font-weight:600;'
            f'margin-top:24px;">{cta_text}</a>'
        )
        if "</body>" in raw_html:
            raw_html = raw_html.replace("</body>", f"{cta_button}\n</body>")
        else:
            raw_html += cta_button
    return raw_html


def _deploy_vercel(html_content: str, slug: str, vercel_token: str) -> Optional[str]:
    """Deploy HTML to Vercel. Returns deployment URL or None."""
    headers = {
        "Authorization": f"Bearer {vercel_token}",
        "Content-Type": "application/json",
    }
    files = {
        "index.html": html_content,
    }
    # Create a deployment with a single HTML file
    payload = {
        "name": f"df-{slug}",
        "project": f"df-{slug}",
        "files": [
            {
                "file": "index.html",
                "data": base64.b64encode(html_content.encode("utf-8")).decode("utf-8"),
            }
        ],
    }
    try:
        resp = httpx.post(
            f"{VERCEL_API_BASE}/v12/deployments",
            headers=headers,
            json=payload,
            timeout=60.0,
        )
        resp.raise_for_status()
        result = resp.json()
        return result.get("url")
    except Exception as e:
        logger.warning(f"Vercel deploy failed: {e}")
        return None


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        slug = job_spec.slug
        output_dir = os.path.join("outputs", slug, "landing")
        os.makedirs(output_dir, exist_ok=True)

        # 1. Get Gumroad URL from context
        gumroad_publish_path = context.get("gumroad_publish")
        gumroad_url = ""
        if gumroad_publish_path and os.path.exists(gumroad_publish_path):
            with open(gumroad_publish_path, "r", encoding="utf-8") as f:
                publish_data = json.load(f)
            gumroad_url = publish_data.get("product_url", "")

        # 2. Generate images via Gemini
        gemini_key = os.getenv("GEMINI_API_KEY")
        images = {}
        if gemini_key:
            images = _generate_images(job_spec.niche, os.path.join(output_dir, "images"), gemini_key)
        else:
            logger.warning("GEMINI_API_KEY not set — skipping image generation")

        # 3. Build Stitch prompt
        stitch_prompt = _build_stitch_prompt(job_spec, images, gumroad_url)

        # 4. Call Stitch API
        stitch_key = os.getenv("STITCH_API_KEY")
        stitch_result = None
        if stitch_key:
            stitch_result = _call_stitch(stitch_prompt, stitch_key)
        else:
            logger.warning("STITCH_API_KEY not set — skipping Stitch API call")

        # 5. Refine HTML
        html_content = ""
        if stitch_result and "html" in stitch_result:
            raw_html = stitch_result["html"]
            html_content = _refine_html(raw_html, gumroad_url, job_spec.call_to_action)
        else:
            # Fallback: use basic template
            from jinja2 import Environment, FileSystemLoader
            env = Environment(loader=FileSystemLoader("templates"))
            template = env.get_template("landing/basic.html.j2")
            html_content = template.render(
                title=job_spec.display_name or job_spec.niche,
                niche=job_spec.niche,
                product_type=job_spec.product_type.replace("_", " ").title(),
                gumroad_url=gumroad_url,
                cta_text=job_spec.call_to_action,
            )

        # Save HTML locally
        html_path = os.path.join(output_dir, "index.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Landing page HTML saved: {html_path}")

        # 6. Deploy to Vercel
        vercel_token = os.getenv("VERCEL_TOKEN")
        deployed_url = None
        if vercel_token:
            deployed_url = _deploy_vercel(html_content, slug, vercel_token)
        else:
            logger.warning("VERCEL_TOKEN not set — skipping deploy")

        # 7. Write result
        result = {
            "status": "done",
            "html_path": html_path,
            "deployed_url": deployed_url or None,
            "images_generated": list(images.keys()),
            "stitch_used": stitch_result is not None,
        }
        output_path = os.path.join("outputs", slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        logger.info(f"Landing page result: {deployed_url or 'local only'}")
        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Landing agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
```

- [ ] **Step 2: Verify file compiles**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python -c "import ast; ast.parse(open('agents/landing_agent.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add agents/landing_agent.py
git commit -m "feat: add landing_agent for Stitch + Vercel landing page deployment"
```

---

### Task 4: Create `agents/social_agent.py`

**Files:**
- Create: `agents/social_agent.py`

Handles social image generation, copy generation, and multi-platform posting.

- [ ] **Step 1: Write `agents/social_agent.py`**

```python
import os
import json
import logging
from typing import Optional

import httpx

from orchestrator.models import ComponentSpec, JobSpec, AgentResult

logger = logging.getLogger(__name__)

FACEBOOK_API_BASE = "https://graph.facebook.com/v21.0"
PINTEREST_API_BASE = "https://api.pinterest.com/v5"


def _post_to_facebook(page_id: str, page_token: str, message: str, image_url: str = "") -> Optional[dict]:
    """Post to Facebook Page."""
    url = f"{FACEBOOK_API_BASE}/{page_id}/photos" if image_url else f"{FACEBOOK_API_BASE}/{page_id}/feed"
    data = {
        "access_token": page_token,
        "message": message,
    }
    if image_url:
        data["url"] = image_url
    try:
        resp = httpx.post(url, data=data, timeout=30.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Facebook post failed: {e}")
        return None


def _post_to_instagram(ig_user_id: str, page_token: str, caption: str, image_url: str) -> Optional[dict]:
    """Post to Instagram Business Account via Graph API."""
    try:
        # Step 1: Create media container
        create_url = f"{FACEBOOK_API_BASE}/{ig_user_id}/media"
        create_data = {
            "access_token": page_token,
            "image_url": image_url,
            "caption": caption,
        }
        resp = httpx.post(create_url, data=create_data, timeout=30.0)
        resp.raise_for_status()
        container_id = resp.json().get("id")
        if not container_id:
            return None

        # Step 2: Publish the container
        publish_url = f"{FACEBOOK_API_BASE}/{ig_user_id}/media_publish"
        publish_data = {
            "access_token": page_token,
            "creation_id": container_id,
        }
        resp = httpx.post(publish_url, data=publish_data, timeout=30.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Instagram post failed: {e}")
        return None


def _post_to_threads(threads_user_id: str, page_token: str, text: str) -> Optional[dict]:
    """Post to Threads via Graph API."""
    try:
        url = f"{FACEBOOK_API_BASE}/{threads_user_id}/threads"
        data = {
            "access_token": page_token,
            "text": text,
        }
        resp = httpx.post(url, data=data, timeout=30.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Threads post failed: {e}")
        return None


def _post_to_pinterest(pinterest_token: str, board_id: str, title: str, description: str, image_url: str, link: str) -> Optional[dict]:
    """Post a Pin to Pinterest."""
    url = f"{PINTEREST_API_BASE}/pins"
    headers = {"Authorization": f"Bearer {pinterest_token}"}
    data = {
        "board_id": board_id,
        "title": title,
        "description": description,
        "media_source": {"source_type": "image_url", "url": image_url},
        "link": link,
    }
    try:
        resp = httpx.post(url, headers=headers, json=data, timeout=30.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Pinterest post failed: {e}")
        return None


def _generate_social_copy(job_spec: JobSpec, gumroad_url: str) -> dict:
    """Generate platform-specific copy using LLM. Falls back to template-based copy if LLM unavailable."""
    from agents.llm_client import generate_text as llm_call

    prompt_lines = [
        f"You are a social media marketing expert. Generate promotional posts for a digital product.",
        f"",
        f"Product: {job_spec.display_name or job_spec.niche}",
        f"Type: {job_spec.product_type.replace('_', ' ').title()}",
        f"Niche: {job_spec.niche}",
        f"Product URL: {gumroad_url}",
        f"CTA: {getattr(job_spec, 'call_to_action', 'Buy Now on Gumroad')}",
        f"",
        f"Generate 4 posts as a JSON object with keys 'instagram', 'threads', 'facebook', 'pinterest'.",
        f"Each value is an object with: 'caption' (string), 'hashtags' (array of strings).",
        f"Pinterest additionally needs a 'title' field.",
        f"",
        f"Instagram: 2-3 sentence caption, 8-12 hashtags, emoji-friendly",
        f"Threads: 1-2 sentence thought-starter, 3-5 hashtags",
        f"Facebook: Paragraph-length post, 5-8 hashtags, link-friendly",
        f"Pinterest: SEO title (max 100 chars), 200-300 char description, 3-5 hashtags",
        f"",
        f"Return ONLY valid JSON, no markdown, no code blocks.",
    ]

    try:
        result = llm_call("\n".join(prompt_lines))
        import re
        match = re.search(r'\{.*\}', result, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        logger.warning(f"Social copy LLM generation failed: {e}")

    # Fallback template-based copy
    cta = getattr(job_spec, 'call_to_action', 'Buy Now on Gumroad')
    name = job_spec.display_name or job_spec.niche
    return {
        "instagram": {
            "caption": f"Introducing {name}! 🚀 Perfect for {job_spec.niche}. {cta} today!",
            "hashtags": ["digitalproduct", job_spec.niche.lower().replace(" ", ""), "gumroad", "productivity"],
        },
        "threads": {
            "caption": f"Just launched {name} — built for {job_spec.niche}. Check it out!",
            "hashtags": ["digital", job_spec.niche.lower().replace(" ", ""), "newlaunch"],
        },
        "facebook": {
            "caption": f"We're excited to announce {name}, a premium {job_spec.product_type.replace('_', ' ')} for {job_spec.niche}. {cta} at {gumroad_url}",
            "hashtags": ["newproduct", "digitalproducts", job_spec.niche.lower().replace(" ", ""), "gumroad"],
        },
        "pinterest": {
            "title": f"{name} — {job_spec.product_type.replace('_', ' ').title()} for {job_spec.niche}",
            "caption": f"Discover {name}, the ultimate {job_spec.product_type.replace('_', ' ')} for {job_spec.niche}. Perfect for professionals and creators. {cta}",
            "hashtags": ["digitalproduct", job_spec.niche.lower().replace(" ", ""), "gumroad"],
        },
    }


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        slug = job_spec.slug
        output_dir = os.path.join("outputs", slug, "landing")
        os.makedirs(output_dir, exist_ok=True)

        # 1. Get landing page URL and Gumroad URL
        landing_page_path = context.get("landing_page")
        landing_page_url = ""
        gumroad_url = ""
        if landing_page_path and os.path.exists(landing_page_path):
            with open(landing_page_path, "r", encoding="utf-8") as f:
                landing_data = json.load(f)
            landing_page_url = landing_data.get("deployed_url", "")

        gumroad_publish_path = context.get("gumroad_publish")
        if gumroad_publish_path and os.path.exists(gumroad_publish_path):
            with open(gumroad_publish_path, "r", encoding="utf-8") as f:
                publish_data = json.load(f)
            gumroad_url = publish_data.get("product_url", "")

        # 2. Generate social copy
        copies = _generate_social_copy(job_spec, gumroad_url)

        # 3. Post to each platform independently
        facebook_token = os.getenv("FACEBOOK_PAGE_TOKEN")
        page_id = os.getenv("FACEBOOK_PAGE_ID", "me")
        ig_user_id = os.getenv("INSTAGRAM_USER_ID", "")
        threads_user_id = os.getenv("THREADS_USER_ID", "")
        pinterest_token = os.getenv("PINTEREST_TOKEN")
        pinterest_board_id = os.getenv("PINTEREST_BOARD_ID", "")

        results = {}

        # Facebook
        if facebook_token and copies.get("facebook"):
            fb_result = _post_to_facebook(
                page_id, facebook_token,
                copies["facebook"]["caption"] + "\n\n" + " ".join(f"#{h}" for h in copies["facebook"]["hashtags"]),
            )
            results["facebook"] = "posted" if fb_result else "failed"

        # Instagram
        if facebook_token and ig_user_id and copies.get("instagram"):
            ig_result = _post_to_instagram(
                ig_user_id, facebook_token,
                copies["instagram"]["caption"] + "\n\n" + " ".join(f"#{h}" for h in copies["instagram"]["hashtags"]),
                landing_page_url or "",
            )
            results["instagram"] = "posted" if ig_result else "failed"

        # Threads
        if facebook_token and threads_user_id and copies.get("threads"):
            threads_result = _post_to_threads(
                threads_user_id, facebook_token,
                copies["threads"]["caption"] + "\n\n" + " ".join(f"#{h}" for h in copies["threads"]["hashtags"]),
            )
            results["threads"] = "posted" if threads_result else "failed"

        # Pinterest
        if pinterest_token and pinterest_board_id and copies.get("pinterest"):
            pin_result = _post_to_pinterest(
                pinterest_token, pinterest_board_id,
                copies["pinterest"]["title"],
                copies["pinterest"]["caption"] + "\n\n" + " ".join(f"#{h}" for h in copies["pinterest"]["hashtags"]),
                landing_page_url or "",
                gumroad_url,
            )
            results["pinterest"] = "posted" if pin_result else "failed"

        # 4. Write result
        result = {
            "status": "done",
            "platforms": results,
            "copies": copies,
        }
        output_path = os.path.join("outputs", slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        posted = sum(1 for v in results.values() if v == "posted")
        logger.info(f"Social promotion: {posted}/{len(results)} platforms posted")
        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Social agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
```

- [ ] **Step 2: Verify file compiles**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python -c "import ast; ast.parse(open('agents/social_agent.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add agents/social_agent.py
git commit -m "feat: add social_agent for multi-platform promotion"
```

---

### Task 5: Create Prompt Templates

**Files:**
- Create: `prompts/landing_stitch.j2`
- Create: `prompts/landing_refine.j2`
- Create: `prompts/social_copy.j2`

- [ ] **Step 1: Create `prompts/landing_stitch.j2`**

```jinja2
You are a landing page designer. Generate a Google Stitch design prompt for a digital product.

Product: {{ display_name or niche }}
Product Type: {{ product_type }}
Niche: {{ niche }}
Theme: {{ theme }}
Cover Image URL: {{ cover_url }}
Call to Action: "{{ cta_text }}"
Gumroad URL: {{ gumroad_url }}

Generate a detailed Stitch prompt that:
1. Specifies a hero section with the cover image, product title, and CTA button linked to {{ gumroad_url }}
2. Lists 3-5 key features or benefits of this product
3. Includes a pricing section showing the product value
4. Has a clean footer

Design style should match the "{{ theme }}" theme.
Output should be a plain text prompt suitable for Stitch's generate_screen_from_text tool.
```

- [ ] **Step 2: Create `prompts/landing_refine.j2`**

```jinja2
You are a frontend developer. Refine the following HTML landing page.

Requirements:
1. Ensure the Gumroad "{{ cta_text }}" button is prominently visible and links to {{ gumroad_url }}
2. Make the page fully responsive on mobile devices
3. Fix any broken image references
4. Polish typography and spacing for a premium look
5. Keep the page self-contained (no external dependencies beyond what's already included)

Raw HTML:
{{ raw_html }}

Output ONLY the refined HTML. No explanations, no markdown.
```

- [ ] **Step 3: Create `prompts/social_copy.j2`**

```jinja2
You are a social media marketing expert. Generate promotional posts for a digital product.

Product: {{ display_name or niche }}
Type: {{ product_type }}
Niche: {{ niche }}
Product URL: {{ gumroad_url }}
CTA: {{ cta_text }}

Generate 4 posts as a JSON object with keys 'instagram', 'threads', 'facebook', 'pinterest'.
Each value is an object with: 'caption' (string), 'hashtags' (array of strings).
Pinterest additionally needs a 'title' field.

Instagram: 2-3 sentence caption, 8-12 hashtags, emoji-friendly
Threads: 1-2 sentence thought-starter, 3-5 hashtags
Facebook: Paragraph-length post, 5-8 hashtags, link-friendly
Pinterest: SEO title (max 100 chars), 200-300 char description, 3-5 hashtags

Return ONLY valid JSON, no markdown, no code blocks.
```

- [ ] **Step 4: Verify files exist**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
Test-Path prompts/landing_stitch.j2; Test-Path prompts/landing_refine.j2; Test-Path prompts/social_copy.j2
```

- [ ] **Step 5: Commit**

```bash
git add prompts/landing_stitch.j2 prompts/landing_refine.j2 prompts/social_copy.j2
git commit -m "feat: add landing page and social copy prompt templates"
```

---

### Task 6: Create Fallback Template

**Files:**
- Create: `templates/landing/basic.html.j2`

- [ ] **Step 1: Create directory and template**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
New-Item -ItemType Directory -Path templates/landing -Force
```

Write `templates/landing/basic.html.j2`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ title }}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #111; background: #fafafa; }
    .container { max-width: 800px; margin: 0 auto; padding: 40px 20px; }
    .hero { text-align: center; padding: 80px 20px 60px; }
    .hero h1 { font-size: 2.5em; font-weight: 700; margin-bottom: 16px; }
    .hero p { font-size: 1.2em; color: #555; margin-bottom: 32px; max-width: 600px; margin-left: auto; margin-right: auto; }
    .cta { display: inline-block; padding: 16px 40px; background: #000; color: #fff; text-decoration: none; border-radius: 8px; font-size: 1.1em; font-weight: 600; transition: background 0.2s; }
    .cta:hover { background: #333; }
    .features { padding: 60px 0; }
    .features h2 { text-align: center; font-size: 1.8em; margin-bottom: 40px; }
    .features-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 24px; }
    .feature { background: #fff; padding: 24px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
    .feature h3 { font-size: 1.1em; margin-bottom: 8px; }
    .feature p { font-size: 0.95em; color: #666; }
    .footer { text-align: center; padding: 40px 0; color: #888; font-size: 0.9em; border-top: 1px solid #eee; margin-top: 60px; }
    @media (max-width: 600px) { .hero h1 { font-size: 1.8em; } .hero { padding: 40px 20px; } }
  </style>
</head>
<body>
  <div class="container">
    <section class="hero">
      <h1>{{ title }}</h1>
      <p>A premium {{ product_type }} for {{ niche }}. Everything you need to succeed.</p>
      {% if gumroad_url %}
      <a href="{{ gumroad_url }}" class="cta">{{ cta_text }}</a>
      {% endif %}
    </section>
    <section class="features">
      <h2>What's Inside</h2>
      <div class="features-grid">
        <div class="feature"><h3>Expert Content</h3><p>Professionally crafted for {{ niche }}.</p></div>
        <div class="feature"><h3>Ready to Use</h3><p>Download and start using immediately.</p></div>
        <div class="feature"><h3>Premium Quality</h3><p>Designed to the highest standards.</p></div>
      </div>
    </section>
    <footer class="footer">
      <p>&copy; {{ title }} — Built with Digital Product Factory</p>
    </footer>
  </div>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add templates/landing/basic.html.j2
git commit -m "feat: add fallback landing page template"
```

---

### Task 7: Update `agents/registry.py`

**Files:**
- Modify: `agents/registry.py`

- [ ] **Step 1: Add imports and registry entries**

```python
from . import (
    research_agent,
    csv_export_agent,
    content_agent,
    render_agent,
    packaging_agent,
    notion_agent,
    catalog_agent,
    visual_agent,
    diagram_agent,
    notion_schema_agent,
    gumroad_agent,
    landing_agent,
    social_agent,
)

AGENT_REGISTRY = {
    "research_agent": research_agent.run,
    "csv_export_agent": csv_export_agent.run,
    "content_agent": content_agent.run,
    "render_agent": render_agent.run,
    "packaging_agent": packaging_agent.run,
    "notion_agent": notion_agent.run,
    "catalog_agent": catalog_agent.run,
    "visual_agent": visual_agent.run,
    "diagram_agent": diagram_agent.run,
    "notion_schema_agent": notion_schema_agent.run,
    "gumroad_agent": gumroad_agent.run,
    "landing_agent": landing_agent.run,
    "social_agent": social_agent.run,
}
```

- [ ] **Step 2: Verify file compiles**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python -c "import ast; ast.parse(open('agents/registry.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add agents/registry.py
git commit -m "feat: register landing_agent and social_agent"
```

---

### Task 8: Update `cli/wizard.py`

**Files:**
- Modify: `cli/wizard.py`

Add landing page + social media questions after the gumroad section, and collect new API keys.

- [ ] **Step 1: Edit `cli/wizard.py`**

After the visual_pack OPENAI key section (after the line that sets `set_key(env_path, "OPENAI_API_KEY", openai_key)` and before `job_spec` construction), add:

```python
    landing_page_enabled = False
    social_promotion_enabled = False
    
    landing_prompt = typer.prompt("\nLanding page bhi banayein? (y/n)", default="n")
    if landing_prompt.lower() == 'y':
        landing_page_enabled = True
        
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            gemini_key = typer.prompt("Gemini API Key (for image generation)")
            set_key(env_path, "GEMINI_API_KEY", gemini_key)
        
        stitch_key = os.getenv("STITCH_API_KEY")
        if not stitch_key:
            stitch_key = typer.prompt("Google Stitch API Key")
            set_key(env_path, "STITCH_API_KEY", stitch_key)
        
        vercel_token = os.getenv("VERCEL_TOKEN")
        if not vercel_token:
            vercel_token = typer.prompt("Vercel Token (for deployment)")
            set_key(env_path, "VERCEL_TOKEN", vercel_token)
        
        cta_text = typer.prompt("Call-to-action text for landing page", default="Buy Now on Gumroad")
        
        social_prompt = typer.prompt("\nSocial media pe bhi share karein? (y/n)", default="n")
        if social_prompt.lower() == 'y':
            social_promotion_enabled = True
            
            fb_token = os.getenv("FACEBOOK_PAGE_TOKEN")
            if not fb_token:
                fb_token = typer.prompt("Facebook Page Access Token")
                set_key(env_path, "FACEBOOK_PAGE_TOKEN", fb_token)
            
            pin_token = os.getenv("PINTEREST_TOKEN")
            if not pin_token:
                pin_token = typer.prompt("Pinterest Access Token")
                set_key(env_path, "PINTEREST_TOKEN", pin_token)
    else:
        cta_text = ""
```

Replace the `job_spec` construction to include the new fields:

```python
    job_spec = {
        "slug": slug,
        "product_type": product_type,
        "niche": niche,
        "theme": theme,
        "notion_sync": notion_sync,
        "notion_parent_page_id": notion_parent_page_id,
        "gumroad_enabled": gumroad_enabled,
        "landing_page_enabled": landing_page_enabled,
        "social_promotion_enabled": social_promotion_enabled,
        "call_to_action": cta_text,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
```

- [ ] **Step 2: Verify file compiles**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python -c "import ast; ast.parse(open('cli/wizard.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add cli/wizard.py
git commit -m "feat: add landing page and social media prompts to wizard"
```

---

### Task 9: Update All 7 Schemas

**Files:**
- Modify: `schemas/research_pack.json`
- Modify: `schemas/operating_system.json`
- Modify: `schemas/visual_pack.json`
- Modify: `schemas/workflow_kit.json`
- Modify: `schemas/blog_kit.json`
- Modify: `schemas/course_launch.json`
- Modify: `schemas/saas_docs.json`

Each schema gets two new components added at the END of the `components` array (after `gumroad_publish`):

```json
    {
      "id": "landing_page",
      "agent": "landing_agent",
      "output": "landing/deployed.json",
      "depends_on": ["gumroad_publish"]
    },
    {
      "id": "social_promotion",
      "agent": "social_agent",
      "output": "landing/social_results.json",
      "depends_on": ["landing_page"]
    }
```

- [ ] **Step 1 through 7: Update each schema file**

Append the two new component objects after the closing brace of `gumroad_publish`'s `depends_on` array, before the closing `]` of `components`.

For `research_pack.json`, the components array should end like this:

```json
    {
      "id": "gumroad_publish",
      "agent": "gumroad_agent",
      "output": "gumroad/published.json",
      "depends_on": [
        "gumroad_research"
      ]
    },
    {
      "id": "landing_page",
      "agent": "landing_agent",
      "output": "landing/deployed.json",
      "depends_on": ["gumroad_publish"]
    },
    {
      "id": "social_promotion",
      "agent": "social_agent",
      "output": "landing/social_results.json",
      "depends_on": ["landing_page"]
    }
```

Repeat the same pattern for all 7 schemas.

- [ ] **Step 8: Validate all schemas**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
foreach ($f in Get-ChildItem schemas/*.json) { try { $null = Get-Content $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json; Write-Output "OK: $($f.Name)" } catch { Write-Output "FAIL: $($f.Name): $_" } }
```

- [ ] **Step 9: Commit**

```bash
git add schemas/
git commit -m "feat: add landing_page and social_promotion to all 7 schemas"
```

---

### Task 10: Update `.env.example`

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add new env vars**

Add after `GUMROAD_ACCESS_TOKEN`:

```
# Landing page generation (Google Stitch + Vercel)
GEMINI_API_KEY=
STITCH_API_KEY=
VERCEL_TOKEN=

# Social media promotion (Facebook Graph API + Pinterest)
FACEBOOK_PAGE_TOKEN=
FACEBOOK_PAGE_ID=
INSTAGRAM_USER_ID=
THREADS_USER_ID=
PINTEREST_TOKEN=
PINTEREST_BOARD_ID=
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "chore: add landing and social API keys to env example"
```

---

### Task 11: Integration Test

Since `landing_page` depends on `gumroad_publish`, we need to create mock state so the orchestrator treats gumroad_publish as "done" and proceeds to landing.

- [ ] **Step 1: Create test directory and state**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
New-Item -ItemType Directory -Path outputs/test-landing/gumroad -Force
```

Create `outputs/test-landing/gumroad/published.json`:
```json
{
  "status": "published",
  "product_id": "test-id",
  "product_url": "https://test.gumroad.com/l/test",
  "price": 29
}
```

Create `outputs/test-landing/job_state.json`:
```json
{
  "slug": "test-landing",
  "components": {
    "gumroad_publish": {
      "status": "done",
      "output_path": "outputs/test-landing/gumroad/published.json"
    }
  }
}
```

- [ ] **Step 2: Create test job_spec with landing enabled**

Create `outputs/test-landing/job_spec.json`:
```json
{
  "slug": "test-landing",
  "product_type": "research_pack",
  "niche": "AI Writing Tools",
  "theme": "default",
  "notion_sync": false,
  "gumroad_enabled": false,
  "landing_page_enabled": true,
  "social_promotion_enabled": false,
  "call_to_action": "Buy Now on Gumroad",
  "created_at": "2026-06-13T00:00:00Z"
}
```

- [ ] **Step 3: Run the pipeline with resume mode**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python main.py --resume outputs/test-landing/job_spec.json
```

The pipeline should:
- Skip gumroad_research (no state for it — will be blocked or skipped)
- Find gumroad_publish already "done" from job_state
- Run landing_page (enabled, dep satisfied)
- Skip social_promotion (disabled)
- Generate HTML at `outputs/test-landing/landing/index.html`

- [ ] **Step 4: Verify output**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
if (Test-Path outputs/test-landing/landing/index.html) { Write-Output "OK: index.html exists" } else { Write-Output "FAIL: index.html missing" }
if (Test-Path outputs/test-landing/landing/deployed.json) { Write-Output "OK: deployed.json exists" } else { Write-Output "FAIL: deployed.json missing" }
```

- [ ] **Step 5: Clean up**

```bash
Remove-Item -Recurse -Force outputs/test-landing -ErrorAction SilentlyContinue
```

---

## Self-Review Checklist

- [ ] Spec coverage: All sections of the design doc have corresponding tasks
- [ ] No placeholders: All code blocks are complete, no TBD/TODO
- [ ] Type consistency: New agent signatures match existing `run(component, job_spec, context) -> AgentResult`
- [ ] Schema pattern: All 7 schemas get identical landing_page + social_promotion additions
- [ ] Graceful degradation: Every external call (Gemini, Stitch, Vercel, Facebook, Pinterest) wrapped in try/except
- [ ] Registry pattern: No new if/elif chains — agents dispatched via `AGENT_REGISTRY`
- [ ] Wizard flow: Landing/social questions are gated (only asked if previous step enabled)
