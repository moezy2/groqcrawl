import asyncio
from pydoll.browser.chromium import Chrome
import os
from urllib.parse import urljoin
import requests # For sending Discord webhooks

# --- Configuration ---
TARGET_URL = "https://www.london.gov.uk/programmes-strategies/housing-and-land/homes-londoners/search/to-rent/property?location=Barfield+Avenue%2C+London+N20%200DE&search-area=15&minimum-bedrooms=2&min-monthly-rent=none&max-monthly-rent=none&lat=51.6267984&lng=-0.1587195&outside=0&show-advanced-form=0"
LINK_SUBSTRING_FILTER = "/programmes-strategies/housing-and-land/homes-londoners/search/property/"
# IMPORTANT FOR RENDER: Use an environment variable for the webhook URL
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL") 
# For Render, use a path that will be mounted as a persistent disk (e.g., /var/data/)
DATABASE_FILE = "/var/data/scraped_links.txt" 

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

# --- Link Database Functions ---
def load_extracted_links(filepath):
    """Loads previously extracted links from a file."""
    if not os.path.exists(filepath):
        print(f"DEBUG: '{filepath}' does not exist. Starting with empty set.")
        return set()
    try:
        with open(filepath, 'r') as f:
            links = {line.strip() for line in f if line.strip()}
            print(f"DEBUG: Successfully loaded {len(links)} links from '{filepath}'.")
            return links
    except Exception as e:
        print(f"ERROR: Could not load links from '{filepath}': {e}")
        return set() # Return empty set if loading fails

def save_extracted_links(filepath, links_set):
    """Saves the current set of extracted links to a file."""
    # Ensure the directory for the file exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    try:
        with open(filepath, 'w') as f:
            for link in sorted(list(links_set)): # Sort for consistent file output
                f.write(link + '\n')
        print(f"DEBUG: Successfully saved {len(links_set)} links to '{filepath}'.")
    except Exception as e:
        print(f"ERROR: Could not save links to '{filepath}': {e}")

# --- Main Scraping Logic ---
async def scrape_and_notify():
    print(f"Starting browser to scrape: {TARGET_URL}")
    
    # Load previously scraped links
    existing_links = load_extracted_links(DATABASE_FILE)
    print(f"Loaded {len(existing_links)} existing links from {DATABASE_FILE}")

    async with Chrome() as browser:
        tab = await browser.start()

        try:
            print("Navigating to the target URL...")
            await tab.go_to(TARGET_URL, timeout=60) 
            print("Page loaded. Waiting for dynamic content (if any)...")
            await asyncio.sleep(10) # Keep increased sleep duration for robustness

            print("Attempting to find all links with class 'development-card'...")
            all_links_elements = await tab.query('a.development-card', find_all=True, timeout=30)

            current_scraped_links = set()
            if all_links_elements:
                print(f"Found {len(all_links_elements)} potential 'development-card' links. Filtering and processing...")
                print("DEBUG: HREFs found:") 
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
                max_links_in_message = 10 
                for i, link in enumerate(sorted(list(new_links))):
                    if i < max_links_in_message:
                        message_content += f"- {link}\n"
                    else:
                        message_content += f"... and {len(new_links) - max_links_in_message} more.\n"
                        break
                
                send_discord_message(message_content)

                updated_links_set = existing_links.union(current_scraped_links) 
                save_extracted_links(DATABASE_FILE, updated_links_set)
                print(f"Database updated with {len(new_links)} new links. Total links: {len(updated_links_set)}")
            else:
                print("\nNo new links found since the last check.")
                send_discord_message("Daily London housing check: No new listings found today.")

        except Exception as e:
            error_message = f"An error occurred during scraping: {e}"
            print(error_message)
            send_discord_message(f"🚨 **Scraping Error!**\n{error_message}")
        finally:
            await tab.close()
            print("Browser tab closed.")

if __name__ == "__main__":
    asyncio.run(scrape_and_notify())
