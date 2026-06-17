"""Gumroad listing optimization: tags, pricing, AIDA descriptions."""

import logging
from collections import Counter

logger = logging.getLogger(__name__)

try:
    from agents.llm_client import generate_text as call_llm
except ImportError:
    call_llm = None


def _generate_tags(niche: str, product_type: str) -> list[str]:
    """Original tag generation (fallback)."""
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


def _extract_tags_from_research(research_data: dict) -> list[str]:
    tags = []
    for comp in research_data.get("competitors", []) or []:
        tags.extend(comp.get("tags", []) or [])
    gumroad_prods = (
        research_data.get("gumroad_products", [])
        or research_data.get("gumroad", {}).get("products", [])
        or []
    )
    for prod in gumroad_prods:
        tags.extend(prod.get("tags", []) or [])
    for kw in research_data.get("trending_keywords", []) or []:
        if isinstance(kw, str):
            tags.extend(kw.lower().split())
    return tags


def generate_optimized_tags(
    niche: str,
    product_type: str,
    research_data: dict | None = None,
) -> list[str]:
    if not research_data:
        return _generate_tags(niche, product_type)

    research_tags = _extract_tags_from_research(research_data)
    niche_tags = [w.strip(",.!?").lower() for w in niche.split() if w.strip(",.!?")]
    ptype_tag = product_type.replace("_", " ").title()

    scored = Counter()
    for tag in research_tags:
        scored[tag.lower()] += 3
    for tag in niche_tags:
        scored[tag] += 2
    scored[ptype_tag] += 1

    sorted_tags = [t for t, _ in scored.most_common()]

    seen: set[str] = set()
    result: list[str] = []
    for t in sorted_tags:
        if t not in seen and t.strip():
            seen.add(t)
            result.append(t)
        if len(result) >= 8:
            break

    if len(result) < 3:
        result.extend(_generate_tags(niche, product_type))
        seen_clean: set[str] = set()
        result_clean: list[str] = []
        for t in result:
            if t not in seen_clean:
                seen_clean.add(t)
                result_clean.append(t)
        result = result_clean[:8]

    return result


def suggest_price(
    product_type: str,
    research_data: dict | None = None,
    base_price_cents: int = 0,
) -> int:
    if not research_data:
        return base_price_cents

    prices: list[int] = []
    for comp in research_data.get("competitors", []) or []:
        p = comp.get("price_cents") or comp.get("price", 0)
        if isinstance(p, (int, float)) and p > 0:
            prices.append(int(p))
    gumroad_prods = (
        research_data.get("gumroad_products", [])
        or research_data.get("gumroad", {}).get("products", [])
        or []
    )
    for prod in gumroad_prods:
        p = prod.get("price_cents") or prod.get("price", 0)
        if isinstance(p, (int, float)) and p > 0:
            prices.append(int(p))

    if not prices:
        return base_price_cents if base_price_cents > 0 else 999

    prices.sort()
    n = len(prices)
    median = prices[n // 2] if n % 2 == 1 else (prices[n // 2 - 1] + prices[n // 2]) // 2
    return median


def generate_aida_description(
    niche: str,
    product_type: str,
    research_data: dict | None = None,
    call_to_action: str = "Download Now",
) -> str:
    if call_llm:
        prompt = (
            f"Write a Gumroad product description for a {product_type.replace('_', ' ')} "
            f"about {niche}. Use AIDA format (Attention, Interest, Desire, Action). "
            f"Call to action: {call_to_action}"
        )
        try:
            result = call_llm(prompt)
            if result and isinstance(result, str) and len(result) > 50:
                return result.strip()
        except Exception as e:
            logger.warning(f"AIDA description generation failed: {e}")

    ptype = product_type.replace("_", " ").title()
    return (
        f"Attention: Are you struggling to find the right {ptype.lower()} for {niche}?\n\n"
        f"Interest: This premium {ptype.lower()} is packed with actionable strategies, "
        f"expert insights, and proven frameworks to help you succeed.\n\n"
        f"Desire: Join thousands of satisfied customers who have transformed their workflow "
        f"with this comprehensive resource.\n\n"
        f"Action: {call_to_action}"
    )
