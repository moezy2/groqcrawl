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
# Filter for the property detail pages
LINK_SUBSTRING_FILTER = "/programmes-strategies/housing-and-land/homes-londoners/search/property/"

# Environment variable for Discord Webhook. Render/Supabase will provide this.
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

# initialize_db, load_extracted_links_from_db, save_new_links_to_db remain unchanged...
# (omitted here for brevity; assume same as original code)

# --- Discord Webhook Function ---
def send_discord_message(message_content):
    """Sends a message to the configured Discord webhook."""
    if not DISCORD_WEBHOOK_URL:
        print("WARNING: Discord Webhook URL not set. Skipping message.")
        return
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": message_content})
        resp.raise_for_status()
        print("INFO: Discord message sent successfully!")
    except Exception as e:
        print(f"ERROR: Sending Discord message failed: {e}")

# --- Main Scraping Logic (using Playwright) ---
async def scrape_and_notify_core():
    print(f"INFO: Starting scrape of: {TARGET_URL}")
    existing_links = load_extracted_links_from_db()
    print(f"INFO: {len(existing_links)} existing links loaded from DB.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            print("INFO: Navigating to target URL...")
            await page.goto(TARGET_URL, timeout=60000)
            await page.wait_for_selector('a.development-card', timeout=60000)
            print("INFO: Page loaded and development-card selector found.")

            # Scroll to load any lazy content
            print("DEBUG: Scrolling to bottom to trigger lazy-load...")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
            await asyncio.sleep(5)

            # Grab all development cards
            link_elements = await page.locator('a.development-card').all()
            print(f"DEBUG: Found {len(link_elements)} raw 'development-card' elements.")
            # Print sample hrefs
            for i, elt in enumerate(link_elements[:5]):
                href = await elt.get_attribute('href')
                print(f"DEBUG sample href {i+1}: {href}")

            current_scraped_links = set()
            for element in link_elements:
                href = await element.get_attribute('href')
                if not href:
                    print("DEBUG: Skipping element with no href.")
                    continue
                absolute_url = urljoin(TARGET_URL, href)
                if LINK_SUBSTRING_FILTER in absolute_url:
                    current_scraped_links.add(absolute_url)

            print(f"INFO: {len(current_scraped_links)} total filtered links found.")
            new_links = current_scraped_links - existing_links
            print(f"INFO: {len(new_links)} new links since last check.")
            if new_links:
                for link in sorted(new_links):
                    print(f"DEBUG new link: {link}")
                # Notify via Discord and save to DB
                msg = f"**New Listings!** Found {len(new_links)} new links.\n"
                for link in sorted(new_links)[:10]: msg += f"- {link}\n"
                send_discord_message(msg)
                save_new_links_to_db(new_links)
            else:
                print("INFO: No new links found.")
                send_discord_message("Daily check: No new listings found.")
            return {"status": "success", "new_links_count": len(new_links)}
        except Exception as e:
            print(f"ERROR: Scraping failed: {e}")
            send_discord_message(f"🚨 Scraping Error: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            await browser.close()
            print("INFO: Browser closed.")

# --- Flask Routes ---
@app.route('/scrape', methods=['GET'])
async def scrape_endpoint():
    print("INFO: /scrape endpoint triggered.")
    result = await scrape_and_notify_core()
    return jsonify(result)

@app.route('/health', methods=['GET'])
def health_check():
    print("INFO: /health endpoint triggered.")
    return jsonify({"status": "healthy"})

# Initialize DB on startup
initialize_db()

if __name__ == "__main__":
    print("DEBUG_APP: Running local Flask server.")
    app.run(debug=True, host='0.0.0.0', port=5000)
