# Image Injection Design

**Date:** 2026-06-13
**Status:** Draft
**Product:** Digital Product Factory

## Overview

Add AI-generated cover images, thumbnails, and social media images to every product type. A unified `image_agent` runs early in the pipeline, generating 3 image variants per product. These images flow into PDF covers, Gumroad listings, landing pages, and social posts through the context system.

## Problem

- `visual_agent` only runs for `visual_pack` (DALL-E)
- Other 6 product types get zero images
- Gumroad publish uploads text only — no cover/thumbnail
- Landing page + social media generate their own images independently (redundant, inconsistent)

## Solution

### Single `image_agent` — Three Variants

```
market_research → image_agent → cover.png + thumbnail.png + social.png
                                    │               │               │
                                    ▼               ▼               ▼
                              render_agent    gumroad_publish   landing_agent
                              (PDF cover)     (API upload)      (hero image)
                                                                social_agent
                                                                (post image)
```

### Agent: `image_agent`

Runs after `market_research`, before all content components.

**3 images per run (Gemini 3.1 Flash):**

| Variant | Size | Uses |
|---------|------|------|
| `cover.png` | 1920×1080 (16:9) | PDF title page background, landing page hero, Gumroad cover |
| `thumbnail.png` | 800×800 (1:1) | Gumroad thumbnail, social square posts, listing preview |
| `social.png` | 1000×1500 (2:3) | Pinterest pins, Instagram portrait, Threads |

**Rate limiting:** 60-second delay between each image generation call.

**Prompt:** LLM generates a context-aware image prompt using `prompts/image_gen.j2` (product type, niche, theme, market research data).

### Output

```
outputs/{slug}/assets/
├── cover.png
├── thumbnail.png
└── social.png
```

Output JSON (`assets/images_generated.json`):
```json
{
  "status": "done",
  "images": {
    "cover": "outputs/{slug}/assets/cover.png",
    "thumbnail": "outputs/{slug}/assets/thumbnail.png",
    "social": "outputs/{slug}/assets/social.png"
  }
}
```

### Gumroad Integration

`gumroad_publish` updated to upload cover + thumbnail via `POST /v2/products/{id}/asset`:

1. After product creation, upload `cover.png` as product preview
2. Upload `thumbnail.png` as additional asset
3. Gumroad auto-generates thumbnail from cover preview
4. Fallback: if API upload fails, save image paths for manual upload

### Render Agent Enhancement

`render_agent` already uses Jinja2 templates for PDFs. Update the shared/base template to accept `cover_image` in context and render it as the PDF title page background.

### Fallback

If Gemini API is unavailable, generate placeholder SVGs:
- Cover: gradient background + product name overlay
- Thumbnail: solid color + product initials
- Social: same as cover cropped

### Schema Changes

All 7 schemas get a new `images` component after `market_research`:

```json
{
  "id": "images",
  "agent": "image_agent",
  "output": "data/images_generated.json",
  "depends_on": ["market_research"]
}
```

### Files to Create

| File | Purpose |
|------|---------|
| `agents/image_agent.py` | Unified image generation agent (Gemini) |
| `prompts/image_gen.j2` | LLM prompt for generating image generation prompts |

### Files to Modify

| File | Changes |
|------|---------|
| `agents/registry.py` | Add `image_agent` entry |
| `agents/gumroad_agent.py` | Upload cover + thumbnail after publishing |
| `agents/render_agent.py` | Use cover.png as PDF title page background (via template) |
| `schemas/*.json` (x7) | Add `images` component after `market_research` |
| `cli/wizard.py` | Add Gemini API key collection (moved from landing_agent section to be global) |

### Constraints

1. Gemini 3.1 Flash for all image generation (replaces DALL-E for new pipeline)
2. 60-second delay between image generation calls to respect rate limits
3. Graceful degradation: all images are optional — pipeline runs without them
4. Gumroad upload only happens after successful product creation
5. visual_agent remains for backward compatibility with existing visual_pack runs

## Self-Review Notes

- Covers all 7 product types uniformly
- Gumroad gets both cover + thumbnail
- Images flow into PDF, landing, social through existing context mechanism
- Fallback chain: Gemini → placeholder SVG → no image (all graceful)
- visual_agent not removed — backward compatible
