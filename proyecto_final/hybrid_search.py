#!/usr/bin/env python3
"""
Búsqueda híbrida (dense + sparse) con reranking opcional, combinando lo que
ya construiste con:
  - build_arxiv_chroma.py     -> embeddings densos (BGE-M3) en Chroma
  - build_bm25_index.py       -> índice léxico/sparse BM25 (estadístico), o
  - build_bge_sparse_index.py -> índice sparse "nativo" de BGE-M3 (aprendido)

El script detecta solo con el archivo de --sparse-index cuál de los dos
generaste (mira el campo "backend" guardado en el pickle), así que sirve
para cualquiera de los dos sin flags extra.

Los dos rankings (dense y sparse) se combinan con Reciprocal Rank Fusion
(RRF), y si pasas --rerank, los candidatos fusionados se reordenan con un
cross-encoder reranker (BAAI/bge-reranker-v2-m3 por defecto) antes del
resultado final. Este es el pipeline que recomienda la documentación
oficial de BGE: dense + sparse -> fusión -> reranking.

Requisitos:
    pip install chromadb sentence-transformers
    # y además, según qué índice sparse hayas construido:
    pip install rank_bm25        # si usas build_bm25_index.py
    pip install FlagEmbedding    # si usas build_bge_sparse_index.py

Uso:
    # Solo híbrido (dense + sparse, sin reranker)
    python hybrid_search.py --query "vector databases for RAG" --sparse-index ./bm25_index.pkl

    # Híbrido + reranker (más lento, más preciso), con el sparse nativo de BGE-M3
    python hybrid_search.py --query "vector databases for RAG" \
        --sparse-index ./bge_sparse_index.pkl --rerank --device mps

Nota: --embedding-model debe ser el mismo que usaste al construir la
colección con build_arxiv_chroma.py (default: BAAI/bge-m3), porque hay que
generar el embedding de la consulta con el mismo modelo que los documentos.
"""

import argparse
import pickle
import re

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


def tokenize(text: str):
    """Misma tokenización simple que usa build_bm25_index.py."""
    return re.findall(r"\w+", text.lower())


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--query", required=True, help="Consulta de búsqueda")

    # Lado dense (Chroma)
    p.add_argument("--persist-dir", default="./chroma_db", help="Carpeta de la base Chroma (default: ./chroma_db)")
    p.add_argument("--collection-name", default="arxiv_abstracts", help="Colección en Chroma (default: arxiv_abstracts)")
    p.add_argument(
        "--embedding-model",
        default="BAAI/bge-m3",
        help="Modelo de embeddings, debe coincidir con el usado al indexar (default: BAAI/bge-m3)",
    )
    p.add_argument("--dense-k", type=int, default=20, help="Candidatos dense antes de fusionar (default: 20)")

    # Lado sparse (BM25 o nativo de BGE-M3, se detecta automáticamente)
    p.add_argument(
        "--sparse-index",
        default="./bm25_index.pkl",
        help="Índice sparse generado por build_bm25_index.py o build_bge_sparse_index.py (default: ./bm25_index.pkl)",
    )
    p.add_argument("--sparse-k", type=int, default=20, help="Candidatos sparse antes de fusionar (default: 20)")

    # Fusión
    p.add_argument("--rrf-k", type=int, default=60, help="Constante k de Reciprocal Rank Fusion (default: 60)")
    p.add_argument("--top-n", type=int, default=5, help="Resultados finales a mostrar (default: 5)")

    # Reranking (opcional)
    p.add_argument("--rerank", action="store_true", help="Reordena los candidatos fusionados con un cross-encoder")
    p.add_argument(
        "--reranker-model",
        default="BAAI/bge-reranker-v2-m3",
        help="Modelo cross-encoder para reranking (default: BAAI/bge-reranker-v2-m3)",
    )
    p.add_argument(
        "--rerank-pool",
        type=int,
        default=20,
        help="Candidatos fusionados que se pasan al reranker, antes de quedarnos con --top-n (default: 20)",
    )

    p.add_argument(
        "--device",
        default="cpu",
        help="Dispositivo para los modelos (embeddings y/o reranker): cpu, cuda o mps (default: cpu)",
    )
    return p.parse_args()


def dense_search(query, persist_dir, collection_name, embedding_model, device, k):
    embedding_fn = SentenceTransformerEmbeddingFunction(
        model_name=embedding_model, device=device, normalize_embeddings=True
    )
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_collection(name=collection_name, embedding_function=embedding_fn)
    results = collection.query(query_texts=[query], n_results=k)
    return results["ids"][0]  # ya vienen ordenados por similitud (más cercano primero)


def sparse_search(query, sparse_data, k, device):
    """
    Despacha según el 'backend' guardado en el pickle:
      - "bm25" (o ausente, por compatibilidad con índices viejos de
        build_bm25_index.py): BM25 estadístico clásico.
      - "bge_sparse" (de build_bge_sparse_index.py): pesos léxicos
        aprendidos por el propio BGE-M3, vía FlagEmbedding.
    """
    backend = sparse_data.get("backend", "bm25")

    if backend == "bge_sparse":
        from FlagEmbedding import BGEM3FlagModel

        model_name = sparse_data["model_name"]
        print(f"Cargando '{model_name}' para el sparse nativo de BGE-M3 (puede tardar la primera vez)...")
        model = BGEM3FlagModel(model_name, use_fp16=(device != "cpu"), device=device)
        query_weights = model.encode([query], return_dense=False, return_sparse=True, return_colbert_vecs=False)[
            "lexical_weights"
        ][0]
        scores = [
            model.compute_lexical_matching_score(query_weights, doc_weights)
            for doc_weights in sparse_data["sparse_weights"]
        ]
    else:
        scores = sparse_data["bm25"].get_scores(tokenize(query))

    ranked_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [sparse_data["ids"][i] for i in ranked_idx]


def reciprocal_rank_fusion(dense_ids, sparse_ids, k=60):
    """
    RRF: cada documento suma 1/(k + rank) por cada ranking en el que aparece.
    No mezcla escalas de score distintas (cosine vs BM25), solo posiciones,
    que es justo lo que hace falta para combinar dos métodos incomparables.
    """
    scores = {}
    for rank, doc_id in enumerate(dense_ids):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    for rank, doc_id in enumerate(sparse_ids):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def rerank(query, candidate_ids, id_to_doc, reranker_model, device):
    from sentence_transformers import CrossEncoder

    print(f"Cargando reranker '{reranker_model}' (puede tardar la primera vez)...")
    model = CrossEncoder(reranker_model, device=device, trust_remote_code=True)
    pairs = [(query, id_to_doc[doc_id]["document"]) for doc_id in candidate_ids]
    scores = model.predict(pairs)
    return sorted(zip(candidate_ids, scores), key=lambda x: x[1], reverse=True)


def print_results(query, final, id_to_doc, score_label):
    print(f"\nResultados finales para {query!r} (top {len(final)}, ordenados por {score_label}):\n")
    for rank, (doc_id, score) in enumerate(final, 1):
        info = id_to_doc.get(doc_id, {})
        meta = info.get("metadata", {}) or {}
        doc = info.get("document", "")
        print(f"{rank}. [{score_label}={float(score):.4f}] {meta.get('title', doc_id)}")
        print(f"   Categorías: {meta.get('categories', '')}")
        print(f"   Abstract: {doc[:200]}...\n")


def main():
    args = parse_args()

    with open(args.sparse_index, "rb") as f:
        sparse_data = pickle.load(f)
    backend = sparse_data.get("backend", "bm25")
    id_to_doc = {
        id_: {"document": doc, "metadata": meta}
        for id_, doc, meta in zip(sparse_data["ids"], sparse_data["documents"], sparse_data["metadatas"])
    }

    print(f"Buscando (dense/BGE-M3) top {args.dense_k}...")
    dense_ids = dense_search(
        args.query, args.persist_dir, args.collection_name, args.embedding_model, args.device, args.dense_k
    )

    print(f"Buscando (sparse, backend='{backend}') top {args.sparse_k}...")
    sparse_ids = sparse_search(args.query, sparse_data, args.sparse_k, args.device)

    fused = reciprocal_rank_fusion(dense_ids, sparse_ids, k=args.rrf_k)
    print(f"{len(fused)} candidatos únicos tras la fusión (dense ∪ sparse)")

    if args.rerank:
        pool_ids = [doc_id for doc_id, _ in fused[: args.rerank_pool]]
        final = rerank(args.query, pool_ids, id_to_doc, args.reranker_model, args.device)[: args.top_n]
        score_label = "reranker score"
    else:
        final = fused[: args.top_n]
        score_label = "RRF score"

    print_results(args.query, final, id_to_doc, score_label)


if __name__ == "__main__":
    main()