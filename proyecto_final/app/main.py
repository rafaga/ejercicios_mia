"""API FastAPI: /health, /ingest, /query.  Arranque: uvicorn app.main:app --port 8000"""
import io
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

from app.chunk import chunk_text  # noqa: E402
from app.citations import apply_intext, build_refs, cited_numbers, meta_available  # noqa: E402
from app.generate import NO_EVIDENCE, LLMConfigError, generate, llm_info, related_questions  # noqa: E402
from app.retrieval import SPARSE_PATHS, retriever  # noqa: E402
from app.verify import normalize_citations, verify_answer  # noqa: E402

KEY_VARS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "opencode": "OPENCODE_API_KEY"}
log = logging.getLogger("uvicorn.error")
MIN_SCORE = float(os.getenv("MIN_SCORE", "0.2"))  # abstención: el MEJOR chunk debe superarlo (score reranker 0-1)
MIN_CHUNK_SCORE = float(os.getenv("MIN_CHUNK_SCORE", "0.02"))  # solo los chunks que lo superan se envían al LLM
SUPPORT_MIN_SCORE = float(os.getenv("SUPPORT_MIN_SCORE", "0.01"))  # respaldo mínimo oración<->chunk citado
STRICT_GROUNDING = os.getenv("STRICT_GROUNDING", "1") not in ("0", "false", "False")
RELATED_N = int(os.getenv("RELATED_N", "3"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "250"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
ABSTAIN = "No tengo evidencia suficiente en el corpus para responder esa pregunta."


def _warmup():
    try:
        retriever.load()
    except Exception as e:  # se reporta en /health
        retriever.error = f"{type(e).__name__}: {e}"


@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=_warmup, daemon=True).start()
    yield


app = FastAPI(title="RAG arXiv cs.AI", version="2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8501"], allow_methods=["*"], allow_headers=["*"])


class RelatedIn(BaseModel):
    question: str = Field(..., min_length=1)
    chunks: list[dict]  # los chunks recuperados que devolvió /query (source, title, text)
    session_id: Optional[str] = None


class QueryIn(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(10, ge=10, le=50, description="Chunks recuperados (mínimo 10)")
    mode: Literal["dense", "hybrid_bm25", "hybrid_bge"] = "hybrid_bm25"
    session_id: Optional[str] = None  # id de conversación (lo usa OpenCode para enrutar/cachear)


def _ready():
    if retriever.error:
        raise HTTPException(503, f"Error cargando el índice: {retriever.error}")
    if not retriever.ready:
        raise HTTPException(503, "El índice aún se está cargando, reintenta en unos segundos.")


@app.get("/health")
def health():
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    info = {"api": "ok", "ready": retriever.ready, "error": retriever.error}
    if retriever.ready:
        info.update(
            arxiv_docs=retriever.arxiv.count(),
            uploaded_chunks=retriever.uploads.count(),
            modes={m: True for m in ("dense",)} | {k: os.path.exists(v) for k, v in SPARSE_PATHS.items()},
            sparse_loaded=list(retriever.sparse),
            llm_provider=provider,
            llm_key_var=KEY_VARS.get(provider, "?"),
            llm_key_configured=bool(os.getenv(KEY_VARS.get(provider, ""))),
            apa_metadata=meta_available(),
        )
    return info


def _read(name: str, data: bytes) -> str:
    if name.lower().endswith(".pdf"):
        from pypdf import PdfReader

        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
    return data.decode("utf-8", errors="ignore")


@app.post("/ingest")
async def ingest(files: list[UploadFile] = File(...)):
    _ready()
    docs = chunks = 0
    skipped = []
    for f in files:
        text = _read(f.filename or "doc", await f.read()).strip()
        parts = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
        if not parts:
            skipped.append(f.filename)
            continue
        retriever.add_chunks(
            ids=[f"up:{f.filename}:{i}" for i in range(len(parts))],
            texts=parts,
            metas=[{"source": f.filename, "title": f.filename, "chunk_index": i} for i in range(len(parts))],
        )
        docs += 1
        chunks += len(parts)
    return {"documents_indexed": docs, "chunks_indexed": chunks, "skipped_empty": skipped}


def _abstain(hits, why, base, extra=None):
    return {"answer": ABSTAIN, "abstained": True, "citations": hits, "references": [], "related_questions": [],
            "llm": {"called": bool(extra), "reason": why, **base, **(extra or {})}}


@app.post("/query")
def query(body: QueryIn):
    _ready()
    q = body.question.strip()
    if not q:
        raise HTTPException(422, "La pregunta está en blanco.")
    t0 = time.time()
    hits = retriever.search(q, top_k=body.top_k, mode=body.mode)
    top = hits[0]["score"] if hits else None
    base = {"mode": body.mode, "top_score": top, "min_score": MIN_SCORE, "min_chunk_score": MIN_CHUNK_SCORE,
            "search_seconds": round(time.time() - t0, 2)}

    if not hits or top < MIN_SCORE:
        log.info("QUERY %r mode=%s top=%s < MIN_SCORE=%s -> abstencion, LLM NO llamado", q[:60], body.mode, top, MIN_SCORE)
        for h in hits:
            h["sent_to_llm"] = False
        return _abstain(hits, "score por debajo de MIN_SCORE", base)

    # Solo los chunks con score suficiente se envían al LLM (numerados 1..M)
    ctx = [h for h in hits if h["score"] >= MIN_CHUNK_SCORE] or hits[:1]
    sent = {h["id"]: n for n, h in enumerate(ctx, 1)}
    for h in hits:
        h["sent_to_llm"] = h["id"] in sent
        h["ref_n"] = sent.get(h["id"])

    info = llm_info()
    log.info("QUERY %r mode=%s top=%s chunks_al_LLM=%d/%d -> %s/%s", q[:60], body.mode, top, len(ctx), len(hits),
             info["provider"], info["model"])
    t1 = time.time()
    try:
        answer = generate(q, ctx, body.session_id)
    except LLMConfigError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        log.error("LLM fallo: %s", e)
        raise HTTPException(502, f"Falló la generación con el LLM: {e}")
    t_llm = round(time.time() - t1, 2)
    if not answer.strip():
        raise HTTPException(502, "El LLM devolvió una respuesta vacía (un modelo de razonamiento puede gastar todos los "
                                 "tokens pensando): sube LLM_MAX_TOKENS en .env o prueba otro LLM_MODEL.")
    raw = answer
    answer = normalize_citations(answer)
    log.info("Respuesta cruda del LLM (primeros 300 car.): %r", raw[:300])
    llm = {"called": True, **info, "llm_seconds": t_llm, **base, "chunks_sent": len(ctx), "raw_answer": raw[:6000]}

    if NO_EVIDENCE in answer:
        log.info("LLM respondio NO_EVIDENCE en %ss", t_llm)
        return _abstain(hits, "el LLM dijo NO_EVIDENCE", base, {**llm})

    # Verificación: cada oración debe citar un chunk que realmente la respalde (reranker)
    v = verify_answer(answer, [c["text"] for c in ctx],
                      lambda pairs: retriever.reranker.predict(pairs), SUPPORT_MIN_SCORE, STRICT_GROUNDING)
    llm.update(kept_sentences=v["kept"], removed_sentences=v["removed"])
    log.info("LLM %ss | oraciones respaldadas=%d, eliminadas=%d", t_llm, v["kept"], len(v["removed"]))
    if v["kept"] == 0:
        return _abstain(hits, "ninguna oración quedó respaldada por las referencias", base, {**llm})

    # [n] -> citas APA enlazadas + lista de referencias solo de lo citado
    refs = build_refs(ctx, cited_numbers(v["text"]))
    text = apply_intext(v["text"], refs)
    for n, r in refs.items():
        hits[[h["id"] for h in hits].index(ctx[n - 1]["id"])]["cited_as"] = f"{r['label']}, {r['year']}"
    references = [{"label": f"{r['label']}, {r['year']}", "apa": r["apa"], "url": r["url"], "id": ctx[n - 1]["id"]}
                  for n, r in sorted(refs.items(), key=lambda kv: kv[1]["sort"])]
    return {"answer": text, "abstained": False, "citations": hits, "references": references,
            "related_questions": [], "llm": llm}


@app.post("/related")
def related(body: RelatedIn):
    """Temas afines a demanda (una llamada al LLM solo cuando el usuario la pide)."""
    chunks = [{"source": c.get("source", ""), "title": c.get("title", ""), "text": c.get("text", "")}
              for c in body.chunks[:15]]
    try:
        return {"related_questions": related_questions(body.question, chunks, RELATED_N, body.session_id)}
    except LLMConfigError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(502, f"Falló la generación de temas afines: {e}")
