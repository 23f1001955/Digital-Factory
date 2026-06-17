import pytest
from channels.base import BaseChannel, PublishResult, ProductArtifact


def test_publish_result_defaults():
    result = PublishResult(status="published", product_url="https://example.com/p")
    assert result.product_id is None
    assert result.price_cents == 0


def test_product_artifact():
    artifact = ProductArtifact(
        slug="test-slug",
        product_type="research_pack",
        niche="test niche",
        display_name="Test Product",
        files=[],
        description="desc",
        price_cents=2900,
        tags=["test"],
    )
    assert artifact.slug == "test-slug"


def test_base_channel_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseChannel()


def test_concrete_channel_must_implement_abstract_methods():
    class FakeChannel(BaseChannel):
        pass

    with pytest.raises(TypeError):
        FakeChannel()
