import json
import unicodedata
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from app.config import settings

def _normalize_title(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t

def load_items(path: str | None = None) -> List[Dict[str, Any]]:
    p = Path(path or settings.DATA_PATH)
    if not p.exists():
        return []
    items: List[Dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            items.append(json.loads(line))
    return items

def list_books() -> List[str]:
    return [it.get("title", "") for it in load_items()]

def get_book(title: str, path: str | None = None) -> Optional[Dict[str, Any]]:
    items = load_items(path or settings.DATA_PATH)
    norm = _normalize_title(title)
    for it in items:
        if _normalize_title(it.get("title", "")) == norm:
            return it
    return None

def add_book(
    title: str,
    tags_csv: str,
    brief_summary: str,
    full_summary: str,
    language: str = "ro",
    path: str | None = None,
) -> Tuple[bool, str]:
    """Adaugă o carte în JSONL (fără duplicate de titlu)."""
    p = Path(path or settings.DATA_PATH)
    items = load_items(p.as_posix())
    title_norm = _normalize_title(title)

    for it in items:
        if _normalize_title(it.get("title", "")) == title_norm:
            return False, f"Titlul '{title}' există deja în dataset."

    tags = [t.strip() for t in tags_csv.split(",") if t.strip()] if tags_csv else []
    new_item = {
        "title": title,
        "language": language or "ro",
        "tags": tags,
        "brief_summary": brief_summary.strip(),
        "full_summary": full_summary.strip(),
    }

    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(new_item, ensure_ascii=False) + "\n")

    return True, f"Adăugat: {title}"

def delete_book(title: str) -> Tuple[bool, str]:
    p = Path(settings.DATA_PATH)
    items = load_items(p.as_posix())
    norm = _normalize_title(title)
    new_items = [it for it in items if _normalize_title(it.get("title","")) != norm]
    if len(new_items) == len(items):
        return False, f"Nu am găsit titlul '{title}'."
    with p.open("w", encoding="utf-8") as f:
        for it in new_items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    return True, f"Șters: {title}"

def update_book(
    original_title: str,
    title: Optional[str] = None,
    tags_csv: Optional[str] = None,
    brief_summary: Optional[str] = None,
    full_summary: Optional[str] = None,
    language: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Actualizează cartea: câmpurile lăsate necompletate rămân neschimbate.
    """
    p = Path(settings.DATA_PATH)
    items = load_items(p.as_posix())
    o = _normalize_title(original_title)
    idx = None
    for i, it in enumerate(items):
        if _normalize_title(it.get("title","")) == o:
            idx = i
            break
    if idx is None:
        return False, f"Nu am găsit titlul '{original_title}'."

    cur = items[idx]
    new_title = (title or cur.get("title","")).strip() or cur.get("title","")
    if tags_csv is None or tags_csv.strip() == "":
        new_tags = cur.get("tags", [])
    else:
        new_tags = [t.strip() for t in tags_csv.split(",") if t.strip()]

    new_brief = brief_summary.strip() if brief_summary is not None and brief_summary.strip() != "" else cur.get("brief_summary","")
    new_full  = full_summary.strip()  if full_summary  is not None and full_summary.strip()  != "" else cur.get("full_summary","")
    new_lang  = language or cur.get("language","ro")

    items[idx] = {
        "title": new_title,
        "language": new_lang,
        "tags": new_tags,
        "brief_summary": new_brief,
        "full_summary": new_full,
    }
    with p.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    return True, f"Actualizat: {original_title} → {new_title}"
