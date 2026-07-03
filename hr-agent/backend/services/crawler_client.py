import os
import logging
import httpx

logger = logging.getLogger(__name__)

CRAWLER_WORKER_URL = os.environ.get("CRAWLER_WORKER_URL", "")


async def crawl_via_worker(
    keywords: str,
    city: str = "",
    platform: str = "51job",
    max_count: int = 3,
    skip_urls: set | None = None,
    skip_keys: set | None = None,
) -> list[dict]:
    if not CRAWLER_WORKER_URL:
        raise RuntimeError("CRAWLER_WORKER_URL not configured")

    async with httpx.AsyncClient(timeout=310) as client:
        resp = await client.post(
            f"{CRAWLER_WORKER_URL}/crawl",
            json={
                "keywords": keywords,
                "city": city,
                "platform": platform,
                "max_count": max_count,
                "skip_urls": list(skip_urls or []),
                "skip_keys": list(skip_keys or []),
            },
        )
        resp.raise_for_status()
        return resp.json()["jobs"]
