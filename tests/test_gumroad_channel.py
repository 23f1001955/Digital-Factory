import pytest
from channels.gumroad_channel import GumroadChannel


def test_channel_name():
    ch = GumroadChannel()
    assert ch.name == "gumroad"


def test_validate_no_token(monkeypatch):
    monkeypatch.delenv("GUMROAD_ACCESS_TOKEN", raising=False)
    ch = GumroadChannel()
    assert ch.validate() is False


def test_generate_tags():
    from channels.gumroad_channel import _generate_tags
    tags = _generate_tags("ai productivity tools", "research_pack")
    assert isinstance(tags, list)
    assert len(tags) <= 8
    assert "ai" in tags
    assert "Research Pack" in tags
    assert "Digital Product" in tags


def test_generate_tags_max():
    from channels.gumroad_channel import _generate_tags
    tags = _generate_tags(
        "artificial intelligence machine learning deep learning data science nlp"
        " computer vision robotics automation analytics",
        "course_launch",
    )
    assert len(tags) <= 8


def test_to_rails_params_dict():
    from channels.gumroad_channel import _to_rails_params
    result = _to_rails_params({"name": "Test", "price": "2999"}, prefix="product")
    assert ("product[name]", "Test") in result
    assert ("product[price]", "2999") in result


def test_to_rails_params_list():
    from channels.gumroad_channel import _to_rails_params
    result = _to_rails_params(["a", "b"], prefix="files")
    assert ("files[]", "a") in result
    assert ("files[]", "b") in result


def test_to_rails_params_bool():
    from channels.gumroad_channel import _to_rails_params
    result = _to_rails_params(True, prefix="active")
    assert result == [("active", "true")]


def test_to_rails_params_none():
    from channels.gumroad_channel import _to_rails_params
    result = _to_rails_params(None, prefix="empty")
    assert result == []


def test_to_rails_params_nested():
    from channels.gumroad_channel import _to_rails_params
    obj = {"files": [{"id": "1"}, {"id": "2"}]}
    result = _to_rails_params(obj, prefix="product")
    assert ("product[files][][id]", "1") in result
    assert ("product[files][][id]", "2") in result


def test_publish_no_token(monkeypatch):
    monkeypatch.delenv("GUMROAD_ACCESS_TOKEN", raising=False)
    from channels.base import ProductArtifact
    artifact = ProductArtifact(
        slug="test", product_type="research_pack", niche="test",
        display_name="Test", files=[],
    )
    ch = GumroadChannel()
    result = ch.publish(artifact)
    assert result.status == "failed"
    assert "token" in (result.error or "").lower()


def test_update_no_token(monkeypatch):
    monkeypatch.delenv("GUMROAD_ACCESS_TOKEN", raising=False)
    from channels.base import ProductArtifact
    artifact = ProductArtifact(
        slug="test", product_type="research_pack", niche="test",
        display_name="Test", files=[],
    )
    ch = GumroadChannel()
    result = ch.update("prod_123", artifact)
    assert result.status == "failed"
    assert "token" in (result.error or "").lower()
