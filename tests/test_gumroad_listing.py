import pytest
from channels.gumroad_listing import generate_optimized_tags, suggest_price, generate_aida_description

SAMPLE_RESEARCH = {
    "competitors": [
        {"name": "Competitor A", "price": 1999, "tags": ["productivity", "ai", "workflow"]},
        {"name": "Competitor B", "price": 2999, "tags": ["automation", "ai", "digital"]},
    ],
    "gumroad_products": [
        {"name": "Prod X", "price": 2499, "tags": ["notion", "template", "productivity"]},
    ],
    "trending_keywords": ["ai productivity", "automation", "workflow optimization"],
}

def test_generate_optimized_tags_with_research():
    tags = generate_optimized_tags("ai productivity", "research_pack", SAMPLE_RESEARCH)
    assert isinstance(tags, list)
    assert len(tags) <= 8
    assert len(tags) >= 1

def test_generate_optimized_tags_without_research():
    tags = generate_optimized_tags("ai productivity", "research_pack")
    assert isinstance(tags, list)
    assert len(tags) <= 8
    assert "Digital Product" in tags

def test_suggest_price_with_research():
    price = suggest_price("research_pack", SAMPLE_RESEARCH, base_price_cents=1500)
    assert isinstance(price, int)
    assert price > 0

def test_suggest_price_without_research():
    price = suggest_price("research_pack", base_price_cents=2000)
    assert price == 2000

def test_suggest_price_median():
    price = suggest_price("research_pack", SAMPLE_RESEARCH)
    assert 1999 <= price <= 2999

def test_generate_aida_description_with_research(monkeypatch):
    def mock_llm(*args, **kwargs):
        return "Attention: Struggling with productivity?\n\nInterest: Our pack solves it.\n\nDesire: Used by 1000+ teams.\n\nAction: Download now."
    import channels.gumroad_listing
    monkeypatch.setattr(channels.gumroad_listing, "call_llm", mock_llm)
    desc = generate_aida_description("ai productivity", "research_pack", SAMPLE_RESEARCH)
    assert isinstance(desc, str)
    assert len(desc) > 50

def test_generate_aida_description_fallback():
    desc = generate_aida_description("ai productivity", "research_pack", None, "Buy Now")
    assert isinstance(desc, str)
    assert len(desc) > 20
