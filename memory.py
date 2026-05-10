# memory.py
# Loads and saves user grocery preferences from user_memory.json.

import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

MEMORY_FILE = "user_memory.json"

_groq_client = None
_semantic_cache: dict[str, str | None] = {}  # query → matched key, lives for the session


def _get_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in environment or .env file")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


def _semantic_match(query: str, keys: list[str]) -> str | None:
    """
    Ask the LLM which key from `keys` best matches `query`.
    Returns the matched key, or None if nothing is a reasonable match.
    Skips the API call if the result is already cached for this session.
    """
    if not keys:
        return None

    cache_key = f"{query}|{','.join(sorted(keys))}"
    if cache_key in _semantic_cache:
        return _semantic_cache[cache_key]

    prompt = (
        f"From this list of grocery item names: {keys}\n"
        f"Which one best matches the query: \"{query}\"?\n"
        "Reply with ONLY the exact matching name from the list, or reply \"none\" "
        "if nothing is a reasonable match. No explanation."
    )

    response = _get_client().chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=20,
    )

    result = response.choices[0].message.content.strip().lower()
    matched = result if result in keys else None
    _semantic_cache[cache_key] = matched
    return matched

# This is what an empty memory looks like when the file is missing or broken.
DEFAULT_MEMORY = {
    "preferences": {},
    "rules": {
        "always_confirm_before_checkout": True,
        "payment_mode": "manual",
        "if_item_unavailable": "ask_user",
        "if_item_ambiguous": "ask_user",
        "max_order_value_without_confirmation": 0,
    },
}


def load_memory() -> dict:
    """
    Read user_memory.json and return its contents as a dict.
    - If the file does not exist, return default memory.
    - If the file has broken JSON, warn the user and return default memory.
    """
    if not os.path.exists(MEMORY_FILE):
        return DEFAULT_MEMORY.copy()

    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Warning: {MEMORY_FILE} has invalid JSON. Using default memory.")
        return DEFAULT_MEMORY.copy()


def save_memory(memory: dict) -> None:
    """
    Write the memory dict back to user_memory.json with readable indentation.
    """
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)


def get_preference(item_name: str) -> dict | None:
    """
    Look up a saved preference for an item (case-insensitive).
    First tries an exact key match, then falls back to a semantic LLM match.
    Returns the preference dict if found, or None if nothing matches.

    Example:
        get_preference("whole milk")  # memory has "milk"
        → {"preferred_product": "Nandini Toned Milk 500ml", "substitute_allowed": true}
    """
    memory = load_memory()
    preferences = memory.get("preferences", {})
    query = item_name.lower()

    if query in preferences:
        return preferences[query]

    matched_key = _semantic_match(query, list(preferences.keys()))
    if matched_key:
        return preferences[matched_key]

    return None


def set_preference(
    item_name: str,
    preferred_product: str,
    substitute_allowed: bool = True,
) -> None:
    """
    Add or update the saved preference for an item, then save to disk.

    Example:
        set_preference("butter", "Amul Butter 500g")
    """
    memory = load_memory()

    memory["preferences"][item_name.lower()] = {
        "preferred_product": preferred_product,
        "substitute_allowed": substitute_allowed,
    }

    save_memory(memory)


def save_preferences_from_cart(cart_result: dict) -> None:
    """
    After a successful Zepto cart build, save the added items as preferences
    so future orders can use the same products automatically.

    Only items with status "added" are saved — failed items are ignored.
    If an item already exists in memory, it is updated with the latest choice.

    Example cart item that gets saved:
        {"original_name": "pasta", "search_query": "Penne Pasta",
         "source": "clarified", "status": "added"}

    Saved as:
        "pasta": {"preferred_product": "Penne Pasta", "substitute_allowed": true}
    """
    added_items = cart_result.get("items_added", [])

    if not added_items:
        print("No successful items to save as preferences.")
        return

    # Load once, update all items in memory, then save once.
    # This is faster and avoids writing the file multiple times.
    memory = load_memory()

    for item in added_items:
        key = item["original_name"].lower()
        memory["preferences"][key] = {
            "preferred_product": item["search_query"],
            "substitute_allowed": True,
        }

    save_memory(memory)
