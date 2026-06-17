"""Content repurposing: turn one content pack into 10+ social posts."""

import os
import re
import logging

from agents.social.models import SocialPost

logger = logging.getLogger(__name__)


def _extract_snippets_from_content(content_paths: list[str]) -> list[str]:
    snippets: list[str] = []
    for path in content_paths:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            logger.warning(f"Failed to read {path}: {e}")
            continue

        for line in text.split("\n"):
            raw = line.strip()
            stripped = raw.lstrip("- *").strip()
            if re.search(r'\d+%', stripped) or re.search(r'^\d+[xX]\s', stripped):
                if stripped and len(stripped) < 200:
                    snippets.append(stripped)

        for line in text.split("\n"):
            raw = line.strip()
            if raw.startswith("- ") or raw.startswith("* ") or (len(raw) > 2 and raw[0].isdigit() and raw[1] == "."):
                stripped = raw.lstrip("- *0123456789.").strip()
                if stripped and len(stripped) > 10 and len(stripped) < 200:
                    snippets.append(stripped)

        for line in text.split("\n"):
            if line.strip().startswith(">"):
                quote = line.strip().lstrip(">").strip()
                if quote and len(quote) < 200:
                    snippets.append(quote)

    seen: set[str] = set()
    unique: list[str] = []
    for s in snippets:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique[:20]


def _generate_repurposed_posts(
    snippets: list[str],
    niche: str,
    product_type: str,
) -> list[SocialPost]:
    posts: list[SocialPost] = []
    for i, snippet in enumerate(snippets[:10]):
        posts.append(SocialPost(
            content=snippet,
            platform="instagram" if i % 2 == 0 else "facebook",
            sequence="repurpose",
            day=5 + i,
            status="draft",
        ))
    return posts


def repurpose_content(
    content_paths: list[str],
    niche: str,
    product_type: str,
) -> list[SocialPost]:
    snippets = _extract_snippets_from_content(content_paths)
    if not snippets:
        logger.info("No content snippets found, using fallback")
        return [
            SocialPost(content=f"Check out this {product_type.replace('_', ' ')} about {niche}", platform="facebook", sequence="repurpose", day=5, status="draft"),
            SocialPost(content=f"Did you know? {niche.title()} insights inside", platform="instagram", sequence="repurpose", day=6, status="draft"),
            SocialPost(content=f"Tip: Start with {niche} fundamentals", platform="threads", sequence="repurpose", day=7, status="draft"),
        ]
    return _generate_repurposed_posts(snippets, niche, product_type)
