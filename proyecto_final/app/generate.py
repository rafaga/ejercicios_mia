"""Generación anclada en evidencia con un LLM por API (Anthropic, OpenAI u OpenCode Go)."""
import json
import os
import re
import time
import uuid

import httpx

NO_EVIDENCE = "NO_EVIDENCE"
DEFAULT_SESSION = str(uuid.uuid4())  # id estable mientras la API siga corriendo
DEFAULT_MODELS = {"anthropic": "claude-haiku-4-5", "openai": "gpt-4o-mini", "opencode": "deepseek-v4-flash"}

SYSTEM_ANSWER = f"""Eres un asistente de investigación con una regla absoluta: SOLO puedes afirmar lo que está escrito en la evidencia numerada que se te da. Está prohibido usar conocimiento propio, aunque sepas la respuesta.

Reglas:
1. Responde en español, con el mayor detalle que la evidencia permita, aprovechando todas las fuentes relevantes.
2. Cada oración con una afirmación debe llevar la cita del fragmento (o fragmentos) que la respaldan, con el formato [n] o [n, m], colocada ANTES del punto final. Ejemplo: "... mediante activación dispersa [3]." No escribas oraciones sin cita.
3. Explica un término solo si la evidencia lo define o lo describe. Si un término relevante no está definido en la evidencia, NO lo expliques: menciónalo en la última sección.
4. No agregues ejemplos, comparaciones, causas ni contexto que no aparezcan en la evidencia. No cites números que no existan.
5. Si la evidencia no permite responder la pregunta, responde exactamente {NO_EVIDENCE} y nada más.

Formato (Markdown, exactamente estas cuatro secciones):
## Resumen
## Términos clave
## Detalle
## Lo que las referencias no cubren
(en la última sección enumera, sin citas, los aspectos o términos que toca la pregunta pero que la evidencia no aclara; si no hay, escribe "Nada relevante.")"""

SYSTEM_RELATED = """Eres un asistente de investigación. A partir de una pregunta y de una lista de documentos recuperados, propones {n} preguntas de seguimiento en español sobre temas afines que esos documentos sí tratan. No tienen que ser variantes de la pregunta original: pueden explorar temas cercanos que aparezcan en los documentos. Cada pregunta debe poder responderse con los documentos listados, ser autocontenida y terminar en '?'.
Devuelve SOLO un JSON con este formato, sin texto adicional: {{"preguntas": ["...", "..."]}}"""


class LLMConfigError(RuntimeError):
    pass


def _post(url, **kw):
    """POST que reintenta ante 5xx y, ante un error HTTP, incluye el cuerpo de la respuesta."""
    retries = int(os.getenv("LLM_RETRIES", "2"))
    for attempt in range(retries + 1):
        r = httpx.post(url, **kw)
        if r.status_code >= 500 and attempt < retries:
            time.sleep(1.5 * (attempt + 1))
            continue
        break
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code} de {url}: {r.text[:500]}")
    return r


def _extra_body() -> dict:
    """Parámetros extra opcionales para el cuerpo de la petición (JSON en LLM_EXTRA_BODY), p. ej. {"reasoning_effort": "low"}."""
    raw = os.getenv("LLM_EXTRA_BODY", "").strip()
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        raise LLMConfigError("LLM_EXTRA_BODY no es un JSON válido")


def _openai_text(resp) -> str:
    data = resp.json()
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    text = (msg.get("content") or "").strip()
    if not text:
        raise RuntimeError(
            f"respuesta vacía del modelo (finish_reason={choice.get('finish_reason')}, usage={data.get('usage')}, "
            f"campos del mensaje={list(msg.keys())}). Si finish_reason=length, sube LLM_MAX_TOKENS."
        )
    return text


def llm_info() -> dict:
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    return {"provider": provider, "model": os.getenv("LLM_MODEL", DEFAULT_MODELS.get(provider, "?"))}


def _chat(system: str, user: str, max_tokens: int, session_id: str | None = None) -> str:
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    timeout = float(os.getenv("LLM_TIMEOUT", "120"))
    model = os.getenv("LLM_MODEL", DEFAULT_MODELS.get(provider, ""))

    if provider == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise LLMConfigError("Falta ANTHROPIC_API_KEY en .env")
        r = _post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            json={"model": model, "max_tokens": max_tokens, "system": system,
                  "messages": [{"role": "user", "content": user}]},
            timeout=timeout,
        )
        return "".join(b.get("text", "") for b in r.json()["content"]).strip()

    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise LLMConfigError("Falta OPENAI_API_KEY en .env")
        r = _post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "temperature": 0, "max_tokens": max_tokens, **_extra_body(),
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
            timeout=timeout,
        )
        return _openai_text(r)

    if provider == "opencode":
        # OpenCode Go: https://opencode.ai/docs/go/  (clave Bearer, User-Agent propio y x-opencode-session)
        key = os.getenv("OPENCODE_API_KEY")
        if not key:
            raise LLMConfigError("Falta OPENCODE_API_KEY en .env")
        base = os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1").rstrip("/")
        headers = {"Authorization": f"Bearer {key}", "User-Agent": "rag-arxiv-proyecto-final/1.0",
                   "x-opencode-session": session_id or DEFAULT_SESSION}
        if os.getenv("OPENCODE_API_STYLE", "openai").lower() == "anthropic":  # modelos servidos por /messages
            headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
            r = _post(f"{base}/messages", headers=headers, timeout=timeout,
                      json={"model": model, "max_tokens": max_tokens, "system": system,
                            "messages": [{"role": "user", "content": user}]})
            return "".join(b.get("text", "") for b in r.json()["content"]).strip()
        r = _post(f"{base}/chat/completions", headers=headers, timeout=timeout,
                  json={"model": model, "max_tokens": max_tokens, **_extra_body(),
                        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        return _openai_text(r)

    raise LLMConfigError(f"LLM_PROVIDER desconocido: {provider} (usa anthropic, openai u opencode)")


def build_prompt(question: str, chunks: list[dict]) -> str:
    evidence = "\n\n".join(
        f"[{i}] {c.get('title') or c['source']}\n{c['text']}" for i, c in enumerate(chunks, 1)
    )
    return f"Evidencia:\n{evidence}\n\nPregunta: {question}"


def generate(question: str, chunks: list[dict], session_id: str | None = None) -> str:
    return _chat(SYSTEM_ANSWER, build_prompt(question, chunks), int(os.getenv("LLM_MAX_TOKENS", "4000")), session_id)


def parse_related(text: str, question: str = "", n: int = 3) -> list[str]:
    items = []
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            obj = json.loads(m.group(0))
            items = obj.get("preguntas") or obj.get("questions") or []
        except (json.JSONDecodeError, AttributeError):
            items = []
    if not items:  # respaldo: líneas que parezcan preguntas
        items = [re.sub(r'^[\s\-*\d.)"]+|["\s,]+$', "", ln) for ln in text.splitlines() if "?" in ln]
    out = []
    for q in items:
        q = str(q).strip()
        if len(q) > 10 and q.endswith("?") and q.lower() != question.strip().lower() and q not in out:
            out.append(q)
    return out[:n]


def related_questions(question: str, chunks: list[dict], n: int = 3, session_id: str | None = None) -> list[str]:
    listing = "\n".join(f"- {c.get('title') or c['source']}: {c['text'][:220]}" for c in chunks)
    text = _chat(SYSTEM_RELATED.format(n=n), f"Pregunta original: {question}\n\nDocumentos:\n{listing}", 500, session_id)
    return parse_related(text, question, n)
