import asyncio
from playwright.async_api import async_playwright # Make sure this is playwright.async_api
import os
import re
from urllib.parse import urljoin
import requests
import psycopg2
from flask import Flask, jsonify

print("DEBUG_APP: --- main.py script started execution ---") # NEW PRINT 1

app = Flask(__name__)

print("DEBUG_APP: Flask app object created.") # NEW PRINT 2

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
    print(f"DEBUG_DB: DATABASE_URL value retrieved: {'(set)' if db_url else '(NOT SET)'}") # NEW PRINT 3
    
    if not db_url: # Changed to 'not db_url' for clarity
        print("ERROR: DATABASE_URL environment variable is not set. Cannot connect to database.")
        return None

    print(f"DEBUG_DB: Attempting to connect to DB using URL: {db_url[:20]}...") # NEW PRINT 4 (shows first 20 chars)
    try:
        conn = psycopg2.connect(db_url)
        print("DEBUG_DB: Successfully connected to database.") # NEW PRINT 5
        return conn
    except Exception as e:
        print(f"ERROR: Could not connect to database using DATABASE_URL: {e}") # This message should now be more likely to appear.
        return None

def initialize_db():
    """Creates the 'scraped_links' table if it doesn't exist."""
    print("DEBUG_DB: Calling initialize_db().") # NEW PRINT 6
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
            print("DEBUG_DB: Database table 'scraped_links' ensured to exist.") # This is your old print, but now with DEBUG_DB
        except Exception as e:
            print(f"ERROR: Could not initialize database table: {e}")
        finally:
            conn.close()
            print("DEBUG_DB: Database connection closed after initialization.") # NEW PRINT 7
    else:
        print("ERROR_DB: No database connection available for initialization.") # NEW PRINT 8

# ... rest of your main.py file ...

# --- Application Startup ---
if __name__ == "__main__":
    print("DEBUG_APP: Inside if __name__ == '__main__': block.") # NEW PRINT 9
    # Initialize the database table when the application starts
    # This will run once when Flask starts (e.g., when gunicorn starts the app)
    initialize_db()
    print("DEBUG_APP: initialize_db() call completed.") # NEW PRINT 10
    # For local development, run with Flask's built-in server
    # Comment out or remove this line for Render deployment if gunicorn is used
    # app.run(debug=True, host='0.0.0.0', port=5000)
    # For Render deployment, gunicorn will manage the server.
