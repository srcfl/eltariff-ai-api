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

# Deploy (Railway)
railway up
```

## Projektstruktur

```
src/eltariff/
├── main.py              # FastAPI app, routes för / och /explorer
├── api/
│   ├── parse.py         # AI-tolkning: /api/parse/{text,pdf,url,combined,improve}
│   ├── generate.py      # Export: /api/generate/{json,excel,package}
│   ├── explore.py       # API Explorer: /api/explore/{goteborg-energi,tekniska-verken}
│   └── results.py       # Delningsfunktion: /api/results/{save,list,id}
├── models/
│   ├── rise_schema.py   # Pydantic RISE-modeller (snake_case attrs, camelCase JSON)
│   └── input.py         # Request-modeller
├── services/
│   ├── ai_parser.py     # OpenRouter integration (Claude Sonnet 4)
│   ├── pdf_parser.py    # PyMuPDF för PDF-extraktion
│   ├── url_scraper.py   # URL/PDF-scraping med httpx + Crawl4AI
│   ├── storage.py       # Filbaserad lagring för delningsbara resultat
│   └── api_generator.py # Genererar deployment-paket
├── templates/
│   ├── index.html       # Huvudsida med tariff-editor (skapar/visar)
│   └── explorer.html    # API Explorer + användargenererade API:er
└── static/
    └── sourceful-logo.png
data/results/            # Sparade resultat (gitignored)
```

## Nyckelfunktioner (december 2024)

### Delningsbara resultat
- Resultat auto-sparas med unik ID och URL uppdateras
- Format: `/r/{id}` → t.ex. `https://eltariff.sourceful.dev/r/abc123`
- Två lägen: "Skapa" (redigering) och "Visa" (endast läsning)
- Tracking: hashed IP, user-agent, käll-URL
- Explorer visar "Användargenererade API:er" sektion

### AI-parser
- Använder OpenRouter som backend (anthropic/claude-sonnet-4)
- OpenAI-kompatibelt API via https://openrouter.ai/api/v1
- Terminal UI i frontend visar progress-meddelanden

### URL-scraping med PDF-stöd
- URL kan peka på PDF direkt (Content-Type detection)
- Crawl4AI för JavaScript-renderade sidor
- SSRF-skydd för interna IP-adresser

## Viktiga tekniska detaljer

### RISE Eltariff API-standard
- Följer https://github.com/RI-SE/Eltariff-API
- Pydantic-modeller använder snake_case internt, camelCase i JSON (via alias)
- Exempel: `price_ex_vat` → `priceExVat` i JSON-output

### Kända RISE API:er
- Göteborg Energi: `https://api.goteborgenergi.cloud/gridtariff/v0`
- Tekniska verken: `https://api.tekniskaverken.net/subscription/public/v0`

### Rate Limiting
- 3 AI-anrop per timme per IP (slowapi)
- Gäller endpoints under `/api/parse/`

### Frontend
- Vanilla JS med Tailwind CSS (via CDN)
- Jinja2-templates
- Färger: `sourceful-green: #017E7A`, `sourceful-grey: #1A1A1A`
- Mobilanpassad (responsiv layout)

## Miljövariabler

```bash
OPENROUTER_API_KEY=sk-or-v1-...  # Obligatorisk (OpenRouter API-nyckel)
ELTARIFF_STORAGE_DIR=/path       # Optional: Var resultat sparas
```

## API Endpoints

### Parse (AI-tolkning)
- `POST /api/parse/text` - Fritext till RISE
- `POST /api/parse/pdf` - PDF till RISE
- `POST /api/parse/url` - URL/webbsida till RISE (stödjer PDF-länkar)
- `POST /api/parse/combined` - Kombinera URL + PDF + text
- `POST /api/parse/improve` - Förbättra befintlig tariff med AI

### Generate (Export)
- `POST /api/generate/json` - Ladda ner JSON (RISE-format)
- `POST /api/generate/excel` - Exportera till Excel
- `POST /api/generate/package` - Docker deployment-paket (ZIP)

### Results (Delning)
- `POST /api/results/save` - Spara resultat, returnerar ID
- `GET /api/results/list/recent` - Lista senaste resultat
- `GET /api/results/{id}` - Hämta sparat resultat

### Explore (Befintliga API:er)
- `GET /api/explore/goteborg-energi` - Göteborg Energi tariffer
- `GET /api/explore/tekniska-verken` - Tekniska verken tariffer
- `POST /api/explore/fetch` - Hämta från valfritt RISE-API

## Vanliga uppgifter

### Lägga till nytt elnätsbolag i Explorer
1. Verifiera att de har RISE-kompatibelt API
2. Lägg till i `KNOWN_APIS` dict i `src/eltariff/api/explore.py`
3. Skapa endpoint-funktion som anropar `fetch_tariffs()`

### Ändra AI-prompt
- Se `src/eltariff/services/ai_parser.py`
- `SYSTEM_PROMPT` för parse, `improve_tariffs()` för förbättringar
- Prompten innehåller RISE-schema och exempel

### Uppdatera RISE-schema
- Modeller finns i `src/eltariff/models/rise_schema.py`
- Generatorn i `api_generator.py` måste matcha schemat

## Kända problem

### OpenRouter API-fel
- Tillfälliga infrastrukturproblem kan förekomma
- Åtgärd: Vänta och försök igen
- Modell kan bytas i `OPENROUTER_MODEL` i `ai_parser.py`

## Deployment

Railway med custom domain:
- App: `eltariff-ai-api`
- Domain: `eltariff.sourceful.dev`
- Källkod: https://github.com/srcfl/eltariff-ai-api
