"""Partición en chunks por palabras con solape (para documentos subidos vía /ingest)."""


def chunk_text(text: str, size: int = 250, overlap: int = 50) -> list[str]:
    words = text.split()
    if not words:
        return []
    step = max(size - overlap, 1)
    chunks = []
    for start in range(0, len(words), step):
        piece = words[start : start + size]
        chunks.append(" ".join(piece))
        if start + size >= len(words):
            break
    return chunks
