# Eltariff AI

AI-drivet webbverktyg för att konvertera svenska elnätstariffer till RISE-standard.

**Byggt av [Sourceful Labs AB](https://sourceful.energy)**

**Live:** https://eltariff.sourceful.dev

## Vad är detta?

Detta är en webbapplikation som hjälper användare att:

- **Skapa tariffer**: Konvertera PDF:er, fritext eller webbsidor till RISE-format med hjälp av AI
- **Dela resultat**: Varje genererad tariff får en unik URL som kan delas
- **Utforska befintliga API:er**: Bläddra bland existerande RISE-API:er via [tariffkatalogen](https://eltariff.deplide.org/tariffcatalogue/all)
- **Exportera**: Ladda ner som JSON (RISE-format), Excel eller komplett Docker-paket

## RISE Eltariff API-standard

Verktyget följer [RISE Eltariff API-standarden](https://github.com/RI-SE/Eltariff-API) för svenska elnätstariffer.

## Lokal utveckling

### Förutsättningar

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- OpenRouter API-nyckel (för AI-funktioner)

### Installation

```bash
# Klona repot
git clone https://github.com/srcfl/eltariff-ai-api.git
cd eltariff-ai-api

# Installera Python-beroenden
uv sync

# Skapa .env-fil
cp .env.example .env
# Redigera .env och lägg till din OPENROUTER_API_KEY
```

### Köra lokalt

```bash
# Starta servern
source .env && uv run uvicorn eltariff.main:app --reload

# Öppna i webbläsare
open http://localhost:8000
```

## Miljövariabler

| Variabel | Beskrivning | Obligatorisk |
|----------|-------------|--------------|
| `OPENROUTER_API_KEY` | API-nyckel för OpenRouter | Ja |
| `ELTARIFF_STORAGE_DIR` | Lagringsplats för resultat | Nej |
| `ELTARIFF_CLEANUP_TOKEN` | Token för städ-endpoint | Nej |

## Deployment

Applikationen kan deployas till valfri container-plattform (Docker, Railway, Fly.io, etc).

### Docker

```bash
docker build -t eltariff-ai-api .
docker run -e OPENROUTER_API_KEY=din-nyckel -p 8000:8000 eltariff-ai-api
```

### Miljövariabler vid deployment

Se till att sätta `OPENROUTER_API_KEY` som en hemlig miljövariabel i din hosting-plattform.

## Licens

Proprietär - Sourceful Labs AB

## Kontakt

- Webb: [sourceful.energy](https://sourceful.energy)
- E-post: info@sourceful.energy
