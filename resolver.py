# resolver.py
# Converts parsed grocery items into exact search queries using saved memory preferences.
# For items with no memory and multiple possible products, asks the user to clarify.

from memory import get_preference, set_preference

# Items that could mean many different products.
# If a user asks for one of these and has no saved preference, we ask which one they want.
AMBIGUOUS_OPTIONS = {
    "chips": [
        "Lays Magic Masala",
        "Kurkure Masala Munch",
        "Bingo Mad Angles",
    ],
    "pasta": [
        "Penne Pasta",
        "Macaroni Pasta",
        "Spaghetti",
    ],
    "milk": [
        "Nandini Toned Milk 500ml",
        "Amul Taaza 500ml",
        "Akshayakalpa Toned Milk 500ml",
    ],
    "bread": [
        "Harvest Gold Brown Bread",
        "White Bread",
        "Multigrain Bread",
    ],
    "curd": [
        "Nandini Curd 500g",
        "Akshayakalpa Curd 500g",
        "Milky Mist Curd 400g",
    ],
    "rice": [
        "India Gate Basmati Rice",
        "Daawat Basmati Rice",
        "Sona Masoori Rice",
    ],
    "atta": [
        "Aashirvaad Atta 5kg",
        "Fortune Chakki Fresh Atta 5kg",
        "Pillsbury Atta 5kg",
    ],
    "oil": [
        "Fortune Sunflower Oil 1L",
        "Saffola Gold Oil 1L",
        "Dhara Refined Oil 1L",
    ],
}


def _ask_clarification(item_name: str, user_quantity: int) -> dict:
    """
    Ask the user to pick one product from the ambiguous options list.
    Returns a fully resolved item dict.

    Called only when:
      - the item has no saved memory preference
      - the item name is in AMBIGUOUS_OPTIONS
    """
    options = AMBIGUOUS_OPTIONS[item_name]

    print(f"\n  Which {item_name} should I choose?")
    for i, option in enumerate(options, start=1):
        print(f"    {i}. {option}")

    choice = input("  Type choice number: ").strip()

    # Check if the user typed a valid number within the options range.
    if choice.isdigit() and 1 <= int(choice) <= len(options):
        selected = options[int(choice) - 1]

        # Ask if the user wants this remembered for future orders.
        remember = input(f"  Should I remember this as your usual {item_name}? yes/no: ").strip().lower()
        if remember == "yes":
            set_preference(item_name, selected, substitute_allowed=True)
            print(f"  Saved! {item_name} -> {selected}")

        return {
            "original_name": item_name,
            "search_query": selected,
            "quantity": user_quantity,
            "source": "clarified",
            "substitute_allowed": True,
        }
    else:
        # Invalid input — fall back to searching the raw item name.
        print(f"  Invalid choice. I will search for {item_name} directly.")
        return {
            "original_name": item_name,
            "search_query": item_name,
            "quantity": user_quantity,
            "source": "user_text",
            "substitute_allowed": True,
        }


def resolve_items(parsed_items: list[dict], memory: dict) -> list[dict]:
    """
    Takes parsed items and user memory, returns a resolved list ready for Zepto search.

    Each input item looks like:  {"name": "milk", "quantity": 1}
    Each output item looks like:
      {
        "original_name":     "milk",
        "search_query":      "Nandini Toned Milk 500ml",
        "quantity":          2,
        "source":            "memory" | "clarified" | "user_text",
        "substitute_allowed": True,
      }

    Rules applied in order:
      A. Item found in memory         → use preferred_product, quantity from user input, source="memory"
      B. No memory + ambiguous item   → ask clarification, source="clarified"
      C. No memory + not ambiguous    → use item name as query, source="user_text"
    """
    resolved = []

    for item in parsed_items:
        name = item["name"].lower()
        user_quantity = item["quantity"]
        pref = get_preference(name)

        if pref:
            # Rule A: saved preference exists — use it directly, no question asked.
            # Rule B: always use the quantity the user typed in the current order.
            quantity = user_quantity
            substitute_allowed = pref.get("substitute_allowed", True)

            resolved.append({
                "original_name": name,
                "search_query": pref["preferred_product"],
                "quantity": quantity,
                "source": "memory",
                "substitute_allowed": substitute_allowed,
            })

        elif name in AMBIGUOUS_OPTIONS:
            # Rule C: no memory but item is ambiguous — ask the user to pick.
            resolved.append(_ask_clarification(name, user_quantity))

        else:
            # Rule D: no memory, not ambiguous — search the raw item name.
            resolved.append({
                "original_name": name,
                "search_query": name,
                "quantity": user_quantity,
                "source": "user_text",
                "substitute_allowed": True,
            })

    return resolved
