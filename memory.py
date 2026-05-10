import os
import json
import re
from supermemory import Supermemory
from dotenv import load_dotenv

load_dotenv()

RULES_FILE = "user_rules.json"
CONTAINER_TAG = "zepto_preferences"

DEFAULT_RULES = {
    "always_confirm_before_checkout": True,
    "payment_mode": "manual",
    "if_item_unavailable": "ask_user",
    "if_item_ambiguous": "ask_user",
    "max_order_value_without_confirmation": 0,
}

_supermemory_client = None


def _get_supermemory() -> Supermemory:
    global _supermemory_client
    if _supermemory_client is None:
        api_key = os.getenv("SUPERMEMORY_API_KEY")
        if not api_key:
            raise ValueError("SUPERMEMORY_API_KEY not set in environment or .env file")
        _supermemory_client = Supermemory(api_key=api_key)
    return _supermemory_client


def get_preference(item_name: str) -> dict | None:
    """
    Semantic preference lookup via Supermemory.
    Supermemory handles matching (e.g. "whole milk" → "milk" preference).
    Preferences are stored as JSON so the response is parsed directly.
    Returns {"preferred_product": str, "substitute_allowed": bool} or None.
    """
    result = _get_supermemory().profile(
        container_tag=CONTAINER_TAG,
        q=item_name,
    )
    profile_text = getattr(getattr(result, "profile", None), "static", None)
    if not profile_text:
        return None

    match = re.search(r'\{[^{}]+\}', profile_text)
    if not match:
        return None
    return json.loads(match.group())


def set_preference(
    item_name: str,
    preferred_product: str,
    substitute_allowed: bool = True,
) -> None:
    """Store a grocery item preference in Supermemory as JSON."""
    _get_supermemory().add(
        content=json.dumps({
            "item": item_name,
            "preferred_product": preferred_product,
            "substitute_allowed": substitute_allowed,
        }),
        container_tag=CONTAINER_TAG,
    )


def save_preferences_from_cart(cart_result: dict) -> None:
    """Save all successfully added cart items as preferences in Supermemory."""
    added_items = cart_result.get("items_added", [])
    if not added_items:
        print("No successful items to save as preferences.")
        return
    for item in added_items:
        set_preference(item["original_name"], item["search_query"])


def load_memory() -> dict:
    """Load rules from local file. Preferences now live in Supermemory."""
    if not os.path.exists(RULES_FILE):
        return {"rules": DEFAULT_RULES.copy()}
    try:
        with open(RULES_FILE, "r") as f:
            return {"rules": json.load(f)}
    except json.JSONDecodeError:
        print(f"Warning: {RULES_FILE} has invalid JSON. Using default rules.")
        return {"rules": DEFAULT_RULES.copy()}


def save_memory(memory: dict) -> None:
    """Persist rules to local file."""
    with open(RULES_FILE, "w") as f:
        json.dump(memory.get("rules", DEFAULT_RULES), f, indent=2)
