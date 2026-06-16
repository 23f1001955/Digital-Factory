import pytest
from unittest import mock
from orchestrator.models import ComponentSpec, JobSpec, AgentResult


@pytest.fixture
def mock_job_spec():
    return JobSpec(
        slug="test-niche",
        product_type="blog_kit",
        niche="Test Niche",
        notion_only=True,
    )


def test_notion_content_agent_fallback(tmp_path, monkeypatch, mock_job_spec):
    """Test that notion_content_agent falls back to content_agent when Notion unavailable."""
    from agents.notion_content_agent import run

    component = ComponentSpec(
        id="test_content",
        agent="notion_content_agent",
        output="content/test_content.md",
        depends_on=["market_research"],
    )

    mock_content = mock.Mock(
        return_value=AgentResult(status="done", output_path="content/test_content.md")
    )
    monkeypatch.setattr("agents.content_agent.run", mock_content)

    result = run(component, mock_job_spec, {})

    assert result.status == "done"
    mock_content.assert_called_once_with(component, mock_job_spec, {})


def test_notion_content_agent_no_context(tmp_path, monkeypatch, mock_job_spec):
    """Test fallback when notion_tree not in context."""
    from agents.notion_content_agent import run

    component = ComponentSpec(
        id="test_content",
        agent="notion_content_agent",
        output="content/test_content.md",
        depends_on=["market_research"],
    )

    monkeypatch.setenv("NOTION_API_KEY", "test-key")
    monkeypatch.setenv("NOTION_PARENT_PAGE_ID", "test-page")

    mock_content = mock.Mock(
        return_value=AgentResult(status="done", output_path="content/test_content.md")
    )
    monkeypatch.setattr("agents.content_agent.run", mock_content)

    result = run(component, mock_job_spec, {"market_research": "some_path.json"})

    assert result.status == "done"
    mock_content.assert_called_once()
