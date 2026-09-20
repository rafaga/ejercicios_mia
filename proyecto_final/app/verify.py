"""Verificación de que cada oración de la respuesta está respaldada por los chunks que cita."""
import re

CITE = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
HEAD = re.compile(r"^\s{0,3}#{1,6}\s+(.*)$")
BULLET = re.compile(r"^(\s*(?:[-*•]|\d+[.)])\s+)")
SKIP_SECTION = "lo que las referencias no cubren"


def normalize_citations(text: str) -> str:
    """Unifica formatos de cita que el LLM pueda usar ([Fuente 2], [1-3], 【1】) a [n, m]."""
    def fix(m):
        nums = []
        for part in re.split(r"[,;]", m.group(1)):
            r = re.search(r"(\d+)\s*[-–]\s*(\d+)", part)
            if r and 0 <= int(r.group(2)) - int(r.group(1)) < 15:
                nums += list(range(int(r.group(1)), int(r.group(2)) + 1))
            else:
                nums += [int(x) for x in re.findall(r"\d+", part)]
        return "[" + ", ".join(map(str, nums)) + "]" if nums else m.group(0)

    return re.sub(r"[\[【]\s*(?:[A-Za-záéíóúñÁÉÍÓÚÑ]+\.?\s*)?(\d+(?:\s*[-–,;]\s*\d+)*)\s*[\]】]", fix, text)


def cited(s: str) -> list[int]:
    return [int(x) for g in CITE.findall(s) for x in re.findall(r"\d+", g)]


def strip_cites(s: str) -> str:
    return re.sub(r"\s*\[\d+(?:\s*[,;]\s*\d+)*\]", "", s).strip(" *_")


def split_sentences(text: str) -> list[str]:
    out = []
    for p in (p for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p):
        if out and len(strip_cites(p)) < 25:  # fragmento corto ("et al.", o solo citas): pertenece a la anterior
            out[-1] += " " + p
        else:
            out.append(p)
    return out


def verify_answer(answer, chunk_texts, predict, min_score, strict=True):
    """predict(pairs)->scores (reranker). Devuelve {text, kept, removed:[{sentence, reason, score}]}."""
    n_chunks = len(chunk_texts)
    blocks, section = [], ""  # cada bloque: [tipo, ...]
    for line in answer.splitlines():
        h = HEAD.match(line)
        if h:
            section = h.group(1).strip().lower()
            blocks.append(["head", line])
        elif not line.strip():
            blocks.append(["blank", line])
        elif SKIP_SECTION in section:
            blocks.append(["keep", line])
        else:
            m = BULLET.match(line)
            prefix = m.group(1) if m else ""
            sents = [{"text": s, "cites": [n for n in cited(s) if 1 <= n <= n_chunks], "score": None}
                     for s in split_sentences(line[len(prefix):])]
            blocks.append(["claims", prefix, sents])

    pairs, owners = [], []
    for b in blocks:
        if b[0] == "claims":
            for s in b[2]:
                for n in dict.fromkeys(s["cites"]):
                    pairs.append((strip_cites(s["text"]), chunk_texts[n - 1]))
                    owners.append(s)
    for s, sc in zip(owners, predict(pairs) if pairs else []):
        s["score"] = max(s["score"] if s["score"] is not None else -1.0, float(sc))

    removed, kept, out = [], 0, []
    for b in blocks:
        if b[0] != "claims":
            out.append(b)
            continue
        good = []
        for s in b[2]:
            if not s["cites"]:
                removed.append({"sentence": s["text"], "reason": "sin cita válida", "score": None})
            elif s["score"] is not None and s["score"] < min_score:
                removed.append({"sentence": s["text"], "reason": "respaldo débil", "score": round(s["score"], 4)})
                if not strict:
                    good.append(s["text"] + " ⚠ *(respaldo débil)*")
            else:
                good.append(s["text"])
                kept += 1
        if good:
            out.append(["keep", b[1] + " ".join(good)])

    # quitar encabezados sin contenido
    lines, i = [], 0
    while i < len(out):
        if out[i][0] == "head":
            j = i + 1
            while j < len(out) and out[j][0] != "head":
                j += 1
            if any(x[0] in ("keep",) and x[1].strip() for x in out[i + 1 : j]):
                lines.extend(x[1] for x in out[i:j])
            i = j
        else:
            lines.append(out[i][1])
            i += 1
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return {"text": text, "kept": kept, "removed": removed}
