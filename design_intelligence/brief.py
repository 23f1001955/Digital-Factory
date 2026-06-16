import csv
import json
import os
from pathlib import Path
from typing import Optional

from .models import DesignBrief, LandingPattern
from .registry import load_rules

DATA_DIR = Path(__file__).parent / "data"
PATTERNS_CSV = DATA_DIR / "landing_patterns.csv"


class DesignBriefGenerator:
    """Generates a design brief from market research data.

    Deterministic (no LLM calls). Reads market research, matches
    design recommendations to rules and patterns, builds a system
    prompt block for the landing page LLM call.
    """

    def generate(self, research_path: str | None) -> DesignBrief | None:
        if not research_path or not os.path.exists(research_path):
            return None

        with open(research_path, encoding="utf-8") as f:
            research = json.load(f)

        design_recs = research.get("design_recommendations", {})
        vibe = design_recs.get("design_vibe", "default")
        layout_pattern = design_recs.get("layout_pattern", "")
        color_strategy = design_recs.get("color_strategy", "")
        motion_level = design_recs.get("motion_level", "moderate")
        typography_mood = design_recs.get("typography_mood", "")
        reasoning = design_recs.get("reasoning", "")

        # Load relevant design rules
        rules_text = load_rules(vibe)

        # Match landing pattern from CSV
        pattern = self._match_pattern(layout_pattern)

        # Build the system prompt block
        system_prompt = self._build_prompt(
            rules_text=rules_text,
            pattern=pattern,
            vibe=vibe,
            color_strategy=color_strategy,
            motion_level=motion_level,
            typography_mood=typography_mood,
            reasoning=reasoning,
        )

        return DesignBrief(
            design_vibe=vibe,
            landing_pattern=pattern,
            system_prompt_block=system_prompt,
        )

    def _match_pattern(self, layout_pattern: str) -> Optional[LandingPattern]:
        """Match a layout pattern string to a CSV pattern entry."""
        if not PATTERNS_CSV.exists():
            return None

        with open(PATTERNS_CSV, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                keywords = row.get("Keywords", "").lower()
                if layout_pattern.lower() in keywords or any(
                    kw.strip() in keywords
                    for kw in layout_pattern.lower().replace("-", " ").split()
                ):
                    return LandingPattern(
                        name=row.get("Pattern Name", ""),
                        section_order=[
                            s.strip().lstrip("0123456789. ")
                            for s in row.get("Section Order", "").split(",")
                        ],
                        cta_placement=row.get("Primary CTA Placement", ""),
                        color_strategy=row.get("Color Strategy", ""),
                        recommended_effects=row.get("Recommended Effects", ""),
                    )

        return None

    def _build_prompt(
        self,
        rules_text: str,
        pattern: Optional[LandingPattern],
        vibe: str,
        color_strategy: str,
        motion_level: str,
        typography_mood: str,
        reasoning: str,
    ) -> str:
        """Build the complete system prompt block for LLM injection."""
        parts: list[str] = [
            "You are a world-class frontend engineer designing a premium landing page.",
            "",
            "=== DESIGN DIRECTION ===",
            f"Design Vibe: {vibe}",
            f"Color Strategy: {color_strategy}",
            f"Motion Level: {motion_level}",
            f"Typography Mood: {typography_mood}",
            f"Design Reasoning: {reasoning}",
            "",
        ]

        if pattern:
            parts.extend(
                [
                    "=== LANDING PATTERN ===",
                    f"Pattern: {pattern.name}",
                    "Section Order:",
                ]
            )
            for section in pattern.section_order:
                parts.append(f"  - {section}")
            if pattern.cta_placement:
                parts.append(f"CTA Placement: {pattern.cta_placement}")
            if pattern.color_strategy:
                parts.append(f"Color Strategy: {pattern.color_strategy}")
            if pattern.recommended_effects:
                parts.append(f"Effects: {pattern.recommended_effects}")
            parts.append("")

        if rules_text:
            parts.extend(
                [
                    "=== DESIGN RULES (FOLLOW THESE EXACTLY) ===",
                    rules_text,
                    "",
                ]
            )

        parts.extend(
            [
                "=== OUTPUT REQUIREMENTS ===",
                "1. Single self-contained HTML file with embedded CSS",
                "2. Responsive design (mobile-first)",
                "3. Follow the design rules above for premium aesthetic",
                "4. No external dependencies (no CDN links, no external fonts)",
                "5. Smooth scroll and hover effects using CSS only",
                "6. Output ONLY the complete HTML. No explanations, no markdown.",
            ]
        )

        return "\n".join(parts)
