from fastapi import FastAPI, Request
from pydantic import BaseModel
from playwright.sync_api import sync_playwright
import traceback

app = FastAPI()

class ScrapeRequest(BaseModel):
    url: str

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/scrape")
def scrape(request_data: ScrapeRequest):
    url = request_data.url
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/113.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            page.goto(url, timeout=60000)
            page.wait_for_load_state("networkidle")
            html = page.content()
            browser.close()
            return {"html": html}
    except Exception as e:
        traceback_str = traceback.format_exc()
        return {
            "error": str(e),
            "trace": traceback_str
        }
