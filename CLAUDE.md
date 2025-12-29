# Eltariff AI API - Claude Code Instructions

## Projektöversikt

AI-drivet verktyg för att konvertera svenska elnätstariffer till RISE-standard API.
Byggt av Sourceful Labs AB.

**Live**: https://eltariff.sourceful.dev

## Snabbkommandon

```bash
# Starta utvecklingsserver
source .env && uv run uvicorn eltariff.main:app --reload

# Kör med PYTHONPATH (om import-problem)
PYTHONPATH=src uv run uvicorn eltariff.main:app --reload

# Installera beroenden
uv sync

# Deploy till Fly.io
fly deploy
```

## Projektstruktur

```
src/eltariff/
├── main.py              # FastAPI app, routes för / och /explorer
├── api/
│   ├── parse.py         # AI-tolkning: /api/parse/{text,pdf,url,combined}
│   ├── generate.py      # Export: /api/generate/{json,excel,package}
│   └── explore.py       # API Explorer: /api/explore/{goteborg-energi,tekniska-verken}
├── models/
│   ├── rise_schema.py   # Pydantic RISE-modeller (snake_case attrs, camelCase JSON)
│   └── input.py         # Request-modeller
├── services/
│   ├── ai_parser.py     # Anthropic Claude integration
│   ├── pdf_parser.py    # PyMuPDF för PDF-extraktion
│   ├── url_scraper.py   # URL/PDF-scraping med httpx
│   └── api_generator.py # Genererar deployment-paket
├── templates/
│   ├── index.html       # Huvudsida med tariff-editor
│   └── explorer.html    # API Explorer för befintliga API:er
└── static/
    └── sourceful-logo.png
```

## Viktiga tekniska detaljer

### RISE Eltariff API-standard
- Följer https://github.com/RI-SE/Eltariff-API
- Pydantic-modeller använder snake_case internt, camelCase i JSON (via alias)
- Exempel: `price_ex_vat` → `priceExVat` i JSON-output

### Kända RISE API:er
- Göteborg Energi: `https://api.goteborgenergi.cloud/gridtariff/v0`
- Tekniska verken: `https://api.tekniskaverken.net/subscription/public/v0`

### Rate Limiting
- 10 AI-anrop per timme per IP (slowapi)
- Gäller endpoints under `/api/parse/`

### Frontend
- Vanilla JS med Tailwind CSS (via CDN)
- Jinja2-templates
- Färger: `sourceful-green: #017E7A`, `sourceful-grey: #1A1A1A`

## Miljövariabler

```bash
ANTHROPIC_API_KEY=sk-ant-...  # Obligatorisk
```

## Vanliga uppgifter

### Lägga till nytt elnätsbolag i Explorer
1. Verifiera att de har RISE-kompatibelt API
2. Lägg till i `KNOWN_APIS` dict i `src/eltariff/api/explore.py`
3. Skapa endpoint-funktion som anropar `fetch_tariffs()`

### Ändra AI-prompt
- Se `src/eltariff/services/ai_parser.py`
- Prompten innehåller RISE-schema och exempel

### Uppdatera RISE-schema
- Modeller finns i `src/eltariff/models/rise_schema.py`
- Generatorn i `api_generator.py` måste matcha schemat

## Deployment

Fly.io med custom domain:
- App: `eltariff-ai-api`
- Domain: `eltariff.sourceful.dev`
- Se `DEPLOYMENT.md` för detaljer
