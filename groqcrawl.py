from typing import List, Dict, Any
from pocketgroq import GroqProvider

# Initialize GroqProvider
groq = GroqProvider()

def scrape_url(url: str, formats: List[str] = ["markdown", "html"], headers: Dict[str, str] = None) -> Dict[str, Any]:
    """
    Scrape a single URL using PocketGroq's enhanced_web_tool.
    Note: 'headers' not currently supported in scrape_page().
    """
    try:
        result = groq.enhanced_web_tool.scrape_page(url, formats)
        return result
    except Exception as e:
        return {"error": str(e)}

def crawl_website(url: str, max_depth: int, max_pages: int, formats: List[str] = ["markdown", "html"], headers: Dict[str, str] = None) -> List[Dict[str, Any]]:
    """
    Crawl a website using PocketGroq's enhanced_web_tool.
    """
    try:
        groq.enhanced_web_tool.max_depth = max_depth
        groq.enhanced_web_tool.max_pages = max_pages
        results = groq.enhanced_web_tool.crawl(url, formats)
        return results
    except Exception as e:
        return [{"error": str(e)}]

def map_website(url: str, headers: Dict[str, str] = None) -> List[str]:
    """
    Map a website using PocketGroq's web_search method.
    """
    try:
        results = groq.web_search(f"site:{url}")
        return [result['url'] for result in results]
    except Exception as e:
        return [f"Error: {str(e)}"]
