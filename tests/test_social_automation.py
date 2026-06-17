from agents.social.automation import (
    register_comment_webhook, register_dm_webhook, auto_reply,
    SUPPORTED_COMMENT_PLATFORMS, SUPPORTED_DM_PLATFORMS
)


def test_supported_platforms():
    assert "facebook" in SUPPORTED_COMMENT_PLATFORMS
    assert "instagram" in SUPPORTED_COMMENT_PLATFORMS
    assert "threads" not in SUPPORTED_COMMENT_PLATFORMS
    assert "facebook" in SUPPORTED_DM_PLATFORMS
    assert "instagram" in SUPPORTED_DM_PLATFORMS
    assert "pinterest" not in SUPPORTED_DM_PLATFORMS


def test_register_comment_webhook_no_token(monkeypatch):
    monkeypatch.delenv("FACEBOOK_PAGE_TOKEN", raising=False)
    result = register_comment_webhook("facebook", "https://example.com/webhook", ["price", "help"])
    assert result.get("status") == "failed" or "token" in str(result).lower()


def test_register_comment_webhook_unsupported():
    result = register_comment_webhook("threads", "https://example.com/webhook", ["test"])
    assert result.get("status") == "unsupported"


def test_register_dm_webhook_no_token(monkeypatch):
    monkeypatch.delenv("FACEBOOK_PAGE_TOKEN", raising=False)
    result = register_dm_webhook("instagram", "https://example.com/dm")
    assert result.get("status") == "failed" or "token" in str(result).lower()


def test_register_dm_webhook_unsupported():
    result = register_dm_webhook("pinterest", "https://example.com/dm")
    assert result.get("status") == "unsupported"


def test_auto_reply_matches_trigger():
    reply = auto_reply("facebook", "What is the price?", "Check our store: {url}")
    assert isinstance(reply, str)
    assert len(reply) > 0


def test_auto_reply_no_match():
    reply = auto_reply("facebook", "Nice post!", "Check our store: {url}")
    assert isinstance(reply, str)


def test_auto_reply_unknown_platform():
    reply = auto_reply("unknown", "Hello", "Reply template")
    assert reply == "Reply template"
