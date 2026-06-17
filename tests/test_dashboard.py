import pytest
from datetime import datetime
from orchestrator.analytics_models import SalesRecord, Insights


def test_dashboard_format_summary():
    from cli.dashboard import format_summary
    records = [
        SalesRecord(product_slug="product-a", channel="gumroad", date=datetime.now(), revenue=100.0, sales=5, views=200),
        SalesRecord(product_slug="product-b", channel="gumroad", date=datetime.now(), revenue=200.0, sales=10, views=500),
    ]
    output = format_summary(records)
    assert "product-a" in output
    assert "product-b" in output
    assert "100.00" in output or "100.0" in output


def test_dashboard_format_summary_empty():
    from cli.dashboard import format_summary
    output = format_summary([])
    assert "No sales data" in output


def test_dashboard_format_insights():
    from cli.dashboard import format_insights
    i = Insights(
        total_revenue=1000.0,
        avg_conversion_rate=2.5,
        best_channel="gumroad",
        top_products=[
            SalesRecord(product_slug="top", channel="gumroad", date=datetime.now(), revenue=500.0, sales=25, views=1000),
        ],
    )
    output = format_insights(i)
    assert "1000.00" in output or "1000" in output
    assert "gumroad" in output


def test_dashboard_format_insights_empty():
    from cli.dashboard import format_insights
    output = format_insights(None)
    assert "No insights" in output


def test_dashboard_main_no_data(monkeypatch):
    monkeypatch.setattr("cli.dashboard.SALES_RECORDS_PATH", "nonexistent.json")
    monkeypatch.setattr("cli.dashboard.INSIGHTS_PATH", "nonexistent.json")
    from cli.dashboard import main
    main()  # Should not raise
