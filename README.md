# Smart Librarian (Basic) – RAG + Tool Calling (CLI)

**Stack:** OpenAI `gpt-4.1-mini` (chat), `text-embedding-3-small` (embeddings), ChromaDB (local, persisted), Python CLI.  
**Only small models are used by default.** You can switch to `gpt-4o-mini` via env var if desired.

## 0) Prerequisites
- Python 3.10+ (recommended)
- An OpenAI API key exported as `OPENAI_API_KEY`

```bash
# macOS/Linux
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export OPENAI_API_KEY="sk-..."   # set your key
# optional overrides
export CHAT_MODEL="gpt-4.1-mini"
export EMBED_MODEL="text-embedding-3-small"
```

On Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:OPENAI_API_KEY="sk-..."
$env:CHAT_MODEL="gpt-4.1-mini"
$env:EMBED_MODEL="text-embedding-3-small"
```

## 1) Ingest (build the vector store)
```bash
python app/ingest.py
```
This will create a Chroma collection in `./chroma` with embeddings for each book (title + tags + short summary).

## 2) Run the CLI
```bash
python app/ui_cli.py
```
Type natural questions in Romanian like:
- `Vreau o carte despre prietenie și magie`  
- `Ce recomanzi pentru cineva care iubește povești de război?`  
- `Ce este 1984?`

Type `exit` to quit.

## Project Layout
```
smart-librarian/
  app/
    config.py
    ingest.py
    retriever.py
    tools.py
    orchestrator.py
    ui_cli.py
  data/
    book_summaries.jsonl
  chroma/                # created at first ingest
  requirements.txt
  README.md
```

## Notes
- The CLI implements: RAG search → model suggestion → automatic tool call (`get_summary_by_title`) → final answer.
- All prompts/responses are in Romanian. Titles remain in original language where appropriate.
- You can edit `data/book_summaries.jsonl` to customize the corpus.
- If you want Streamlit/TTS/STT later, keep this base and we’ll extend it.

