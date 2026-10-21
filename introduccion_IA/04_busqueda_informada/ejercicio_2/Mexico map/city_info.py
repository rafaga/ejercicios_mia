#!/usr/bin/env python3
"""Consulta la información de las ciudades de mexico_cities_graph.json.

Usos:
    python city_info.py Puebla              (una o varias palabras, sin comillas)
    python city_info.py --state Yucatan     (listar ciudades de un estado)
    python city_info.py --all               (listar las 1000 ciudades)
    python city_info.py                     (modo interactivo)

Las coincidencias son sin distinción de mayúsculas ni acentos. Los nombres
repetidos se consultan como 'Ciudad, Estado' o por '#id' (p. ej. Puebla,
'Puebla, Baja California' o '#580').
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

JSON_PATH = Path(__file__).resolve().parent / "mexico_cities_graph.json"

EXIT_WORDS = {"q", "quit", "salir", "exit"}


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold()


def load_payload() -> dict:
    with JSON_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def build_adjacency(edges: list[dict]) -> dict[int, list[tuple[int, float, str]]]:
    adj: dict[int, list[tuple[int, float, str]]] = {}
    for e in edges:
        adj.setdefault(e["source"], []).append((e["target"], e["km"], e.get("kind", "")))
        adj.setdefault(e["target"], []).append((e["source"], e["km"], e.get("kind", "")))
    return adj


def find_matches(nodes: list[dict], query: str) -> list[dict]:
    key = fold(query)
    qualified = lambda n: fold(f"{n['name']}, {n['state']}")
    for test in (
        lambda n: fold(n["name"]) == key,
        lambda n: qualified(n) == key,
        lambda n: fold(n["name"]).startswith(key),
        lambda n: qualified(n).startswith(key),
        lambda n: key in fold(n["name"]),
    ):
        matches = [n for n in nodes if test(n)]
        if matches:
            return sorted(matches, key=lambda n: -n["population"])
    return []


def fmt_pop(population: int) -> str:
    return f"{population:,}".replace(",", ".")


def print_city(node: dict, nodes_by_id: dict[int, dict], adj: dict[int, list[tuple[int, float, str]]]) -> None:
    print(f"● {node['name']} — {node['state']}")
    print(f"    id:          {node['id']}")
    print(f"    geoname_id:  {node['geoname_id']}")
    print(f"    población:   {fmt_pop(node['population'])}")
    print(f"    coordenadas: {node['lat']:.5f}, {node['lon']:.5f}")
    print(f"    grado:       {node['degree']}")
    neighbors = sorted(adj.get(node["id"], []), key=lambda t: t[1])
    print(f"    vecinos ({len(neighbors)}):")
    for other_id, km, kind in neighbors:
        other = nodes_by_id[other_id]
        tag = f" [{kind}]" if kind else ""
        print(f"      {other['name']:<34} {other['state']:<24} {km:7.1f} km{tag}")
    print()


def show_by_id(text: str, nodes_by_id: dict[int, dict], adj: dict[int, list[tuple[int, float, str]]]) -> None:
    text = text.strip()
    if not text.isdigit():
        print(f"id inválido {text!r}: usa '#<número>'\n")
        return
    node = nodes_by_id.get(int(text))
    if node is None:
        print(f"no hay ciudad con id {text} (válidos: 0-{max(nodes_by_id)})\n")
        return
    print(f"ciudad con id {text}:\n")
    print_city(node, nodes_by_id, adj)


def show_matches(query: str, nodes: list[dict], nodes_by_id: dict[int, dict], adj: dict[int, list[tuple[int, float, str]]]) -> None:
    if query.startswith("#"):
        show_by_id(query[1:], nodes_by_id, adj)
        return
    matches = find_matches(nodes, query)
    if matches:
        print(f"{len(matches)} coincidencia(s) para {query!r}:\n")
        for node in matches:
            print_city(node, nodes_by_id, adj)
        return
    if query.strip().isdigit():
        show_by_id(query, nodes_by_id, adj)
        return
    print(f"sin coincidencias para {query!r}\n")


def print_state(nodes: list[dict], state: str) -> None:
    key = fold(state)
    matches = [n for n in nodes if key in fold(n["state"])]
    if not matches:
        sys.exit(f"error: no hay ciudades cuyo estado coincida con {state!r}")
    matches.sort(key=lambda n: -n["population"])
    print(f"{len(matches)} ciudades con estado que coincide con {state!r}:\n")
    for n in matches:
        print(f"  {n['name']:<34} {n['state']:<24} {fmt_pop(n['population']):>12}")


def interactive(nodes: list[dict], nodes_by_id: dict[int, dict], adj: dict[int, list[tuple[int, float, str]]]) -> None:
    print(f"{len(nodes)} ciudades cargadas. Escribe un nombre para consultarla")
    print(f"(vacío o {sorted(EXIT_WORDS)[0]}/{sorted(EXIT_WORDS)[2]} para terminar).\n")
    while True:
        try:
            query = input("ciudad> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not query or query.lower() in EXIT_WORDS:
            break
        show_matches(query, nodes, nodes_by_id, adj)


def main() -> None:
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        if stream.encoding and stream.encoding.lower() not in ("utf-8", "utf8"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Consulta información de las ciudades del grafo de México.",
        epilog="ejemplos: python city_info.py Puebla | python city_info.py --state Yucatan | python city_info.py --all",
    )
    parser.add_argument("ciudad", nargs="*", help="nombre de la ciudad (palabras sueltas o entre comillas)")
    parser.add_argument("--state", help="listar las ciudades de un estado")
    parser.add_argument("--all", dest="list_all", action="store_true", help="listar todas las ciudades por población")
    args = parser.parse_args()

    payload = load_payload()
    nodes = payload["nodes"]
    nodes_by_id = {n["id"]: n for n in nodes}
    adj = build_adjacency(payload["edges"])

    if args.state:
        print_state(nodes, args.state)
    elif args.list_all:
        for n in sorted(nodes, key=lambda n: -n["population"]):
            print(f"{n['name']:<34} {n['state']:<24} {fmt_pop(n['population']):>12}")
    elif args.ciudad:
        show_matches(" ".join(args.ciudad), nodes, nodes_by_id, adj)
    else:
        interactive(nodes, nodes_by_id, adj)


if __name__ == "__main__":
    main()
