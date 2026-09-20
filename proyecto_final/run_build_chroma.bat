@echo off
REM Indexacion completa: Chroma (BGE-M3) + BM25 + BGE-M3 sparse.
REM Solo categoria cs.AI. El limite de papers es opcional (por defecto, sin limite).
REM Uso:  run_build_chroma.bat [cuda|cpu] [limite]      (default: cuda, sin limite)
setlocal
set DEVICE=%1
if "%DEVICE%"=="" set DEVICE=cuda
REM build_arxiv_chroma.py corta en 5000 por defecto; sin limite se pasa un valor enorme.
set LIMIT=%2
set LIMIT_TXT=%2
if "%LIMIT%"=="" (
  set LIMIT=1000000000
  set LIMIT_TXT=sin limite
)
set CHROMA=.\.chroma_db

if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat

echo === [1/4] Embeddings densos en Chroma (device=%DEVICE%, categoria cs.AI, limite: %LIMIT_TXT%) ===
python build_arxiv_chroma.py --category cs.AI --limit %LIMIT% --persist-dir %CHROMA% --device %DEVICE%
if errorlevel 1 goto :error

echo === [2/4] Indice sparse BM25 ===
python build_bm25_index.py --persist-dir %CHROMA% --collection-name arxiv_abstracts --output .\bm25_index.pkl
if errorlevel 1 goto :error

echo === [3/4] Indice sparse BGE-M3 (device=%DEVICE%) ===
python build_bge_sparce_index.py --persist-dir %CHROMA% --collection-name arxiv_abstracts --output .\bge_sparse_index.pkl --device %DEVICE%
if errorlevel 1 goto :error

echo === [4/4] Metadatos (autores y anio) para referencias APA ===
python build_arxiv_meta_index.py --category cs.AI --output .\arxiv_meta.sqlite
if errorlevel 1 goto :error

echo Listo: .chroma_db, bm25_index.pkl, bge_sparse_index.pkl y arxiv_meta.sqlite generados.
exit /b 0

:error
echo Fallo la indexacion (codigo %errorlevel%). Revisa el mensaje anterior.
exit /b 1
