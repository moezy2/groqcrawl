import importlib    
import json
import sys
from pocketgroq import GroqProvider
from typing import List, Dict, Any

# Initialize GroqProvider
groq = GroqProvider()

def check_import(module_name):
    try:
        importlib.import_module(module_name)
        return None
    except ImportError as e:
        return str(e)

# Check for required modules
required_modules = ['pocketgroq', 'groq', 'langchain_groq', 'langchain', 'langchain_community']
import_errors = {module: check_import(module) for module in required_modules}

if any(import_errors.values()):
    raise ImportError(f"Missing required modules: {import_errors}")

# Initialize GroqProvider again (safe re-init if needed)
groq = GroqProvider()

def scrape_url(url: str, formats: List[str] = ["markdown", "html"]) -> Dict[str, Any]:
    """
    Scrape a single URL using PocketGroq's enhanced_web_tool.
    """
    try:
        result = groq.enhanced_web_tool.scrape_page(url, formats)
        return result
    except Exception as e:
        return {"error": str(e)}

def crawl_website(url: str, max_depth: int = 3, max_pages: int = 10, formats: List[str] = ["markdown", "html"]) -> List[Dict[str, Any]]:
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

def map_website(url: str) -> List[str]:
    """
    Map a website using PocketGroq's web_search method.
    """
    try:
        results = groq.web_search(f"site:{url}")
        return [result['url'] for result in results]
    except Exception as e:
        return [f"Error: {str(e)}"]
