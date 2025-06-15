import os
import asyncio
from flask import Flask, request, jsonify, Response
from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions

app = Flask(__name__)

async def fetch_full_html(url: str) -> str:
    options = ChromiumOptions()
    
    # Point Pydoll to the installed Chromium binary
    options.binary_location = '/usr/bin/chromium-browser'
    
    # Add necessary Chrome arguments for containerized environments
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-features=VizDisplayCompositor')
    options.add_argument('--headless')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-images')
    options.add_argument('--disable-javascript')  # Remove this if you need JS
    options.add_argument('--user-agent=Mozilla/5.0 (Linux; x86_64) AppleWebKit/537.36')
    
    try:
        async with Chrome(options=options) as browser:
            tab = await browser.start()
            await tab.go_to(url)
            
            # Wait for page to load
            await tab.wait_for_load_state('networkidle')
            await asyncio.sleep(2)
            
            # Get the HTML content
            html = await tab.content()
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
