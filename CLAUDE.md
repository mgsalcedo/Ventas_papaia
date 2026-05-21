# CLAUDE.md — Memoria del proyecto

## Qué es esto
Dashboard local de análisis de contenido para Instagram. Lee datos de Zernio API, los cachea en SQLite, y genera ideas de contenido con Claude Sonnet via Anthropic API.

## Stack
- Python 3.9+ con venv en `.venv/`
- Streamlit 1.39 (UI)
- Plotly 5.24 (gráficos)
- SQLite (cache local en `data.nosync/cache.db`)
- anthropic==0.97.0 + httpx==0.28.1
- Zernio API (datos de Instagram/YouTube)

## Archivos principales
- `app.py` — UI Streamlit, 7 pestañas
- `refresh.py` — descarga datos de Zernio
- `zernio_client.py` — cliente REST con retry/backoff
- `cache.py` — 18 tablas SQLite, lectores/escritores
- `ideas.py` — generación con Claude, prompt caching
- `idea_filters.py` — filtros de comentarios/DMs triviales
- `prompts/ideas_system.md` — system prompt calibrado, NO modificar sin razón

## Variables de entorno (.env)
```
ZERNIO_API_KEY=sk_...
ZERNIO_ACCOUNT_ID=          # auto-descubierto en primer refresh
ZERNIO_ACCOUNT_ID_YOUTUBE=  # opcional
ANTHROPIC_API_KEY=sk-ant-api03-...
DASHBOARD_TZ=America/Lima
```

## Importante: load_dotenv(override=True)
Siempre usar `override=True` en `refresh.py`, `app.py`, `ideas.py` para que las keys del `.env` sobreescriban variables de entorno vacías del shell.

## Endpoints Zernio verificados
Base: `https://api.zernio.com/v1`
- NO uses `/v1/analytics` (bug, devuelve 400)
- Mejor hora: `/analytics/best-time` (NO `/best-time-to-post`)
- Usage: `/usage-stats` (NO `/usage`)

## Sistema de ideas
- Distribución IG: 10 comments + 5 DMs + 10 top_content = ~25 ideas
- Distribución YT: 10 comments + 10 top_content = ~20 ideas
- Descartes van en bloque NO cacheado del user message
- max_tokens=16000 para cubrir 25 ideas con 3 bloques

## Para correr localmente
```bash
source .venv/bin/activate
python refresh.py          # primer refresh (auto-descubre account_id)
.venv/bin/streamlit run app.py
```
