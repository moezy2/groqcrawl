from fastapi import FastAPI
from pydantic import BaseModel
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

app = FastAPI()

class ScrapeRequest(BaseModel):
    url: str

@app.post("/scrape")
async def scrape_page(req: ScrapeRequest):
    try:
        browser_conf = BrowserConfig(headless=True)
        run_conf = CrawlerRunConfig()
        async with AsyncWebCrawler(config=browser_conf) as crawler:
            result = await crawler.arun(url=req.url, config=run_conf)
            return {
                "markdown": result.markdown,
                "html": result.html,
                "url": req.url
            }
    except Exception as e:
        return {"error": str(e)}
