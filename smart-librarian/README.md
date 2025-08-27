# 📚 Smart Librarian — RAG + Tool Calling (CLI & Streamlit)

Chatbot care recomandă cărți în funcție de interesele utilizatorului. Folosește **RAG cu ChromaDB** și, după recomandare, apelează un **tool** pentru a livra **rezumatul complet** al cărții selectate. Include **filtru de limbaj nepotrivit**, **TTS**, **STT** și **generare de imagini** (copertă). UI: CLI și Streamlit.

> Conform cerințelor: folosește **modele mici** (4.1-mini / 4o-mini / 4.1-nano; embeddings *text-embedding-3-small*), dataset cu **10+ cărți**, RAG + tool calling, UI și README.

---

## 🚀 Demo rapid

```bash
# 1) pregătește mediul
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
pip install -r requirements.txt

# 2) setează cheia (alege una din opțiuni)
$env:OPENAI_API_KEY="...cheia ta..."               # doar sesiunea curentă
# sau (persistă între sesiuni): setx OPENAI_API_KEY "...cheia ta..."

# 3) ingestă dataset-ul în Chroma (vector store local)
python -m app.ingest

# 4) rulează CLI
python -m app.ui_cli

# 5) rulează Streamlit
python -m streamlit run streamlit_app.py
```

---

## 🧱 Arhitectură & tehnologii

- **LLM chat**: `gpt-4.1-mini`  
- **Embeddings**: `text-embedding-3-small`  
- **Vector store**: **ChromaDB** (HNSW, cosine)  
- **RAG**: `app/retriever.py` (căutare semantică, filtre limbă/taguri)  
- **Tool calling**: `get_summary_by_title(title)` → livrează rezumatul complet al cărții recomandate  
- **UI**:
  - **CLI** (`app/ui_cli.py`)
  - **Streamlit** (`streamlit_app.py`) – chat + citații, STT, TTS, generare copertă
- **Guard**: filtru de limbaj nepotrivit (RO/EN) care oprește promptul ofensator înainte de LLM

---

## 📁 Structura proiectului

```
smart-librarian/
├─ app/
│  ├─ config.py            # setări (modele mici, căi absolute, etc.)
│  ├─ ingest.py            # construiește embeddings + salvează în Chroma
│  ├─ retriever.py         # interogare Chroma (cosine), filtre
│  ├─ orchestrator.py      # prompt sistem, tool-calling, integrare RAG
│  ├─ tools.py             # spec + dispatch pentru get_summary_by_title
│  ├─ dataset.py           # CRUD pe book_summaries.jsonl + re-ingest
│  ├─ guard.py             # filtru limbaj nepotrivit
│  ├─ images.py            # generare copertă cu gpt-image-1
│  └─ ui_cli.py            # interfața CLI
├─ data/
│  └─ book_summaries.jsonl # 10+ cărți (titlu, limbă, taguri, rezumate)
├─ streamlit_app.py        # UI grafică
├─ requirements.txt
└─ README.md
```

---

## 🔧 Configurare

Setează **OPENAI_API_KEY**:
- Rapid (doar sesiunea curentă):
  ```powershell
  $env:OPENAI_API_KEY="...cheia ta..."
  ```
- Persistent (utilizator Windows):
  ```powershell
  setx OPENAI_API_KEY "...cheia ta..."
  ```
- **Streamlit secrets** (opțional):
  - `.streamlit/secrets.toml`:
    ```toml
    OPENAI_API_KEY = "…"
    ```

Setări în `app/config.py`:
- `CHAT_MODEL="gpt-4.1-mini"`, `EMBED_MODEL="text-embedding-3-small"`
- `DATA_PATH`, `CHROMA_PATH`, `COLLECTION_NAME`
- `TOP_K`, `SIMILARITY_MAX_DISTANCE`
- `IMAGE_MODEL="gpt-image-1"`, `IMAGE_SIZE`
- `SIDEBAR_WIDTH` (opțional, lățimea sidebar-ului Streamlit; se aplică doar când sidebar-ul e deschis)

---

## 🗂️ Dataset (book_summaries.jsonl)

Format **JSONL** — un obiect JSON pe linie:

```json
{"title":"The Hobbit","language":"ro","tags":["aventură","prietenie"],"brief_summary":"3–5 rânduri…","full_summary":"rezumat complet…"}
```

> Minim **10 cărți**. Poți administra dataset-ul direct din Streamlit: **🛠️ Admin dataset** → Add/Edit/Delete → **Re-ingest**.

---

## 🖥️ Rulare & utilizare

### CLI
```bash
python -m app.ui_cli
```
Exemple:  
- „Vreau o carte despre prietenie și magie.”  
- „Ce recomanzi dacă iubesc poveștile de război?”  
- „Ce este 1984?”

### Streamlit
```bash
python -m streamlit run streamlit_app.py
```
Funcționalități:
- **Chat** în română
- **Citații pe răspuns** (expander „📚 Surse folosite la acest răspuns”)
- **TTS** – „🔊 Ascultă recomandarea” → MP3 (cu download)
- **STT** – încărcare WAV/MP3/M4A → „Transcrie și întreabă”
- **Generare copertă** – „🎨 Generează copertă” (gpt-image-1)
- **Admin** – CRUD pe dataset + **Re-ingest**

---

## 🧠 Cum funcționează

1. **Ingest**: citește `book_summaries.jsonl`, compune text „Titlu + Etichete + Rezumat scurt”, creează **embeddings** cu `text-embedding-3-small`, salvează în Chroma.  
2. **RAG**: la întrebare, caută top-K rezultate (cosine), opțional filtrează pe limbă și taguri.  
3. **LLM**: construiește prompt cu **CONTEXT** (rezultatele RAG) + întrebare și recomandă o carte.  
4. **Tool calling**: apelează `get_summary_by_title` pentru **rezumatul complet** al cărții recomandate.  
5. **Citații**: UI reține contextul folosit pentru acel răspuns și îl afișează sub mesaj.

---

## 💸 Modele & costuri (orientativ)

- Chat: **gpt-4.1-mini**  
- Embeddings: **text-embedding-3-small**  
- STT: **gpt-4o-mini-transcribe**  
- TTS: **gpt-4o-mini-tts**  
- Imagini: **gpt-image-1**  

Toate sunt **modele mici** / economice pentru proiecte educaționale.

---

## 🛠️ Troubleshooting

- **`RuntimeError: Set OPENAI_API_KEY…`** → setează cheia (vezi Configurare) și redeschide terminalul.  
- **Chroma: `Expected metadata value… list`** → metadatele trebuie să fie *scalare* (stringuri). În ingest convertim tagurile la CSV.  
- **`NotFoundError: Collection … does not exist`** → rulează **Re-ingest** sau `python -m app.ingest`.  
- **STT: același fișier apăsat de 2 ori** → UI marchează fișierul ca „deja procesat”. Reîncarcă fișierul sau încarcă altul.  
- **Sidebar**: lățimea se controlează din `SIDEBAR_WIDTH`; CSS-ul se aplică doar când e deschis (colapsat = chat centrat).

---

## ✅ Checklist cerințe

- [x] Dataset cu **10+** cărți  
- [x] Ingest + vector store local (**Chroma**)  
- [x] **RAG** + **tool calling** pentru rezumat complet  
- [x] **CLI** + **Streamlit** UI  
- [x] **Filtru limbaj**, **TTS**, **STT**, **generare imagine**  
- [x] README cu pașii de build/rulare

---

## 📄 Licență

Proiect educațional; utilizează API-urile OpenAI. Respectă termenii de utilizare.
