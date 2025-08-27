from typing import List, Dict, Any
from openai import OpenAI

from app.config import settings, require_api_key
from app.retriever import Retriever
from app.tools import tool_spec, dispatch_tool
from app.guard import check_inappropriate

SYSTEM_PROMPT = (
    "Ești Smart Librarian. Primești o întrebare a utilizatorului și un CONTEXT cu mai multe cărți "
    "(titlu, etichete, rezumat scurt) recuperate prin căutare semantică. "
    "Sarcina ta: recomandă clar o singură carte din CONTEXT (sau două dacă sunt foarte strânse), "
    "explică pe scurt potrivirea. Dacă recomanzi un titlu anume, APELEAZĂ tool-ul "
    "`get_summary_by_title` cu argumentul `title` IDENTIC cu câmpul 'title' din CONTEXT pentru a obține "
    "rezumatul complet și include-l după recomandare. Răspunde concis, în limba română."
)

def _format_context(rows: List[Dict[str, Any]]) -> str:
    """Construiește un blob compact cu titlu, taguri și brief pentru fiecare rezultat."""
    if not rows:
        return "— (niciun rezultat) —"
    lines = []
    for r in rows:
        md = r.get("metadata", {})
        title = md.get("title", "N/A")
        tags = md.get("tags", "")
        brief = r.get("document", "")
        lines.append(f"- Title: {title}\n  Tags: {tags}\n  Brief: {brief}")
    return "\n".join(lines)

def _apply_filters(rows: List[Dict[str, Any]], flang: str | None, ftags: list[str] | None) -> List[Dict[str, Any]]:
    """Aplică filtre pe limbă și taguri; dacă filtrarea golește lista, întoarce lista inițială."""
    if not rows:
        return rows
    out: List[Dict[str, Any]] = []
    for r in rows:
        md = r.get("metadata", {})
        # limba
        if flang and md.get("language") != flang:
            continue
        # taguri (toate cerute trebuie să apară în stringul de taguri)
        if ftags:
            tags_str = str(md.get("tags", "")).lower()
            if not all(t.strip().lower() in tags_str for t in ftags if t.strip()):
                continue
        out.append(r)
    return out or rows

class SmartLibrarian:
    def __init__(self):
        require_api_key()
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.retriever = Retriever()

    def chat_once(
        self,
        user_query: str,
        filter_language: str | None = None,
        filter_tags: list[str] | None = None,
        override_context: List[Dict[str, Any]] | None = None,
    ) -> str:
        """
        Generează un răspuns folosind contextul RAG.
        - override_context: dacă e furnizat (din UI), îl folosim direct în loc să căutăm aici.
        - filter_language / filter_tags: filtre logice suplimentare asupra contextului.
        """

        # 0) Guard pentru limbaj nepotrivit
        bad, _ = check_inappropriate(user_query or "")
        if bad:
            return (
                "Îți mulțumesc pentru mesaj, dar conține termeni nepotriviți. "
                "Te rog reformulează fără limbaj ofensator și reîncearcă."
            )

        # 1) Obține contextul: fie din override, fie prin retriever
        if override_context is not None:
            top = override_context
        else:
            top = self.retriever.search(user_query, k=settings.TOP_K)

        # 2) Aplică filtre (dacă sunt)
        top = _apply_filters(top, filter_language, filter_tags)

        # 3) Construiește promptul + tool spec
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Întrebarea utilizatorului: {user_query}\n\n"
                    f"CONTEXT (câte {len(top)} rezultate):\n{_format_context(top)}"
                ),
            },
        ]
        tools = [tool_spec()]

        # 4) Primul apel (modelul poate decide să apeleze tool-ul)
        first = self.client.chat.completions.create(
            model=settings.CHAT_MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.3,
        )
        msg = first.choices[0].message

        # 5) Dacă există tool calls, executăm și apoi cerem răspunsul final
        if getattr(msg, "tool_calls", None):
            # Reprezentăm tool_calls în formatul compatibil pentru mesaj
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            })

            for tc in msg.tool_calls:
                name = tc.function.name
                args_json = tc.function.arguments
                tool_output = dispatch_tool(name, args_json)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": tool_output,
                })

            final = self.client.chat.completions.create(
                model=settings.CHAT_MODEL,
                messages=messages,
                temperature=0.3,
            )
            return (final.choices[0].message.content or "").strip()

        # 6) Fără tool calls: răspuns direct
        return (msg.content or "").strip()
