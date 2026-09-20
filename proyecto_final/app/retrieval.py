"""Recuperación híbrida sobre lo que ya construiste: Chroma (BGE-M3 denso) + índice sparse
(.pkl de BM25 o BGE-M3) -> RRF -> reranker. Reutiliza .chroma_db sin modificarlo."""
import os
import pickle
import re
import threading
from pathlib import Path

import chromadb
import numpy as np
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

BASE = Path(__file__).resolve().parent.parent
CHROMA_DIR = os.getenv("CHROMA_DIR", str(BASE / ".chroma_db"))
ARXIV_COLLECTION = os.getenv("ARXIV_COLLECTION", "arxiv_abstracts")
UPLOAD_COLLECTION = os.getenv("UPLOAD_COLLECTION", "user_docs")
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-m3")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
SPARSE_PATHS = {
    "bm25": os.getenv("BM25_INDEX", str(BASE / "bm25_index.pkl")),
    "bge": os.getenv("BGE_SPARSE_INDEX", str(BASE / "bge_sparse_index.pkl")),
}
MODES = ("dense", "hybrid_bm25", "hybrid_bge")


def _tok(text):
    return re.findall(r"\w+", text.lower())


def _device():
    d = os.getenv("DEVICE")
    if d:
        return d
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class Retriever:
    def __init__(self):
        self.lock = threading.Lock()
        self.ready = False
        self.error = None
        self.upload_bm25 = None  # (bm25, ids) cache de los documentos subidos

    def load(self):
        with self.lock:
            if self.ready:
                return
            dev = _device()
            self.embedder = SentenceTransformerEmbeddingFunction(
                model_name=EMBED_MODEL, device=dev, normalize_embeddings=True
            )
            self.client = chromadb.PersistentClient(path=CHROMA_DIR)
            self.arxiv = self.client.get_collection(ARXIV_COLLECTION, embedding_function=self.embedder)
            self.uploads = self.client.get_or_create_collection(
                UPLOAD_COLLECTION, embedding_function=self.embedder, metadata={"hnsw:space": "cosine"}
            )
            self.device = dev
            self.sparse = {}  # carga perezosa por backend
            self.m3 = None
            from sentence_transformers import CrossEncoder

            self.reranker = CrossEncoder(RERANKER_MODEL, device=dev, trust_remote_code=True)
            self.ready = True

    def embed(self, texts):
        return [list(map(float, v)) for v in self.embedder(texts)]

    # ---- sparse ----
    def _get_sparse(self, backend):
        with self.lock:
            if backend not in self.sparse:
                with open(SPARSE_PATHS[backend], "rb") as f:
                    self.sparse[backend] = pickle.load(f)
                if backend == "bge" and self.m3 is None:
                    from FlagEmbedding import BGEM3FlagModel

                    name = self.sparse["bge"]["model_name"]
                    self.m3 = BGEM3FlagModel(name, use_fp16=(self.device != "cpu"), device=self.device)
            return self.sparse[backend]

    def _sparse_arxiv(self, q, k, backend):
        data = self._get_sparse(backend)
        if backend == "bge":
            w = self.m3.encode([q], return_dense=False, return_sparse=True, return_colbert_vecs=False)["lexical_weights"][0]
            scores = np.array([self.m3.compute_lexical_matching_score(w, d) for d in data["sparse_weights"]])
        else:
            scores = np.asarray(data["bm25"].get_scores(_tok(q)))
        idx = np.argsort(-scores)[:k]
        return [data["ids"][i] for i in idx]

    def _sparse_uploads(self, q, k):
        if self.uploads.count() == 0:
            return []
        if self.upload_bm25 is None:
            from rank_bm25 import BM25Okapi

            data = self.uploads.get(include=["documents"])
            self.upload_bm25 = (BM25Okapi([_tok(d) for d in data["documents"]]), data["ids"])
        bm25, ids = self.upload_bm25
        idx = np.argsort(-np.asarray(bm25.get_scores(_tok(q))))[:k]
        return [ids[i] for i in idx]

    # ---- búsqueda ----
    def search(self, q, top_k=10, mode="hybrid_bm25", dense_k=None, sparse_k=None, pool=None, rrf_k=60):
        dense_k = dense_k or max(30, top_k * 2)
        sparse_k = sparse_k or max(30, top_k * 2)
        pool = pool or max(40, top_k * 2)
        if mode not in MODES:
            raise ValueError(f"mode debe ser uno de {MODES}")
        qv = self.embed([q])[0]
        cands, dense_ranks = {}, []
        for col in (self.arxiv, self.uploads):
            if col.count() == 0:
                continue
            r = col.query(query_embeddings=[qv], n_results=dense_k, include=["documents", "metadatas"])
            for i, d, m in zip(r["ids"][0], r["documents"][0], r["metadatas"][0]):
                cands[i] = (d, m or {})
                dense_ranks.append(i)
        sparse_ranks = []
        if mode != "dense":
            backend = "bge" if mode == "hybrid_bge" else "bm25"
            sparse_ranks = self._sparse_arxiv(q, sparse_k, backend) + self._sparse_uploads(q, sparse_k)

        fused = {}
        for ranking in (dense_ranks, sparse_ranks):
            for rank, i in enumerate(ranking):
                fused[i] = fused.get(i, 0.0) + 1.0 / (rrf_k + rank + 1)
        pool_ids = [i for i, _ in sorted(fused.items(), key=lambda x: -x[1])[:pool]]

        # ids que solo salieron del sparse: se resuelven desde Chroma
        for col, pref in ((self.uploads, True), (self.arxiv, False)):
            miss = [i for i in pool_ids if i not in cands and i.startswith("up:") == pref]
            if miss:
                r = col.get(ids=miss, include=["documents", "metadatas"])
                for i, d, m in zip(r["ids"], r["documents"], r["metadatas"]):
                    cands[i] = (d, m or {})
        pool_ids = [i for i in pool_ids if i in cands]
        if not pool_ids:
            return []
        scores = self.reranker.predict([(q, cands[i][0]) for i in pool_ids])
        ranked = sorted(zip(pool_ids, scores), key=lambda x: -float(x[1]))[:top_k]
        out = []
        for i, s in ranked:
            text, meta = cands[i]
            is_up = "source" in meta
            out.append(
                {
                    "id": i,
                    "source": meta["source"] if is_up else f"arXiv:{i}",
                    "title": meta.get("title", ""),
                    "text": text,
                    "score": round(float(s), 4),
                    "url": None if is_up else f"https://arxiv.org/abs/{i}",
                }
            )
        return out

    def add_chunks(self, ids, texts, metas, batch=32):
        for s in range(0, len(texts), batch):
            self.uploads.upsert(
                ids=ids[s : s + batch],
                documents=texts[s : s + batch],
                embeddings=self.embed(texts[s : s + batch]),
                metadatas=metas[s : s + batch],
            )
        self.upload_bm25 = None


retriever = Retriever()
