import json, os
from agents.catalog_agent import run
from agents import catalog_agent
from orchestrator.models import ComponentSpec, JobSpec


def test_catalog_agent_prompt_mode(tmp_path, monkeypatch):
    """catalog_agent generates prompt templates in prompt mode."""
    output_dir = tmp_path / "outputs" / "test-slug" / "data"
    output_dir.mkdir(parents=True)

    research_path = tmp_path / "research.json"
    with open(research_path, "w") as f:
        json.dump({"niche": "copywriting", "competitors": ["Swiped.co"]}, f)

    images_path = tmp_path / "images.json"
    with open(images_path, "w") as f:
        json.dump(["Write better emails", "Create landing pages"], f)

    comp = ComponentSpec(
        id="prompt_catalog",
        agent="catalog_agent",
        output="data/test_prompts.json",
        depends_on=["market_research", "images"],
        delivery=["zip"],
        format="prompt",
    )
    monkeypatch.setattr(
        catalog_agent,
        "generate_text",
        lambda p: json.dumps(
            [
                {"prompt": "Write a {{type}} email about {{topic}}", "category": "email", "use_case": "Email copywriting"},
                {"prompt": "Create a {{format}} landing page for {{product}}", "category": "landing", "use_case": "Landing page copy"},
            ]
        ) if "AI prompt engineer" in p else json.dumps(
            [
                {"title": "Item 1", "description": "First item"},
            ]
        ),
    )

    job = JobSpec(slug="test-slug", product_type="prompt_pack", niche="copywriting")
    context = {
        "market_research": str(research_path),
        "image_prompts": str(images_path),
    }

    result = run(comp, job, context)
    assert result.status == "done"
    with open(result.output_path) as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) > 0
    assert "prompt" in data[0] or "category" in data[0]
