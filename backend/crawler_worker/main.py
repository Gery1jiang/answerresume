"""Crawler worker — wraps kimi_crawler as HTTP microservice."""

import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from services.kimi_crawler import crawl as _crawl

app = FastAPI(title="Crawler Worker", version="1.0.0")


class CrawlRequest(BaseModel):
    keywords: str
    city: str = ""
    platform: str = "51job"
    max_count: int = 5
    skip_urls: list[str] = []
    skip_keys: list[str] = []


class CrawlResponse(BaseModel):
    jobs: list[dict]


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/crawl", response_model=CrawlResponse)
async def api_crawl(req: CrawlRequest):
    try:
        results = await asyncio.wait_for(
            _crawl(
                keywords=req.keywords,
                city=req.city,
                platform=req.platform,
                max_count=req.max_count,
                skip_urls=set(req.skip_urls),
                skip_keys=set(req.skip_keys),
            ),
            timeout=300
        )
        return CrawlResponse(jobs=results)
    except asyncio.TimeoutError:
        raise HTTPException(504, "爬虫超时（300s）")
    except Exception as e:
        raise HTTPException(500, str(e))
