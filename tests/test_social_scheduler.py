import os
import json
import pytest
from datetime import datetime, timedelta
from agents.social.models import SocialPost, ContentCalendar, PostResult
from agents.social.scheduler import queue_posts, dequeue_due, dispatch


def test_queue_and_dequeue(tmp_path, monkeypatch):
    monkeypatch.setattr("agents.social.scheduler.POST_QUEUE_DIR", str(tmp_path))
    posts = [
        SocialPost(id="p1", platform="facebook", content="Post 1", scheduled_at=datetime.now()),
        SocialPost(id="p2", platform="instagram", content="Post 2", scheduled_at=datetime.now() - timedelta(hours=1)),
        SocialPost(id="p3", platform="threads", content="Post 3", scheduled_at=datetime.now() + timedelta(days=1)),
    ]
    cal = ContentCalendar(niche="test", product_type="pack", posts=posts)
    queue_posts(cal)

    files = os.listdir(tmp_path)
    assert len(files) == 3
    assert any("p1" in f for f in files)

    due = dequeue_due()
    assert len(due) == 2
    ids = {p.id for p in due}
    assert "p1" in ids
    assert "p2" in ids
    assert "p3" not in ids


def test_dequeue_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("agents.social.scheduler.POST_QUEUE_DIR", str(tmp_path))
    due = dequeue_due()
    assert due == []


def test_dispatch_no_token(monkeypatch):
    monkeypatch.delenv("FACEBOOK_PAGE_TOKEN", raising=False)
    post = SocialPost(platform="facebook", content="Test")
    result = dispatch(post)
    assert isinstance(result, PostResult)
    assert result.status == "failed"


def test_dispatch_unknown_platform():
    post = SocialPost(platform="unknown", content="Test")
    result = dispatch(post)
    assert result.status == "failed"


def test_dispatch_returns_result():
    post = SocialPost(id="test-id", platform="facebook", content="Hello")
    result = dispatch(post)
    assert result.post_id == "test-id"
    assert result.platform == "facebook"
