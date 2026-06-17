"""Multi-post sequence templates for product launches."""

from agents.social.models import SocialPost

SEQUENCE_TYPES = ["teaser", "launch", "followup", "testimonial", "repurpose"]

SEQUENCE_TEMPLATES: dict[str, str] = {
    "teaser": "Something exciting is coming soon. Get ready for {name}.",
    "launch": "We're excited to announce {name}! Check it out at {url}",
    "followup": "Here's another look at {name} — built for {niche}.",
    "testimonial": "See what people are saying about {name} for {niche}.",
    "repurpose": "Did you know? Key insight from {name} about {niche}.",
}


def _get_sequence_template(sequence_type: str) -> str:
    return SEQUENCE_TEMPLATES.get(sequence_type, SEQUENCE_TEMPLATES["launch"])


def generate_sequence(
    sequence_type: str,
    product_info: dict,
    day: int,
    platform: str,
) -> SocialPost:
    if sequence_type not in SEQUENCE_TEMPLATES:
        sequence_type = "launch"

    template = SEQUENCE_TEMPLATES[sequence_type]
    name = product_info.get("name", product_info.get("display_name", "Product"))
    niche = product_info.get("niche", "")
    url = product_info.get("url", product_info.get("product_url", ""))

    content = template.format(name=name, niche=niche, url=url)

    return SocialPost(
        platform=platform,
        content=content,
        sequence=sequence_type,
        day=day,
        status="draft",
    )
