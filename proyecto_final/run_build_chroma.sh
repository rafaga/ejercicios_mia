#!/usr/bin/env bash
# Indexacion completa: Chroma (BGE-M3) + BM25 + BGE-M3 sparse. Mac y Linux.
# Solo categoria cs.AI. El limite de papers es opcional (por defecto, sin limite).
# Uso:  ./run_build_chroma.sh [mps|cuda|cpu] [limite]
# Sin dispositivo lo detecta (mps en Mac, cuda si hay NVIDIA, si no cpu). Ej. prueba rapida: ./run_build_chroma.sh cpu 2000
set -euo pipefail
cd "$(dirname "$0")"

DEVICE="${1:-}"
# build_arxiv_chroma.py corta en 5000 por defecto; sin limite se pasa un valor enorme.
LIMIT="${2:-1000000000}"
LIMIT_TXT="${2:-sin limite}"
if [ -z "$DEVICE" ]; then
  if [ "$(uname -s)" = "Darwin" ]; then DEVICE=mps
  elif command -v nvidia-smi >/dev/null 2>&1; then DEVICE=cuda
  else DEVICE=cpu; fi
fi
CHROMA=./.chroma_db

[ -f venv/bin/activate ] && source venv/bin/activate

echo "=== [1/4] Embeddings densos en Chroma (device=$DEVICE, categoria cs.AI, limite: $LIMIT_TXT) ==="
python build_arxiv_chroma.py --category cs.AI --limit "$LIMIT" --persist-dir "$CHROMA" --device "$DEVICE"

echo "=== [2/4] Indice sparse BM25 ==="
python build_bm25_index.py --persist-dir "$CHROMA" --collection-name arxiv_abstracts --output ./bm25_index.pkl

echo "=== [3/4] Indice sparse BGE-M3 (device=$DEVICE) ==="
python build_bge_sparce_index.py --persist-dir "$CHROMA" --collection-name arxiv_abstracts \
  --output ./bge_sparse_index.pkl --device "$DEVICE"

echo "=== [4/4] Metadatos (autores y anio) para referencias APA ==="
python build_arxiv_meta_index.py --category cs.AI --output ./arxiv_meta.sqlite

echo "Listo: .chroma_db, bm25_index.pkl, bge_sparse_index.pkl y arxiv_meta.sqlite generados."
