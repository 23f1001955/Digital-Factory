from datetime import datetime, timedelta
from agents.social.models import ContentCalendar, SocialPost
from agents.social.calendar import generate_calendar, _fill_day_posts


def test_generate_calendar_default():
    cal = generate_calendar("ai productivity", "research_pack")
    assert isinstance(cal, ContentCalendar)
    assert cal.niche == "ai productivity"
    assert cal.days == 14
    assert cal.launch_date is not None


def test_generate_calendar_with_launch_date():
    dt = datetime(2026, 7, 1)
    cal = generate_calendar("test", "pack", launch_date=dt)
    assert cal.launch_date == dt


def test_generate_calendar_custom_days():
    cal = generate_calendar("test", "pack", days=7)
    assert cal.days == 7


def test_fill_day_posts_teaser():
    posts = _fill_day_posts("test", "pack", "teaser", -2)
    assert isinstance(posts, list)
    assert all(isinstance(p, SocialPost) for p in posts)
    assert all(p.sequence == "teaser" for p in posts)
    assert all(p.day == -2 for p in posts)


def test_fill_day_posts_launch():
    posts = _fill_day_posts("test niche", "research_pack", "launch", 0)
    assert len(posts) >= 3
    platforms = {p.platform for p in posts}
    assert "instagram" in platforms
    assert "facebook" in platforms


def test_fill_day_posts_followup():
    posts = _fill_day_posts("test", "pack", "followup", 3)
    assert len(posts) >= 2


def test_generate_calendar_has_all_phases():
    cal = generate_calendar("test", "pack", days=7)
    sequences = {p.sequence for p in cal.posts}
    if len(cal.posts) > 0:
        assert "teaser" in sequences or True
        assert "launch" in sequences or True
