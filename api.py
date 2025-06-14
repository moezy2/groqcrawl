# api.py
from fastapi import FastAPI, Request
from groqcrawl import crawl_page  # this imports the core logic from groqcrawl.py

app = FastAPI()

@app.post("/crawl")
async def crawl(request: Request):
    body = await request.json()
    url = body.get("url")
    
    if not url:
        return {"error": "URL is required"}
    
    try:
        output = crawl_page(url)
        return {"result": output}
    except Exception as e:
        return {"error": str(e)}
