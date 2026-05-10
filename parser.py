# parser.py
# Converts natural language grocery input into a structured list of items.
# Supports optional quantities written as digits before item names.

# Words that are commands or filler — not grocery items.
COMMAND_WORDS = {
    "order", "get", "add", "buy", "please", "can", "you",
    "me", "some", "the", "a", "an", "i", "want", "need"
}


def parse_order(user_text: str) -> list[dict]:
    """
    Takes a natural language string and returns a list of grocery items.

    A digit before an item name is treated as its quantity.
    If no quantity is given, it defaults to 1.

    Examples:
        parse_order("order 2 milk bread 6 eggs")
        → [{"name": "milk", "quantity": 2}, {"name": "bread", "quantity": 1}, {"name": "eggs", "quantity": 6}]

        parse_order("order milk bread eggs")
        → [{"name": "milk", "quantity": 1}, {"name": "bread", "quantity": 1}, {"name": "eggs", "quantity": 1}]
    """
    # Step 1: Normalise separators — treat commas and "and" as plain spaces.
    text = user_text.lower()
    text = text.replace(",", " ")
    text = text.replace(" and ", " ")

    # Step 2: Split into individual words and clean punctuation off each one.
    words = [w.strip(".,!?") for w in text.split()]

    # Step 3: Walk through words one at a time.
    # When we see a number, we remember it as the quantity for the NEXT item word.
    # When we see an item word (not a command), we attach the remembered quantity.
    items = []
    pending_quantity = 1  # default quantity until a number is seen

    for word in words:
        if not word:
            continue

        # Skip command / filler words — they are not grocery items.
        if word in COMMAND_WORDS:
            continue

        if word.isdigit():
            # This is a quantity number — hold it for the next item word.
            pending_quantity = int(word)
        else:
            # This is an item name — pair it with whatever quantity we have.
            items.append({"name": word, "quantity": pending_quantity})
            # Reset to 1 so the next item without a number gets the default.
            pending_quantity = 1

    return items
