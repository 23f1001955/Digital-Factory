import pytest
from channels.base import AnalyticsData, BaseChannel, PublishResult, ProductArtifact


def test_publish_result_defaults():
    result = PublishResult(status="published", product_url="https://example.com/p")
    assert result.product_id is None
    assert result.price_cents == 0
    assert result.error is None


def test_publish_result_all_fields():
    result = PublishResult(
        status="failed",
        product_url="",
        product_id="prod_123",
        price_cents=1999,
        error="rate limit",
    )
    assert result.product_id == "prod_123"
    assert result.error == "rate limit"


def test_product_artifact():
    from channels.base import ArtifactFile

    files = [
        ArtifactFile(path="/tmp/a.pdf", name="a.pdf", delivery_tags=["gumroad"]),
        ArtifactFile(path="/tmp/b.zip", name="b.zip"),
    ]
    artifact = ProductArtifact(
        slug="test-slug",
        product_type="research_pack",
        niche="test niche",
        display_name="Test Product",
        files=files,
        cover_image="/tmp/cover.png",
        thumbnail="/tmp/thumb.png",
        description="desc",
        price_cents=2900,
        tags=["test", "digital"],
    )
    assert artifact.slug == "test-slug"
    assert artifact.price_cents == 2900
    assert len(artifact.files) == 2
    assert artifact.files[0].delivery_tags == ["gumroad"]
    assert artifact.files[1].delivery_tags == []
    assert artifact.cover_image == "/tmp/cover.png"
    assert artifact.thumbnail == "/tmp/thumb.png"


def test_artifact_file_defaults():
    from channels.base import ArtifactFile
    f = ArtifactFile(path="x.pdf", name="x.pdf")
    assert f.delivery_tags == []


def test_base_channel_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseChannel()


def test_concrete_channel_must_implement_abstract_methods():
    class FakeChannel(BaseChannel):
        pass

    with pytest.raises(TypeError):
        FakeChannel()


def test_listing_quality_score_defaults():
    from channels.base import ListingQualityScore
    score = ListingQualityScore()
    assert score.overall_score == 0.0
    assert score.passed is True
    assert score.issues == []


def test_get_analytics_default():
    class MinimalChannel(BaseChannel):
        def validate(self):
            return True
        def publish(self, artifact):
            return PublishResult(status="published")
        def update(self, pid, artifact):
            return PublishResult(status="published")

    ch = MinimalChannel()
    result = ch.get_analytics("prod_1")
    assert isinstance(result, AnalyticsData)
    assert result.product_id == "prod_1"
    assert result.product_slug == ""
