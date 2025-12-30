# Eltariff AI

AI-drivet webbverktyg för att konvertera svenska elnätstariffer till RISE-standard.

**Byggt av [Sourceful Labs AB](https://sourceful.energy)**

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
- Node.js (för Tailwind CSS)
- Anthropic API-nyckel

### Installation

```bash
# Klona repot
git clone https://github.com/sourceful-labs/eltariff-ai-api.git
cd eltariff-ai-api

# Installera Python-beroenden
uv sync

# Bygg optimerad CSS (Tailwind)
npm install
npm run build:css

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

## Miljövariabler

| Variabel | Beskrivning | Obligatorisk |
|----------|-------------|--------------|
| `ANTHROPIC_API_KEY` | API-nyckel för Claude | Ja |
| `ELTARIFF_STORAGE_DIR` | Lagringsplats för resultat | Nej |
| `ELTARIFF_CLEANUP_TOKEN` | Token för städ-endpoint | Nej |

## Deployment

Se [DEPLOYMENT.md](DEPLOYMENT.md) för instruktioner om deployment till Fly.io med custom domain.

```bash
# Snabb-deploy till Fly.io
fly launch
fly secrets set ANTHROPIC_API_KEY=din-nyckel
fly deploy
```

## Licens

Proprietär - Sourceful Labs AB

## Kontakt

- Webb: [sourceful.energy](https://sourceful.energy)
- E-post: info@sourceful.energy
