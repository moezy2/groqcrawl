from fastapi import FastAPI
from pydantic import BaseModel
import asyncio
from playwright.async_api import async_playwright
import nest_asyncio

nest_asyncio.apply()
app = FastAPI()

class ScrapeRequest(BaseModel):
    url: str

@app.post("/scrape")
async def scrape(request: ScrapeRequest):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
            page = await context.new_page()
            await page.goto(request.url, timeout=60000)
            content = await page.content()
            await browser.close()
            return {
                "url": request.url,
                "html": content
            }
    except Exception as e:
        return {"error": str(e)}
