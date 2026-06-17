import os
import sys
import json
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator.models import QualityReport, QualityIssue, ComponentSpec, JobSpec
from orchestrator.quality import (
    run_quality_checks,
    check_word_count,
    check_headings,
    check_empty_sections,
    detect_ai_isms,
    check_format_compliance,
    compute_score,
)
from agents.evaluation_agent import evaluate, EVALUATION_TARGETS


class TestQualityChecks:
    def test_word_count_passes(self):
        content = "word " * 800
        issues = check_word_count(content, "full")
        assert len(issues) == 0

    def test_word_count_fails_short(self):
        content = "short text"
        issues = check_word_count(content, "full")
        assert len(issues) >= 1
        assert issues[0]["category"] == "word_count"
        assert issues[0]["severity"] == "error"

    def test_headings_no_h1(self):
        content = "## Some section\n\nBody text here."
        issues = check_headings(content)
        assert any(i["category"] == "headings" and i["severity"] == "error" for i in issues)

    def test_headings_with_h1(self):
        content = "# Title\n\n## Section 1\n\nBody text."
        issues = check_headings(content)
        assert not any(i["category"] == "headings" and i["severity"] == "error" for i in issues)

    def test_empty_sections_detected(self):
        content = "# Title\n\n## Empty Section\n\n### Another Empty\n"
        issues = check_empty_sections(content)
        assert len(issues) >= 1

    def test_ai_isms_detected(self):
        content = "In today's digital landscape, let's dive in and delve into this."
        issues = detect_ai_isms(content)
        assert len(issues) >= 3

    def test_clean_content_no_ai_isms(self):
        content = "# Guide to Python\n\nPython is a programming language."
        issues = detect_ai_isms(content)
        assert len(issues) == 0

    def test_score_perfect(self):
        assert compute_score([]) == 1.0

    def test_score_deducts(self):
        issues = [{"severity": "error", "category": "test", "message": "test"}]
        assert compute_score(issues) == 0.75

    def test_score_min_zero(self):
        issues = [{"severity": "error", "category": "test", "message": "t"}] * 10
        assert compute_score(issues) == 0.0

    def test_format_compliance_broken_link(self):
        content = "[click here]()"
        issues = check_format_compliance(content)
        assert len(issues) >= 1


class TestEvaluationAgent:
    def test_evaluate_good_content(self):
        component = ComponentSpec(id="test_content", agent="content_agent", output="test.md", format="guide")
        job_spec = JobSpec(slug="test", product_type="research_pack", niche="python")
        context = {}

        paragraph = ("Python is a programming language. It was created by Guido van Rossum and released in 1991. "
                     "Python is known for its simple syntax and readability. It is widely used in web development, "
                     "data science, artificial intelligence, and automation. The language supports multiple paradigms "
                     "including procedural, object-oriented, and functional programming. Python has a large standard "
                     "library that provides tools for many common tasks. The Python community is active and maintains "
                     "thousands of third-party packages. Many large companies use Python in production. The language "
                     "continues to evolve with new features added regularly. Learning Python is often recommended for "
                     "beginners because of its gentle learning curve. Python code is typically shorter than equivalent "
                     "code in other languages. The interpreter can run on many operating systems. Python files use the "
                     ".py extension and are executed by the Python interpreter. The language supports dynamic typing "
                     "and automatic memory management. These features make Python a productive choice for developers. "
                     "Python 3 is the current major version and is recommended for all new projects. ")
        content = "# Python Guide\n\n## Introduction\n\n" + paragraph + "\n\n## Installation\n\n" + paragraph

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(content)
            tmp_path = f.name

        try:
            report = evaluate(component, job_spec, context, tmp_path)
            assert report.passed is True
            assert report.score >= 0.6
        finally:
            os.unlink(tmp_path)

    def test_evaluate_poor_content(self):
        component = ComponentSpec(id="test_bad", agent="content_agent", output="bad.md")
        job_spec = JobSpec(slug="test", product_type="research_pack", niche="python")
        context = {}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("In today's digital landscape, let's dive in! short")
            tmp_path = f.name

        try:
            report = evaluate(component, job_spec, context, tmp_path)
            assert report.passed is False
            assert report.score < 0.6
            assert report.fix_prompt is not None
        finally:
            os.unlink(tmp_path)

    def test_evaluation_targets_include_content_agent(self):
        assert "content_agent" in EVALUATION_TARGETS

    def test_quality_report_model(self):
        report = QualityReport(
            component_id="test",
            score=0.5,
            threshold=0.6,
            issues=[QualityIssue(category="word_count", severity="error", message="Too short")],
            hallucination_flags=["Unsupported claim about X"],
            needs_human_review=True,
            fix_prompt="Please expand the content.",
        )
        assert report.component_id == "test"
        assert report.passed is False  # 0.5 < 0.6
        assert len(report.issues) == 1
        assert report.needs_human_review is True

    def test_quality_issue_model(self):
        issue = QualityIssue(category="headings", severity="error", message="No H1", location="line 1")
        assert issue.category == "headings"
        assert issue.location == "line 1"

    def test_evaluate_non_existent_file(self):
        component = ComponentSpec(id="test", agent="content_agent", output="nope.md")
        job_spec = JobSpec(slug="test", product_type="research_pack", niche="python")
        report = evaluate(component, job_spec, {}, "/nonexistent/path.md")
        assert report.passed is False
        assert report.score == 0.0

    def test_evaluate_json_skips_checks(self):
        component = ComponentSpec(id="market_research", agent="market_agent", output="data/market_research.json")
        job_spec = JobSpec(slug="test", product_type="research_pack", niche="python")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            f.write('{"niche": "test", "pipeline_plan": {"components": []}}')
            tmp_path = f.name

        try:
            report = evaluate(component, job_spec, {}, tmp_path)
            assert report.passed is True
            assert report.score == 1.0
        finally:
            os.unlink(tmp_path)
