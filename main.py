import os
import asyncio
import random
from flask import Flask, request, jsonify, Response
from playwright.async_api import async_playwright

app = Flask(__name__)

# List of realistic user agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
]

async def fetch_full_html_with_stealth(url: str) -> str:
    browser = None
    try:
        async with async_playwright() as p:
            # Launch browser with stealth options
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
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--disable-default-apps',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--disable-component-extensions-with-background-pages',
                    '--disable-ipc-flooding-protection',
                    '--enable-features=NetworkService,NetworkServiceLogging',
                    '--force-color-profile=srgb',
                    '--metrics-recording-only',
                    '--use-mock-keychain',
                    '--disable-background-networking'
                ]
            )
            
            # Create context with realistic settings
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={'width': 1366, 'height': 768},
                locale='en-US',
                timezone_id='America/New_York',
                permissions=['geolocation'],
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
            )
            
            # Create page
            page = await context.new_page()
            
            # Remove automation indicators
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                // Remove the automation flag
                delete navigator.__proto__.webdriver;
                
                // Mock chrome runtime
                window.chrome = {
                    runtime: {}
                };
                
                // Mock permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Deniedß }) :
                        originalQuery(parameters)
                );
                
                // Mock plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                // Mock languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
            """)
            
            # Set longer timeout
            page.set_default_timeout(90000)  # 90 seconds
            
            # Navigate with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Add random delay to seem more human
                    await asyncio.sleep(random.uniform(1, 3))
                    
                    # Try different wait strategies
                    if attempt == 0:
                        await page.goto(url, wait_until='networkidle', timeout=60000)
                    elif attempt == 1:
                        await page.goto(url, wait_until='domcontentloaded', timeout=45000)
                        await asyncio.sleep(5)  # Wait for potential Cloudflare check
                    else:
                        await page.goto(url, wait_until='load', timeout=30000)
                        await asyncio.sleep(8)  # Longer wait for Cloudflare
                    
                    # Check if we hit Cloudflare challenge
                    title = await page.title()
                    content = await page.content()
                    
                    if "cloudflare" in title.lower() or "checking your browser" in content.lower() or "just a moment" in content.lower():
                        if attempt < max_retries - 1:
                            print(f"Cloudflare detected, waiting and retrying... (attempt {attempt + 1})")
                            await asyncio.sleep(random.uniform(10, 15))  # Wait for Cloudflare check
                            continue
                        else:
                            # Wait longer on final attempt
                            await asyncio.sleep(20)
                    
                    break
                    
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    await asyncio.sleep(random.uniform(2, 5))
            
            # Additional wait to ensure page is fully loaded
            await asyncio.sleep(3)
            
            # Get the HTML content
            html = await page.content()
            
            # Close everything
            await context.close()
            await browser.close()
            
            return html
            
    except Exception as e:
        if browser:
            try:
                await browser.close()
            except:
                pass
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
        html = asyncio.run(fetch_full_html_with_stealth(url))
        return Response(html, mimetype='text/html')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"})

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "message": "HTML Fetcher API with Cloudflare Bypass",
        "endpoints": {
            "/fetch-html": "GET - Fetch HTML content of a webpage (includes Cloudflare bypass)",
            "/health": "GET - Health check"
        }
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
