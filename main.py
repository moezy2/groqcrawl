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
TARGET_URL = "https://www.london.gov.uk/programmes-strategies/housing-and-land/homes-londoners/search/to-rent/property?location=Barfield+Avenue%2C+London+N20%200DE&search-area=15&minimum-bedrooms=2&min-monthly-rent=none&max-monthly-rent=none&lat=51.6267984&lng=-0.1587195&outside=0&show-advanced-form=0"
LINK_SUBSTRING_FILTER = "/programmes-strategies/housing-and-land/homes-londoners/search/property/"

# Environment variable for Discord Webhook. Render will provide this.
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# --- Database Functions ---
def get_db_connection():
    """Establishes and returns a PostgreSQL database connection.
    Prioritizes DATABASE_URL (from Render's internal connection or external string).
    """
    db_url = os.getenv("DATABASE_URL")
    print(f"DEBUG_DB: DATABASE_URL value retrieved: {'(set)' if db_url else '(NOT SET)'}")
    
    if not db_url:
        print("ERROR: DATABASE_URL environment variable is not set. Cannot connect to database.")
        return None

    # Redact sensitive parts for logging but confirm URL format
    logged_db_url = re.sub(r'(://[^:]+):[^@]+@', r'\1:********@', db_url)
    print(f"DEBUG_DB: Attempting to connect to DB using URL: {logged_db_url}")
    try:
        conn = psycopg2.connect(db_url)
        print("DEBUG_DB: Successfully connected to database.")
        return conn
    except Exception as e:
        print(f"ERROR: Could not connect to database using DATABASE_URL: {e}")
        return None

def initialize_db():
    """Creates the 'scraped_links' table if it doesn't exist."""
    print("DEBUG_DB: Calling initialize_db().")
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scraped_links (
                    id SERIAL PRIMARY KEY,
                    url TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            print("DEBUG_DB: Database table 'scraped_links' ensured to exist.")
        except Exception as e:
            print(f"ERROR: Could not initialize database table: {e}")
        finally:
            conn.close()
            print("DEBUG_DB: Database connection closed after initialization.")
    else:
        print("ERROR_DB: No database connection available for initialization.")

def load_extracted_links_from_db():
    """Loads previously extracted links from the database."""
    conn = get_db_connection()
    if not conn:
        print("ERROR_DB: No database connection available to load links.")
        return set()

    links = set()
    try:
        cur = conn.cursor()
        cur.execute("SELECT url FROM scraped_links;")
        for row in cur.fetchall():
            links.add(row[0])
        print(f"DEBUG_DB: Successfully loaded {len(links)} links from database.")
    except Exception as e:
        print(f"ERROR_DB: Could not load links from database: {e}")
    finally:
        conn.close()
        print("DEBUG_DB: Database connection closed after loading links.")
    return links

def save_new_links_to_db(new_links_set):
    """Saves new extracted links to the database."""
    if not new_links_set:
        print("DEBUG_DB: No new links to save to database.")
        return
    
    conn = get_db_connection()
    if not conn:
        print("ERROR_DB: No database connection available to save links.")
        return

    try:
        cur = conn.cursor()
        for link in new_links_set:
            try:
                cur.execute("INSERT INTO scraped_links (url) VALUES (%s) ON CONFLICT (url) DO NOTHING;", (link,))
            except Exception as e:
                # Log a warning but don't stop the loop for other links
                print(f"WARNING_DB: Could not insert link {link} into DB: {e}")
        conn.commit()
        print(f"DEBUG_DB: Attempted to save {len(new_links_set)} new links to database.")
    except Exception as e:
        print(f"ERROR_DB: Could not save links to database: {e}")
    finally:
        conn.close()
        print("DEBUG_DB: Database connection closed after saving links.")

# --- Discord Webhook Function ---
def send_discord_message(message_content):
    """Sends a message to the configured Discord webhook."""
    if not DISCORD_WEBHOOK_URL:
        print("WARNING: Discord Webhook URL not set as environment variable. Skipping message.")
        return

    payload = {
        "content": message_content
    }
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        print("INFO: Discord message sent successfully!")
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Error sending Discord message: {e}")

# --- Main Scraping Logic (using Playwright) ---
async def scrape_and_notify_core():
    print(f"INFO: Starting browser to scrape: {TARGET_URL}")
    
    existing_links = load_extracted_links_from_db()
    print(f"INFO: Loaded {len(existing_links)} existing links from database.")

    async with async_playwright() as p:
        browser = None # Initialize browser to None
        try:
            print("INFO: Launching Chromium browser...")
            # Use headless=True for production deployment
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            print("INFO: Navigating to the target URL...")
            await page.goto(TARGET_URL, timeout=60000) # 60 seconds timeout
            print("INFO: Page loaded. Waiting for dynamic content (if any)...")
            await asyncio.sleep(8) # Adjusted sleep duration for robustness (was 5)

            # Added a print to show the current URL after navigation and sleep, for debugging
            print(f"DEBUG: Current page URL after navigation and sleep: {page.url}")
            
            # Added a print to get the page's HTML content, to inspect if elements are loaded
            page_content = await page.content()
            print(f"DEBUG: Page content snippet (first 500 chars): {page_content[:500]}...")


            print("INFO: Attempting to find all links with class 'development-card'...")
            link_elements = await page.locator('a.development-card').all()
            print(f"DEBUG: Number of raw 'development-card' link elements found: {len(link_elements)}")


            current_scraped_links = set()
            if link_elements:
                print(f"INFO: Found {len(link_elements)} potential 'development-card' links. Filtering and processing...")
                for i, element in enumerate(link_elements):
                    href = await element.get_attribute('href')
                    if href:
                        absolute_url = urljoin(TARGET_URL, href)
                        
                        if LINK_SUBSTRING_FILTER in absolute_url:
                            current_scraped_links.add(absolute_url)
                            # Only print processed links for brevity
                            # print(f"DEBUG: Processed link {i+1}: {absolute_url}") 
                        else:
                            # print(f"DEBUG: Skipped link {i+1} (filter mismatch): {absolute_url}")
                            pass # Skip printing for mismatch, reduce log verbosity unless deep debug is needed
                    else:
                        print(f"DEBUG: Link element {i+1} had no href attribute.")
            else:
                print("INFO: No 'development-card' links found on the page with current selectors.")
            
            print(f"INFO: Total current scraped links after filtering: {len(current_scraped_links)}")

            new_links = current_scraped_links - existing_links
            print(f"INFO: Found {len(new_links)} new unique links.")
            # Print the actual new links for debugging
            if new_links:
                print("DEBUG: New links identified:")
                for link in sorted(list(new_links)):
                    print(f"- {link}")


            if new_links:
                print(f"\n--- Found {len(new_links)} New Links! ---")
                message_content = f"**New London Housing Listings Found!** ({len(new_links)} new links)\n"
                max_links_in_message = 10 
                for i, link in enumerate(sorted(list(new_links))):
                    if i < max_links_in_message:
                        message_content += f"- {link}\n"
                    else:
                        message_content += f"... and {len(new_links) - max_links_in_message} more.\n"
                        break
                
                send_discord_message(message_content)
                save_new_links_to_db(new_links)
                print(f"INFO: Database updated with {len(new_links)} new links.")
            else:
                print("\nINFO: No new links found since the last check.")
                send_discord_message("Daily London housing check: No new listings found today.")

            return {"status": "success", "new_links_count": len(new_links), "total_scraped": len(current_scraped_links)}

        except Exception as e:
            error_message = f"An error occurred during scraping: {e}"
            print(f"ERROR: {error_message}")
            send_discord_message(f"🚨 **Scraping Error!**\n{error_message}")
            return {"status": "error", "message": error_message}
        finally:
            if browser:
                await browser.close()
                print("INFO: Browser closed.")

# --- Flask Routes ---
@app.route('/scrape', methods=['GET'])
async def scrape_endpoint():
    """Endpoint to trigger the scraping process."""
    print("INFO: Scrape endpoint hit. Initiating scraping process...") # Corrected print
    result = await scrape_and_notify_core()
    return jsonify(result)

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint for GitHub Actions/ping services."""
    print("INFO: Health check endpoint hit.") # Clarified print
    return jsonify({"status": "healthy", "message": "Service is running."})

# --- Application Startup ---
# Initialize the database table when the application starts.
initialize_db()

# This block is ONLY for local development. Gunicorn handles server startup on Render.
if __name__ == "__main__":
    print("DEBUG_APP: Inside if __name__ == '__main__': block (for local development only).")
    app.run(debug=True, host='0.0.0.0', port=5000)
