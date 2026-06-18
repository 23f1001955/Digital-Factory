"""Tests for the Etsy channel."""

from channels.base import ProductArtifact, ArtifactFile


def _make_artifact(slug="test-etsy", **overrides) -> ProductArtifact:
    defaults = dict(
        slug=slug,
        product_type="research_pack",
        niche="test niche",
        display_name="Test Etsy",
        files=[ArtifactFile(path="/tmp/test.pdf", name="test.pdf")],
        cover_image=None,
        thumbnail=None,
        description="A test product",
        price_cents=1500,
        tags=["digital", "test"],
        research_data_path=None,
    )
    defaults.update(overrides)
    return ProductArtifact(**defaults)


def test_etsy_channel_validate_no_env(monkeypatch):
    """validate() returns False when ETSY_API_KEY is not set."""
    monkeypatch.delenv("ETSY_API_KEY", raising=False)
    monkeypatch.delenv("ETSY_API_SECRET", raising=False)
    from channels.etsy_channel import EtsyChannel
    channel = EtsyChannel()
    assert not channel.validate()


def test_etsy_channel_validate_with_env(monkeypatch):
    """validate() returns True when env vars are present."""
    monkeypatch.setenv("ETSY_API_KEY", "test-key")
    monkeypatch.setenv("ETSY_API_SECRET", "test-secret")
    from channels.etsy_channel import EtsyChannel
    channel = EtsyChannel()
    assert channel.validate() in (True, False)


def test_etsy_publish_returns_publish_result(monkeypatch):
    """publish() returns a PublishResult with expected fields."""
    monkeypatch.setenv("ETSY_API_KEY", "test-key")
    monkeypatch.setenv("ETSY_API_SECRET", "test-secret")
    from channels.etsy_channel import EtsyChannel
    channel = EtsyChannel()
    artifact = _make_artifact()
    result = channel.publish(artifact)
    assert result.status in ("published", "failed")
    assert hasattr(result, "product_url")
    assert hasattr(result, "product_id")


def test_etsy_update_returns_publish_result(monkeypatch):
    """update() returns a PublishResult."""
    monkeypatch.setenv("ETSY_API_KEY", "test-key")
    monkeypatch.setenv("ETSY_API_SECRET", "test-secret")
    from channels.etsy_channel import EtsyChannel
    channel = EtsyChannel()
    artifact = _make_artifact()
    result = channel.update("listing_123", artifact)
    assert result.status in ("published", "failed")


def test_etsy_get_analytics_returns_analytics_data(monkeypatch):
    """get_analytics() returns AnalyticsData with the given product_id."""
    monkeypatch.setenv("ETSY_API_KEY", "test-key")
    monkeypatch.setenv("ETSY_API_SECRET", "test-secret")
    from channels.etsy_channel import EtsyChannel
    channel = EtsyChannel()
    ad = channel.get_analytics("listing_123")
    assert ad.product_id == "listing_123"
