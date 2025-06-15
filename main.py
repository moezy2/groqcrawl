import os
import asyncio
from flask import Flask, request, jsonify, Response
from playwright.async_api import async_playwright

app = Flask(__name__)

async def fetch_full_html(url: str) -> str:
    try:
        async with async_playwright() as p:
            # Launch browser with necessary options for containerized environment
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-extensions',
                    '--disable-plugins',
                    '--disable-images',
                    '--user-agent=Mozilla/5.0 (Linux; x86_64) AppleWebKit/537.36'
                ]
            )
            
            # Create a new page
            page = await browser.new_page()
            
            # Navigate to URL
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Optional: Wait a bit more for dynamic content
            await asyncio.sleep(2)
            
            # Get the HTML content
            html = await page.content()
            
            # Close browser
            await browser.close()
            
            return html
    except Exception as e:
        raise Exception(f"Browser automation failed: {str(e)}")

@app.route('/fetch-html', methods=['GET'])
def fetch_html_endpoint():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Missing 'url' parameter"}), 400
    
    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        return jsonify({"error": "URL must start with http:// or https://"}), 400
    
    try:
        html = asyncio.run(fetch_full_html(url))
        return Response(html, mimetype='text/html')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "message": "HTML Fetcher API",
        "endpoints": {
            "/fetch-html": "GET - Fetch HTML content of a webpage",
            "/health": "GET - Health check"
        }
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
