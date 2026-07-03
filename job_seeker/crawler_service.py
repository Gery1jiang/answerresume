import os
import json
import logging
from fastapi import FastAPI
from pydantic import BaseModel
from contextlib import asynccontextmanager
from boss_crawler import search_boss_jobs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("job-crawler")

app = FastAPI(title="Job Crawler Service")


class CrawlRequest(BaseModel):
    keywords: str
    city: str = ""
    pages: int = 1


class CrawlResponse(BaseModel):
    success: bool
    message: str
    jobs: list = []


@app.post("/crawl")
async def crawl(req: CrawlRequest):
    """Trigger a crawl for jobs matching keywords."""
    logger.info(f"Crawl start: keywords={req.keywords}, city={req.city}")
    try:
        jobs = await search_boss_jobs(req.keywords, req.city, pages=req.pages)
        logger.info(f"Crawl done: {len(jobs)} jobs found")
        return CrawlResponse(success=True, message=f"找到 {len(jobs)} 个岗位", jobs=jobs)
    except Exception as e:
        logger.error(f"Crawl failed: {e}")
        return CrawlResponse(success=False, message=f"抓取失败: {str(e)}")


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
