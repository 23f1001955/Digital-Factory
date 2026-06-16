import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

RULES_DIR = Path(__file__).parent / "rules"

VIBE_RULE_MAP: dict[str, list[str]] = {
    "editorial": ["impeccable.md", "frontend-design.md", "design-taste-frontend.md"],
    "minimal": ["frontend-design.md", "design-taste-frontend.md"],
    "dark": ["impeccable.md", "gpt-taste.md", "design-taste-frontend.md"],
    "luxury": ["impeccable.md", "frontend-design.md", "design-taste-frontend.md"],
    "playful": ["gpt-taste.md", "frontend-design.md", "design-taste-frontend.md"],
    "tech": ["impeccable.md", "gpt-taste.md", "design-taste-frontend.md"],
    "professional": ["impeccable.md", "ui-ux-pro-max.md", "design-taste-frontend.md"],
    "bento": ["impeccable.md", "gpt-taste.md", "frontend-design2.md", "frontend-design.md"],
    "storytelling": ["gpt-taste.md", "frontend-design2.md", "frontend-design.md"],
    "scroll": ["frontend-design2.md", "gpt-taste.md", "design-taste-frontend.md"],
    "video": ["impeccable.md", "frontend-design2.md", "frontend-design.md"],
    "funnel": ["ui-ux-pro-max.md", "impeccable.md", "design-taste-frontend.md"],
}

_DEFAULT_FILES = ["impeccable.md", "frontend-design.md"]


def _match_vibe(vibe: str | None) -> list[str]:
    """Match a design vibe keyword to rule filenames using word-boundary matching."""
    if not vibe:
        return _DEFAULT_FILES

    vibe_lower = vibe.lower().replace("-", " ").replace("_", " ")

    for key, files in VIBE_RULE_MAP.items():
        if re.search(rf"\b{re.escape(key)}\b", vibe_lower):
            return files

    return _DEFAULT_FILES


def load_rules(vibe: str | None = None) -> str:
    """Load design rule content as a single text block.

    Selects rule files based on the vibe keyword, reads them,
    and returns their content concatenated with headers.
    """
    rule_files = _match_vibe(vibe)
    parts: list[str] = []

    for filename in rule_files:
        filepath = RULES_DIR / filename
        if not filepath.exists():
            logger.warning("Rule file not found: %s", filepath)
            continue
        content = filepath.read_text(encoding="utf-8").strip()
        label = filename.replace(".md", "").replace("-", " ").title()
        parts.append(f"[Design Rules: {label}]\n{content}")

    return "\n\n".join(parts)
