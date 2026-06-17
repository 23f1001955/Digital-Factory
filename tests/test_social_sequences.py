from agents.social.models import SocialPost
from agents.social.sequences import generate_sequence, SEQUENCE_TYPES, _get_sequence_template


def test_sequence_types_defined():
    assert "teaser" in SEQUENCE_TYPES
    assert "launch" in SEQUENCE_TYPES
    assert "followup" in SEQUENCE_TYPES
    assert "testimonial" in SEQUENCE_TYPES
    assert "repurpose" in SEQUENCE_TYPES


def test_generate_teaser_sequence():
    post = generate_sequence("teaser", {"name": "Test Pack", "niche": "ai"}, 0, "instagram")
    assert isinstance(post, SocialPost)
    assert post.sequence == "teaser"
    assert post.platform == "instagram"
    assert post.day == 0


def test_generate_launch_sequence():
    post = generate_sequence("launch", {"name": "Pro Pack", "niche": "productivity", "url": "https://gum.co/test"}, 0, "facebook")
    assert post.sequence == "launch"
    assert "Pro Pack" in post.content


def test_generate_followup_sequence():
    post = generate_sequence("followup", {"name": "Pack", "niche": "test"}, 2, "threads")
    assert post.sequence == "followup"
    assert post.day == 2


def test_generate_testimonial_sequence():
    post = generate_sequence("testimonial", {"name": "Pack", "niche": "test"}, 5, "instagram")
    assert post.sequence == "testimonial"


def test_generate_repurpose_sequence():
    post = generate_sequence("repurpose", {"name": "Pack", "niche": "test"}, 7, "pinterest")
    assert post.sequence == "repurpose"


def test_generate_unknown_sequence_fallback():
    post = generate_sequence("unknown", {"name": "Pack", "niche": "test"}, 0, "instagram")
    assert post.sequence == "launch"


def test_get_sequence_template():
    template = _get_sequence_template("launch")
    assert "announce" in template.lower() or "launch" in template.lower()
