from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Optional
from groqcrawl import scrape_url, crawl_website, map_website

app = FastAPI()

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

class ScrapeRequest(BaseModel):
    url: str
    formats: Optional[List[str]] = ["markdown", "html"]

class CrawlRequest(BaseModel):
    url: str
    max_depth: Optional[int] = 3
    max_pages: Optional[int] = 10
    formats: Optional[List[str]] = ["markdown", "html"]

class MapRequest(BaseModel):
    url: str

@app.post("/scrape")
async def scrape(request: ScrapeRequest):
    return scrape_url(request.url, request.formats, headers=DEFAULT_HEADERS)

@app.post("/crawl")
async def crawl(request: CrawlRequest):
    return crawl_website(
        request.url,
        max_depth=request.max_depth,
        max_pages=request.max_pages,
        formats=request.formats,
        headers=DEFAULT_HEADERS
    )

@app.post("/map")
async def map_site(request: MapRequest):
    return map_website(request.url, headers=DEFAULT_HEADERS)
