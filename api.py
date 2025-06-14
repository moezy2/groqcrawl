from fastapi import FastAPI
from pydantic import BaseModel
import cloudscraper
import nest_asyncio

nest_asyncio.apply()
app = FastAPI()

class ScrapeRequest(BaseModel):
    url: str

@app.post("/scrape-cloud")
def scrape_cloud(request: ScrapeRequest):
    try:
        scraper = cloudscraper.create_scraper(
            interpreter='js2py',
            delay=5,
            enable_stealth=True,
            stealth_options={
                'min_delay': 2.0,
                'max_delay': 6.0,
                'human_like_delays': True,
                'randomize_headers': True,
                'browser_quirks': True
            },
            browser='chrome',
            debug=True,
            allow_brotli=False  # Prevent binary junk response
        )

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept-Encoding": "identity"
        }

        response = scraper.get(request.url, headers=headers, timeout=30)

        return {
            "status_code": response.status_code,
            "url": request.url,
            "html": response.text
        }

    except Exception as e:
        return {"error": str(e)}
