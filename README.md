# Zepto Grocery Agent

A terminal-based Python agent that lets you order groceries on Zepto using natural language. Powered by Groq LLM for parsing and Supermemory for preference storage and semantic lookup.

## What it does

You type something like:

```
What do you want to order? get me 2 litres of whole milk, a dozen eggs and some butter
```

And the agent will:
1. Parse your input using an LLM into a structured item list
2. Match items against your saved preferences (semantically — "whole milk" finds "milk" in Supermemory)
3. Ask clarification for ambiguous items (e.g. which pasta, which bread)
4. Show a simulated cart preview before touching the browser
5. Open Zepto, add all items, let you review and remove items, then place the order with Cash on Delivery

## Setup

**1. Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium
```

**2. Add your API keys**

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_groq_key_here
SUPERMEMORY_API_KEY=your_supermemory_key_here
```

- Groq free key: [console.groq.com](https://console.groq.com)
- Supermemory key: [supermemory.ai](https://supermemory.ai)

**3. Run the agent**

```bash
python main.py
```

## How it works

### Parsing
`parser.py` sends your raw input to `llama-3.1-8b-instant` via Groq and gets back a structured JSON list of items with quantities. Handles natural phrasing, typos, and indirect references ("a dozen eggs", "couple of bananas") that a rule-based parser would miss.

### Memory & semantic lookup
`memory.py` stores preferences in Supermemory as JSON objects. On lookup, Supermemory does the semantic matching natively — so "whole milk" correctly resolves to a saved "milk" preference without any extra LLM call. The returned profile is parsed directly. Order rules (confirmation settings, payment mode) are stored locally in `user_rules.json`.

### Resolving items
`resolver.py` maps each parsed item to a Zepto search query using three rules in order:
- **Memory hit** — use your saved preferred product directly
- **Ambiguous item** (chips, pasta, milk, bread, etc.) — ask you to pick from a list and optionally save the choice to Supermemory
- **Everything else** — search Zepto using the item name as-is

### Browser automation
`zepto_browser.py` drives a persistent Chromium session via Playwright. It adds all items in one browser session, reads back the actual cart, lets you remove items from the terminal, selects Cash on Delivery, and only places the order after an explicit "yes" confirmation.

## Project structure

| File | Purpose |
|---|---|
| `main.py` | Entry point — terminal input/output loop |
| `parser.py` | LLM-powered natural language parser (Groq) |
| `memory.py` | Preference storage and lookup via Supermemory |
| `resolver.py` | Map parsed items to Zepto search queries |
| `cart.py` | Simulated and real cart display |
| `zepto_browser.py` | Playwright browser automation for Zepto |
| `config.py` | App-wide constants (URL, browser settings) |
| `user_rules.json` | Persisted order rules (auto-created) |
| `.env` | API keys — Groq and Supermemory (you create this) |

## Safety

- The "Place Order" button is only clicked after an explicit `yes` at the terminal.
- Payment buttons (UPI, card, OTP, wallet) are never clicked automatically.
- All other payments beyond Cash on Delivery must be completed manually in the browser.
