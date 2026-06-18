import time
import json
import tempfile
import os
import pytest
from orchestrator.bottleneck import BottleneckTracker


def test_tracks_single_call():
    bt = BottleneckTracker()
    with bt.track("llm_call"):
        time.sleep(0.01)
    report = bt.report()
    assert "llm_call" in report
    assert report["llm_call"]["count"] == 1


def test_tracks_multiple_calls():
    bt = BottleneckTracker()
    for _ in range(3):
        with bt.track("api_call"):
            time.sleep(0.01)
    report = bt.report()
    assert report["api_call"]["count"] == 3


def test_percentiles():
    bt = BottleneckTracker()
    for i in range(1, 101):
        with bt.track("test_cat"):
            time.sleep(0.001 * i)
    report = bt.report()
    tc = report["test_cat"]
    assert tc["p50_ms"] < tc["p95_ms"]
    assert tc["p95_ms"] < tc["p99_ms"]


def test_no_calls_returns_empty():
    bt = BottleneckTracker()
    report = bt.report()
    assert report == {}


def test_save_report():
    bt = BottleneckTracker()
    with bt.track("test"):
        pass
    path = os.path.join(tempfile.gettempdir(), "test_bottleneck.json")
    bt.save_report(path)
    assert os.path.exists(path)
    with open(path) as f:
        data = json.load(f)
    assert "test" in data
    os.remove(path)
