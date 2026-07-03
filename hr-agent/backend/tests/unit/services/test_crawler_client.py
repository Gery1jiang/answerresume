"""Tests for crawler_client."""

import pytest


class TestCrawlerClient:
    @pytest.mark.asyncio
    async def test_crawl_via_worker_raises_when_no_url(self):
        """When CRAWLER_WORKER_URL is empty, raise RuntimeError."""
        import services.crawler_client as cc
        orig = cc.CRAWLER_WORKER_URL
        cc.CRAWLER_WORKER_URL = ""
        try:
            with pytest.raises(RuntimeError, match="CRAWLER_WORKER_URL not configured"):
                await cc.crawl_via_worker("python", "北京", "51job", 1)
        finally:
            cc.CRAWLER_WORKER_URL = orig
