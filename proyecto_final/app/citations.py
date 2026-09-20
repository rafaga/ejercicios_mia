"""Referencias en estilo APA 7 (en español) construidas por código, no por el LLM.
Autores y año salen de arxiv_meta.sqlite (build_arxiv_meta_index.py)."""
import json
import os
import re
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
META_DB = os.getenv("ARXIV_META", str(BASE / "arxiv_meta.sqlite"))
RUN = re.compile(r"((?:\[\d+(?:\s*[,;]\s*\d+)*\]\s*)+)")


def meta_available() -> bool:
    return os.path.exists(META_DB)


def get_meta(ids: list[str]) -> dict:
    if not ids or not meta_available():
        return {}
    con = sqlite3.connect(f"file:{META_DB}?mode=ro", uri=True)
    out = {}
    try:
        for s in range(0, len(ids), 500):
            part = ids[s : s + 500]
            q = ",".join("?" * len(part))
            for i, title, authors, year in con.execute(f"select id,title,authors,year from meta where id in ({q})", part):
                out[i] = {"title": title, "authors": json.loads(authors or "[]"), "year": year}
    finally:
        con.close()
    return out


def initials(first: str) -> str:
    return " ".join(p[0].upper() + "." for p in re.split(r"[\s\-]+", (first or "").strip()) if p and p[0].isalpha())


def apa_authors(authors: list) -> str:
    names = []
    for a in authors:
        last, first = (a + ["", ""])[:2]
        ini = initials(first)
        names.append(f"{last.strip()}, {ini}" if ini else last.strip())
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) <= 20:
        return ", ".join(names[:-1]) + ", y " + names[-1]
    return ", ".join(names[:19]) + ", . . . " + names[-1]


def intext_author(authors: list, fallback: str) -> str:
    lasts = [a[0].strip() for a in authors if a and a[0].strip()]
    if not lasts:
        return fallback
    if len(lasts) == 1:
        return lasts[0]
    if len(lasts) == 2:
        return f"{lasts[0]} y {lasts[1]}"
    return f"{lasts[0]} et al."


def describe(hit: dict, meta: dict | None) -> dict:
    """Devuelve label (cita en el texto sin año), year, url y la referencia APA en Markdown."""
    title = (hit.get("title") or hit["source"]).strip()
    short = title if len(title) <= 40 else title[:37].rstrip() + "..."
    is_arxiv = hit["source"].startswith("arXiv:")
    if is_arxiv:
        m = meta or {}
        authors, year = m.get("authors", []), m.get("year") or "s. f."
        url = hit.get("url") or f"https://arxiv.org/abs/{hit['id']}"
        who = apa_authors(authors)
        label = intext_author(authors, f"*{short}*")
        head = f"{who} ({year}). " if who else f"*{title}*. ({year}). "
        body = f"*{title}*. arXiv. " if who else "arXiv. "
        apa = f"{head}{body}[{url}]({url})"
    else:
        year, url = "s. f.", None
        label = hit["source"]
        apa = f"*{hit['source']}*. (s. f.). Documento subido por el usuario."
    return {"label": label, "year": str(year), "url": url, "apa": apa, "sort": (label.lower(), str(year))}


def build_refs(ctx: list[dict], cited: list[int]) -> dict:
    """ctx: chunks numerados 1..M enviados al LLM. cited: números realmente citados. -> {n: ref}"""
    meta = get_meta([c["id"] for c in ctx if c["source"].startswith("arXiv:")])
    refs = {n: describe(ctx[n - 1], meta.get(ctx[n - 1]["id"])) for n in dict.fromkeys(cited) if 1 <= n <= len(ctx)}
    # desambiguar autor+año repetidos con a, b, c (regla APA)
    groups = {}
    for n, r in refs.items():
        groups.setdefault((r["label"], r["year"]), []).append(n)
    for (label, year), ns in groups.items():
        if len(ns) > 1 and year != "s. f.":
            for k, n in enumerate(sorted(ns, key=lambda n: ctx[n - 1].get("title", "")), 0):
                refs[n]["year"] = f"{year}{chr(97 + k)}"
                refs[n]["apa"] = refs[n]["apa"].replace(f"({year})", f"({refs[n]['year']})", 1)
                refs[n]["sort"] = (refs[n]["label"].lower(), refs[n]["year"])
    return refs


def cited_numbers(text: str) -> list[int]:
    return [int(x) for grp in RUN.findall(text) for x in re.findall(r"\d+", grp)]


def apply_intext(text: str, refs: dict) -> str:
    """Reemplaza [n] / [n, m] / [1][2] por citas APA enlazadas: (Autor, 2020; Otro et al., 2021)."""
    def repl(m):
        nums = list(dict.fromkeys(int(x) for x in re.findall(r"\d+", m.group(1))))
        parts = []
        for n in nums:
            r = refs.get(n)
            if r:
                lab = f"{r['label']}, {r['year']}"
                parts.append((r["sort"], f"[{lab}]({r['url']})" if r["url"] else lab))
        if not parts:
            return ""
        trailing = m.group(1)[len(m.group(1).rstrip()):]
        return " (" + "; ".join(p for _, p in sorted(parts)) + ")" + trailing
    return re.sub(r"\s*" + RUN.pattern, repl, text)
