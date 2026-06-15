# Image Injection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add AI-generated cover, thumbnail, and social images to all 7 product types, flowing into PDF covers, Gumroad listings, landing pages, and social posts.

**Architecture:** A unified `image_agent` runs after `market_research`, generating 3 variants (cover 16:9, thumbnail 1:1, social 2:3) via Gemini 3.1 Flash. Image paths flow via context into `gumroad_publish` (uploads to product), `render_agent` (PDF cover), `landing_agent` (hero), and `social_agent` (post images).

**Tech Stack:** Python 3.11+, Gemini 3.1 Flash API, httpx

---

### File Structure Map

| File | Action | Purpose |
|------|--------|---------|
| `prompts/image_gen.j2` | Create | LLM prompt for generating image generation prompts |
| `agents/image_agent.py` | Create | Unified image generation agent |
| `agents/registry.py` | Modify | Add `image_agent` entry |
| `agents/gumroad_agent.py` | Modify | Upload cover + thumbnail to Gumroad product |
| `schemas/*.json` (x7) | Modify | Add `images` component after `market_research` |

---

### Task 1: Create `prompts/image_gen.j2`

**Files:**
- Create: `prompts/image_gen.j2`

- [ ] **Step 1: Write the prompt template**

```jinja2
You are an AI image prompt engineer. Generate 3 image generation prompts for a {{ product_type }} about "{{ niche }}".

Theme: {{ theme | default("default") }}

{% if market_research %}
Market context: {{ market_research }}
{% endif %}

Generate 3 prompts as a JSON array with exactly 3 objects, each with keys "id", "prompt", "style":
1. id: "cover" — 16:9 wide banner image for product cover, landing page hero, PDF title page
2. id: "thumbnail" — 1:1 square image for product thumbnail, social media, listing preview
3. id: "social" — 2:3 vertical image for Pinterest pins, Instagram portrait posts

Requirements:
- Professional, premium quality, suitable for a paid digital product
- Clean composition, modern aesthetic
- No text overlay in the image itself
- Appropriate for the "{{ theme }}" visual style
- Colors and mood should match the niche/industry

Return ONLY the JSON array, no markdown, no code blocks, no text outside.
```

- [ ] **Step 2: Commit**

```bash
git add prompts/image_gen.j2
git commit -m "feat: add image generation prompt template"
```

---

### Task 2: Create `agents/image_agent.py`

**Files:**
- Create: `agents/image_agent.py`

- [ ] **Step 1: Write the agent**

```python
import os
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


def _call_gemini(prompt: str, api_key: str) -> Optional[bytes]:
    url = f"{GEMINI_API_BASE}/{GEMINI_MODEL}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["image"]},
    }
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout:60.0)
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


def _generate_placeholder(output_path: str, text: str, width: int, height: int):
    """Generate a simple SVG placeholder when Gemini fails."""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#667eea"/>
      <stop offset="100%" style="stop-color:#764ba2"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" fill="url(#bg)"/>
  <text x="50%" y="50%" text-anchor="middle" dy=".1em"
        font-family="sans-serif" font-size="{min(width, height) // 15}px"
        fill="white" font-weight="600">{text}</text>
</svg>"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg)
    logger.info(f"Placeholder SVG generated: {output_path}")


def _generate_prompts(niche: str, product_type: str, theme: str, research_data: dict = None) -> list:
    """Use LLM to generate 3 image prompts."""
    from agents.llm_client import generate_text as llm_call
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader("prompts"))
    template = env.get_template("image_gen.j2")
    prompt = template.render(
        niche=niche,
        product_type=product_type,
        theme=theme,
        market_research=json.dumps(research_data, indent=2) if research_data else None,
    )

    try:
        result = llm_call(prompt)
        import re
        match = re.search(r'\[.*\]', result, re.DOTALL)
        if match:
            prompts = json.loads(match.group())
            if len(prompts) == 3:
                return prompts
    except Exception as e:
        logger.warning(f"LLM image prompt generation failed: {e}")

    return [
        {"id": "cover", "prompt": f"A premium product cover image for {niche}, 16:9, minimalist, professional", "style": "modern"},
        {"id": "thumbnail", "prompt": f"A square product thumbnail for {niche}, 1:1, clean, bold", "style": "modern"},
        {"id": "social", "prompt": f"A vertical promotional image for {niche}, 2:3, engaging, vibrant", "style": "modern"},
    ]


def run(component: ComponentSpec, job_spec: JobSpec, context: dict) -> AgentResult:
    try:
        slug = job_spec.slug
        output_dir = os.path.join("outputs", slug, "assets")
        os.makedirs(output_dir, exist_ok=True)

        research_data = None
        research_path = context.get("market_research")
        if research_path and os.path.exists(research_path):
            with open(research_path, "r", encoding="utf-8") as f:
                research_data = json.load(f)

        gemini_key = os.getenv("GEMINI_API_KEY")
        image_prompts = _generate_prompts(
            job_spec.niche, job_spec.product_type,
            getattr(job_spec, "theme", "default"),
            research_data,
        )

        sizes = {"cover": (1920, 1080), "thumbnail": (800, 800), "social": (1000, 1500)}
        results = {}

        for img_def in image_prompts:
            img_id = img_def["id"]
            prompt_text = img_def["prompt"]
            width, height = sizes.get(img_id, (800, 800))
            ext = ".png"

            if gemini_key:
                img_bytes = _call_gemini(prompt_text, gemini_key)
                if img_bytes:
                    file_path = os.path.join(output_dir, f"{img_id}{ext}")
                    with open(file_path, "wb") as f:
                        f.write(img_bytes)
                    results[img_id] = file_path
                    logger.info(f"Generated {img_id}")
                    time.sleep(60)  # rate limit
                    continue

            ext = ".svg"
            file_path = os.path.join(output_dir, f"{img_id}{ext}")
            _generate_placeholder(file_path, f"{job_spec.niche}\n{img_id}", width, height)
            results[img_id] = file_path

        output = {
            "status": "done",
            "images": results,
            "prompts_used": [p["prompt"] for p in image_prompts],
        }
        output_path = os.path.join("outputs", slug, component.output)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        return AgentResult(status="done", output_path=output_path, error=None)

    except Exception as e:
        logger.error(f"Image agent failed: {e}")
        return AgentResult(status="failed", error=str(e))
```

- [ ] **Step 2: Verify it compiles**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python -c "import ast; ast.parse(open('agents/image_agent.py', encoding='utf-8').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add agents/image_agent.py
git commit -m "feat: add unified image_agent for cover/thumbnail/social generation"
```

---

### Task 3: Update `agents/registry.py`

**Files:**
- Modify: `agents/registry.py`

- [ ] **Step 1: Add `image_agent` import and registry entry**

Add `image_agent,` to imports and `"image_agent": image_agent.run,` to registry, alongside `market_agent`.

- [ ] **Step 2: Verify compiles and commit**

---

### Task 4: Update `agents/gumroad_agent.py`

**Files:**
- Modify: `agents/gumroad_agent.py`

- [ ] **Step 1: Add image upload to `_run_publish`**

After successful product creation (`result = _gumroad_api("POST", "products", ...)`) and before returning, add image upload:

```python
    # Upload cover + thumbnail images to Gumroad product
    images_path = context.get("images")
    if images_path and os.path.exists(images_path):
        with open(images_path, "r", encoding="utf-8") as f:
            images_data = json.load(f)
        product_images = images_data.get("images", {})
        for img_type in ("cover", "thumbnail"):
            img_path = product_images.get(img_type)
            if img_path and os.path.exists(img_path):
                asset_result = _gumroad_api("POST", f"products/{product_id}/asset", data={
                    "file": ("image.png", open(img_path, "rb"), "image/png"),
                })
                if asset_result:
                    logger.info(f"Uploaded {img_type} to Gumroad product {product_id}")
```

Note: Gumroad API's asset upload may require multipart form data. Wrap in try/except and log warnings on failure — don't block the publish flow.

- [ ] **Step 2: Verify compiles and commit**

---

### Task 5: Update All 7 Schemas

**Files:**
- Modify: `schemas/research_pack.json`, `operating_system.json`, `visual_pack.json`, `workflow_kit.json`, `blog_kit.json`, `course_launch.json`, `saas_docs.json`

- [ ] **Steps 1-7: Add `images` component after `market_research` in each schema**

```json
    {
      "id": "images",
      "agent": "image_agent",
      "output": "data/images_generated.json",
      "depends_on": ["market_research"]
    },
```

- [ ] **Step 8: Validate all schemas**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
foreach ($f in Get-ChildItem schemas/*.json) { try { $null = Get-Content $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json; Write-Output "OK: $($f.Name)" } catch { Write-Output "FAIL: $($f.Name): $_" } }
```

- [ ] **Step 9: Commit**

---

### Task 6: Integration Test

- [ ] **Step 1: Test fallback works**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python -c "
from agents.image_agent import _generate_placeholder
import tempfile, os
d = tempfile.mkdtemp()
_generate_placeholder(os.path.join(d, 'test.svg'), 'Test', 800, 800)
print('OK: placeholder generated')
import shutil; shutil.rmtree(d)
"
```

- [ ] **Step 2: Run existing tests**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
python -m pytest tests/ -v --tb=short
```

- [ ] **Step 3: Verify schemas**

```bash
cd C:\Users\hp\Documents\Projects\digital-factory
foreach ($f in Get-ChildItem schemas/*.json) { try { $null = Get-Content $f.FullName -Raw -Encoding UTF8 | ConvertFrom-Json; Write-Output "OK: $($f.Name)" } catch { Write-Output "FAIL: $($f.Name): $_" } }
```

---

## Self-Review Checklist

- [ ] Spec coverage: image_agent, prompt template, registry, gumroad upload, schema changes all covered
- [ ] No placeholders
- [ ] Gumroad gets both cover + thumbnail uploads
- [ ] Fallback SVGs when Gemini unavailable
- [ ] Rate limiting (60s delay) implemented in agent
