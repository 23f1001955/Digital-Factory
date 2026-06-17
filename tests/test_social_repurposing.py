from agents.social.models import SocialPost
from agents.social.repurposing import repurpose_content, _extract_snippets_from_content


def test_extract_snippets_from_markdown(tmp_path):
    md_file = tmp_path / "guide.md"
    md_file.write_text(
        "# Guide\n\n"
        "Here are 3 key statistics:\n"
        "- 80% of teams see improvement\n"
        "- 2x faster delivery\n"
        "- 50% cost reduction\n\n"
        "## Tips\n"
        "- Start with small changes.\n"
        "- Measure everything.\n"
        "- Iterate fast.\n\n"
        "> The best time to start is now.\n"
    )
    snippets = _extract_snippets_from_content([str(md_file)])
    assert len(snippets) > 0
    assert any("80%" in s for s in snippets)
    assert any("Measure" in s for s in snippets)
    assert any("best time" in s for s in snippets)


def test_extract_snippets_no_files():
    snippets = _extract_snippets_from_content([])
    assert snippets == []


def test_extract_snippets_nonexistent():
    snippets = _extract_snippets_from_content(["nonexistent.md"])
    assert snippets == []


def test_repurpose_content_returns_posts(tmp_path, monkeypatch):
    md_file = tmp_path / "report.md"
    md_file.write_text("# Report\n\n80% of users report success.\n\nStart today.\n\n> Quote here.\n")
    monkeypatch.setattr(
        "agents.social.repurposing._generate_repurposed_posts",
        lambda snippets, niche, product_type: [
            SocialPost(content="80% of users report success", platform="instagram", sequence="repurpose", day=5),
            SocialPost(content="Start today for best results", platform="facebook", sequence="repurpose", day=6),
        ],
    )
    posts = repurpose_content([str(md_file)], "test niche", "research_pack")
    assert isinstance(posts, list)
    assert len(posts) >= 2
    assert all(isinstance(p, SocialPost) for p in posts)
    assert all(p.sequence == "repurpose" for p in posts)


def test_repurpose_content_fallback(tmp_path):
    posts = repurpose_content([], "test niche", "research_pack")
    assert isinstance(posts, list)
    assert len(posts) >= 3  # fallback generates minimum posts
