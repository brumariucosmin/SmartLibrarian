from typing import List, Dict, Any
import chromadb
from openai import OpenAI

from app.config import settings, require_api_key

class Retriever:
    def __init__(self):
        require_api_key()
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.chroma = chromadb.PersistentClient(path=settings.CHROMA_PATH)
        self.collection = self.chroma.get_collection(settings.COLLECTION_NAME)

    def embed(self, text: str) -> List[float]:
        emb = self.client.embeddings.create(model=settings.EMBED_MODEL, input=text)
        return emb.data[0].embedding

    def _query(self, q_emb: List[float], k: int):
        return self.collection.query(
            query_embeddings=[q_emb],
            n_results=k,
            include=["metadatas", "documents", "distances"],
        )

    def search(
        self,
        query: str,
        k: int | None = None,
        max_distance: float | None = None
    ) -> List[Dict[str, Any]]:
        if k is None:
            k = settings.TOP_K
        q_emb = self.embed(query)

        # Prima încercare (colecția poate fi invalidată după re-ingest)
        try:
            res = self._query(q_emb, k)
        except Exception:
            # Re-obține colecția și reîncearcă o singură dată
            self.collection = self.chroma.get_collection(settings.COLLECTION_NAME)
            res = self._query(q_emb, k)

        threshold = settings.SIMILARITY_MAX_DISTANCE if (max_distance is None) else max_distance
        out = []
        for i in range(len(res["ids"][0])):
            d = res["distances"][0][i] if "distances" in res else None
            # cosine distance: 0 = identic, 1 = opus (mai mic = mai relevant)
            if d is None or d <= threshold:
                out.append({
                    "id": res["ids"][0][i],
                    "document": res["documents"][0][i],
                    "metadata": res["metadatas"][0][i],
                    "distance": d,
                })

        # fallback: dacă filtrul goleşte lista, păstrăm măcar top-1
        if not out and res["ids"][0]:
            out.append({
                "id": res["ids"][0][0],
                "document": res["documents"][0][0],
                "metadata": res["metadatas"][0][0],
                "distance": res["distances"][0][0] if "distances" in res else None,
            })
        return out
