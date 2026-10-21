"""UI Streamlit: cliente HTTP de FastAPI. Arranque: streamlit run ui/streamlit_app.py"""
import uuid

import httpx
import streamlit as st

st.set_page_config(page_title="RAG arXiv cs.AI", layout="wide")
API = st.sidebar.text_input("URL de la API", "http://localhost:8000")
st.session_state.setdefault("history", [])
st.session_state.setdefault("sid", str(uuid.uuid4()))
st.session_state.setdefault("pending", None)


def call(method, path, **kw):
    try:
        r = httpx.request(method, API + path, timeout=kw.pop("timeout", 180), **kw)
    except httpx.ConnectError:
        st.error("No se pudo conectar con la API. ¿Está corriendo `uvicorn app.main:app --port 8000`?")
        return None
    if r.status_code >= 400:
        detail = r.json().get("detail", r.text) if r.headers.get("content-type", "").startswith("application/json") else r.text
        st.error(f"Error {r.status_code}: {detail}")
        return None
    return r.json()


def ask_related(question):
    """Callback de los botones de preguntas relacionadas: pone la pregunta y la lanza en el siguiente ciclo."""
    st.session_state.q_input = question
    st.session_state.pending = question


st.title("RAG sobre arXiv cs.AI")

with st.sidebar:
    h = call("GET", "/health", timeout=5)
    if h:
        if h["ready"]:
            st.success(f"API lista · {h['arxiv_docs']:,} abstracts · {h['uploaded_chunks']} chunks subidos")
            if "llm_key_var" not in h:
                st.warning("La API está corriendo una versión anterior del código: reinicia uvicorn.")
            elif not h["llm_key_configured"]:
                st.warning(f"Falta {h['llm_key_var']} en .env (LLM_PROVIDER={h['llm_provider']}).")
            else:
                st.caption(f"LLM: {h['llm_provider']}")
            if h.get("apa_metadata") is False:
                st.warning("Sin arxiv_meta.sqlite: las referencias APA saldrán sin autores ni año. Ejecuta build_arxiv_meta_index.py.")
        else:
            st.info(h["error"] or "Cargando modelos e índices…")
    st.header("Cargar documentos")
    files = st.file_uploader("txt / md / pdf", accept_multiple_files=True, type=["txt", "md", "pdf"])
    if st.button("Indexar", disabled=not files):
        res = call("POST", "/ingest", files=[("files", (f.name, f.getvalue())) for f in files], timeout=600)
        if res:
            st.success(f"{res['documents_indexed']} documentos, {res['chunks_indexed']} chunks indexados")
            if res["skipped_empty"]:
                st.warning(f"Sin texto (omitidos): {res['skipped_empty']}")
    top_k = st.slider("Chunks a recuperar (top_k)", 10, 30, 10)
    MODES = {
        "Híbrido: BM25 + embeddings": "hybrid_bm25",
        "Híbrido: BGE-M3 sparse + embeddings": "hybrid_bge",
        "Solo embeddings (denso)": "dense",
    }
    mode = MODES[st.radio("Tipo de recuperación", list(MODES))]
    st.caption("El reranker se aplica en los tres modos; su score decide la abstención.")


def run_query(question):
    with st.spinner("Buscando, generando y verificando citas…"):
        res = call("POST", "/query", json={"question": question, "top_k": top_k, "mode": mode,
                                           "session_id": st.session_state.sid})
    if res:
        st.session_state.history.insert(0, (question, res))


q = st.text_input("Pregunta", key="q_input")
if st.button("Preguntar", type="primary"):
    if not q.strip():
        st.warning("Escribe una pregunta.")
    else:
        run_query(q)
if st.session_state.pending:
    pending, st.session_state.pending = st.session_state.pending, None
    run_query(pending)

for idx, (question, res) in enumerate(st.session_state.history):
    llm = res.get("llm") or {}
    st.markdown(f"### {question}")
    st.caption(f"Modo: {llm.get('mode') or res.get('mode', '?')}")
    (st.warning if res["abstained"] else st.success)(res["answer"])
    if llm.get("called"):
        extra = f" · {llm['chunks_sent']} de {len(res['citations'])} chunks enviados al LLM" if "chunks_sent" in llm else ""
        st.caption(f"LLM llamado: {llm['provider']}/{llm['model']} · {llm['llm_seconds']} s · búsqueda {llm['search_seconds']} s · mejor score {llm['top_score']}{extra}")
        rem = llm.get("removed_sentences") or []
        if rem:
            with st.expander(f"Oraciones eliminadas por falta de respaldo ({len(rem)})"):
                for r in rem:
                    st.markdown(f"- *{r['reason']}* (score {r['score']}): {r['sentence']}")
        if res["abstained"] and llm.get("raw_answer"):
            st.caption(f"Motivo de la abstención: {llm.get('reason')}")
            with st.expander("Respuesta cruda del LLM (diagnóstico)"):
                st.text(llm["raw_answer"])
    elif llm:
        st.caption(f"LLM NO llamado ({llm.get('reason')}): mejor score {llm.get('top_score')} < MIN_SCORE {llm.get('min_score')}")

    if res.get("references"):
        st.markdown("#### Referencias")
        for ref in res["references"]:
            st.markdown(f"- {ref['apa']}")

    if res.get("related_questions"):
        st.markdown("#### Temas afines")
        for j, rq in enumerate(res["related_questions"]):
            st.button(rq, key=f"rel-{idx}-{j}", on_click=ask_related, args=(rq,))
    elif not res["abstained"]:
        if st.button("Sugerir temas afines", key=f"sug-{idx}"):
            with st.spinner("Buscando temas afines…"):
                rel = call("POST", "/related", json={"question": question, "chunks": res["citations"],
                                                     "session_id": st.session_state.sid})
            if rel:
                res["related_questions"] = rel["related_questions"] or []
                if not res["related_questions"]:
                    st.info("No se pudieron generar temas afines esta vez.")
                else:
                    st.rerun()

    with st.expander(f"Chunks recuperados ({len(res['citations'])})"):
        for c in res["citations"]:
            sent = "✅ enviado al LLM" if c.get("sent_to_llm") else f"⛔ no enviado (score < {llm.get('min_chunk_score')})"
            cited = f" · citado como *{c['cited_as']}*" if c.get("cited_as") else ""
            st.markdown(f"**{c['source']}** {('· ' + c['title']) if c['title'] else ''} · score `{c['score']}` · {sent}{cited}")
            if c.get("url"):
                st.markdown(c["url"])
            st.write(c["text"])
