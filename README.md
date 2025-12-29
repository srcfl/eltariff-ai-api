# Eltariff AI API

AI-drivet verktyg för att konvertera svenska elnätstariffer till RISE-standard API.

**Byggt av [Sourceful Labs AB](https://sourceful.energy)**

## Funktioner

- **Tariff-tolkning**: Konvertera PDF, fritext eller webbsidor till RISE-format med AI
- **API-generering**: Generera kompletta deployment-paket (Docker, FastAPI, OpenAPI)
- **API Explorer**: Utforska och visualisera befintliga RISE-kompatibla API:er

## Snabbstart

### Förutsättningar

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Anthropic API-nyckel

### Installation

```bash
# Klona repot
git clone https://github.com/sourceful-labs/eltariff-ai-api.git
cd eltariff-ai-api

# Installera beroenden
uv sync

# Skapa .env-fil
cp .env.example .env
# Redigera .env och lägg till din ANTHROPIC_API_KEY
```

### Köra lokalt

```bash
# Starta servern
uv run uvicorn eltariff.main:app --reload

# Öppna i webbläsare
open http://localhost:8000
```

## API-dokumentation

- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## Endpoints

| Endpoint | Metod | Beskrivning |
|----------|-------|-------------|
| `/api/parse/text` | POST | Tolka tariff från fritext |
| `/api/parse/pdf` | POST | Tolka tariff från PDF |
| `/api/parse/url` | POST | Tolka tariff från webbsida (inkl. PDF-länkar) |
| `/api/parse/combined` | POST | Kombinera URL + PDF + fritext i en analys |
| `/api/generate/json` | POST | Ladda ner tariffdata som JSON (RISE-format) |
| `/api/generate/package` | POST | Generera deployment-paket (ZIP med Docker) |
| `/api/generate/excel` | POST | Exportera till Excel |
| `/api/explore/goteborg-energi` | GET | Hämta tariffer från Göteborg Energi (12 st) |
| `/api/explore/tekniska-verken` | GET | Hämta tariffer från Tekniska verken (171 st) |
| `/api/explore/fetch` | POST | Hämta tariffer från valfritt RISE-API |

## RISE Eltariff API-standard

Detta verktyg följer [RISE Eltariff API-standarden](https://github.com/RI-SE/Eltariff-API) för svenska elnätstariffer.

## Säkerhet

- **Rate limiting**: 10 AI-anrop/timme per IP
- **SSRF-skydd**: Blockering av interna IP-adresser
- **Inputvalidering**: Storleksbegränsningar på text (100KB) och PDF (10MB)

## Deployment

Se [DEPLOYMENT.md](DEPLOYMENT.md) för instruktioner om deployment till Fly.io med custom domain.

```bash
# Snabb-deploy till Fly.io
fly launch
fly secrets set ANTHROPIC_API_KEY=din-nyckel
fly deploy
```

## Miljövariabler

| Variabel | Beskrivning | Obligatorisk |
|----------|-------------|--------------|
| `ANTHROPIC_API_KEY` | API-nyckel för Claude | Ja |

## Projektstruktur

```
eltariff-ai-api/
├── src/eltariff/
│   ├── main.py              # FastAPI app
│   ├── api/
│   │   ├── parse.py         # AI-tolkning endpoints
│   │   ├── generate.py      # Kodgenerering
│   │   └── explore.py       # API Explorer
│   ├── models/
│   │   ├── rise_schema.py   # Pydantic RISE-modeller
│   │   └── input.py         # Input-modeller
│   ├── services/
│   │   ├── ai_parser.py     # Anthropic-integration
│   │   ├── pdf_parser.py    # PDF-extraktion
│   │   ├── url_scraper.py   # URL-scraping
│   │   └── api_generator.py # Kodgenerering
│   └── templates/
│       └── *.html           # Web UI
├── Dockerfile
├── fly.toml
└── pyproject.toml
```

## Licens

Proprietär - Sourceful Labs AB

## Kontakt

- Webb: [sourceful.energy](https://sourceful.energy)
- E-post: hello@sourceful.energy
