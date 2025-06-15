import os
import asyncio
from flask import Flask, request, jsonify, Response
from pydoll.browser import Chrome
from pydoll.browser.options import ChromiumOptions

app = Flask(__name__)

async def fetch_full_html(url: str) -> str:
    options = ChromiumOptions()
    options.add_argument('--no-sandbox')
    async with Chrome(options=options) as browser:
        tab = await browser.start()
        await tab.go_to(url)
        await tab.wait_for_load_state('networkidle')
        await asyncio.sleep(2)
        html = await tab.content()
    return html

@app.route('/fetch-html', methods=['GET'])
def fetch_html_endpoint():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Missing 'url' parameter"}), 400
    try:
        html = asyncio.run(fetch_full_html(url))
        return Response(html, mimetype='text/html')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
