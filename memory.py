# memory.py
# Loads and saves user grocery preferences from user_memory.json.

import json
import os

MEMORY_FILE = "user_memory.json"

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
    Returns the preference dict if found, or None if not saved.

    Example:
        get_preference("milk")
        → {"preferred_product": "Nandini Toned Milk 500ml", "quantity": 2, ...}
    """
    memory = load_memory()
    preferences = memory.get("preferences", {})
    return preferences.get(item_name.lower())


def set_preference(
    item_name: str,
    preferred_product: str,
    quantity: int = 1,
    substitute_allowed: bool = True,
) -> None:
    """
    Add or update the saved preference for an item, then save to disk.

    Example:
        set_preference("butter", "Amul Butter 500g", quantity=1)
    """
    memory = load_memory()

    memory["preferences"][item_name.lower()] = {
        "preferred_product": preferred_product,
        "quantity": quantity,
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
         "quantity": 1, "source": "clarified", "status": "added"}

    Saved as:
        "pasta": {"preferred_product": "Penne Pasta",
                  "quantity": 1, "substitute_allowed": true}
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
            "quantity":          item["quantity"],
            "substitute_allowed": True,
        }

    save_memory(memory)
