import os
import time
import json
import requests
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

ANAKIN_API_KEY = os.getenv("ANAKIN_API_KEY")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")

ANAKIN_BASE    = "https://api.anakin.io/v1"
POLL_INTERVAL  = 3   # seconds between polls
MAX_POLLS      = 20  # give up after this many attempts

# ── Hardcoded test values ────────────────────────────────────────────────────

TEST_ITEM       = "milk"
TEST_SEARCH_URL = "https://www.zepto.com/search?query=milk"

# ── Anakin helpers ───────────────────────────────────────────────────────────

def _scrape_url(url: str) -> str | None:
    """
    Submit a URL to Anakin scraper and poll until completed.
    Returns the markdown content of the page, or None on failure.
    Zepto is JS-heavy so useBrowser is set to True.
    """
    headers = {
        "X-API-Key":    ANAKIN_API_KEY,
        "Content-Type": "application/json",
    }

    # Step 1: Submit scrape job
    print(f"[anakin] Submitting scrape job for: {url}")
    response = requests.post(
        f"{ANAKIN_BASE}/url-scraper",
        headers=headers,
        json={"url": url, "useBrowser": True, "country": "in"},
    )
    response.raise_for_status()
    job_id = response.json()["jobId"]
    print(f"[anakin] Job ID: {job_id}")

    # Step 2: Poll until completed
    for attempt in range(1, MAX_POLLS + 1):
        time.sleep(POLL_INTERVAL)
        result = requests.get(f"{ANAKIN_BASE}/url-scraper/{job_id}", headers=headers)
        result.raise_for_status()
        data = result.json()
        status = data.get("status")
        print(f"[anakin] Poll {attempt}/{MAX_POLLS} — status: {status}")

        if status == "completed":
            print(f"[anakin] Full response: {json.dumps(data, indent=2)}")
            results = data.get("results", [])
            if not results:
                print("[anakin] No results in response.")
                return None
            return results[0].get("markdown", "")

        if status == "failed":
            print("[anakin] Scrape job failed.")
            return None

    print("[anakin] Timed out waiting for scrape job.")
    return None


# ── Groq: pick best product from scraped content ─────────────────────────────

def _pick_best_product(item: str, page_markdown: str) -> str | None:
    """
    Feed scraped Zepto search results to Groq and ask it to pick the best product.
    Returns the product name string, or None if nothing useful is found.
    """
    client = Groq(api_key=GROQ_API_KEY)

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a grocery shopping assistant. Given scraped content from a "
                    "Zepto search results page, identify the best product for the user's "
                    "item. Consider relevance, popularity, and value. "
                    "Reply with ONLY the exact product name as it appears on the page. "
                    "No explanation."
                ),
            },
            {
                "role": "user",
                "content": f"Item I want: {item}\n\nZepto search results:\n{page_markdown[:4000]}",
            },
        ],
        temperature=0,
        max_tokens=100,
    )

    return response.choices[0].message.content.strip()


# ── Main test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"=== Anakin scraper test: '{TEST_ITEM}' ===\n")

    markdown = _scrape_url(TEST_SEARCH_URL)

    if not markdown:
        print("No content returned from Anakin. Exiting.")
        exit(1)

    print(f"\n[scraped] Got {len(markdown)} characters of content.")
    print("\n--- Raw markdown preview (first 500 chars) ---")
    print(markdown[:500])
    print("----------------------------------------------\n")

    best = _pick_best_product(TEST_ITEM, markdown)
    print(f"[groq] Best product for '{TEST_ITEM}': {best}")
