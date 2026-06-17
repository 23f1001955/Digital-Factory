"""Content calendar generation for social media product launches."""

from datetime import datetime, timedelta
from agents.social.models import SocialPost, ContentCalendar

CALENDAR_CADENCE: list[tuple[int, str, str]] = [
    (-3, "teaser", ""),
    (-2, "teaser", ""),
    (-1, "teaser", ""),
    (0, "launch", ""),
    (1, "followup", ""),
    (2, "followup", ""),
    (3, "followup", ""),
    (4, "followup", ""),
    (5, "testimonial", ""),
    (6, "repurpose", ""),
    (7, "repurpose", ""),
    (8, "repurpose", ""),
    (9, "repurpose", ""),
    (10, "repurpose", ""),
    (11, "repurpose", ""),
    (12, "repurpose", ""),
    (13, "repurpose", ""),
    (14, "followup", ""),
]


def _make_content(niche: str, product_type: str, sequence: str, day: int) -> str:
    ptype = product_type.replace("_", " ").title()
    templates = {
        "teaser": f"Something big is coming for {niche}... Day {abs(day)} to go.",
        "launch": f"Introducing our new {ptype} for {niche}! Check it out now.",
        "followup": f"Here's more on how our {ptype} helps with {niche}.",
        "testimonial": f"People love this {ptype}! See what they're saying about {niche}.",
        "repurpose": f"Did you know? Key insight about {niche} from our {ptype}.",
    }
    return templates.get(sequence, f"Post about {niche} — day {day}")


def _fill_day_posts(niche: str, product_type: str, sequence: str, day: int) -> list[SocialPost]:
    platforms = ["instagram", "facebook", "threads", "pinterest"]
    posts: list[SocialPost] = []
    for i, plat in enumerate(platforms):
        if sequence == "teaser" and plat == "pinterest":
            continue
        if sequence == "teaser" and plat == "threads" and abs(day) > 1:
            continue
        content = _make_content(niche, product_type, sequence, day)
        posts.append(SocialPost(
            platform=plat,
            content=content,
            sequence=sequence,
            day=day,
            status="draft",
        ))
    return posts


def generate_calendar(
    niche: str,
    product_type: str,
    launch_date: datetime | None = None,
    days: int = 14,
    research_data: dict | None = None,
) -> ContentCalendar:
    if launch_date is None:
        launch_date = datetime.now() + timedelta(days=3)

    all_posts: list[SocialPost] = []
    for day_offset, sequence, _ in CALENDAR_CADENCE:
        if day_offset > days:
            break
        posts = _fill_day_posts(niche, product_type, sequence, day_offset)
        all_posts.extend(posts)

    return ContentCalendar(
        niche=niche,
        product_type=product_type,
        launch_date=launch_date,
        posts=all_posts,
        days=days,
    )
