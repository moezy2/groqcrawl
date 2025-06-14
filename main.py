import asyncio
from playwright.async_api import async_playwright
import os
import re
from urllib.parse import urljoin
import requests
import psycopg2
from flask import Flask, jsonify

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
# Substring filter to identify detail pages
LINK_SUBSTRING_FILTER = "/programmes-strategies/housing-and-land/homes-londoners/search/property/"

# Environment variables (set in Render)
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")  # e.g. postgresql://postgres:Moiscool123!@db.vhgwznxepleditelqcxm.supabase.co:5432/postgres

# --- Database Functions ---
def get_db_connection():
    """Establishes and returns a PostgreSQL database connection."""
    if not DATABASE_URL:
        print("ERROR_DB: DATABASE_URL not set. Cannot connect to database.")
        return None
    print("DEBUG_DB: Using DATABASE_URL from environment.")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        print("DEBUG_DB: Successfully connected to database.")
        return conn
    except Exception as e:
        print(f"ERROR_DB: Could not connect: {e}")
        return None


def initialize_db():
    """Creates the 'scraped_links' table if it doesn't exist."""
    print("DEBUG_DB: initialize_db() called.")
    conn = get_db_connection()
    if not conn:
        print("ERROR_DB: No DB connection; skipping initialization.")
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
        print("DEBUG_DB: ensured scraped_links table exists.")
    except Exception as e:
        print(f"ERROR_DB: initialize_db failed: {e}")
    finally:
        conn.close()
        print("DEBUG_DB: DB connection closed after init.")


def load_extracted_links_from_db():
    """Loads previously extracted links from the database."""
    conn = get_db_connection()
    if not conn:
        print("ERROR_DB: No DB connection; returning empty set.")
        return set()
    links = set()
    try:
        cur = conn.cursor()
        cur.execute("SELECT url FROM scraped_links;")
        rows = cur.fetchall()
        for row in rows:
            links.add(row[0])
        print(f"DEBUG_DB: loaded {len(links)} links from DB.")
    except Exception as e:
        print(f"ERROR_DB: load_extracted_links failed: {e}")
    finally:
        conn.close()
        print("DEBUG_DB: DB connection closed after load.")
    return links


def save_new_links_to_db(new_links):
    """Saves new extracted links to the database."""
    if not new_links:
        print("DEBUG_DB: no new links to save.")
        return
    conn = get_db_connection()
    if not conn:
        print("ERROR_DB: No DB connection; cannot save.")
        return
    try:
        cur = conn.cursor()
        for link in new_links:
            try:
                cur.execute("INSERT INTO scraped_links (url) VALUES (%s) ON CONFLICT (url) DO NOTHING;", (link,))
            except Exception as e:
                print(f"WARNING_DB: insert failed for {link}: {e}")
        conn.commit()
        print(f"DEBUG_DB: attempted to save {len(new_links)} new links.")
    except Exception as e:
        print(f"ERROR_DB: save_new_links failed: {e}")
    finally:
        conn.close()
        print("DEBUG_DB: DB connection closed after save.")

# --- Discord Webhook Function ---
def send_discord_message(message_content):
    """Sends a message to the configured Discord webhook."""
    if not DISCORD_WEBHOOK_URL:
        print("WARNING: Discord Webhook URL not set. Skipping message.")
        return
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": message_content})
        resp.raise_for_status()
        print("INFO: Discord message sent.")
    except Exception as e:
        print(f"ERROR: Discord message failed: {e}")

# --- Main Scraping Logic ---
async def scrape_and_notify_core():
    print(f"INFO: Starting scrape of {TARGET_URL}")
    existing_links = load_extracted_links_from_db()
    print(f"INFO: {len(existing_links)} existing links loaded.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            print("INFO: Navigating to target URL...")
            await page.goto(TARGET_URL, timeout=60000)
            # wait for at least one card to appear
            await page.wait_for_selector('a.development-card', timeout=60000)
            print("INFO: development-card selector found.")
            # scroll to bottom to trigger lazy load
            print("DEBUG: scrolling to bottom...")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            await asyncio.sleep(5)

            # collect card elements
            link_elements = await page.locator('a.development-card').all()
            print(f"DEBUG: found {len(link_elements)} development-card elements.")
            # sample hrefs
            for i, elt in enumerate(link_elements[:5]):
                print(f"DEBUG sample href {i+1}: {await elt.get_attribute('href')}")

            current_scraped_links = set()
            for elt in link_elements:
                href = await elt.get_attribute('href')
                if not href:
                    print("DEBUG: element missing href; skipping.")
                    continue
                abs_url = urljoin(TARGET_URL, href)
                if LINK_SUBSTRING_FILTER in abs_url:
                    current_scraped_links.add(abs_url)

            print(f"INFO: {len(current_scraped_links)} filtered links found.")
            new_links = current_scraped_links - existing_links
            print(f"INFO: {len(new_links)} new links.")

            if new_links:
                for link in sorted(new_links):
                    print(f"DEBUG new link: {link}")
                msg = f"**New London Listings!** {len(new_links)} new links:\n"
                for link in sorted(new_links)[:10]:
                    msg += f"- {link}\n"
                send_discord_message(msg)
                save_new_links_to_db(new_links)
            else:
                print("INFO: no new links found.")
                send_discord_message("Daily check: no new listings found.")

            return {"status": "success", "new_links_count": len(new_links)}
        except Exception as e:
            print(f"ERROR: scraping failed: {e}")
            send_discord_message(f"🚨 Scraping error: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            await browser.close()
            print("INFO: browser closed.")

# --- Flask Routes ---
@app.route('/scrape', methods=['GET'])
async def scrape_endpoint():
    print("INFO: /scrape endpoint called.")
    result = await scrape_and_notify_core()
    return jsonify(result)

@app.route('/health', methods=['GET'])
def health_check():
    print("INFO: /health endpoint called.")
    return jsonify({"status": "healthy"})

# Initialize DB on startup
initialize_db()

if __name__ == "__main__":
    print("DEBUG_APP: Running local Flask server.")
    app.run(debug=True, host='0.0.0.0', port=5000)
