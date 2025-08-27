import json, unicodedata, re
from pathlib import Path
from typing import Dict, Any

from app.config import settings

# Preload dataset to serve as the source for full summaries
_DATA = {}
def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()

def _load():
    p = Path(settings.DATA_PATH)
    if not p.exists():
        raise FileNotFoundError(f"Dataset not found at {p.resolve()}")
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        _DATA[_normalize(item["title"])] = item
_load()

def get_summary_by_title(title: str) -> str:
    key = _normalize(title)
    item = _DATA.get(key)
    if not item:
        # attempt soft match by ignoring punctuation
        key2 = re.sub(r"[^a-z0-9 ]+", "", key)
        for k, v in _DATA.items():
            k2 = re.sub(r"[^a-z0-9 ]+", "", k)
            if k2 == key2:
                item = v
                break
    if not item:
        return f"Titlul '{title}' nu a fost găsit în baza locală."
    return item.get("full_summary", "Nu există rezumat complet.")

def tool_spec() -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "get_summary_by_title",
            "description": "Returnează rezumatul complet al unei cărți pentru un titlu exact (string).",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titlul exact al cărții"}
                },
                "required": ["title"],
                "additionalProperties": False,
            },
        },
    }

# Simple dispatcher for tool calls
def dispatch_tool(name: str, arguments_json: str) -> str:
    if name != "get_summary_by_title":
        return f"Tool necunoscut: {name}"
    try:
        args = json.loads(arguments_json or "{}")
    except Exception:
        return "Argumente invalide pentru tool."
    title = args.get("title", "")
    return get_summary_by_title(title)
