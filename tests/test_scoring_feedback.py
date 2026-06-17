import pytest
from orchestrator.analytics_models import SalesRecord
from datetime import datetime


def test_compute_score_adjustment():
    from orchestrator.feedback_loop import compute_score_adjustment
    records = [
        SalesRecord(product_slug="research-pack-ai", channel="gumroad", date=datetime.now(), revenue=500.0, sales=25, views=1000, conversion_rate=2.5),
        SalesRecord(product_slug="blog-kit-test", channel="gumroad", date=datetime.now(), revenue=100.0, sales=5, views=400, conversion_rate=1.25),
    ]
    adj = compute_score_adjustment(records)
    assert "research_pack" in adj
    assert "blog_kit" in adj
    assert adj["research_pack"] >= adj["blog_kit"]


def test_compute_score_adjustment_empty():
    from orchestrator.feedback_loop import compute_score_adjustment
    adj = compute_score_adjustment([])
    assert adj == {}


def test_compute_score_adjustment_single_product():
    from orchestrator.feedback_loop import compute_score_adjustment
    records = [
        SalesRecord(product_slug="prompt-pack-pro", channel="gumroad", date=datetime.now(), revenue=300.0, sales=15, views=500, conversion_rate=3.0),
    ]
    adj = compute_score_adjustment(records)
    assert "prompt_pack" in adj
    assert adj["prompt_pack"] == 5.0


def test_apply_score_adjustments():
    from orchestrator.feedback_loop import apply_score_adjustments
    scores = {"research_pack": 75.0, "blog_kit": 60.0, "prompt_pack": 50.0}
    adjustments = {"research_pack": 5.0, "prompt_pack": -2.0}
    adjusted = apply_score_adjustments(scores, adjustments)
    assert adjusted["research_pack"] == 80.0
    assert adjusted["blog_kit"] == 60.0
    assert adjusted["prompt_pack"] == 48.0


def test_apply_score_adjustments_no_adjustments():
    from orchestrator.feedback_loop import apply_score_adjustments
    scores = {"research_pack": 75.0}
    adjusted = apply_score_adjustments(scores, {})
    assert adjusted["research_pack"] == 75.0


def test_apply_score_adjustments_clamps_below_zero():
    from orchestrator.feedback_loop import apply_score_adjustments
    scores = {"research_pack": 1.0}
    adjustments = {"research_pack": -5.0}
    adjusted = apply_score_adjustments(scores, adjustments)
    assert adjusted["research_pack"] == 0.0


def test_slug_to_product_type_unknown():
    from orchestrator.feedback_loop import _slug_to_product_type
    assert _slug_to_product_type("some-random-thing") == ""
    assert _slug_to_product_type("research-pack-2026") == "research_pack"
    assert _slug_to_product_type("blog-kit-pro") == "blog_kit"
