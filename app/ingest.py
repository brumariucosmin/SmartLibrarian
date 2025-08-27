import json, unicodedata, re
from pathlib import Path
from typing import List, Dict, Any

import chromadb
from openai import OpenAI

from app.config import settings, require_api_key

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9\-_]+", "-", text).strip("-").lower()
    return text or "untitled"

def load_dataset(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset not found at {p.resolve()}")
    items = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        items.append(json.loads(line))
    return items

def build_text_to_embed(item: Dict[str, Any]) -> str:
    tags = item.get("tags", [])
    tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
    return f"Titlu: {item['title']}\nEtichete: {tags_str}\nRezumat scurt: {item['brief_summary']}"

def sanitize_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in meta.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, list):
            out[k] = ", ".join(map(str, v))
        else:
            out[k] = json.dumps(v, ensure_ascii=False)
    return out

def ingest_all() -> int:
    """Reconstruiește COLECȚIA de la zero și încarcă toate item-urile din dataset.
       Returnează numărul de item-uri adăugate.
    """
    require_api_key()

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    chroma = chromadb.PersistentClient(path=settings.CHROMA_PATH)

    # recreăm colecția curat (evităm duplicate la re-ingest)
    try:
        chroma.delete_collection(settings.COLLECTION_NAME)
    except Exception:
        pass
    collection = chroma.create_collection(
        name=settings.COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    items = load_dataset(settings.DATA_PATH)
    ids, documents, metadatas, inputs = [], [], [], []

    for item in items:
        ids.append(slugify(item["title"]))
        doc = build_text_to_embed(item)
        documents.append(doc)

        tags = item.get("tags", [])
        tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
        md = {
            "title": item["title"],
            "language": item.get("language", "ro"),
            "tags": tags_str,
        }
        metadatas.append(sanitize_metadata(md))
        inputs.append(doc)

    resp = client.embeddings.create(
        model=settings.EMBED_MODEL,
        input=inputs,
    )
    embeddings = [d.embedding for d in resp.data]

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    return len(ids)

def main():
    n = ingest_all()
    print(f"Ingest complete. Added {n} items to collection '{settings.COLLECTION_NAME}' at {settings.CHROMA_PATH}")

if __name__ == "__main__":
    main()
