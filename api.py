from fastapi import FastAPI, Request
from pydantic import BaseModel
import nest_asyncio
import asyncio
from playwright.async_api import async_playwright

nest_asyncio.apply()
app = FastAPI()

class ScrapeRequest(BaseModel):
    url: str

@app.post("/scrape")
async def scrape(request: ScrapeRequest):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
            page = await context.new_page()
            await page.goto(request.url, timeout=60000)
            html = await page.content()
            await browser.close()
            return {"html": html}
    except Exception as e:
        return {"error": str(e)}
