#!/usr/bin/env python3
"""
Construye un índice BM25 (búsqueda léxica/sparse) a partir de los documentos
que ya cargaste en una colección de Chroma con build_arxiv_chroma.py, para
usarlo como parte de un pipeline híbrido de RAG (dense + sparse).

BM25 es puramente estadístico (frecuencia de términos), no un modelo
neuronal: no necesita GPU ni descargar nada, y no vuelve a tocar los
embeddings densos de BGE-M3 que ya generaste. Solo lee el texto de los
documentos directo de la colección de Chroma.

Requisitos:
    pip install rank_bm25 chromadb tqdm

Uso:
    # 1. Construir el índice (lee los documentos directo de tu colección Chroma)
    python build_bm25_index.py \
        --persist-dir ./chroma_db \
        --collection-name arxiv_abstracts \
        --output ./bm25_index.pkl

    # 2. Probarlo con una consulta (puedes recargar el índice ya guardado)
    python build_bm25_index.py --load ./bm25_index.pkl --query "vector databases for machine learning"
"""

import argparse
import pickle
import re

import chromadb
from rank_bm25 import BM25Okapi
from tqdm import tqdm


def tokenize(text: str):
    """Tokenización simple: minúsculas + separar en palabras (sin puntuación)."""
    return re.findall(r"\w+", text.lower())


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--persist-dir",
        default="./chroma_db",
        help="Carpeta de la base Chroma de la que se leen los documentos (default: ./chroma_db)",
    )
    p.add_argument(
        "--collection-name",
        default="arxiv_abstracts",
        help="Nombre de la colección en Chroma (default: arxiv_abstracts)",
    )
    p.add_argument(
        "--output",
        default="./bm25_index.pkl",
        help="Ruta donde guardar el índice BM25 construido (default: ./bm25_index.pkl)",
    )
    p.add_argument(
        "--load",
        default=None,
        help="En vez de reconstruirlo, carga un índice ya guardado desde esta ruta",
    )
    p.add_argument("--query", default=None, help="Si se especifica, corre una consulta de prueba contra el índice")
    p.add_argument("--top-k", type=int, default=5, help="Resultados a mostrar en la consulta de prueba (default: 5)")
    return p.parse_args()


def get_all_documents(collection, page_size: int = 300):
    """
    Trae todos los documentos de la colección en páginas (limit/offset) en
    vez de una sola llamada a get(). Con colecciones grandes, un get() sin
    paginar puede toparse con el límite de variables de SQLite que usa
    Chroma por debajo ("too many SQL variables").
    """
    total = collection.count()
    ids, documents, metadatas = [], [], []
    for offset in tqdm(range(0, total, page_size), desc="Leyendo de Chroma (paginado)"):
        batch = collection.get(limit=page_size, offset=offset, include=["documents", "metadatas"])
        ids.extend(batch["ids"])
        documents.extend(batch["documents"])
        metadatas.extend(batch["metadatas"])
    return ids, documents, metadatas


def load_documents_from_chroma(persist_dir: str, collection_name: str):
    """
    Lee todos los documentos (texto + metadata + ids) directo de la colección
    de Chroma. No necesita la función de embeddings (BGE-M3): collection.get()
    solo lee lo que ya está guardado, no genera vectores nuevos.
    """
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_collection(name=collection_name)

    total = collection.count()
    print(f"Leyendo {total} documentos de la colección '{collection_name}'...")

    return get_all_documents(collection)


def build_bm25(documents):
    tokenized_corpus = [tokenize(doc) for doc in tqdm(documents, desc="Tokenizando")]
    print("Construyendo índice BM25...")
    return BM25Okapi(tokenized_corpus)


def save_index(path: str, bm25, ids, documents, metadatas):
    with open(path, "wb") as f:
        pickle.dump({"bm25": bm25, "ids": ids, "documents": documents, "metadatas": metadatas}, f)
    print(f"Índice guardado en '{path}'")


def load_index(path: str):
    with open(path, "rb") as f:
        data = pickle.load(f)
    return data["bm25"], data["ids"], data["documents"], data["metadatas"]


def query_index(bm25, ids, documents, metadatas, query: str, top_k: int):
    scores = bm25.get_scores(tokenize(query))
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    print(f"\nConsulta BM25: {query!r}\n")
    for rank, i in enumerate(ranked, 1):
        meta = metadatas[i] or {}
        print(f"{rank}. [score={scores[i]:.3f}] {meta.get('title', ids[i])}")
        print(f"   Categorías: {meta.get('categories', '')}")
        print(f"   Abstract: {documents[i][:200]}...\n")


def main():
    args = parse_args()

    if args.load:
        bm25, ids, documents, metadatas = load_index(args.load)
        print(f"Índice cargado desde '{args.load}' ({len(ids)} documentos)")
    else:
        ids, documents, metadatas = load_documents_from_chroma(args.persist_dir, args.collection_name)
        if not documents:
            print("La colección está vacía. Corre primero build_arxiv_chroma.py.")
            return
        bm25 = build_bm25(documents)
        save_index(args.output, bm25, ids, documents, metadatas)

    if args.query:
        query_index(bm25, ids, documents, metadatas, args.query, args.top_k)


if __name__ == "__main__":
    main()