#!/usr/bin/env python3
"""
Construye el índice sparse "nativo" de BGE-M3 (pesos léxicos aprendidos por
la propia red neuronal), a diferencia de build_bm25_index.py que usa BM25
estadístico clásico.

BGE-M3 es "multi-functionality": el mismo forward pass puede devolver tres
representaciones (dense, sparse/léxico, y multi-vector ColBERT). Aquí solo
pedimos la parte sparse, usando la librería oficial FlagEmbedding de BAAI.
A diferencia de BM25, esto SÍ necesita correr el modelo (CPU/GPU), porque
los pesos por token los calcula la red, no una fórmula estadística fija.

Lee los documentos directo de tu colección de Chroma (no vuelve a tocar
los embeddings densos que ya generaste con build_arxiv_chroma.py).

Requisitos:
    pip install FlagEmbedding chromadb tqdm

Uso:
    # 1. Construir el índice sparse nativo
    python build_bge_sparse_index.py \
        --persist-dir ./chroma_db \
        --collection-name arxiv_abstracts \
        --output ./bge_sparse_index.pkl \
        --device mps

    # 2. Probarlo con una consulta
    python build_bge_sparse_index.py --load ./bge_sparse_index.pkl \
        --query "vector databases for RAG" --device mps
"""

import argparse
import pickle

import chromadb
from tqdm import tqdm


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--persist-dir", default="./chroma_db", help="Carpeta de la base Chroma de la que se leen los documentos"
    )
    p.add_argument(
        "--collection-name", default="arxiv_abstracts", help="Nombre de la colección en Chroma"
    )
    p.add_argument(
        "--output", default="./bge_sparse_index.pkl", help="Ruta donde guardar el índice sparse construido"
    )
    p.add_argument(
        "--load", default=None, help="En vez de reconstruirlo, carga un índice ya guardado desde esta ruta"
    )
    p.add_argument("--model-name", default="BAAI/bge-m3", help="Modelo BGE a usar (default: BAAI/bge-m3)")
    p.add_argument(
        "--device",
        default="cpu",
        help="Dispositivo: 'cpu', 'cuda' (GPU NVIDIA) o 'mps' (GPU Apple Silicon) (default: cpu)",
    )
    p.add_argument("--batch-size", type=int, default=32, help="Tamaño de lote para el encoding (default: 32)")
    p.add_argument("--query", default=None, help="Si se especifica, corre una consulta de prueba contra el índice")
    p.add_argument("--top-k", type=int, default=5, help="Resultados a mostrar en la consulta de prueba (default: 5)")
    return p.parse_args()


def load_documents_from_chroma(persist_dir: str, collection_name: str):
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_collection(name=collection_name)
    total = collection.count()
    print(f"Leyendo {total} documentos de la colección '{collection_name}'...")
    result = collection.get(include=["documents", "metadatas"])
    return result["ids"], result["documents"], result["metadatas"]


def load_model(model_name: str, device: str):
    from FlagEmbedding import BGEM3FlagModel

    print(f"Cargando '{model_name}' (puede tardar la primera vez, ~2GB)...")
    # use_fp16 acelera el cómputo en GPU con una pérdida de precisión mínima;
    # en CPU no aplica, por eso se desactiva ahí.
    return BGEM3FlagModel(model_name, use_fp16=(device != "cpu"), device=device)


def build_sparse_weights(model, documents, batch_size: int):
    print("Generando pesos léxicos (sparse) con BGE-M3 para todos los documentos...")
    output = model.encode(
        documents,
        batch_size=batch_size,
        return_dense=False,
        return_sparse=True,
        return_colbert_vecs=False,
    )
    return output["lexical_weights"]


def save_index(path, model_name, ids, documents, metadatas, sparse_weights):
    with open(path, "wb") as f:
        pickle.dump(
            {
                "backend": "bge_sparse",
                "model_name": model_name,
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
                "sparse_weights": sparse_weights,
            },
            f,
        )
    print(f"Índice guardado en '{path}'")


def load_index(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def query_index(model, data, query: str, top_k: int):
    query_output = model.encode([query], return_dense=False, return_sparse=True, return_colbert_vecs=False)
    query_weights = query_output["lexical_weights"][0]

    scores = [
        model.compute_lexical_matching_score(query_weights, doc_weights)
        for doc_weights in tqdm(data["sparse_weights"], desc="Calculando scores")
    ]
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    print(f"\nConsulta (sparse nativo BGE-M3): {query!r}\n")
    for rank, i in enumerate(ranked, 1):
        meta = data["metadatas"][i] or {}
        print(f"{rank}. [score={scores[i]:.4f}] {meta.get('title', data['ids'][i])}")
        print(f"   Categorías: {meta.get('categories', '')}")
        print(f"   Abstract: {data['documents'][i][:200]}...\n")


def main():
    args = parse_args()

    if args.load:
        data = load_index(args.load)
        print(f"Índice cargado desde '{args.load}' ({len(data['ids'])} documentos, modelo: {data['model_name']})")
        model_name = data["model_name"]
        model = load_model(model_name, args.device) if args.query else None
    else:
        ids, documents, metadatas = load_documents_from_chroma(args.persist_dir, args.collection_name)
        if not documents:
            print("La colección está vacía. Corre primero build_arxiv_chroma.py.")
            return
        model = load_model(args.model_name, args.device)
        sparse_weights = build_sparse_weights(model, documents, args.batch_size)
        save_index(args.output, args.model_name, ids, documents, metadatas, sparse_weights)
        data = {
            "backend": "bge_sparse",
            "model_name": args.model_name,
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
            "sparse_weights": sparse_weights,
        }

    if args.query:
        query_index(model, data, args.query, args.top_k)


if __name__ == "__main__":
    main()