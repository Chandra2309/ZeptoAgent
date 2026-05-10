# Zepto Grocery Agent

A terminal-based Python agent that lets you order groceries on Zepto using natural language.

## What it does

You type something like:

```
What do you want to order? milk bread eggs coke
```

And the agent will (eventually) parse your input, find matching products on Zepto, add them to your cart, and ask for confirmation before checkout.

## How to run

**1. Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium
```

**2. Run the agent**

```bash
python main.py
```

**3. Test it**

- Type any grocery items and press Enter — you will see them echoed back.
- Type `exit` or `quit` to stop.

## Project structure

| File | Purpose |
|---|---|
| `main.py` | Entry point — handles terminal input/output |
| `parser.py` | (Coming soon) Parse natural language into item list |
| `memory.py` | (Coming soon) Load/save user preferences |
| `resolver.py` | (Coming soon) Match items to Zepto products |
| `cart.py` | (Coming soon) Manage cart state |
| `zepto_browser.py` | (Coming soon) Playwright browser automation |
| `config.py` | App-wide constants (URL, browser settings) |
| `user_memory.json` | Stores user preferences and rules |

## Current status

**Block 1 complete** — Project setup only.

The agent starts, accepts input, echoes it back, and exits cleanly. No browser automation or parsing is implemented yet.
