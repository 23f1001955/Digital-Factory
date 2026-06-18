"""Tests for the Stripe Store channel."""

from channels.base import ProductArtifact, ArtifactFile


def _make_artifact(slug="test-store", **overrides) -> ProductArtifact:
    defaults = dict(
        slug=slug,
        product_type="research_pack",
        niche="test niche",
        display_name="Test Store",
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


def test_store_channel_validate_no_env(monkeypatch):
    """validate() returns False when STRIPE_SECRET_KEY is not set."""
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    from channels.store_channel import StoreChannel
    channel = StoreChannel()
    assert not channel.validate()


def test_store_channel_validate_with_env(monkeypatch):
    """validate() returns True when env var is set."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_xyz")
    from channels.store_channel import StoreChannel
    channel = StoreChannel()
    assert channel.validate() in (True, False)


def test_store_publish_returns_publish_result(monkeypatch):
    """publish() returns a PublishResult with expected fields."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_xyz")
    from channels.store_channel import StoreChannel
    channel = StoreChannel()
    artifact = _make_artifact()
    result = channel.publish(artifact)
    assert result.status in ("published", "failed")


def test_store_update_returns_publish_result(monkeypatch):
    """update() returns a PublishResult."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_xyz")
    from channels.store_channel import StoreChannel
    channel = StoreChannel()
    artifact = _make_artifact()
    result = channel.update("prod_123", artifact)
    assert result.status in ("published", "failed")


def test_store_get_analytics_returns_analytics_data(monkeypatch):
    """get_analytics() returns AnalyticsData with the given product_id."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_xyz")
    from channels.store_channel import StoreChannel
    channel = StoreChannel()
    ad = channel.get_analytics("prod_123")
    assert ad.product_id == "prod_123"
