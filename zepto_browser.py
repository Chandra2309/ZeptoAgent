# zepto_browser.py
# Controls the Zepto website using Playwright.
# Full flow: add items → capture cart → terminal review → COD checkout → place order.
#
# SAFETY BOUNDARY: The final "Place Order" step always requires explicit terminal
# confirmation ("yes") from the user.  No payment automation beyond COD selection.

import os
import re
from config import ZEPTO_URL, HEADLESS, BROWSER_DATA_DIR

# ── Selector lists ───────────────────────────────────────────────────────────
# Each list is tried top-to-bottom; the first match wins.
# This makes the code resilient to Zepto changing its HTML between versions.


ADD_BUTTON_SELECTORS = [
    'button:has-text("Add")',
    'button:has-text("ADD")',
    '[data-testid*="add"]',
    '[aria-label*="Add to cart"]',
]

PLUS_BUTTON_SELECTORS = [
    'button:has-text("+")',
    '[aria-label*="increment"]',
    '[aria-label*="increase"]',
    '[aria-label*="Increase"]',
]

# Direct search page — more reliable than trying to find the homepage search box.
ZEPTO_SEARCH_URL = "https://www.zepto.com/search"

# Zepto cart page URL.
ZEPTO_CART_URL = "https://www.zepto.com/cart?cart=open"

# Selectors for the cart / checkout button that appears after adding items.
CHECKOUT_SELECTORS = [
    'button:has-text("Cart")',
    'text=Cart',
    'button:has-text("View Cart")',
    'text=View Cart',
    'button:has-text("Checkout")',
    'text=Checkout',
    'button:has-text("Proceed")',
    'text=Proceed',
]

# Selectors to find the Cash on Delivery payment option.
COD_SELECTORS = [
    'text=Cash on Delivery',
    'label:has-text("Cash on Delivery")',
    '[data-testid*="cod"]',
    '[data-testid*="cash"]',
    'input[value*="cod"]',
    'input[value*="CASH"]',
    'div:has-text("Cash on Delivery") >> input',
]

# Selectors for the final "Place Order" / "Confirm Order" button.
FINAL_ORDER_SELECTORS = [
    'button:has-text("Place Order")',
    'button:has-text("Confirm Order")',
    'button:has-text("Pay")',
    'button:has-text("Proceed to Pay")',
    '[data-testid*="place-order"]',
    '[data-testid*="confirm-order"]',
]

# Words that indicate a payment/OTP/UPI button — never click these automatically.
FORBIDDEN_PAYMENT_WORDS = {
    "upi", "card", "wallet", "netbanking", "emi", "otp",
    "pin", "cvv", "pay now", "payment",
}


# ── Low-level page helpers ───────────────────────────────────────────────────
# These work on an already-open Playwright page.
# They do NOT open or close the browser — that is the caller's job.

def _open_context(playwright):
    """
    Create or reuse the persistent Chromium context.
    Returns (context, page).  Shared by all public functions.
    """
    os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
    context = playwright.chromium.launch_persistent_context(
        user_data_dir=BROWSER_DATA_DIR,
        headless=HEADLESS,
    )
    page = context.pages[0] if context.pages else context.new_page()
    return context, page



def search_product_on_page(page, search_query: str) -> bool:
    """
    Navigate directly to ZEPTO_SEARCH_URL and search for a product.
    Returns True if the search action completes, False on total failure.

    Strategy:
      1. Open zepto.com/search — the search input is always present here,
         so we avoid the unreliable homepage search-box detection.
      2. Try CSS/placeholder locators to find the <input>.
      3. If no locator works, click the known screen coordinate (720, 170)
         where the search bar sits on the /search page.
      4. Clear the field and type the query, then press Enter.
      5. Save a screenshot after search for debugging.
    """
    try:
        print("  Opening Zepto search page...")
        page.goto(ZEPTO_SEARCH_URL)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(5000)   # let Zepto's JS fully render the search input

        print(f"  Searching for: {search_query}")

        # ── Strategy 1: locator-based input detection ─────────────────────────
        input_field = None
        candidates = [
            page.locator("input").first,
            page.locator("input[placeholder*='Search']").first,
            page.locator("input[placeholder*='search']").first,
            page.get_by_placeholder(re.compile("search", re.I)).first,
        ]
        for candidate in candidates:
            try:
                candidate.wait_for(state="visible", timeout=2000)
                input_field = candidate
                break
            except Exception:
                continue

        if input_field:
            # Clear any existing text, then fill the query.
            input_field.click()
            page.keyboard.press("Meta+a")      # Cmd+A on Mac
            page.keyboard.press("Backspace")
            page.keyboard.press("Control+a")   # Ctrl+A as fallback
            page.keyboard.press("Backspace")
            try:
                input_field.fill(search_query)
            except Exception:
                page.keyboard.type(search_query, delay=50)
        else:
            # ── Strategy 2: coordinate fallback ──────────────────────────────
            # Click the approximate position of the search bar on /search page.
            page.mouse.click(720, 170)
            page.wait_for_timeout(1000)
            page.keyboard.press("Meta+a")
            page.keyboard.press("Backspace")
            page.keyboard.type(search_query, delay=50)

        page.keyboard.press("Enter")
        page.wait_for_timeout(4000)   # wait for search results to load
        print("  Search submitted.")

        page.screenshot(path="debug_after_search.png")
        return True

    except Exception as e:
        page.screenshot(path="debug_search_failed.png")
        print(f"  Search failed on Zepto search page. Screenshot saved as debug_search_failed.png")
        print(f"  Details: {e}")
        return False


def click_first_add_button(page):
    """
    Try each selector in ADD_BUTTON_SELECTORS and click the first visible Add
    button.  Returns True on success, False if no button is found.
    """
    for selector in ADD_BUTTON_SELECTORS:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=4000)
            locator.click()
            return True
        except Exception:
            continue
    return False


def adjust_quantity(page, quantity: int) -> bool:
    """
    Click the "+" button (quantity - 1) times to reach the desired quantity.
    The first click of 'Add' already sets the count to 1, so we only need
    (quantity - 1) additional clicks.

    Returns True if all clicks succeeded, False if the plus button was not found.
    """
    if quantity <= 1:
        return True   # nothing to do

    extra_clicks = quantity - 1
    for selector in PLUS_BUTTON_SELECTORS:
        try:
            plus = page.locator(selector).first
            plus.wait_for(state="visible", timeout=3000)
            for _ in range(extra_clicks):
                plus.click()
                page.wait_for_timeout(500)   # let Zepto register each click
            return True
        except Exception:
            continue
    return False


def _add_product_on_page(page, item: dict) -> dict:
    """
    On an already-open page, add one product to the Zepto cart.

    item dict must have:  original_name, search_query, quantity, source

    Returns a result dict:
      status "added"  — product was added (reason may note quantity issue)
      status "failed" — search box or Add button was not found
    """
    search_query  = item["search_query"]
    quantity      = item["quantity"]
    original_name = item.get("original_name", search_query)
    source        = item.get("source", "user_text")

    def _fail(reason: str) -> dict:
        return {
            "original_name": original_name,
            "search_query":  search_query,
            "quantity":      quantity,
            "source":        source,
            "status":        "failed",
            "reason":        reason,
        }

    # Search
    print(f"  Searching for: {search_query}")
    if not search_product_on_page(page, search_query):
        return _fail("Search box not found")

    # Add
    print(f"  Looking for Add button...")
    if not click_first_add_button(page):
        return _fail("Add button not found")

    page.wait_for_timeout(1500)   # wait for the quantity counter UI to appear
    print(f"  Added to cart.")

    # Adjust quantity
    reason = None
    if quantity > 1:
        print(f"  Adjusting quantity to {quantity}...")
        if adjust_quantity(page, quantity):
            print(f"  Quantity set to {quantity}.")
        else:
            reason = "Added item, but could not adjust quantity automatically"
            print(f"  {reason}")

    return {
        "original_name": original_name,
        "search_query":  search_query,
        "quantity":      quantity,
        "source":        source,
        "status":        "added",
        "reason":        reason,
    }


# ── Public functions ─────────────────────────────────────────────────────────

def open_zepto() -> None:
    """
    Open Zepto in a persistent Chromium session so the user can log in
    or set their delivery location.  Session is saved for future runs.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Could not open Zepto. Please check Playwright setup.")
        print("Run: pip install playwright && playwright install chromium")
        return

    try:
        with sync_playwright() as p:
            context, page = _open_context(p)

            print(f"Opening {ZEPTO_URL} ...")
            page.goto(ZEPTO_URL)
            page.wait_for_load_state("domcontentloaded")

            print("Zepto opened with persistent browser session.")
            print()
            print("If login or location is required, complete it in the browser.")
            print("After that, come back here and press Enter.")
            input()

            context.close()

    except Exception as e:
        print("Could not open Zepto. Please check Playwright setup.")
        print(f"Details: {e}")


def search_one_product(search_query: str) -> None:
    """Open Zepto, search for a product, and keep the browser open for review."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Could not open Zepto. Please check Playwright setup.")
        print("Run: pip install playwright && playwright install chromium")
        return

    try:
        with sync_playwright() as p:
            context, page = _open_context(p)

            print(f"Opening {ZEPTO_URL} ...")
            if search_product_on_page(page, search_query):
                print(f"Search results loaded for: {search_query}")
            else:
                print("Could not find Zepto search box. Please inspect the page manually.")

            print()
            print("Look at the browser to see results.")
            print("Press Enter to close the browser...")
            input()

            context.close()

    except Exception as e:
        print("Could not open Zepto. Please check Playwright setup.")
        print(f"Details: {e}")


def add_one_product_to_cart(search_query: str, quantity: int = 1) -> dict:
    """
    Open Zepto, add one product to the cart, and return a result dict.
    Kept for backwards compatibility; internally uses _add_product_on_page.
    """
    item = {
        "original_name": search_query,
        "search_query":  search_query,
        "quantity":      quantity,
        "source":        "user_text",
    }

    def _fail(reason: str) -> dict:
        return {"search_query": search_query, "quantity": quantity,
                "status": "failed", "reason": reason}

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Could not open Zepto. Please check Playwright setup.")
        print("Run: pip install playwright && playwright install chromium")
        return _fail("Playwright not installed")

    try:
        with sync_playwright() as p:
            context, page = _open_context(p)

            print(f"Opening {ZEPTO_URL} ...")
            result = _add_product_on_page(page, item)

            if result["status"] == "added":
                print(f"  Successfully added '{search_query}' to cart.")
            else:
                print(f"  Failed to add '{search_query}': {result['reason']}")

            print()
            print("Check the browser to confirm the item is in your cart.")
            print("Press Enter to close the browser...")
            input()

            context.close()
            return result

    except Exception as e:
        print("Could not open Zepto. Please check Playwright setup.")
        print(f"Details: {e}")
        return _fail(str(e))


def build_zepto_cart(resolved_items: list[dict]) -> dict:
    """
    Open Zepto once and add every resolved item to the cart in sequence.

    Uses a single browser session for all items — no open/close between products.
    If one item fails, the loop continues with the next item.

    Returns:
      {
        "items_added":  [ {original_name, search_query, quantity, source, status, reason}, ... ],
        "items_failed": [ ... ],
        "mode": "zepto"
      }
    """
    items_added  = []
    items_failed = []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Could not open Zepto. Please check Playwright setup.")
        print("Run: pip install playwright && playwright install chromium")
        return {"items_added": [], "items_failed": [], "mode": "zepto"}

    try:
        with sync_playwright() as p:
            context, page = _open_context(p)

            # Open Zepto home to get a visible starting state.
            print(f"Opening {ZEPTO_URL} ...")
            page.goto(ZEPTO_URL)
            page.wait_for_load_state("domcontentloaded")
            print()

            for item in resolved_items:
                print(f"Adding: {item['search_query']} x {item['quantity']}")

                # _add_product_on_page navigates to ZEPTO_URL itself before each
                # search, so every item starts from a clean home-page state.
                result = _add_product_on_page(page, item)

                if result["status"] == "added":
                    items_added.append(result)
                    print(f"  Done.\n")
                else:
                    items_failed.append(result)
                    print(f"  Failed: {result['reason']}\n")

            print("Finished building Zepto cart.")
            print("Check the browser to review all items in your cart.")
            print("Press Enter to close the browser...")
            input()

            context.close()

    except Exception as e:
        print("Could not build Zepto cart. Please check Playwright setup.")
        print(f"Details: {e}")

    return {
        "items_added":  items_added,
        "items_failed": items_failed,
        "mode":         "zepto",
    }


def open_checkout_page() -> dict:
    """
    Open Zepto and navigate to the cart / checkout page so the user can
    review their order and complete payment manually.

    Returns:
      {"status": "opened", "reason": None}      — checkout page found and opened
      {"status": "failed", "reason": "..."}     — button not found
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Could not open Zepto. Please check Playwright setup.")
        print("Run: pip install playwright && playwright install chromium")
        return {"status": "failed", "reason": "Playwright not installed"}

    try:
        with sync_playwright() as p:
            context, page = _open_context(p)

            print(f"Opening {ZEPTO_URL} ...")
            page.goto(ZEPTO_URL)
            page.wait_for_load_state("domcontentloaded")

            print("Looking for cart / checkout button...")

            clicked = False
            for selector in CHECKOUT_SELECTORS:
                try:
                    locator = page.locator(selector).first
                    locator.wait_for(state="visible", timeout=3000)
                    locator.click()
                    clicked = True
                    break
                except Exception:
                    continue

            if clicked:
                page.wait_for_load_state("domcontentloaded")
                print("Checkout page opened. Please complete payment manually.")
                print()
                print("Press Enter to close the browser when you are done...")
                input()
                context.close()
                return {"status": "opened", "reason": None}

            else:
                print("Could not find cart/checkout button. Please open the cart manually in the browser.")
                print()
                print("Press Enter to close the browser...")
                input()
                context.close()
                return {"status": "failed", "reason": "Cart or checkout button not found"}

    except Exception as e:
        print("Could not open checkout page. Please check Playwright setup.")
        print(f"Details: {e}")
        return {"status": "failed", "reason": str(e)}


# ── Cart capture helpers ─────────────────────────────────────────────────────


def _extract_price_from_text(text: str) -> str:
    """Return the first ₹-prefixed price string found, or empty string."""
    m = re.search(r"₹\s*[\d,]+(?:\.\d+)?", text)
    return m.group().replace(" ", "") if m else ""


def _extract_total_from_page(page) -> str:
    """
    Try several selectors to read the order total shown on the cart page.
    Returns a formatted string like '₹248' or empty string if not found.
    """
    total_selectors = [
        '[data-testid*="total"]',
        'text=/Total/i',
        'text=/Grand Total/i',
        'text=/Order Total/i',
        'text=/Bill Total/i',
        'text=/Amount/i',
    ]
    for sel in total_selectors:
        try:
            el = page.locator(sel).last
            el.wait_for(state="visible", timeout=2000)
            raw = el.inner_text()
            price = _extract_price_from_text(raw)
            if price:
                return price
        except Exception:
            continue
    return ""


# ── Public cart-capture / review / checkout functions ────────────────────────

def capture_cart_items(page) -> dict:
    """
    Navigate to the Zepto cart page and read every item currently in the cart.

    Returns:
      {
        "status": "captured" | "empty" | "failed",
        "reason": str | None,
        "items":  [{"name": str, "quantity": int, "price": str}, ...],
        "total":  str,
      }

    XPath pattern (1-based index N per item):
      name     — …/div[1]/div/div/div[N]/div[1]/div[2]/p
      quantity — …/div[1]/div/div/div[N]/div[2]/div[1]/p
    """
    BASE = "/html/body/div[4]/div/div/div/div[1]/div[2]/div[2]/div[1]/div"

    def name_xpath(n):
        return f"xpath={BASE}/div[{n}]/div[1]/div[2]/p"

    def qty_xpath(n):
        return f"xpath={BASE}/div[{n}]/div[2]/div[1]/p"

    try:
        print("  Opening cart page...")
        page.goto(ZEPTO_CART_URL)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(6000)   # cart modal needs time to render after JS loads

        page.screenshot(path="debug_cart_before_read.png")

        items = []
        n = 1
        while True:
            name_loc = page.locator(name_xpath(n))
            # First item gets a longer timeout in case the cart is still loading.
            timeout = 8000 if n == 1 else 2000
            try:
                name_loc.wait_for(state="visible", timeout=timeout)
            except Exception:
                break  # no more items

            name = name_loc.inner_text().strip()

            quantity = 1
            try:
                qty_text = page.locator(qty_xpath(n)).inner_text().strip()
                m = re.search(r"\d+", qty_text)
                if m:
                    quantity = int(m.group())
            except Exception:
                pass

            items.append({"name": name, "quantity": quantity, "price": ""})
            print(f"  Item {n}: {name} x{quantity}")
            n += 1

        if not items:
            page.screenshot(path="debug_cart_empty.png")
            return {"status": "empty", "reason": "Cart is empty", "items": [], "total": ""}

        total = _extract_total_from_page(page)
        return {"status": "captured", "reason": None, "items": items, "total": total}

    except Exception as e:
        page.screenshot(path="debug_cart_capture_failed.png")
        return {
            "status": "failed",
            "reason": str(e),
            "items": [],
            "total": "",
        }


def remove_cart_item(page, item_index: int, captured_cart: dict) -> dict:
    """
    Remove the item at `item_index` (0-based) from the Zepto cart.

    Strategy: on the cart page, find the delete / minus button for the
    target row and click it until the item is gone.

    Returns:
      {"status": "removed", "reason": None}
      {"status": "failed",  "reason": "..."}
    """
    items = captured_cart.get("items", [])
    if item_index < 0 or item_index >= len(items):
        return {"status": "failed", "reason": f"Item index {item_index} out of range"}

    item_name = items[item_index]["name"]

    # Selectors for a row-level delete / minus button.
    delete_selectors = [
        '[data-testid*="remove"]',
        '[data-testid*="delete"]',
        '[aria-label*="remove"]',
        '[aria-label*="delete"]',
        '[aria-label*="Remove"]',
        'button:has-text("−")',
        'button:has-text("-")',
        '[data-testid*="decrement"]',
        '[aria-label*="decrement"]',
        '[aria-label*="decrease"]',
    ]

    try:
        # Ensure we are on the cart page.
        if "cart" not in page.url:
            page.goto(ZEPTO_CART_URL)
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)

        # Collect all rows again (page may have re-rendered after prior removal).
        CART_ITEMS_XPATH = "xpath=/html/body/div[5]/div/div/div/div[1]/div[2]/div[2]/div[1]/div"
        rows = []
        try:
            locator = page.locator(CART_ITEMS_XPATH)
            if locator.count() > 0:
                rows = locator.all()
        except Exception:
            pass

        if not rows:
            for sel in ['[data-testid*="cart-item"]', '[class*="CartItem"]', 'section li']:
                try:
                    locator = page.locator(sel)
                    if locator.count() > 0:
                        rows = locator.all()
                        break
                except Exception:
                    continue

        if not rows or item_index >= len(rows):
            return {"status": "failed", "reason": f"Row {item_index} not found in cart DOM"}

        target_row = rows[item_index]

        # Click the item's quantity down to 0 by pressing the minus/delete button.
        quantity = items[item_index].get("quantity", 1)
        clicked = False
        for sel in delete_selectors:
            try:
                btn = target_row.locator(sel).first
                btn.wait_for(state="visible", timeout=2000)
                for _ in range(quantity):
                    btn.click()
                    page.wait_for_timeout(400)
                clicked = True
                break
            except Exception:
                continue

        if not clicked:
            return {"status": "failed", "reason": f"Could not find remove button for '{item_name}'"}

        page.wait_for_timeout(1000)
        print(f"  Removed: {item_name}")
        return {"status": "removed", "reason": None}

    except Exception as e:
        return {"status": "failed", "reason": str(e)}


def select_cash_on_delivery(page) -> dict:
    """
    On the checkout/payment page, select the Cash on Delivery option.

    Returns:
      {"status": "selected", "reason": None}
      {"status": "failed",   "reason": "..."}
    """
    COD_XPATH = "xpath=/html/body/div[7]/div/div/div/div[2]/div[6]/div[2]/div"
    try:
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)

        el = page.locator(COD_XPATH)
        el.wait_for(state="visible", timeout=5000)
        el.click()
        page.wait_for_timeout(1000)
        print("  Cash on Delivery selected.")
        return {"status": "selected", "reason": None}

    except Exception as e:
        page.screenshot(path="debug_cod_failed.png")
        return {
            "status": "failed",
            "reason": f"Could not click COD option: {e}. Screenshot saved as debug_cod_failed.png",
        }


def is_safe_final_order_button(button_text: str) -> bool:
    """
    Return True only if button_text looks like a place-order button
    and NOT like a payment / OTP / UPI button.

    Used as a guard before clicking anything that places the order.
    """
    lower = button_text.lower()
    for word in FORBIDDEN_PAYMENT_WORDS:
        if word in lower:
            return False
    safe_phrases = {"place order", "confirm order", "proceed to pay"}
    return any(p in lower for p in safe_phrases)


def _place_final_order(page) -> dict:
    """
    Click the final Place Order button.

    This is the ONLY place in the codebase that clicks a button which
    actually places an order.  Always called after the user types 'yes'
    at the terminal confirmation prompt.

    Returns:
      {"status": "placed",  "reason": None}
      {"status": "failed",  "reason": "..."}
    """
    PLACE_ORDER_XPATH = "xpath=/html/body/div[7]/div/div/div/div[2]/div[6]/div[2]/button"
    try:
        btn = page.locator(PLACE_ORDER_XPATH)
        btn.wait_for(state="visible", timeout=5000)
        btn.click()
        page.wait_for_timeout(2000)
        print("  Order placed.")
        return {"status": "placed", "reason": None}

    except Exception as e:
        page.screenshot(path="debug_place_order_failed.png")
        return {
            "status": "failed",
            "reason": f"Could not click Place Order button: {e}. Screenshot saved as debug_place_order_failed.png",
        }


# ── Full-flow orchestrator ───────────────────────────────────────────────────

def run_full_zepto_flow(resolved_items: list[dict]) -> dict:
    """
    One browser session that handles the complete order flow:

      1. Add all resolved items to the Zepto cart.
      2. Navigate to the cart page and capture its contents.
      3. Show the cart in the terminal and let the user:
           - proceed to checkout
           - remove individual items
           - cancel the order
      4. Navigate to checkout and select Cash on Delivery.
      5. Ask the user for final terminal confirmation before placing the order.
      6. Place the order (or abort if the user says no).

    Returns:
      {
        "items_added":   [...],
        "items_failed":  [...],
        "cart_captured": {...},
        "order_status":  "placed" | "cancelled" | "failed" | "manual",
        "mode":          "zepto",
      }
    """
    items_added  = []
    items_failed = []
    cart_captured = {"status": "not_attempted", "items": [], "total": ""}
    order_status  = "not_started"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Could not open Zepto. Please check Playwright setup.")
        print("Run: pip install playwright && playwright install chromium")
        return {
            "items_added": [], "items_failed": [], "cart_captured": cart_captured,
            "order_status": "failed", "mode": "zepto",
        }

    try:
        with sync_playwright() as p:
            context, page = _open_context(p)

            # ── Step 1: Add all items ────────────────────────────────────────
            print(f"Opening {ZEPTO_URL} ...")
            page.goto(ZEPTO_URL)
            page.wait_for_load_state("domcontentloaded")
            print()

            for item in resolved_items:
                print(f"Adding: {item['search_query']} x {item['quantity']}")
                result = _add_product_on_page(page, item)
                if result["status"] == "added":
                    items_added.append(result)
                    print(f"  Done.\n")
                else:
                    items_failed.append(result)
                    print(f"  Failed: {result['reason']}\n")

            if not items_added:
                print("No items were added to the cart. Aborting.")
                order_status = "cancelled"
                context.close()
                return {
                    "items_added": items_added, "items_failed": items_failed,
                    "cart_captured": cart_captured, "order_status": order_status,
                    "mode": "zepto",
                }

            # ── Step 2: Capture cart ─────────────────────────────────────────
            print("Reading cart contents...")
            cart_captured = capture_cart_items(page)

            # ── Step 3: Terminal review loop ─────────────────────────────────
            # Import here to avoid circular dependency at module load time.
            from cart import print_captured_cart_summary

            print_captured_cart_summary(cart_captured)

            while True:
                print("\nWhat would you like to do?")
                print("  [p] Proceed to checkout")
                print("  [r] Remove an item")
                print("  [c] Cancel order")
                action = input("Choice: ").strip().lower()

                if action == "p":
                    break

                elif action == "c":
                    print("Order cancelled. Browser will close.")
                    order_status = "cancelled"
                    context.close()
                    return {
                        "items_added": items_added, "items_failed": items_failed,
                        "cart_captured": cart_captured, "order_status": order_status,
                        "mode": "zepto",
                    }

                elif action == "r":
                    if not cart_captured.get("items"):
                        print("  No items in captured cart to remove.")
                        continue

                    print("\n  Which item to remove?")
                    for i, it in enumerate(cart_captured["items"], start=1):
                        print(f"    {i}. {it['name']} x {it['quantity']}")
                    idx_input = input("  Item number: ").strip()

                    if not idx_input.isdigit() or not (1 <= int(idx_input) <= len(cart_captured["items"])):
                        print("  Invalid choice.")
                        continue

                    idx = int(idx_input) - 1
                    remove_result = remove_cart_item(page, idx, cart_captured)
                    if remove_result["status"] == "removed":
                        # Re-capture cart after removal.
                        cart_captured = capture_cart_items(page)
                        print_captured_cart_summary(cart_captured)
                        if not cart_captured.get("items"):
                            print("Cart is now empty.")
                            order_status = "cancelled"
                            context.close()
                            return {
                                "items_added": items_added, "items_failed": items_failed,
                                "cart_captured": cart_captured, "order_status": order_status,
                                "mode": "zepto",
                            }
                    else:
                        print(f"  Could not remove item: {remove_result['reason']}")
                else:
                    print("  Please type p, r, or c.")

            # ── Step 4: Navigate to checkout ─────────────────────────────────
            print("\nProceeding to checkout...")
            CHECKOUT_BTN_XPATH = "xpath=/html/body/div[4]/div/div/div/div[2]/div/div/button"
            try:
                btn = page.locator(CHECKOUT_BTN_XPATH)
                btn.wait_for(state="visible", timeout=5000)
                btn.click()
                print("  Checkout button clicked.")
            except Exception as e:
                print(f"  Could not click checkout button: {e}")
                print("  Please click the checkout button manually in the browser.")
                input("  Press Enter when you are on the checkout page... ")

            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)

            # ── Step 5: Select Cash on Delivery ──────────────────────────────
            print("Selecting Cash on Delivery...")
            cod_result = select_cash_on_delivery(page)
            if cod_result["status"] != "selected":
                print(f"  Warning: {cod_result['reason']}")
                print("  Please select Cash on Delivery manually in the browser.")
                print("  Press Enter when done, or type 'skip' to cancel.")
                user_action = input("  > ").strip().lower()
                if user_action == "skip":
                    order_status = "cancelled"
                    context.close()
                    return {
                        "items_added": items_added, "items_failed": items_failed,
                        "cart_captured": cart_captured, "order_status": order_status,
                        "mode": "zepto",
                    }

            # ── Step 6: Final confirmation before placing the order ───────────
            print()
            print("=" * 55)
            print("FINAL CONFIRMATION")
            print("=" * 55)
            if cart_captured.get("total"):
                print(f"  Order total:    {cart_captured['total']}")
            print(f"  Payment method: Cash on Delivery")
            print("=" * 55)
            confirm = input("Place this order with Cash on Delivery? yes/no: ").strip().lower()

            if confirm != "yes":
                print("Order not placed. Browser will stay open for manual review.")
                print("Press Enter to close the browser...")
                input()
                order_status = "cancelled"
                context.close()
                return {
                    "items_added": items_added, "items_failed": items_failed,
                    "cart_captured": cart_captured, "order_status": order_status,
                    "mode": "zepto",
                }

            # User confirmed — place the order.
            place_result = _place_final_order(page)
            if place_result["status"] == "placed":
                order_status = "placed"
                print()
                print("Order placed successfully! Check the browser for confirmation.")
                page.wait_for_timeout(3000)
            else:
                order_status = "failed"
                print(f"  Could not place order automatically: {place_result['reason']}")
                print("  Please complete the order manually in the browser.")
                print("  Press Enter to close the browser...")
                input()

            context.close()

    except Exception as e:
        print(f"Zepto flow error: {e}")
        order_status = "failed"

    return {
        "items_added":   items_added,
        "items_failed":  items_failed,
        "cart_captured": cart_captured,
        "order_status":  order_status,
        "mode":          "zepto",
    }
