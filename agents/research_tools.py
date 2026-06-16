import os
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def duckduckgo_search(query: str, count: int = 10) -> list[dict]:
    """DuckDuckGo HTML search — no API key needed. Less reliable but zero setup."""
    try:
        import httpx
        import re
        resp = httpx.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=10.0,
        )
        resp.raise_for_status()
        results = []
        for match in re.finditer(
            r'<a rel="nofollow" class="result__a" href="([^"]+)".*?>(.*?)</a>',
            resp.text, re.DOTALL
        ):
            href = match.group(1)
            if href.startswith("//"):
                href = "https:" + href
            title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            if title and href:
                results.append({
                    "title": title,
                    "url": href,
                    "description": "",
                    "source": "duckduckgo",
                })
            if len(results) >= count:
                break
        logger.info(f"DuckDuckGo returned {len(results)} results for: {query}")
        return results
    except Exception as e:
        logger.debug(f"DuckDuckGo search failed (non-critical): {e}")
        return []


def brave_search(query: str, count: int = 10) -> list[dict]:
    """Brave Search API — real competitor URLs + snippets. Free tier: 2K/mo."""
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        logger.warning("BRAVE_API_KEY not set — skipping Brave search")
        return []
    try:
        import httpx
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "X-Subscription-Token": api_key,
                "Accept": "application/json",
            },
            params={"q": query, "count": count},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("web", {}).get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("description", ""),
                "source": "brave",
            })
        logger.info(f"Brave search returned {len(results)} results for: {query}")
        return results
    except Exception as e:
        logger.warning(f"Brave search failed: {e}")
        return []


def _reddit_token() -> str | None:
    """Get OAuth2 access token for Reddit API. Falls back to None (public mode)."""
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    try:
        import httpx
        resp = httpx.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": "DigitalProductFactory/1.0"},
            timeout=10.0,
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if token:
            logger.info("Reddit OAuth token acquired")
            return token
    except Exception as e:
        logger.warning(f"Reddit OAuth failed (falling back to public): {e}")
    return None


def reddit_search(query: str, limit: int = 10) -> list[dict]:
    """Reddit API — real user discussions, pain points, sentiment.
    Uses OAuth2 if REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET set in .env.
    Falls back to public endpoint if not. Both are free."""
    try:
        import httpx
        token = _reddit_token()
        headers = {"User-Agent": "DigitalProductFactory/1.0"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        resp = httpx.get(
            "https://oauth.reddit.com/r/all/search" if token
            else "https://www.reddit.com/r/all/search.json",
            params={"q": query, "limit": limit, "sort": "relevance"},
            headers=headers,
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            results.append({
                "title": d.get("title", ""),
                "selftext": d.get("selftext", "")[:500],
                "subreddit": d.get("subreddit", ""),
                "score": d.get("score", 0),
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "num_comments": d.get("num_comments", 0),
                "source": "reddit",
            })
        mode = "OAuth2" if token else "public"
        logger.info(f"Reddit search ({mode}) returned {len(results)} results for: {query}")
        return results
    except Exception as e:
        logger.warning(f"Reddit search failed: {e}")
        return []


def gdelt_news(query: str, max_records: int = 10) -> list[dict]:
    """GDelt Project — global news events. Free, no API key needed. Unlimited."""
    try:
        import httpx
        resp = httpx.get(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            params={
                "query": query,
                "mode": "artlist",
                "format": "json",
                "maxrecords": max_records,
                "sort": "DateDesc",
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for article in data.get("articles", []):
            results.append({
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "source": article.get("sourcecountry", ""),
                "domain": article.get("domain", ""),
                "date": article.get("seendate", "")[:10],
                "source_field": "gdelt",
            })
        logger.info(f"GDelt returned {len(results)} articles for: {query}")
        return results
    except Exception as e:
        logger.warning(f"GDelt news search failed: {e}")
        return []


FIRECRAWL_USAGE_FILE = os.path.join("data", ".firecrawl_usage.json")
FIRECRAWL_MONTHLY_LIMIT = 500


def _firecrawl_remaining() -> int:
    """Check remaining Firecrawl credits this month."""
    try:
        os.makedirs(os.path.dirname(FIRECRAWL_USAGE_FILE), exist_ok=True)
        current_month = datetime.now().strftime("%Y-%m")
        usage = {"month": current_month, "count": 0}
        if os.path.exists(FIRECRAWL_USAGE_FILE):
            with open(FIRECRAWL_USAGE_FILE) as f:
                saved = json.load(f)
            if saved.get("month") == current_month:
                usage = saved
        remaining = FIRECRAWL_MONTHLY_LIMIT - usage["count"]
        if remaining <= 0:
            logger.warning(f"Firecrawl limit exhausted this month ({FIRECRAWL_MONTHLY_LIMIT}/{FIRECRAWL_MONTHLY_LIMIT})")
        return remaining
    except Exception as e:
        logger.debug(f"Firecrawl usage check failed: {e}")
        return 0


def _firecrawl_increment():
    """Increment Firecrawl usage counter."""
    try:
        os.makedirs(os.path.dirname(FIRECRAWL_USAGE_FILE), exist_ok=True)
        current_month = datetime.now().strftime("%Y-%m")
        usage = {"month": current_month, "count": 0}
        if os.path.exists(FIRECRAWL_USAGE_FILE):
            with open(FIRECRAWL_USAGE_FILE) as f:
                saved = json.load(f)
            if saved.get("month") == current_month:
                usage = saved
        usage["count"] += 1
        with open(FIRECRAWL_USAGE_FILE, "w") as f:
            json.dump(usage, f)
    except Exception as e:
        logger.debug(f"Firecrawl increment failed: {e}")


def firecrawl_scrape(url: str) -> str | None:
    """Firecrawl — full page content extraction (markdown). Free: 500 pages/mo.
    Rate-limited automatically — tracks usage in data/.firecrawl_usage.json.
    Resets every month. Skips silently if limit exhausted."""
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        return None
    remaining = _firecrawl_remaining()
    if remaining <= 0:
        logger.warning("Firecrawl monthly limit reached — skipping further scrapes")
        return None
    try:
        import httpx
        resp = httpx.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"url": url, "formats": ["markdown"]},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        markdown = data.get("data", {}).get("markdown", "")
        if markdown:
            _firecrawl_increment()
            remaining_after = _firecrawl_remaining()
            logger.info(f"Firecrawl scraped: {url} ({len(markdown)} chars, {remaining_after}/{FIRECRAWL_MONTHLY_LIMIT} left)")
            return markdown[:8000]
        return None
    except Exception as e:
        logger.warning(f"Firecrawl scrape failed for {url}: {e}")
        return None


def newsapi_headlines(query: str, page_size: int = 10) -> list[dict]:
    """NewsAPI — latest industry news. Free: 100 requests/day."""
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        logger.warning("NEWSAPI_KEY not set — skipping NewsAPI")
        return []
    try:
        import httpx
        resp = httpx.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "pageSize": page_size,
                "sortBy": "publishedAt",
                "language": "en",
                "apiKey": api_key,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for article in data.get("articles", []):
            results.append({
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "description": article.get("description", ""),
                "source_name": article.get("source", {}).get("name", ""),
                "published_at": article.get("publishedAt", "")[:10],
                "source_api": "newsapi",
            })
        logger.info(f"NewsAPI returned {len(results)} articles for: {query}")
        return results
    except Exception as e:
        logger.warning(f"NewsAPI search failed: {e}")
        return []


def pytrends_data(keywords: list[str]) -> dict:
    """Google Trends — keyword popularity, related queries, seasonality. Free."""
    if not keywords:
        return {}
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        pytrends.build_payload(keywords, cat=0, timeframe="today 12-m", geo="", gprop="")

        interest = pytrends.interest_over_time()
        related = pytrends.related_queries()

        result: dict[str, Any] = {}
        if not interest.empty:
            result["interest_over_time"] = {
                str(k): v for k, v in interest[keywords[0]].to_dict().items()
            }
            result["trend_direction"] = (
                "rising"
                if list(interest[keywords[0]].tail(4).values())[-1]
                > list(interest[keywords[0]].tail(4).values())[0]
                else "declining"
            )

        for kw in keywords:
            rq = related.get(kw)
            if rq is not None:
                top = rq.get("top")
                rising = rq.get("rising")
                if top is not None and not top.empty:
                    result[f"{kw}_top_related"] = top.head(10).to_dict("records")
                if rising is not None and not rising.empty:
                    result[f"{kw}_rising_related"] = rising.head(10).to_dict("records")

        logger.info(f"PyTrends data fetched for {len(keywords)} keywords")
        return result
    except Exception as e:
        logger.warning(f"PyTrends failed (non-critical): {e}")
        return {}


def gather_all(niche: str) -> dict:
    """Run all research sources in parallel and return combined data.
    Every source is optional — if it fails, we get empty data, never a crash."""
    import concurrent.futures

    product_keywords = niche.lower().split()[:3]

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        brave_future = executor.submit(brave_search, f"{niche} tools resources market", 10)
        reddit_future = executor.submit(reddit_search, f"{niche}", 10)
        gdelt_future = executor.submit(gdelt_news, niche, 10)
        news_future = executor.submit(newsapi_headlines, niche, 10)
        trends_future = executor.submit(pytrends_data, product_keywords)

        brave_results = brave_future.result()
        reddit_results = reddit_future.result()
        gdelt_results = gdelt_future.result()
        news_results = news_future.result()
        trends_data = trends_future.result()

    competitor_urls = [r["url"] for r in brave_results[:5] if r.get("url")]

    firecrawl_results = {}
    if competitor_urls and os.getenv("FIRECRAWL_API_KEY"):
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            fc_futures = {
                executor.submit(firecrawl_scrape, url): url for url in competitor_urls[:3]
            }
            for future in concurrent.futures.as_completed(fc_futures):
                url = fc_futures[future]
                content = future.result()
                if content:
                    firecrawl_results[url] = content

    combined = {
        "brave_search": brave_results,
        "reddit_discussions": reddit_results,
        "gdelt_news": gdelt_results,
        "newsapi_articles": news_results,
        "google_trends": trends_data,
        "firecrawl_pages": firecrawl_results,
        "total_sources": sum([
            1 for r in [brave_results, reddit_results, gdelt_results, news_results]
            if r
        ]),
    }

    logger.info(
        f"Research gathered: {len(brave_results)} Brave, {len(reddit_results)} Reddit, "
        f"{len(gdelt_results)} GDelt, {len(news_results)} NewsAPI, "
        f"{len(firecrawl_results)} Firecrawl pages"
    )
    return combined
