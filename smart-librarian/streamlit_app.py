import os
import re
import time
import tempfile
from pathlib import Path

import streamlit as st
from openai import OpenAI

from app.orchestrator import SmartLibrarian
from app.retriever import Retriever
from app.config import settings
from app.images import generate_cover
from app.ingest import ingest_all
from app.dataset import add_book, list_books, delete_book, update_book, get_book, load_items
from app.guard import check_inappropriate  # pentru mesajele din STT/Chat

# --- config UI (doar sidebar mai lat, chat rămâne centered) ---
st.set_page_config(page_title="Smart Librarian", page_icon="📚", layout="centered")

SIDEBAR_WIDTH = int(os.getenv("SIDEBAR_WIDTH", "380"))  # ajustează 380 după preferință

st.markdown(f"""
<style>
/* ====== Lățime doar când sidebarul e DESCHIS ====== */
[data-testid="stSidebar"][aria-expanded="true"] {{
  width: {SIDEBAR_WIDTH}px !important;
}}
[data-testid="stSidebar"][aria-expanded="true"] > div:first-child {{
  width: {SIDEBAR_WIDTH}px !important;
  min-width: {SIDEBAR_WIDTH}px !important;
  max-width: {SIDEBAR_WIDTH}px !important;
}}

/* ====== Când e COLAPSAT, nu impune nicio lățime (lasă centrul la loc) ====== */
[data-testid="stSidebar"][aria-expanded="false"] {{
  width: 0 !important;
  min-width: 0 !important;
  max-width: none !important;
}}

/* ====== Muta butonul de toggle în stânga-sus ====== */
/* unele versiuni folosesc 'collapsedControl', altele 'stSidebarCollapseButton' */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapseButton"] {{
  position: fixed;
  left: 12px;
  top: 12px;
  z-index: 1000;
}}
</style>
""", unsafe_allow_html=True)

# --- init state ---
if "bot" not in st.session_state:
    st.session_state.bot = SmartLibrarian()
if "retriever" not in st.session_state:
    st.session_state.retriever = Retriever()
if "messages" not in st.session_state:
    st.session_state.messages = []
# TTS per mesaj
if "tts_audio" not in st.session_state:
    st.session_state.tts_audio = {}
# Cover per mesaj
if "covers" not in st.session_state:
    st.session_state.covers = {}
# Citații per mesaj: index_mesaj_asistent -> lista de rezultate RAG (context) folosit atunci
if "ctx_by_idx" not in st.session_state:
    st.session_state.ctx_by_idx = {}

client = OpenAI(api_key=settings.OPENAI_API_KEY)

# --- sidebar controls ---
st.sidebar.title("Setări")
top_k = st.sidebar.slider("TOP_K (pentru context afișat)", 1, 8, settings.TOP_K)
threshold = st.sidebar.slider("Prag similaritate (max distance)", 0.0, 1.0, settings.SIMILARITY_MAX_DISTANCE, 0.01)

st.sidebar.markdown("### Filtre recomandare")
flang = st.sidebar.selectbox("Limbă", ["(fără)", "ro", "en"], index=0)
ftags_csv = st.sidebar.text_input("Taguri (CSV)", placeholder="ex: prietenie, magie")

st.sidebar.markdown("### Afișare")
show_citations = st.sidebar.checkbox("Citații sub fiecare răspuns", value=True)
show_context = st.sidebar.checkbox("Arată contextul RAG (doar promptul curent)", value=False)

st.sidebar.button("Reset chat", on_click=lambda: st.session_state.update(messages=[], tts_audio={}, covers={}, ctx_by_idx={}))

# --- Admin dataset ---
with st.sidebar.expander("🛠️ Admin dataset", expanded=False):
    st.caption("Adaugă / modifică / șterge cărți și reconstruiește vector store-ul.")

    # INFO: fișier + timestamp + preview
    with st.expander("📄 Dataset info", expanded=True):
        p = Path(settings.DATA_PATH)
        st.markdown("**Fișier folosit:**")
        st.code(str(p.resolve()))
        if p.exists():
            ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime))
            st.markdown(f"**Ultima modificare:** {ts}")
            items = load_items()
            st.markdown(f"**Total item-uri:** {len(items)}")
            if items:
                preview = [{"title": it.get("title",""), "lang": it.get("language",""), "tags": ", ".join(it.get("tags",[]))} for it in items]
                st.table(preview[:10])
        else:
            st.warning("Fișierul nu există încă. Adaugă o carte sau verifică permisiunile/calea.")

    # Re-ingest rapid (buton mereu vizibil)
    if st.button("🧠 Re-ingest (rebuild vector store)", key="reingest_btn"):
        try:
            with st.spinner("Reconstruiesc colecția..."):
                n = ingest_all()
            st.session_state.retriever = Retriever()
            st.session_state.bot = SmartLibrarian()
            st.success(f"Re-ingest complet: {n} item-uri.")
            st.rerun()
        except Exception as e:
            st.error(f"Eroare la re-ingest: {e}")

    # Tabs: Add / Edit / Delete
    tabs = st.tabs(["➕ Adaugă", "✏️ Editează", "🗑️ Șterge"])

    # --- Add ---
    with tabs[0]:
        with st.form("add_book_form", clear_on_submit=False):
            title = st.text_input("Titlu")
            tags_csv_add = st.text_input("Etichete (CSV)", placeholder="prietenie, magie, aventură")
            language_add = st.selectbox("Limbă", ["ro", "en"], index=0, key="add_lang")
            brief_add = st.text_area("Rezumat scurt (3–5 linii)")
            full_add = st.text_area("Rezumat complet", height=180)
            submitted = st.form_submit_button("➕ Adaugă carte")
            if submitted:
                if not title or not brief_add or not full_add:
                    st.error("Completează cel puțin Titlu, Rezumat scurt și Rezumat complet.")
                else:
                    ok, msg = add_book(title, tags_csv_add, brief_add, full_add, language_add)
                    if ok:
                        st.success(msg)
                    else:
                        st.warning(msg)

    # --- Edit ---
    with tabs[1]:
        all_titles = list_books()
        sel_edit = st.selectbox("Alege titlul", ["(selectează)"] + all_titles)
        if sel_edit and sel_edit != "(selectează)":
            existing = get_book(sel_edit)
            if not existing:
                st.warning("Nu am putut încărca cartea selectată.")
            else:
                default_tags = ", ".join(existing.get("tags", []))
                default_lang = existing.get("language", "ro")
                default_brief = existing.get("brief_summary", "")
                default_full  = existing.get("full_summary", "")

                with st.form("edit_book_form", clear_on_submit=False):
                    new_title = st.text_input("Titlu nou", value=existing.get("title", sel_edit))
                    tags_csv  = st.text_input("Etichete (CSV)", value=default_tags, placeholder="prietenie, magie, aventură")
                    language  = st.selectbox("Limbă", ["ro", "en"], index=0 if default_lang=="ro" else 1, key="edit_lang")
                    brief     = st.text_area("Rezumat scurt (3–5 linii)", value=default_brief)
                    full      = st.text_area("Rezumat complet", height=180, value=default_full)
                    submitted = st.form_submit_button("💾 Salvează modificările")
                    if submitted:
                        ok, msg = update_book(sel_edit, new_title, tags_csv, brief, full, language)
                        if ok:
                            st.success(msg)
                        else:
                            st.warning(msg)

    # --- Delete ---
    with tabs[2]:
        all_titles = list_books()
        sel_del = st.selectbox("Alege titlul", ["(selectează)"] + all_titles, key="del_sel")
        if st.button("Șterge cartea", disabled=(sel_del in ("", "(selectează)"))):
            ok, msg = delete_book(sel_del)
            if ok:
                st.success(msg)
            else:
                st.warning(msg)

st.sidebar.caption(
    "Filtrele și opțiunile de mai sus afectează contextul și recomandarea."
)

# --- STT: întrebare vocală (cu guard + citații salvate) ---
st.sidebar.subheader("🎙️ Întrebare vocală (STT)")
audio_up = st.sidebar.file_uploader("Încarcă audio (wav/mp3/m4a)", type=["wav", "mp3", "m4a"])
if st.sidebar.button("Transcrie și întreabă", disabled=(audio_up is None)):
    if audio_up is not None:
        with st.spinner("Transcriu audio..."):
            fd, tmp_path = tempfile.mkstemp(suffix=f"_{audio_up.name}")
            try:
                with os.fdopen(fd, "wb") as tmpf:
                    tmpf.write(audio_up.getvalue())
                with open(tmp_path, "rb") as f:
                    trx = client.audio.transcriptions.create(
                        model="gpt-4o-mini-transcribe",
                        file=f,
                    )
            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            user_q = getattr(trx, "text", None) or getattr(trx, "transcript", None) or ""

    # Guard pe mesajul transcris
    bad, _ = check_inappropriate(user_q or "")
    if bad:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Îți mulțumesc pentru mesaj, dar conține termeni nepotriviți. Te rog reformulează fără limbaj ofensator și reîncearcă."
        })
        st.rerun()

    if user_q.strip():
        st.session_state.messages.append({"role": "user", "content": user_q})

        # Context + filtre pentru acest mesaj (citații)
        ctx = st.session_state.retriever.search(user_q, k=top_k, max_distance=threshold)
        fl = None if flang == "(fără)" else flang
        ft = [t.strip() for t in ftags_csv.split(",") if t.strip()] if ftags_csv else None
        if fl or ft:
            filtered = []
            for r in ctx:
                ok_lang = (not fl) or (r.get("metadata", {}).get("language") == fl)
                ok_tags = True
                if ft:
                    tags_str = str(r.get("metadata", {}).get("tags", "")).lower()
                    ok_tags = all(t.lower() in tags_str for t in ft)
                if ok_lang and ok_tags:
                    filtered.append(r)
            if filtered:
                ctx = filtered

        # Răspuns + stocare context pentru citații
        answer = st.session_state.bot.chat_once(
            user_q,
            filter_language=fl,
            filter_tags=ft,
            override_context=ctx,
        )
        next_idx = len(st.session_state.messages)
        st.session_state.ctx_by_idx[next_idx] = ctx
        st.session_state.messages.append({"role": "assistant", "content": answer})

    st.rerun()

st.title("📚 Smart Librarian (Streamlit)")

def extract_title(text: str) -> str | None:
    m = re.search(r"[\"„](.*?)[\"”]", text)
    return m.group(1).strip() if m else None

# --- istoric + acțiuni per răspuns (TTS, Cover, Citații) ---
client_tts = OpenAI(api_key=settings.OPENAI_API_KEY)

for idx, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

        if m["role"] == "assistant":
            c1, c2, c3 = st.columns([1, 1, 1])

            # TTS
            with c1:
                if st.button("🔊 Ascultă recomandarea", key=f"tts_btn_{idx}"):
                    try:
                        with st.spinner("Generez audio..."):
                            fd, out_path = tempfile.mkstemp(suffix=".mp3")
                            os.close(fd)
                            try:
                                with client_tts.audio.speech.with_streaming_response.create(
                                    model="gpt-4o-mini-tts",
                                    voice="alloy",
                                    input=m["content"],
                                ) as resp:
                                    resp.stream_to_file(out_path)
                                with open(out_path, "rb") as f:
                                    st.session_state.tts_audio[idx] = f.read()
                            finally:
                                try:
                                    os.remove(out_path)
                                except Exception:
                                    pass
                    except Exception as e:
                        st.error(f"Eroare la TTS: {e}")

            if idx in st.session_state.tts_audio:
                st.audio(st.session_state.tts_audio[idx], format="audio/mp3")
                with c2:
                    st.download_button(
                        "⬇️ MP3",
                        data=st.session_state.tts_audio[idx],
                        file_name=f"recomandare_{idx}.mp3",
                        mime="audio/mpeg",
                        key=f"dl_mp3_{idx}",
                    )

            # Cover
            with c3:
                if st.button("🎨 Generează copertă", key=f"cover_btn_{idx}"):
                    try:
                        title_cov = extract_title(m["content"]) or "Suggested Book"
                        with st.spinner(f"Generez coperta pentru: {title_cov} ..."):
                            img_bytes = generate_cover(title_cov)
                            st.session_state.covers[idx] = (title_cov, img_bytes)
                    except Exception as e:
                        st.error(f"Eroare la generarea copertei: {e}")

            if idx in st.session_state.covers:
                title_cov, img_bytes = st.session_state.covers[idx]
                st.image(img_bytes, caption=f"Copertă generată – {title_cov}", use_column_width=True)
                st.download_button(
                    "⬇️ PNG",
                    data=img_bytes,
                    file_name=f"coperta_{idx}.png",
                    mime="image/png",
                    key=f"dl_png_{idx}",
                )

            # Citații (sursele pentru acest răspuns)
            if show_citations and idx in st.session_state.ctx_by_idx:
                ctx_used = st.session_state.ctx_by_idx[idx]
                if ctx_used:
                    with st.expander("📚 Surse folosite la acest răspuns"):
                        for j, r in enumerate(ctx_used, start=1):
                            md = r.get("metadata", {})
                            title = md.get("title", "N/A")
                            tags = md.get("tags", "")
                            dist = r.get("distance")
                            dist_str = f"{dist:.3f}" if isinstance(dist, (int, float)) else "n/a"
                            st.markdown(f"**[{j}] {title}** — _tags: {tags}_ — dist: {dist_str}")
                            st.code(r.get("document", ""), language="markdown")

# --- prompt text curent (cu guard + citații) ---
prompt = st.chat_input("Întreabă despre o carte, temă, gen etc.")
if prompt:
    # Guard pe inputul text
    bad, _ = check_inappropriate(prompt)
    if bad:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Îți mulțumesc pentru mesaj, dar conține termeni nepotriviți. Te rog reformulează fără limbaj ofensator și reîncearcă."
        })
        st.rerun()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Context + filtre pentru acest mesaj (citații)
    ctx = st.session_state.retriever.search(prompt, k=top_k, max_distance=threshold)
    fl = None if flang == "(fără)" else flang
    ft = [t.strip() for t in ftags_csv.split(",") if t.strip()] if ftags_csv else None
    if fl or ft:
        filtered = []
        for r in ctx:
            ok_lang = (not fl) or (r.get("metadata", {}).get("language") == fl)
            ok_tags = True
            if ft:
                tags_str = str(r.get("metadata", {}).get("tags", "")).lower()
                ok_tags = all(t.lower() in tags_str for t in ft)
            if ok_lang and ok_tags:
                filtered.append(r)
        if filtered:
            ctx = filtered

    # Răspuns + stocăm contextul pentru citații la indexul asistentului
    answer = st.session_state.bot.chat_once(
        prompt,
        filter_language=fl,
        filter_tags=ft,
        override_context=ctx,
    )
    next_idx = len(st.session_state.messages)
    st.session_state.ctx_by_idx[next_idx] = ctx

    st.session_state.messages.append({"role": "assistant", "content": answer})
    with st.chat_message("assistant"):
        st.markdown(answer)
        if show_context:
            with st.expander("Context RAG (rezultate pentru promptul curent)"):
                for r in ctx:
                    md = r["metadata"]
                    title = md.get("title", "N/A")
                    tags = md.get("tags", "")
                    dist = r.get("distance")
                    dist_str = f"{dist:.3f}" if isinstance(dist, (int, float)) else "n/a"
                    st.markdown(f"**{title}** — _dist: {dist_str}_")
                    st.code(r["document"], language="markdown")

    st.rerun()
