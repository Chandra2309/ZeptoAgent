# cart.py
# Builds and displays a simulated shopping cart from resolved grocery items.
#
# This is a FAKE cart — it does not open a browser or touch Zepto yet.
# Its job is to confirm the final item list before real automation is added
# in a later block. Every item gets status "simulated" to make that clear.


def build_simulated_cart(resolved_items: list[dict]) -> dict:
    """
    Converts a list of resolved items into a simulated cart structure.

    Each resolved item in:
      {"original_name": "milk", "search_query": "Nandini Toned Milk 500ml",
       "quantity": 2, "source": "memory", "substitute_allowed": True}

    Cart returned:
      {
        "items_added": [{"original_name": ..., "product_name": ...,
                          "quantity": ..., "source": ..., "status": "simulated"}],
        "items_failed": [],
        "mode": "simulated"
      }
    """
    items_added = []

    for r in resolved_items:
        items_added.append({
            "original_name": r["original_name"],
            "product_name":  r["search_query"],
            "quantity":      r["quantity"],
            "source":        r["source"],
            "status":        "simulated",
        })

    return {
        "items_added":  items_added,
        "items_failed": [],          # real failures will be added when Zepto automation lands
        "mode":         "simulated",
    }


def print_real_cart_summary(cart_result: dict) -> None:
    """
    Print a clean summary of the real Zepto cart built by build_zepto_cart().

    cart_result structure:
      {
        "items_added":  [ {original_name, search_query, quantity, source, status, reason} ],
        "items_failed": [ ... ],
        "mode": "zepto"
      }

    Example output:
      Zepto cart result:

      Added:
      1. Nandini Toned Milk 500ml x 2 [memory]
      2. Harvest Gold Brown Bread x 1 [memory]

      Failed:
      1. Penne Pasta x 1 [clarified] — Add button not found
    """
    print("\nZepto cart result:")

    # Added items
    print("\nAdded:")
    added = cart_result.get("items_added", [])
    if added:
        for i, item in enumerate(added, start=1):
            line = f"  {i}. {item['search_query']} x {item['quantity']} [{item['source']}]"
            # If quantity adjustment had a note, show it inline.
            if item.get("reason"):
                line += f"  *{item['reason']}*"
            print(line)
    else:
        print("  None")

    # Failed items
    print("\nFailed:")
    failed = cart_result.get("items_failed", [])
    if failed:
        for i, item in enumerate(failed, start=1):
            print(f"  {i}. {item['search_query']} x {item['quantity']} [{item['source']}] — {item['reason']}")
    else:
        print("  None")

    # Next-step guidance
    print()
    if added:
        print("Review the cart in the browser before checkout.")
    else:
        print("No items were added. Please check Zepto manually or try again.")


def print_captured_cart_summary(captured_cart: dict) -> None:
    """
    Print the cart as it actually appears on Zepto after items were added.

    captured_cart structure (from capture_cart_items):
      {
        "status": "captured" | "empty" | "failed",
        "reason": str | None,
        "items":  [{"name": str, "quantity": int, "price": str}, ...],
        "total":  str,
      }

    Example output:
      Cart on Zepto:
        1. Nandini Toned Milk 500ml  x2  ₹52
        2. Harvest Gold Brown Bread  x1  ₹35
      Total: ₹87
    """
    status = captured_cart.get("status", "failed")

    if status == "failed":
        print(f"\nCould not read cart from Zepto: {captured_cart.get('reason', 'unknown error')}")
        print("Please review the cart in the browser.")
        return

    if status == "empty":
        print("\nCart on Zepto: (empty)")
        return

    print("\nCart on Zepto:")
    items = captured_cart.get("items", [])
    if not items:
        print("  (no items found)")
    else:
        for i, item in enumerate(items, start=1):
            price_part = f"  {item['price']}" if item["price"] else ""
            print(f"  {i}. {item['name']}  x{item['quantity']}{price_part}")

    total = captured_cart.get("total", "")
    if total:
        print(f"  ───────────────────────────")
        print(f"  Total: {total}")


def print_cart_summary(cart: dict) -> None:
    """
    Prints a human-readable summary of the simulated cart.

    Example output:
      Simulated cart:
        1. Nandini Toned Milk 500ml x 2 [memory]
        2. Harvest Gold Brown Bread x 1 [memory]
        3. Penne Pasta x 1 [clarified]

      Failed items:
        None
    """
    print("\nSimulated cart:")

    if not cart["items_added"]:
        print("  (empty)")
    else:
        for i, item in enumerate(cart["items_added"], start=1):
            print(f"  {i}. {item['product_name']} x {item['quantity']} [{item['source']}]")

    print("\nFailed items:")
    if not cart["items_failed"]:
        print("  None")
    else:
        for item in cart["items_failed"]:
            print(f"  - {item}")
