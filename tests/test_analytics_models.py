import pytest
from datetime import datetime
from orchestrator.analytics_models import SalesRecord, Insights, load_sales_records, save_sales_records, save_insights, load_insights


def test_sales_record_defaults():
    r = SalesRecord(product_slug="test", channel="gumroad", date=datetime.now())
    assert r.views == 0
    assert r.sales == 0
    assert r.revenue == 0.0


def test_sales_record_with_values():
    r = SalesRecord(
        product_slug="my-product", channel="gumroad",
        date=datetime(2026, 6, 15), views=100, sales=5,
        revenue=49.99, refunds=0, conversion_rate=5.0,
        traffic_source="landing",
    )
    assert r.product_slug == "my-product"
    assert r.conversion_rate == 5.0


def test_sales_record_serialization_roundtrip(tmp_path):
    r = SalesRecord(product_slug="test", channel="gumroad", date=datetime(2026, 6, 15), sales=3)
    path = tmp_path / "sales.json"
    save_sales_records([r], str(path))
    loaded = load_sales_records(str(path))
    assert len(loaded) == 1
    assert loaded[0].sales == 3
    assert loaded[0].product_slug == "test"


def test_sales_record_dedup(tmp_path):
    date = datetime(2026, 6, 15)
    r1 = SalesRecord(product_slug="a", channel="gumroad", date=date, sales=3)
    r2 = SalesRecord(product_slug="a", channel="gumroad", date=date, sales=5)
    r3 = SalesRecord(product_slug="b", channel="gumroad", date=date, sales=1)
    path = tmp_path / "sales.json"
    save_sales_records([r1, r2, r3], str(path))
    loaded = load_sales_records(str(path))
    assert len(loaded) == 2
    # Find record by slug instead of relying on insertion order
    record_a = next(r for r in loaded if r.product_slug == "a")
    assert record_a.sales == 5


def test_insights_defaults():
    i = Insights()
    assert i.total_revenue == 0.0
    assert i.avg_conversion_rate == 0.0


def test_insights_from_records():
    records = [
        SalesRecord(product_slug="a", channel="gumroad", date=datetime.now(), revenue=100.0, sales=5, views=200, conversion_rate=2.5),
        SalesRecord(product_slug="b", channel="gumroad", date=datetime.now(), revenue=200.0, sales=10, views=500, conversion_rate=2.0),
    ]
    i = Insights.from_records(records)
    assert i.total_revenue == 300.0
    assert i.avg_conversion_rate == 2.25
    assert len(i.top_products) == 2
    assert i.top_products[0].revenue >= i.top_products[1].revenue


def test_load_sales_records_nonexistent(tmp_path):
    loaded = load_sales_records(str(tmp_path / "nonexistent.json"))
    assert loaded == []


def test_insights_serialization_roundtrip(tmp_path):
    i = Insights(total_revenue=500.0, avg_conversion_rate=2.5)
    path = tmp_path / "insights.json"
    save_insights(i, str(path))
    loaded = load_insights(str(path))
    assert loaded is not None
    assert loaded.total_revenue == 500.0
    assert loaded.avg_conversion_rate == 2.5


def test_load_insights_nonexistent(tmp_path):
    loaded = load_insights(str(tmp_path / "nonexistent.json"))
    assert loaded is None
