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
DATABASE_URL = os.getenv("DATABASE_URL")  # ensure '?sslmode=require' if needed

# --- Database Functions ---
def get_db_connection():
    if not DATABASE_URL:
        print("ERROR_DB: DATABASE_URL not set.")
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        print("DEBUG_DB: Connected to database.")
        return conn
    except Exception as e:
        print(f"ERROR_DB: DB connection failed: {e}")
        return None


def initialize_db():
    conn = get_db_connection()
    if not conn:
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
        return set()
    links = set()
    try:
        cur = conn.cursor()
        cur.execute("SELECT url FROM scraped_links;")
        for row in cur.fetchall():
            links.add(row[0])
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
        return
    try:
        cur = conn.cursor()
        for link in new_links:
            try:
                cur.execute(
                    "INSERT INTO scraped_links (url) VALUES (%s) ON CONFLICT DO NOTHING;",
                    (link,)
                )
            except Exception as e:
                print(f"WARNING_DB: Failed to insert {link}: {e}")
        conn.commit()
        print(f"DEBUG_DB: Saved {len(new_links)} new links to DB.")
    except Exception as e:
        print(f"ERROR_DB: save_new_links failed: {e}")
    finally:
        conn.close()

# --- Discord Webhook ---
def send_discord_message(content):
    if not DISCORD_WEBHOOK_URL:
        print("WARNING: DISCORD_WEBHOOK_URL not set.")
        return
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=10)
        resp.raise_for_status()
        print("INFO: Discord message sent.")
    except Exception as e:
        print(f"ERROR: Discord message failed: {e}")

# --- Core scraping logic ---
async def scrape_and_notify_core():
    print(f"INFO: Starting scrape of {TARGET_URL}")
    existing_links = load_extracted_links_from_db()
    print(f"INFO: {len(existing_links)} existing links loaded.")

    current_links = set()
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = await browser.new_page(user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "  
                "AppleWebKit/537.36 (KHTML, like Gecko) "  
                "Chrome/114.0.0.0 Safari/537.36"
            ))
            await page.goto(TARGET_URL, timeout=60000)
            print("DEBUG: Page navigated to target; waiting for network idle...")
            await page.wait_for_load_state("networkidle", timeout=60000)
            await asyncio.sleep(8)

            # debug snippet of content
            content = await page.content()
            print(f"DEBUG: Page content snippet (500 chars): {content[:500].replace('\n',' ')}")

            elems = await page.locator('a.development-card').all()
            print(f"DEBUG: Found {len(elems)} raw development-card elements.")
            for i, elt in enumerate(elems[:5], 1):
                print(f"DEBUG sample href {i}: {await elt.get_attribute('href')}")

            for elt in elems:
                href = await elt.get_attribute('href')
                if href and LINK_SUBSTRING_FILTER in urljoin(TARGET_URL, href):
                    current_links.add(urljoin(TARGET_URL, href))

            await browser.close()
    except Exception as e:
        error_msg = f"Scraping error: {e}"
        print(f"ERROR: {error_msg}")
        send_discord_message(f"🚨 {error_msg}")
        return {"status": "error", "message": error_msg}

    print(f"INFO: {len(current_links)} filtered links found.")
    new_links = current_links - existing_links
    print(f"INFO: {len(new_links)} new links detected.")

    if new_links:
        for link in sorted(new_links):
            print(f"DEBUG new link: {link}")
        msg = f"**New London Listings!** {len(new_links)} new links found:\n"
        for link in sorted(new_links)[:10]:
            msg += f"- {link}\n"
        send_discord_message(msg)
        save_new_links_to_db(new_links)
    else:
        print("INFO: No new links found.")
        send_discord_message("Daily check: no new listings found.")

    return {"status": "success", "new_links_count": len(new_links)}

# --- Flask routes and threading ---
def trigger_scrape():
    asyncio.run(scrape_and_notify_core())

@app.route('/scrape', methods=['GET'])
def scrape_endpoint():
    print("INFO: /scrape endpoint called; triggering background job.")
    thread = threading.Thread(target=trigger_scrape, daemon=True)
    thread.start()
    return jsonify({"status": "started"})

@app.route('/health', methods=['GET'])
def health_check():
    print("INFO: /health endpoint called.")
    return jsonify({"status": "healthy", "message": "Service is running."})

# Initialize DB on startup
initialize_db()

if __name__ == "__main__":
    print("DEBUG_APP: Running local Flask server.")
    app.run(debug=True, host='0.0.0.0', port=5000)
