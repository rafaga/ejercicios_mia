#!/usr/bin/env python3
"""
Construye arxiv_meta.sqlite con autores y año de publicación (versión v1) de los papers de arXiv,
para poder armar referencias en estilo APA. Lee el mismo JSON de Kaggle que build_arxiv_chroma.py
(arxiv_data/*arxiv-metadata*.json) y guarda solo los papers de la categoría indicada.
No usa GPU ni modelos; tarda unos minutos y se corre una sola vez.

Uso:
    python build_arxiv_meta_index.py                       # cs.AI, sin límite
    python build_arxiv_meta_index.py --input ruta/arxiv-metadata-oai-snapshot.json --output ./arxiv_meta.sqlite
"""
import argparse
import json
import re
import sqlite3
from pathlib import Path

from tqdm import tqdm


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default=None, help="JSON de metadatos (default: busca en --download-dir)")
    p.add_argument("--download-dir", default="./arxiv_data")
    p.add_argument("--output", default="./arxiv_meta.sqlite")
    p.add_argument("--category", default="cs.AI", help="Misma categoría usada al indexar en Chroma (default: cs.AI)")
    args = p.parse_args()

    path = Path(args.input) if args.input else next(iter(sorted(Path(args.download_dir).glob("*arxiv-metadata*.json"))), None)
    if not path or not path.exists():
        raise SystemExit("No encuentro el JSON de arXiv. Pasa --input o corre antes build_arxiv_chroma.py (lo descarga).")

    out = Path(args.output)
    if out.exists():
        out.unlink()
    con = sqlite3.connect(out)
    con.execute("create table meta (id text primary key, title text, authors text, year text, doi text)")

    rows, total = [], 0
    with open(path, "r", encoding="utf-8") as f:
        for line in tqdm(f, desc=f"Leyendo {path.name}"):
            if args.category not in line:  # filtro rápido antes de parsear el JSON
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if args.category not in (d.get("categories") or ""):
                continue
            versions = d.get("versions") or []
            m = re.search(r"\b(\d{4})\b", versions[0].get("created", "")) if versions else None
            year = m.group(1) if m else (d.get("update_date") or "")[:4] or None
            authors = [[a[0], a[1]] for a in (d.get("authors_parsed") or []) if a]
            rows.append((d["id"], " ".join((d.get("title") or "").split()), json.dumps(authors, ensure_ascii=False),
                         year, d.get("doi")))
            if len(rows) >= 5000:
                con.executemany("insert or replace into meta values (?,?,?,?,?)", rows)
                total += len(rows)
                rows = []
    if rows:
        con.executemany("insert or replace into meta values (?,?,?,?,?)", rows)
        total += len(rows)
    con.commit()
    con.close()
    print(f"Listo: {total} papers guardados en '{out}'")


if __name__ == "__main__":
    main()
