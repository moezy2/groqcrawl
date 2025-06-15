import asyncio
from playwright.async_api import async_playwright
import os
import re
from urllib.parse import urljoin
import requests
import psycopg2
from flask import Flask, jsonify
import threading

print("DEBUG_APP: --- main.py script started execution ---")
app = Flask(__name__)
print("DEBUG_APP: Flask app object created.")

# --- Configuration ---
TARGET_URL = (
    "https://www.london.gov.uk/programmes-strategies/housing-and-land/"
    "homes-londoners/search/to-rent/property?location=Barfield+Avenue%2C+London+N20%200DE&"
    "search-area=15&minimum-bedrooms=2&min-monthly-rent=none&max-monthly-rent=none&"
    "lat=51.6267984&lng=-0.1587195&outside=0&show-advanced-form=0"
)
LINK_SUBSTRING_FILTER = "/programmes-strategies/housing-and-land/homes-londoners/search/property/"

# Environment variable for Discord Webhook
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Database Functions ---
def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    print(f"DEBUG_DB: DATABASE_URL retrieved: {'set' if db_url else 'NOT SET'}")
    if not db_url:
        return None
    try:
        conn = psycopg2.connect(db_url)
        print("DEBUG_DB: Successfully connected to DB.")
        return conn
    except Exception as e:
        print(f"ERROR_DB: DB connection failed: {e}")
        return None

# ...initialize_db, load_extracted_links_from_db, save_new_links_to_db unchanged...
# (Assume these are defined as before.)

# --- Discord Webhook Function ---
def send_discord_message(message_content):
    if not DISCORD_WEBHOOK_URL:
        print("WARNING: Discord webhook URL not set.")
        return
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json={"content": message_content}, timeout=10)
        r.raise_for_status()
        print("DEBUG_DISCORD: Message sent.")
    except Exception as e:
        print(f"ERROR_DISCORD: Failed to send message: {e}")

# --- Main Scraping Logic ---
async def scrape_and_notify_core():
    print(f"INFO: Starting scrape of {TARGET_URL}")
    existing = load_extracted_links_from_db()
    print(f"INFO: {len(existing)} existing links in DB.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        await page.goto(TARGET_URL, timeout=60000)
        await page.wait_for_load_state('networkidle')
        print("DEBUG: Page loaded, grabbing content...")
        html = await page.content()
        print(f"DEBUG_HTML: First 300 chars: {html[:300].replace('\n',' ')}")

        links = await page.locator('a.development-card').all()
        print(f"DEBUG: Found {len(links)} <a.development-card> elements.")

        raw_hrefs = []
        for idx, elt in enumerate(links, start=1):
            href = await elt.get_attribute('href')
            raw_hrefs.append(href)
            print(f"DEBUG raw[{idx}]: {href}")

        filtered = set()
        for idx, href in enumerate(raw_hrefs, start=1):
            if not href:
                print(f"DEBUG filter[{idx}]: Skipped, no href")
                continue
            full = urljoin(TARGET_URL, href)
            if LINK_SUBSTRING_FILTER in full:
                filtered.add(full)
                print(f"DEBUG filter[{idx}]: PASSED -> {full}")
            else:
                print(f"DEBUG filter[{idx}]: SKIPPED -> {full}")

        print(f"INFO: {len(filtered)} links after filtering.")
        new = filtered - existing
        print(f"INFO: {len(new)} new links found.")
        for link in new:
            print(f"DEBUG NEW: {link}")

        if new:
            content = f"**{len(new)} New Listings**\n" + "\n".join(new)
            send_discord_message(content)
            save_new_links_to_db(new)
        else:
            print("INFO: No new listings.")
            send_discord_message("No new listings found.")

        await browser.close()
        return {"new_count": len(new)}

# --- Flask Routes ---
def trigger():
    asyncio.run(scrape_and_notify_core())

@app.route('/scrape')
def scrape():
    threading.Thread(target=trigger, daemon=True).start()
    return jsonify({"status": "started"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

# Initialize DB at startup
initialize_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
