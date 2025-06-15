import os
import threading
import asyncio
from urllib.parse import urljoin
import requests
import psycopg2
from flask import Flask, jsonify
from playwright.async_api import async_playwright

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

# Environment variables
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

# --- Database Functions ---
def get_db_connection():
    db_url = DATABASE_URL
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


def initialize_db():
    conn = get_db_connection()
    if not conn:
        print("ERROR_DB: Skipping DB init; no connection.")
        return
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS scraped_links (
                id SERIAL PRIMARY KEY,
                url TEXT UNIQUE NOT NULL,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()
        print("DEBUG_DB: Initialized scraped_links table.")
    except Exception as e:
        print(f"ERROR_DB: initialize_db failed: {e}")
    finally:
        conn.close()


def load_extracted_links_from_db():
    conn = get_db_connection()
    if not conn:
        print("ERROR_DB: No DB connection; returning empty set.")
        return set()
    links = set()
    try:
        cur = conn.cursor()
        cur.execute("SELECT url FROM scraped_links;")
        rows = cur.fetchall()
        for (url,) in rows:
            links.add(url)
        print(f"DEBUG_DB: Loaded {len(links)} links from DB.")
    except Exception as e:
        print(f"ERROR_DB: load_extracted_links failed: {e}")
    finally:
        conn.close()
    return links


def save_new_links_to_db(new_links):
    if not new_links:
        print("DEBUG_DB: No new links to save.")
        return
    conn = get_db_connection()
    if not conn:
        print("ERROR_DB: No DB connection; cannot save.")
        return
    try:
        cur = conn.cursor()
        count = 0
        for link in new_links:
            try:
                cur.execute(
                    "INSERT INTO scraped_links (url) VALUES (%s) ON CONFLICT DO NOTHING;",
                    (link,)
                )
                count += 1
            except Exception as e:
                print(f"WARNING_DB: Failed to insert {link}: {e}")
        conn.commit()
        print(f"DEBUG_DB: Saved {count} new links to DB.")
    except Exception as e:
        print(f"ERROR_DB: save_new_links failed: {e}")
    finally:
        conn.close()

# --- Discord Webhook ---
def send_discord_message(content):
    if not DISCORD_WEBHOOK_URL:
        print("WARNING: Discord webhook URL not set.")
        return
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=10)
        resp.raise_for_status()
        print("DEBUG_DISCORD: Message sent.")
    except Exception as e:
        print(f"ERROR_DISCORD: Failed to send message: {e}")

# --- Main Scraping Logic ---
async def scrape_and_notify_core():
    print(f"INFO: Starting scrape of {TARGET_URL}")
    existing_links = load_extracted_links_from_db()
    print(f"INFO: {len(existing_links)} existing links loaded.")

    new_links = set()
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = await browser.new_page(user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " 
                "AppleWebKit/537.36 (KHTML, like Gecko) " 
                "Chrome/114.0.0.0 Safari/537.36"
            ))
            await page.goto(TARGET_URL, timeout=60000)
            print("DEBUG: Navigated to target; waiting network idle...")
            await page.wait_for_load_state('networkidle', timeout=60000)
            await asyncio.sleep(5)

            html = await page.content()
            snippet = html[:300].replace('\n', ' ')
            print(f"DEBUG_HTML: Snippet: {snippet}")
            # Check presence of class in HTML
            class_count = snippet.count('development-card')
            print(f"DEBUG_HTML: 'development-card' occurrences in snippet: {class_count}")

            elements = await page.locator('a.development-card').all()
            print(f"DEBUG: Found {len(elements)} <a.development-card> elements.")

            raw_hrefs = []
            for idx, elt in enumerate(elements, 1):
                href = await elt.get_attribute('href')
                raw_hrefs.append(href)
                print(f"DEBUG raw[{idx}]: {href}")

            filtered = []
            for idx, href in enumerate(raw_hrefs, 1):
                if not href:
                    print(f"DEBUG filter[{idx}]: no href, skip")
                    continue
                full = urljoin(TARGET_URL, href)
                if LINK_SUBSTRING_FILTER in full:
                    filtered.append(full)
                    print(f"DEBUG filter[{idx}]: PASSED {full}")
                else:
                    print(f"DEBUG filter[{idx}]: SKIPPED {full}")

            print(f"INFO: {len(filtered)} links after filtering.")
            for link in filtered:
                if link not in existing_links:
                    new_links.add(link)

            print(f"INFO: {len(new_links)} new links detected.")
            for link in new_links:
                print(f"DEBUG NEW: {link}")

            if new_links:
                msg = f"**{len(new_links)} New Listings**\n" + "\n".join(sorted(new_links))
                send_discord_message(msg)
                save_new_links_to_db(new_links)
            else:
                print("INFO: No new listings.")
                send_discord_message("No new listings found.")

            await browser.close()
    except Exception as e:
        print(f"ERROR: Scraper error: {e}")
        send_discord_message(f"🚨 Scraper error: {e}")
    return {"new_count": len(new_links)}

# --- Flask Routes ---
def run_scrape():
    asyncio.run(scrape_and_notify_core())

@app.route('/scrape', methods=['GET'])
def scrape_endpoint():
    print("INFO: /scrape called; starting background thread.")
    thread = threading.Thread(target=run_scrape, daemon=True)
    thread.start()
    return jsonify({"status": "started"})

@app.route('/health', methods=['GET'])
def health():
    print("INFO: /health called.")
    return jsonify({"status": "healthy"})

# Initialize DB on startup
initialize_db()

if __name__ == '__main__':
    print("DEBUG_APP: Running local Flask server.")
    app.run(host='0.0.0.0', port=5000, debug=True)
