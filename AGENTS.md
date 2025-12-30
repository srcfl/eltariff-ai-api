# Repositoryriktlinjer

## Projektstruktur & modulindelning
Detta är en FastAPI-tjänst som är paketerad som ett Python-modul.

- Källkod finns i `src/eltariff/` med API-routes under `src/eltariff/api/` och logik i `src/eltariff/services/`.
- Pydantic-modeller finns i `src/eltariff/models/`.
- HTML-mallar och statiska tillgångar finns i `src/eltariff/templates/` och `src/eltariff/static/`.
- Genererade resultat lagras i `data/results/` (gitignored).
- Explorer-listor ska hämtas från tariffkatalogen via `https://eltariff.deplide.org/tariffcatalogue/all`, inte hårdkodas.
- Resultat ska endast sparas om det är elnäts-/effekttariffer (valideras server-side).

## Bygg, test och utvecklingskommandon
Använd `uv` för beroendehantering och körning.

- `uv sync` installerar alla beroenden (inklusive dev-beroenden från `pyproject.toml`).
- `uv run uvicorn eltariff.main:app --reload` startar utvecklingsservern.
- `PYTHONPATH=src uv run uvicorn eltariff.main:app --reload` om imports fallerar lokalt.
- `fly deploy` deployar till Fly.io (se `DEPLOYMENT.md`).

## Kodstil & namngivning
Ingen formatterare är tvingande i repot ännu.

- Python: följ PEP 8 med 4-space indentation.
- Moduler och funktioner använder `snake_case`; Pydantic-modeller använder `PascalCase`.
- JSON-utdata från RISE-modeller använder camelCase-alias (se `src/eltariff/models/rise_schema.py`).

## Testningsriktlinjer
Pytest finns som dev-beroende, men inga tester är spårade i nuläget.

- Om du lägger till tester, placera dem under `tests/` och namnge filer `test_*.py`.
- Kör tester med `uv run pytest`.

## Commit- & PR-riktlinjer
Senaste commits använder korta, imperativa svenska meddelanden (t.ex. “Lägg till ...”, “Förbättra ...”).

- Håll commit-meddelanden korta och handlingsinriktade.
- PR:er ska ha en kort beskrivning, relevanta API-ändringar och screenshots vid UI-uppdateringar.

## Säkerhet & konfiguration
- Obligatorisk env-variabel: `ANTHROPIC_API_KEY` (sätts i `.env`).
- Valfritt: `ELTARIFF_STORAGE_DIR` för egen lagringsplats.
- Valfritt: `ELTARIFF_CLEANUP_TOKEN` för att skydda städ-endpointen `/api/results/cleanup`.
- Rate limiting och SSRF-skydd finns; behåll dem när parse/scrape-flöden ändras.
