import asyncio
from pydoll.browser.chromium import Chrome
import os
import re # Not strictly used after DATABASE_URL change, but can keep for robustness
from urllib.parse import urljoin
import requests
import psycopg2 # For PostgreSQL connectivity
from flask import Flask, jsonify # For the web service

app = Flask(__name__)

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
    if db_url:
        print("DEBUG: Using DATABASE_URL for connection.")
        try:
            return psycopg2.connect(db_url)
        except Exception as e:
            print(f"ERROR: Could not connect to database using DATABASE_URL: {e}")
            return None
    else:
        # Fallback for local testing if DATABASE_URL is not set (e.g., from .env file)
        print("ERROR: DATABASE_URL environment variable is not set. Cannot connect to database.")
        return None

def initialize_db():
    """Creates the 'scraped_links' table if it doesn't exist."""
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
            print("Database table 'scraped_links' ensured to exist.")
        except Exception as e:
            print(f"ERROR: Could not initialize database table: {e}")
        finally:
            conn.close()

def load_extracted_links_from_db():
    """Loads previously extracted links from the database."""
    conn = get_db_connection()
    if not conn:
        return set()

    links = set()
    try:
        cur = conn.cursor()
        cur.execute("SELECT url FROM scraped_links;")
        for row in cur.fetchall():
            links.add(row[0])
        print(f"DEBUG: Successfully loaded {len(links)} links from database.")
    except Exception as e:
        print(f"ERROR: Could not load links from database: {e}")
    finally:
        conn.close()
    return links

def save_new_links_to_db(new_links_set):
    """Saves new extracted links to the database."""
    if not new_links_set:
        return
    
    conn = get_db_connection()
    if not conn:
        return

    try:
        cur = conn.cursor()
        for link in new_links_set:
            try:
                # ON CONFLICT (url) DO NOTHING prevents errors if a link somehow already exists
                cur.execute("INSERT INTO scraped_links (url) VALUES (%s) ON CONFLICT (url) DO NOTHING;", (link,))
            except Exception as e:
                # This log is for unexpected errors, as ON CONFLICT should handle duplicates
                print(f"WARNING: Could not insert link {link} into DB: {e}") 
        conn.commit()
        print(f"DEBUG: Attempted to save {len(new_links_set)} new links to database.")
    except Exception as e:
        print(f"ERROR: Could not save links to database: {e}")
    finally:
        conn.close()

# --- Discord Webhook Function ---
def send_discord_message(message_content):
    """Sends a message to the configured Discord webhook."""
    if not DISCORD_WEBHOOK_URL:
        print("Discord Webhook URL not set as environment variable. Skipping message.")
        return

    payload = {
        "content": message_content
    }
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        print("Discord message sent successfully!")
    except requests.exceptions.RequestException as e:
        print(f"Error sending Discord message: {e}")

# --- Main Scraping Logic (now an async function for Flask) ---
async def scrape_and_notify_core():
    print(f"Starting browser to scrape: {TARGET_URL}")
    
    # Load previously scraped links from DB
    existing_links = load_extracted_links_from_db()
    print(f"Loaded {len(existing_links)} existing links from database.")

    async with Chrome() as browser:
        tab = await browser.start()

        try:
            print("Navigating to the target URL...")
            await tab.go_to(TARGET_URL, timeout=60) 
            print("Page loaded. Waiting for dynamic content (if any)...")
            await asyncio.sleep(10) # Increased sleep duration for robustness

            print("Attempting to find all links with class 'development-card'...")
            # Using the specific CSS selector based on your inspection
            all_links_elements = await tab.query('a.development-card', find_all=True, timeout=30)

            current_scraped_links = set()
            if all_links_elements:
                print(f"Found {len(all_links_elements)} potential 'development-card' links. Filtering and processing...")
                print("DEBUG: HREFs found by selector:") 
                for link_element in all_links_elements:
                    href = link_element.get_attribute('href')
                    if href:
                        print(f"  - {href}")
                        if LINK_SUBSTRING_FILTER in href:
                            absolute_url = urljoin(TARGET_URL, href)
                            current_scraped_links.add(absolute_url)
            else:
                print("No 'development-card' links found on the page with current selectors.")
            
            print(f"DEBUG: Current scraped links count (after filter): {len(current_scraped_links)}")
            print(f"DEBUG: Existing links count: {len(existing_links)}")

            new_links = current_scraped_links - existing_links
            print(f"DEBUG: New links found (current - existing) count: {len(new_links)}")

            if new_links:
                print(f"\n--- Found {len(new_links)} New Links! ---")
                message_content = f"**New London Housing Listings Found!** ({len(new_links)} new links)\n"
                max_links_in_message = 10 # Limit for Discord message length
                for i, link in enumerate(sorted(list(new_links))):
                    if i < max_links_in_message:
                        message_content += f"- {link}\n"
                    else:
                        message_content += f"... and {len(new_links) - max_links_in_message} more.\n"
                        break
                
                send_discord_message(message_content)

                save_new_links_to_db(new_links) # Save only the truly new ones
                print(f"Database updated with {len(new_links)} new links.")
            else:
                print("\nNo new links found since the last check.")
                send_discord_message("Daily London housing check: No new listings found today.")

            return {"status": "success", "new_links_count": len(new_links), "total_scraped": len(current_scraped_links)}

        except Exception as e:
            error_message = f"An error occurred during scraping: {e}"
            print(error_message)
            send_discord_message(f"🚨 **Scraping Error!**\n{error_message}")
            return {"status": "error", "message": error_message}
        finally:
            await tab.close()
            print("Browser tab closed.")

# --- Flask Routes ---
@app.route('/scrape', methods=['GET'])
async def scrape_endpoint():
    """Endpoint to trigger the scraping process."""
    print("Scrape endpoint hit. Initiating scraping process...")
    result = await scrape_and_notify_core()
    return jsonify(result)

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint for GitHub Actions/ping services."""
    return jsonify({"status": "healthy", "message": "Service is running."})

# --- Application Startup ---
if __name__ == "__main__":
    # Initialize the database table when the application starts
    # This will run once when Flask starts (e.g., when gunicorn starts the app)
    initialize_db() 
    # For local development, run with Flask's built-in server
    app.run(debug=True, host='0.0.0.0', port=5000)
    # For Render deployment, gunicorn will manage the server.
