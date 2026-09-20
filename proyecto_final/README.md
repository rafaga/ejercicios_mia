# RAG sobre arXiv cs.AI (Streamlit + FastAPI + ChromaDB + BGE-M3)

Sistema RAG sobre ~90 000 abstracts de arXiv (categoría `cs.AI`).

```
Streamlit (8501) ──HTTP──> FastAPI (8000) ──> ChromaDB (.chroma_db, embeddings BGE-M3)
                                         ├──> índice sparse (bm25_index.pkl | bge_sparse_index.pkl)
                                         ├──> reranker bge-reranker-v2-m3
                                         └──> LLM por API (Anthropic u OpenAI) para la respuesta
```

Modos de recuperación (se eligen en Streamlit o con `mode` en `/query`):
`hybrid_bm25` (BM25 + denso, RRF), `hybrid_bge` (BGE-M3 sparse + denso, RRF) y `dense` (solo embeddings).
En los tres se aplica el reranker, cuyo score decide la abstención (`MIN_SCORE`).

## 1. Requisitos

- Python 3.10+ (probado con 3.10).
- Espacio en disco: el dataset de arXiv pesa ~5.5 GB, `.chroma_db` ~2.3 GB y los `.pkl` ~1.6 GB.
- Los modelos (`BAAI/bge-m3` ~2 GB y `BAAI/bge-reranker-v2-m3`) se descargan de Hugging Face la primera vez.
- Una clave de LLM (Anthropic u OpenAI) solo para la generación de respuestas.

## 2. Entorno virtual

No reutilices un `venv/` creado en otro sistema operativo: bórralo y créalo de nuevo.

### Mac (Apple Silicon, GPU vía MPS)

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

El torch de PyPI ya incluye soporte MPS. Usa `--device mps` en los scripts y `DEVICE=mps` para la API.

### Windows, solo CPU

```bat
py -3 -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

En PowerShell, si bloquea la activación: `Set-ExecutionPolicy -Scope Process RemoteSigned` y luego `venv\Scripts\Activate.ps1`.
Instalar torch antes evita que `requirements.txt` traiga otra variante. Si pip quiere reemplazarlo por la
versión fijada, quita la línea `torch==...` del archivo o instala con `--no-deps` esa línea.

### Windows con GPU NVIDIA (CUDA)

Igual que el caso CPU, pero instala torch con el índice CUDA que corresponda a tu driver
(consúltalo en https://pytorch.org/get-started/locally/; `<cuXXX>` es p. ej. `cu126`):

```bat
pip install torch --index-url https://download.pytorch.org/whl/<cuXXX>
pip install -r requirements.txt
python -c "import torch; print(torch.cuda.is_available())"   :: debe imprimir True
```

Usa `--device cuda` en los scripts y `DEVICE=cuda` para la API.

## 3. Construir los índices (una sola vez, en este orden)

Ejecútalos desde esta carpeta con el venv activo. Usa `--device mps` (Mac), `--device cuda` (Windows+NVIDIA)
o `--device cpu`. En Windows escribe `.\` en vez de `./` y `^` en vez de `\` para continuar líneas.

**Ojo con la ruta de Chroma:** la API espera `.chroma_db` (con punto). El default de los scripts es `./chroma_db`,
así que pasa siempre `--persist-dir ./.chroma_db`, o define `CHROMA_DIR` en `.env` si usas otra ruta.

### Atajo: los tres pasos con un solo comando

```bat
run_build_chroma.bat            :: Windows: usa cuda por defecto
run_build_chroma.bat cpu        :: o elige el dispositivo
run_build_chroma.bat cpu 2000   :: límite opcional de papers (prueba rápida)
```

```bash
chmod +x run_build_chroma.sh    # solo la primera vez
./run_build_chroma.sh           # Mac/Linux: detecta mps, cuda o cpu
./run_build_chroma.sh cpu       # o elige el dispositivo
./run_build_chroma.sh cpu 2000  # límite opcional de papers (prueba rápida)
```

Indexan solo la categoría `cs.AI`; el límite de papers es opcional y, si no lo das, se indexa todo. Activan `venv` si existe, ejecutan 3.1, 3.2, 3.3 y 3.4 en orden y se detienen si alguno falla.
Como todos los pasos son incrementales o reconstruyen desde Chroma, puedes repetirlos sin riesgo.

### 3.1 Embeddings densos en ChromaDB — `build_arxiv_chroma.py`

Descarga el dataset `Cornell-University/arxiv` con Kaggle (primero pon tu `kaggle.json` en
`~/.kaggle/` en Mac, o en `C:\Users\<usuario>\.kaggle\` en Windows; o define `KAGGLE_USERNAME` y `KAGGLE_KEY`)
y lo indexa con BGE-M3 (coseno, normalizado) en la colección `arxiv_abstracts`.

```bash
python build_arxiv_chroma.py --category cs.AI --limit 1000000000 --persist-dir ./.chroma_db --device mps
```

- `--limit` es el máximo de papers; el default del script (5000) es solo de prueba, por eso aquí (y en los atajos) se pasa un valor enorme para no limitar. Para una prueba rápida usa p. ej. `--limit 2000`.
- Es incremental: si lo repites solo embebe lo nuevo o modificado. `--rebuild` borra la colección y empieza de cero;
  `--refresh-download` vuelve a bajar el dataset. Si ya tienes el archivo: `--input ruta/arxiv-metadata-oai-snapshot.json`.

### 3.2 Índice BM25 — `build_bm25_index.py` → `bm25_index.pkl`

Lee los documentos desde Chroma (no usa GPU ni descarga modelos):

```bash
python build_bm25_index.py --persist-dir ./.chroma_db --collection-name arxiv_abstracts --output ./bm25_index.pkl
python build_bm25_index.py --load ./bm25_index.pkl --query "vector databases for RAG"   # prueba
```

### 3.3 Índice sparse de BGE-M3 — `build_bge_sparce_index.py` → `bge_sparse_index.pkl`

(El archivo se llama `sparce`, con «c».) Corre BGE-M3 sobre todos los documentos, por lo que es la parte lenta:

```bash
python build_bge_sparce_index.py --persist-dir ./.chroma_db --collection-name arxiv_abstracts \
    --output ./bge_sparse_index.pkl --device mps --batch-size 32
python build_bge_sparce_index.py --load ./bge_sparse_index.pkl --query "vector databases for RAG" --device mps   # prueba
```

Si te quedas sin memoria de GPU baja `--batch-size`.

### 3.4 Metadatos para referencias APA — `build_arxiv_meta_index.py` → `arxiv_meta.sqlite`

Chroma solo guarda título y fechas, no autores. Este script lee el JSON de Kaggle (`arxiv_data/`) y guarda autores, año
de la primera versión y DOI de los papers `cs.AI` en un SQLite pequeño. No usa GPU ni modelos y se corre una sola vez:

```bash
python build_arxiv_meta_index.py --category cs.AI --output ./arxiv_meta.sqlite
```

Sin este archivo la API funciona, pero las referencias APA salen sin autores ni año (Streamlit lo avisa en la barra lateral).

### 3.5 Probar la recuperación sin la API — `hybrid_search.py`

```bash
python hybrid_search.py --query "vector databases for RAG" --persist-dir ./.chroma_db \
    --sparse-index ./bm25_index.pkl --rerank --device mps
```

Detecta solo si el `.pkl` es BM25 o BGE sparse. Si cambias las rutas, usa las mismas en la API (ver §4).

## 4. Configuración (`.env`)

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

| Variable | Para qué |
|---|---|
| `LLM_PROVIDER` | `anthropic`, `openai` u `opencode` (OpenCode Go) |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OPENCODE_API_KEY` | Clave del proveedor elegido (en Anthropic: https://console.anthropic.com; en OpenAI: https://platform.openai.com/api-keys) |
| `OPENCODE_API_STYLE` | Solo con `opencode`: `openai` (default, `/chat/completions`) o `anthropic` (`/messages`, p. ej. Qwen). Según el endpoint de cada modelo en https://opencode.ai/docs/go/ |
| `LLM_MODEL` | Opcional. Modelo del proveedor (por defecto `claude-haiku-4-5`, `gpt-4o-mini` o `deepseek-v4-flash`) |
| `MIN_SCORE` | Umbral del reranker (0–1): si el **mejor** chunk no lo supera, el sistema se abstiene sin llamar al LLM. Default 0.2; calibra con tus preguntas |
| `MIN_CHUNK_SCORE` | Score mínimo de cada chunk para enviarlo al LLM (default 0.02). Todos los recuperados se muestran igual en pantalla, marcando cuáles se enviaron |
| `SUPPORT_MIN_SCORE` / `STRICT_GROUNDING` | Verificación de citas (ver §7): score mínimo oración↔chunk y modo estricto (elimina) o no (marca con ⚠) |
| `RELATED_N` | Cuántas preguntas relacionadas sugiere el LLM (default 3) |
| `ARXIV_META` | Ruta de `arxiv_meta.sqlite` (autores y año para APA) |
| `DEVICE` | `cuda`, `mps` o `cpu`. Si no se define, se detecta automáticamente |
| `CHROMA_DIR` | Ruta de Chroma si no es `./.chroma_db` |
| `BM25_INDEX`, `BGE_SPARSE_INDEX` | Rutas de los `.pkl` si no están en la raíz |

`.env` está en `.gitignore`; nunca lo subas.

## 5. Levantar el sistema

Dos terminales, ambas con el venv activo y en esta carpeta.

```bash
# Terminal 1: API (documentación en http://localhost:8000/docs)
uvicorn app.main:app --port 8000

# Terminal 2: UI (http://localhost:8501)
streamlit run ui/streamlit_app.py
```

Al arrancar la API carga los modelos en segundo plano; `GET /health` indica `"ready": true` cuando termina.
Los `.pkl` solo se cargan al usar por primera vez su modo.

Probar la API sin la UI:

```bash
curl -X POST http://localhost:8000/query -H "Content-Type: application/json" \
  -d '{"question": "¿Qué es retrieval-augmented generation?", "top_k": 5, "mode": "hybrid_bm25"}'
```

En Windows cmd usa comillas dobles con escape: `-d "{\"question\": \"...\", \"mode\": \"dense\"}"`.

## 6. Endpoints

- `GET /health`: estado, número de abstracts, chunks subidos y modos disponibles.
- `POST /ingest`: archivos `.txt`, `.md` o `.pdf` (multipart, campo `files`). Se parten en chunks de 250 palabras con 50
  de solape, se incrustan con BGE-M3 y se guardan en la colección `user_docs` de Chroma, que también se consulta.
- `POST /related`: `{question, chunks}` devuelve `related_questions` (temas afines a demanda; usa una llamada extra al LLM).
- `POST /query`: `{question, top_k, mode}`; `top_k` mínimo 10 (default 10) y `mode` en `dense | hybrid_bm25 | hybrid_bge`.
  Devuelve `answer` (con citas APA enlazadas en el texto), `abstained`, `references` (lista APA de lo citado),
  `citations` (los chunks recuperados: id, source, title, text, score, url, `sent_to_llm`, `cited_as`)
  y `llm` (proveedor, modelo, tiempos y oraciones eliminadas).

## 7. Abstención y respuestas ancladas a las referencias

1. **Abstención por score:** si el mejor score del reranker es menor que `MIN_SCORE`, responde «no tengo evidencia suficiente»
   sin llamar al LLM (`abstained = true`).
2. **Chunks enviados al LLM:** de los `top_k` (≥ 10) solo se envían los que superan `MIN_CHUNK_SCORE`.
3. **Prompt estricto:** el LLM solo puede afirmar lo que está en la evidencia numerada, cada oración debe llevar cita,
   los términos no definidos en las fuentes no se explican sino que se listan en «Lo que las referencias no cubren», y
   si la evidencia no basta responde `NO_EVIDENCE` (también `abstained = true`).
4. **Verificación en el backend:** cada oración se puntúa con el reranker contra los chunks que cita. Se eliminan las
   oraciones sin cita válida o con respaldo menor que `SUPPORT_MIN_SCORE` (o se marcan con ⚠ si `STRICT_GROUNDING=0`).
   Si no queda ninguna oración respaldada, el sistema se abstiene. No es una garantía absoluta: reduce el riesgo de
   que el modelo use conocimiento propio; calibra el umbral con tus preguntas.
5. **Citas APA:** las citas `[n]` se reemplazan por citas APA 7 en español enlazadas, `(Vaswani et al., 2017)`, y se añade una
   lista «Referencias» con lo realmente citado. Las arma el código con `arxiv_meta.sqlite`, no el LLM. Los documentos
   subidos con `/ingest` se citan por nombre de archivo y `(s. f.)`.
6. **Temas afines (a demanda):** el botón «Sugerir temas afines» de cada respuesta llama a `POST /related`, que pide al LLM
   preguntas relacionadas a partir de los chunks recuperados; aparecen como botones que lanzan una nueva consulta. No se
   generan automáticamente, para ahorrar tokens.
