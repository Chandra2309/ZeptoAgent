from parser import parse_order
from memory import load_memory, save_preferences_from_cart
from resolver import resolve_items
from cart import build_simulated_cart, print_cart_summary
from zepto_browser import open_zepto, run_full_zepto_flow


def main():
    print("Zepto Grocery Agent started.")
    print("Type 'exit' or 'quit' to stop.\n")

    while True:
        user_input = input("What do you want to order? ").strip()

        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        if not user_input:
            print("Please enter something.\n")
            continue

        items = parse_order(user_input)

        if not items:
            print("No grocery items found. Please try again.\n")
            continue

        # Show what the parser found.
        print("\nParsed items:")
        for i, item in enumerate(items, start=1):
            print(f"  {i}. {item['name']} x {item['quantity']}")

        # Resolve each item — may ask clarification questions for ambiguous items.
        memory = load_memory()
        resolved = resolve_items(items, memory)

        # Show the final resolved list with source tag.
        print("\nResolved items:")
        for i, r in enumerate(resolved, start=1):
            print(f"  {i}. {r['original_name']} -> {r['search_query']} x {r['quantity']} [{r['source']}]")

        if not resolved:
            print("\nNo items to add to cart.")
            print()
            continue

        # Show a simulated cart preview before touching Zepto.
        cart = build_simulated_cart(resolved)
        print_cart_summary(cart)

        # Ask the user whether to run the full Zepto flow.
        confirm = input("\nRun full Zepto flow (add → review → checkout → place order)? yes/no: ").strip().lower()
        if confirm == "yes":
            print("\nStarting Zepto flow...")
            result = run_full_zepto_flow(resolved)

            # Report outcome.
            print()
            added_count  = len(result.get("items_added",  []))
            failed_count = len(result.get("items_failed", []))
            order_status = result.get("order_status", "unknown")

            print(f"Items added:  {added_count}")
            if failed_count:
                print(f"Items failed: {failed_count}")
                for it in result["items_failed"]:
                    print(f"  - {it['search_query']}: {it['reason']}")

            if order_status == "placed":
                print("Order status: placed — check the Zepto app for confirmation.")
            elif order_status == "cancelled":
                print("Order status: cancelled by user.")
            elif order_status == "failed":
                print("Order status: something went wrong — check the browser.")
            else:
                print(f"Order status: {order_status}")

            # Offer to save preferences for successfully added items.
            if result.get("items_added"):
                remember = input("\nRemember successfully added items for next time? yes/no: ").strip().lower()
                if remember == "yes":
                    save_preferences_from_cart(result)
                    print("Preferences saved.")
                else:
                    print("Preferences not updated.")
        else:
            print("Okay, flow cancelled.")

        print()


if __name__ == "__main__":
    main()
