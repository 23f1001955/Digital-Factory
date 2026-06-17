import pytest
from datetime import datetime
from orchestrator.analytics_models import SalesRecord, Insights


def test_build_past_performance_with_data():
    from orchestrator.feedback_loop import build_past_performance
    records = [
        SalesRecord(product_slug="best-seller", channel="gumroad", date=datetime.now(), revenue=500.0, sales=25, views=1000, conversion_rate=2.5),
        SalesRecord(product_slug="ok-product", channel="gumroad", date=datetime.now(), revenue=100.0, sales=5, views=400, conversion_rate=1.25),
    ]
    insights = Insights.from_records(records)
    pp = build_past_performance(records, insights)
    assert "top_seller" in pp
    assert pp["total_revenue"] == 600.0
    assert pp["avg_conversion_rate"] == 2.14


def test_build_past_performance_empty():
    from orchestrator.feedback_loop import build_past_performance
    pp = build_past_performance([], Insights())
    assert pp["total_revenue"] == 0.0
    assert pp["avg_conversion_rate"] == 0.0


def test_generate_prompt_section():
    from orchestrator.feedback_loop import generate_prompt_section
    pp = {
        "top_seller": {"slug": "ai-workflow-pack", "revenue": 499.99, "niche": "ai productivity"},
        "avg_conversion_rate": 2.5,
        "total_revenue": 12499.00,
    }
    section = generate_prompt_section(pp)
    assert "ai-workflow-pack" in section
    assert "499.99" in section
    assert "ai productivity" in section


def test_generate_prompt_section_empty():
    from orchestrator.feedback_loop import generate_prompt_section
    section = generate_prompt_section({})
    assert section == ""


def test_generate_prompt_section_zero_revenue():
    from orchestrator.feedback_loop import generate_prompt_section
    section = generate_prompt_section({"total_revenue": 0, "avg_conversion_rate": 0, "total_sales": 0})
    assert section == ""


def test_inject_feedback():
    from orchestrator.feedback_loop import inject_feedback
    context = {}
    records = [
        SalesRecord(product_slug="top", channel="gumroad", date=datetime.now(), revenue=300.0, sales=15, views=600, conversion_rate=2.5),
    ]
    inject_feedback(context, records, Insights.from_records(records))
    assert "past_performance" in context
    assert context["past_performance"]["total_revenue"] == 300.0


def test_inject_feedback_empty_records():
    from orchestrator.feedback_loop import inject_feedback
    context = {}
    inject_feedback(context, [], Insights())
    assert context.get("past_performance", {}).get("total_revenue") == 0.0
