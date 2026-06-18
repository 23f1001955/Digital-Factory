import os
import json
import tempfile
import pytest
from orchestrator.conversion_tracker import ConversionTracker


def _path(name):
    return os.path.join(tempfile.gettempdir(), name)


def test_record_visit_and_sale():
    path = _path("test_conv1.json")
    if os.path.exists(path):
        os.remove(path)
    ct = ConversionTracker(storage_path=path)
    ct.record_landing_visit("test-slug", {"source": "organic"})
    ct.record_gumroad_sale("test-slug", source="landing")
    assert ct._data["test-slug"].landing_visitors == 1
    assert ct._data["test-slug"].gumroad_sales_landing == 1
    os.remove(path)


def test_compute_report_below_minimum():
    path = _path("test_conv2.json")
    if os.path.exists(path):
        os.remove(path)
    ct = ConversionTracker(storage_path=path)
    ct.record_landing_visit("slug-a", {})
    report = ct.compute_report(min_impressions=10)
    assert report is None
    os.remove(path)


def test_compute_report_returns_data():
    path = _path("test_conv3.json")
    if os.path.exists(path):
        os.remove(path)
    ct = ConversionTracker(storage_path=path)
    for _ in range(100):
        ct.record_landing_visit("slug-b", {})
    for _ in range(10):
        ct.record_gumroad_sale("slug-b", source="landing")
    for _ in range(50):
        ct.record_gumroad_visit_direct("slug-b")
    for _ in range(2):
        ct.record_gumroad_sale("slug-b", source="direct")
    report = ct.compute_report(min_impressions=10)
    assert report is not None
    assert report["slug"] == "slug-b"
    assert report["landing_visitors"] == 100
    assert report["gumroad_sales_landing"] == 10
    assert report["gumroad_visits_direct"] == 50
    assert report["gumroad_sales_direct"] == 2
    os.remove(path)


def test_save_report():
    path = _path("test_conv4.json")
    if os.path.exists(path):
        os.remove(path)
    ct = ConversionTracker(storage_path=path)
    for _ in range(100):
        ct.record_landing_visit("slug-c", {})
    ct.record_gumroad_sale("slug-c", source="landing")
    out_path = _path("test_conv_report.json")
    ct.save_report(path=out_path)
    assert os.path.exists(out_path)
    os.remove(path)
    os.remove(out_path)


def test_persists_across_instances():
    path = _path("test_conv_persist.json")
    if os.path.exists(path):
        os.remove(path)
    ct1 = ConversionTracker(storage_path=path)
    ct1.record_landing_visit("persist-test", {})
    ct2 = ConversionTracker(storage_path=path)
    assert "persist-test" in ct2._data
    os.remove(path)
