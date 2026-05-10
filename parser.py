import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in environment or .env file")
        _client = Groq(api_key=api_key)
    return _client


_SYSTEM_PROMPT = (
    "You are a grocery order parser. Extract grocery items and their quantities "
    "from the user's message. Return ONLY a JSON array of objects with \"name\" "
    "(string, lowercase, singular) and \"quantity\" (integer, default 1 if not "
    "specified). Example output: [{\"name\": \"milk\", \"quantity\": 2}, "
    "{\"name\": \"eggs\", \"quantity\": 12}]. "
    "Do not include any explanation or markdown — just the raw JSON array."
)


def parse_order(user_text: str) -> list[dict]:
    """
    Sends user_text to Groq LLM and returns a structured list of grocery items.
    Falls back to the rule-based parser if the API call fails.
    """
    client = _get_client()
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        temperature=0,
        max_tokens=512,
    )
    raw = response.choices[0].message.content.strip()
    items = json.loads(raw)
    return [
        {"name": str(item["name"]).lower(), "quantity": int(item.get("quantity", 1))}
        for item in items
        if "name" in item
    ]
