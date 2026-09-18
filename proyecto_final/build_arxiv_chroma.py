#!/usr/bin/env python3
"""
Descarga (vía la API de Kaggle) el dataset de abstracts de arXiv
(Cornell-University/arxiv) y lo carga en una base de datos vectorial Chroma,
usando BGE-M3 como modelo de embeddings.

Requisitos:
    pip install chromadb tqdm sentence-transformers kaggle

Credenciales de Kaggle (una sola vez):
    1. En kaggle.com -> Settings -> API -> "Create New Token"
       (descarga kaggle.json)
    2. Colócalo en ~/.kaggle/kaggle.json (Linux/Mac) o
       C:\\Users\\<usuario>\\.kaggle\\kaggle.json (Windows)

Nota sobre el modelo: se usa BGE-M3 (BAAI/bge-m3), no BGE-VL. BGE-VL es un
modelo multimodal (imagen+texto) pensado para buscar imágenes con texto o
viceversa; para un dataset de solo texto como los abstracts de arXiv no
aporta nada y es más pesado de correr. BGE-M3 es la opción correcta aquí:
texto puro, multilingüe, buen contexto (8192 tokens) y no necesita prefijos
de instrucción especiales para las queries (a diferencia de BGE 1.5).

Uso (descarga automática la primera vez, y reutiliza el archivo después):
    python build_arxiv_chroma.py \
        --limit 5000 \
        --category cs.AI \
        --persist-dir ./chroma_db \
        --device mps

Si ya tienes el archivo descargado y no quieres pasar por Kaggle, sigue
pudiendo pasarlo directo:
    python build_arxiv_chroma.py --input arxiv-metadata-oai-snapshot.json ...
"""

import argparse
import json
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from tqdm import tqdm


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--input",
        default=None,
        help=(
            "Ruta al archivo arxiv-metadata-oai-snapshot.json. Si no se especifica, "
            "el script lo descarga automáticamente vía la API de Kaggle a --download-dir."
        ),
    )
    p.add_argument(
        "--download-dir",
        default="./arxiv_data",
        help="Carpeta donde se descarga/busca el dataset cuando no se pasa --input (default: ./arxiv_data)",
    )
    p.add_argument(
        "--kaggle-dataset",
        default="Cornell-University/arxiv",
        help="Slug del dataset de Kaggle a descargar (default: Cornell-University/arxiv)",
    )
    p.add_argument("--limit", type=int, help="Número máximo de papers a indexar (default: todos)")
    p.add_argument("--category", default=None, help="Filtrar por categoría, ej. cs.AI, cs.CL (default: sin filtro)")
    p.add_argument("--persist-dir", default="./chroma_db", help="Carpeta donde se guarda la base Chroma")
    p.add_argument("--collection-name", default="arxiv_abstracts", help="Nombre de la colección en Chroma")
    p.add_argument("--batch-size", type=int, default=200, help="Tamaño de lote para insertar en Chroma")
    p.add_argument("--query", default="advances in language models", help="Consulta de prueba al final")
    p.add_argument(
        "--embedding-model",
        default="BAAI/bge-m3",
        help="Modelo de sentence-transformers a usar para los embeddings (default: BAAI/bge-m3)",
    )
    p.add_argument(
        "--device",
        default="cpu",
        help=(
            "Dispositivo para correr el modelo de embeddings: 'cpu', 'cuda' (GPU NVIDIA) "
            "o 'mps' (GPU de Apple Silicon, ej. M1/M2/M3/M4) (default: cpu)"
        ),
    )
    return p.parse_args()


def find_metadata_file(download_dir: Path) -> Optional[Path]:
    """Busca el .json del dump de arXiv dentro de download_dir (ya descargado o descomprimido)."""
    if not download_dir.exists():
        return None
    candidates = sorted(download_dir.glob("*arxiv-metadata*.json"))
    return candidates[0] if candidates else None


def ensure_dataset_file(download_dir: str, kaggle_dataset: str) -> Path:
    """
    Devuelve la ruta al archivo de metadata de arXiv, descargándolo con la
    API de Kaggle si todavía no existe en download_dir.
    """
    download_path = Path(download_dir)
    existing = find_metadata_file(download_path)
    if existing:
        print(f"Usando dataset ya descargado en '{existing}'")
        return existing

    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
    except ImportError as e:
        raise ImportError(
            "Falta el paquete 'kaggle'. Instálalo con:\n"
            "  pip install kaggle\n"
            "y configura tus credenciales (kaggle.json) como se explica al inicio del script."
        ) from e

    print(f"Descargando '{kaggle_dataset}' desde Kaggle a '{download_path}' (puede tardar, son varios GB)...")
    download_path.mkdir(parents=True, exist_ok=True)

    api = KaggleApi()
    api.authenticate()  # lee ~/.kaggle/kaggle.json (o KAGGLE_USERNAME/KAGGLE_KEY del entorno)
    api.dataset_download_files(kaggle_dataset, path=str(download_path), unzip=True, quiet=False)

    metadata_file = find_metadata_file(download_path)
    if not metadata_file:
        raise FileNotFoundError(
            f"Se descargó '{kaggle_dataset}' en '{download_path}' pero no encontré un archivo "
            "que coincida con '*arxiv-metadata*.json'. Revisa el contenido de esa carpeta y pasa "
            "la ruta correcta con --input."
        )
    print(f"Dataset listo en '{metadata_file}'")
    return metadata_file


def load_records(path: Path, category: Optional[str], limit: int=0):
    """
    El archivo de Kaggle viene en formato JSON Lines (un JSON por línea),
    así que lo leemos línea por línea sin cargar todo el archivo a memoria
    (el dump completo pesa varios GB).
    """
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in tqdm(f, desc="Leyendo dataset"):
            if limit is not None and len(records) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                paper = json.loads(line)
            except json.JSONDecodeError:
                continue

            categories = paper.get("categories", "") or ""
            if category and category not in categories:
                continue

            abstract = (paper.get("abstract") or "").strip().replace("\n", " ")
            title = (paper.get("title") or "").strip().replace("\n", " ")
            paper_id = paper.get("id")
            if not abstract or not paper_id:
                continue

            records.append(
                {
                    "id": paper_id,
                    "title": title,
                    "abstract": abstract,
                    "categories": categories,
                    "update_date": paper.get("update_date", ""),
                }
            )
    return records


def build_collection(records, persist_dir, collection_name, batch_size, embedding_model, device):
    client = chromadb.PersistentClient(path=persist_dir)

    # Si la colección ya existe de una corrida anterior, la recreamos para
    # evitar duplicados al probar el script varias veces.
    existing = [c.name for c in client.list_collections()]
    if collection_name in existing:
        client.delete_collection(collection_name)

    # BGE-M3 se descarga la primera vez desde Hugging Face (~2GB) y luego
    # queda cacheado localmente. normalize_embeddings=True es importante:
    # BGE-M3 está entrenado para compararse con similitud coseno, así que
    # normalizamos los vectores y usamos "cosine" como métrica de distancia
    # de la colección (ver hnsw:space más abajo).
    print(f"Cargando modelo de embeddings '{embedding_model}' (puede tardar la primera vez)...")
    embedding_fn = SentenceTransformerEmbeddingFunction(
        model_name=embedding_model,
        device=device,
        normalize_embeddings=True,
    )

    collection = client.create_collection(
        name=collection_name,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

    for i in tqdm(range(0, len(records), batch_size), desc="Insertando en Chroma"):
        batch = records[i : i + batch_size]
        collection.add(
            ids=[r["id"] for r in batch],
            documents=[r["abstract"] for r in batch],
            metadatas=[
                {
                    "title": r["title"],
                    "categories": r["categories"],
                    "update_date": r["update_date"],
                }
                for r in batch
            ],
        )

    return collection


def demo_query(collection, query: str):
    print(f"\nConsulta de prueba: {query!r}\n")
    results = collection.query(query_texts=[query], n_results=3)
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    for i, (doc, meta) in enumerate(zip(docs, metas), 1):
        print(f"{i}. {meta['title']}")
        print(f"   Categorías: {meta['categories']}")
        print(f"   Abstract: {doc[:200]}...\n")


def main():
    args = parse_args()

    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            raise FileNotFoundError(f"No encontré '{input_path}'.")
    else:
        input_path = ensure_dataset_file(args.download_dir, args.kaggle_dataset)

    records = load_records(input_path, args.category, args.limit)
    suffix = f" (categoría: {args.category})" if args.category else ""
    print(f"\n{len(records)} papers cargados{suffix}")

    if not records:
        print("No se encontraron registros con esos filtros. Revisa --category o --limit.")
        return

    collection = build_collection(
        records,
        args.persist_dir,
        args.collection_name,
        args.batch_size,
        args.embedding_model,
        args.device,
    )
    print(f"\nColección '{args.collection_name}' creada en '{args.persist_dir}' con {collection.count()} documentos.")

    demo_query(collection, args.query)


if __name__ == "__main__":
    main()
