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
    competitors = [
        {"price_cents": 1999},
        {"price_cents": 2999},
        {"price_cents": 2499},
    ]
    price = suggest_price(competitors, default_price=1500)
    assert isinstance(price, int)
    assert price > 0

def test_suggest_price_without_competitors():
    price = suggest_price(default_price=2000)
    assert price == 2000

def test_suggest_price_median():
    competitors = [
        {"price_cents": 1999},
        {"price_cents": 2999},
        {"price_cents": 2499},
    ]
    price = suggest_price(competitors)
    assert 1999 <= price <= 2999

def test_suggest_price_free_tier():
    price = suggest_price(value_tier="free")
    assert price == 0

def test_suggest_price_low_ticket():
    competitors = [{"price_cents": 3000}]
    price = suggest_price(competitors, value_tier="low_ticket")
    assert 500 <= price <= 1500

def test_suggest_price_high_ticket():
    competitors = [{"price_cents": 3000}]
    price = suggest_price(competitors, value_tier="high_ticket")
    assert price >= 5000

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
