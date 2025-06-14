from fastapi import FastAPI, Request
from groqcrawl import scrape_url, crawl_website, map_website

app = FastAPI()

@app.post("/scrape")
async def scrape(request: Request):
    data = await request.json()
    url = data.get("url")
    formats = data.get("formats", ["markdown", "html"])
    return scrape_url(url, formats)

@app.post("/crawl")
async def crawl(request: Request):
    data = await request.json()
    url = data.get("url")
    max_depth = data.get("max_depth", 3)
    max_pages = data.get("max_pages", 10)
    formats = data.get("formats", ["markdown", "html"])
    return crawl_website(url, max_depth, max_pages, formats)

@app.post("/map")
async def map_site(request: Request):
    data = await request.json()
    url = data.get("url")
    return map_website(url)
