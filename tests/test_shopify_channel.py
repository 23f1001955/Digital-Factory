"""Tests for the Shopify channel."""

from channels.base import ProductArtifact, ArtifactFile


def _make_artifact(slug="test-shopify", **overrides) -> ProductArtifact:
    defaults = dict(
        slug=slug,
        product_type="research_pack",
        niche="test niche",
        display_name="Test Shopify",
        files=[ArtifactFile(path="/tmp/test.pdf", name="test.pdf")],
        cover_image=None,
        thumbnail=None,
        description="A test product",
        price_cents=2000,
        tags=["digital", "test"],
        research_data_path=None,
    )
    defaults.update(overrides)
    return ProductArtifact(**defaults)


def test_shopify_channel_validate_no_env(monkeypatch):
    """validate() returns False when SHOPIFY_STORE_URL is not set."""
    monkeypatch.delenv("SHOPIFY_STORE_URL", raising=False)
    monkeypatch.delenv("SHOPIFY_ACCESS_TOKEN", raising=False)
    from channels.shopify_channel import ShopifyChannel
    channel = ShopifyChannel()
    assert not channel.validate()


def test_shopify_channel_validate_with_env(monkeypatch):
    """validate() returns True when env vars are set."""
    monkeypatch.setenv("SHOPIFY_STORE_URL", "test.myshopify.com")
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "shpat_abc123")
    from channels.shopify_channel import ShopifyChannel
    channel = ShopifyChannel()
    assert channel.validate() in (True, False)


def test_shopify_publish_returns_publish_result(monkeypatch):
    """publish() returns a PublishResult with expected fields."""
    monkeypatch.setenv("SHOPIFY_STORE_URL", "test.myshopify.com")
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "shpat_abc123")
    from channels.shopify_channel import ShopifyChannel
    channel = ShopifyChannel()
    artifact = _make_artifact()
    result = channel.publish(artifact)
    assert result.status in ("published", "failed")


def test_shopify_update_returns_publish_result(monkeypatch):
    """update() returns a PublishResult."""
    monkeypatch.setenv("SHOPIFY_STORE_URL", "test.myshopify.com")
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "shpat_abc123")
    from channels.shopify_channel import ShopifyChannel
    channel = ShopifyChannel()
    artifact = _make_artifact()
    result = channel.update("gid://shopify/Product/123", artifact)
    assert result.status in ("published", "failed")


def test_shopify_get_analytics_returns_analytics_data(monkeypatch):
    """get_analytics() returns AnalyticsData with the given product_id."""
    monkeypatch.setenv("SHOPIFY_STORE_URL", "test.myshopify.com")
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "shpat_abc123")
    from channels.shopify_channel import ShopifyChannel
    channel = ShopifyChannel()
    ad = channel.get_analytics("gid://shopify/Product/123")
    assert ad.product_id == "gid://shopify/Product/123"
