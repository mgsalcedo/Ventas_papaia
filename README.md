# Dashboard de Análisis de Contenido

Dashboard local para analizar tu cuenta de Instagram con IA.

## Requisitos

- Python 3.9+
- Cuenta de Instagram Business o Creator
- API key de Zernio (con add-ons Analytics e Inbox activos)
- API key de Anthropic

## Instalación

```bash
# 1. Crea el entorno virtual
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# 2. Instala dependencias
pip install -r requirements.txt

# 3. Configura tus API keys (ya están en .env si usaste Claude Code para el setup)
# Verifica que .env tiene:
#   ZERNIO_API_KEY=sk_...
#   ANTHROPIC_API_KEY=sk-ant-api03-...
#   DASHBOARD_TZ=America/Lima
```

## Uso diario

### Refrescar datos (~30 segundos)

```bash
source .venv/bin/activate
python refresh.py
```

La primera vez, `refresh.py` auto-descubre y guarda tu account ID de Zernio.

### Abrir el dashboard

```bash
source .venv/bin/activate
.venv/bin/streamlit run app.py
```

Se abre en http://localhost:8501

Para cerrar: `Ctrl+C` en la terminal.

### Generar ideas de contenido

1. Abre el dashboard
2. Ve a la pestaña **💡 Ideas**
3. Selecciona Instagram
4. Click en **✨ Generar todas las ideas de Instagram**
5. Espera ~15-30 segundos (~$0.10-0.30 USD por generación)

## Troubleshooting

| Error | Solución |
|-------|----------|
| `[401] Unauthorized` | API key de Zernio expiró. Genera nueva en zernio.com |
| `[402] Analytics add-on required` | Activa add-on Analytics en Zernio |
| `[403] Inbox addon required` | Activa add-on Inbox en Zernio |
| Dashboard no abre | Asegúrate de activar el venv: `source .venv/bin/activate` |
| Ideas fallan | Verifica `ANTHROPIC_API_KEY` en `.env` |

## Estructura del proyecto

```
dashboard-instagram/
├── .env                    # API keys (no se sube a git)
├── .env.example            # Plantilla
├── app.py                  # UI Streamlit (7 pestañas)
├── refresh.py              # Descarga datos de Zernio
├── zernio_client.py        # Cliente REST Zernio
├── cache.py                # Base de datos SQLite local
├── ideas.py                # Generación de ideas con Claude
├── idea_filters.py         # Filtros de comentarios/DMs triviales
├── prompts/
│   └── ideas_system.md     # System prompt para generación de ideas
└── data.nosync/
    └── cache.db            # Base de datos local (no se sube a git)
```
