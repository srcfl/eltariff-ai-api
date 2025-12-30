"""AI-powered tariff parser using OpenRouter."""

import json
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from openai import OpenAI

# OpenRouter configuration
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "anthropic/claude-sonnet-4"  # Claude Sonnet 4 via OpenRouter

from ..models.rise_schema import (
    ActivePeriod,
    CalendarPattern,
    CalendarPatternReference,
    ComponentType,
    Currency,
    DEFAULT_CALENDAR_PATTERNS,
    Direction,
    PeakIdentificationSettings,
    Price,
    PriceComponent,
    PriceElement,
    RecurringPeriod,
    Tariff,
    TariffsResponse,
    Unit,
    ValidPeriod,
)

SYSTEM_PROMPT = """Du är en expert på svenska elnätstariffer och RISE Eltariff API-standarden.

Din uppgift är att analysera tariffbeskrivningar och konvertera dem till strukturerad JSON enligt RISE-standarden.
EXTRAHERA ALLTID företagsnamn (companyName) från innehållet - det står ofta i sidhuvud, footer eller domännamn.

## RISE Eltariff API-standard (OBLIGATORISK)

Du MÅSTE följa RISE-standarden exakt. Fältnamn är camelCase och följer denna specifikation:

### Tariff (huvudobjekt)
- `name` (string, OBLIGATORISK) - Namn på tariffen
- `description` (string, valfri) - Beskrivning
- `validPeriod` (objekt, OBLIGATORISK) - `fromIncluding` (datum), `toExcluding` (datum eller null)
- `timeZone` (string) - Standard: "Europe/Stockholm"
- `companyName` (string, OBLIGATORISK) - Företagsnamn
- `companyOrgNo` (string, OBLIGATORISK) - Organisationsnummer (kan vara tom sträng)
- `product` (string, valfri) - Produktnamn
- `direction` (enum) - "consumption" eller "production"
- `billingPeriod` (string) - ISO 8601 duration, t.ex. "P1M" (månadsvis)
- `fixedPrice`, `energyPrice`, `powerPrice` - Se nedan

### Price (prisobjekt)
- `priceExVat` (decimal, OBLIGATORISK) - Pris exklusive moms
- `priceIncVat` (decimal, OBLIGATORISK) - Pris inklusive moms
- `currency` (string) - "SEK" eller "EUR"

### PriceComponent (för alla typer)
- `name` (string, OBLIGATORISK)
- `description` (string, valfri)
- `type` (string, OBLIGATORISK) - "fixed", "variable", "peak", eller "dynamic"
- `reference` (string) - Standard: "main"
- `price` (Price-objekt, OBLIGATORISK)
- `unit` (string) - "kWh", "kW", "kVAr"
- `pricedPeriod` (string) - "P1M" (månad) eller "P1Y" (år)
- `recurringPeriods` (array, valfri) - För tidsdifferentiering
- `peakIdentificationSettings` (objekt, valfri) - För effektavgifter

### RecurringPeriod (tidsdifferentiering)
- `reference` (string) - Standard: "main"
- `frequency` (string) - "P1D" (daglig)
- `activePeriods` (array) - Lista av ActivePeriod

### ActivePeriod
- `fromIncluding` (time) - T.ex. "06:00:00"
- `toExcluding` (time) - T.ex. "22:00:00"
- `calendarPatternReferences` (objekt) - `include` och `exclude` arrays med t.ex. ["weekdays"], ["holidays"]

### PeakIdentificationSettings (OBLIGATORISK för effektavgifter)
- `peakFunction` (string) - T.ex. "peak(main)" eller "max(peak(high),peak(low)/2)"
- `peakIdentificationPeriod` (string) - T.ex. "P1M" (månad), "P1D" (dag)
- `peakDuration` (string) - T.ex. "PT1H" (1 timme)
- `numberOfPeaksForAverageCalculation` (integer) - Antal toppar för medelvärde

## VIKTIGT: Skapa SEPARATA tariffer!

Om det finns olika priser för olika säkringsstorlekar (16A, 20A, 25A, 35A, etc.) ska du skapa EN SEPARAT TARIFF för varje säkringsstorlek!

## Svenska elnätstariffer - Bakgrund

Svenska elnätstariffer består typiskt av:

1. **Fast avgift** (fixedPrice): Månads- eller årsavgift som inte beror på förbrukning
2. **Energiavgift** (energyPrice): Pris per kWh, ofta tidsdifferentierat
3. **Effektavgift** (powerPrice): Pris per kW - kräver peakIdentificationSettings!

## Tidsdifferentiering - Standardmönster

- **Höglast**: vardagar 06:00-22:00 → `calendarPatternReferences: {"include": ["weekdays"], "exclude": ["holidays"]}`
- **Låglast**: nätter + helger → `calendarPatternReferences: {"include": ["weekends", "holidays"]}` ELLER tidsintervall 22:00-06:00

## Output-format

```json
{
  "tariffs": [
    {
      "name": "Tariffnamn",
      "description": "Beskrivning",
      "validPeriod": {"fromIncluding": "2025-01-01", "toExcluding": null},
      "companyName": "Företagsnamn AB",
      "companyOrgNo": "",
      "direction": "consumption",
      "billingPeriod": "P1M",
      "fixedPrice": {
        "name": "Fast avgift",
        "components": [{
          "name": "Abonnemangsavgift",
          "type": "fixed",
          "price": {"priceExVat": 100, "priceIncVat": 125, "currency": "SEK"},
          "pricedPeriod": "P1M"
        }]
      },
      "energyPrice": {
        "name": "Energiavgift",
        "components": [{
          "name": "Överföringsavgift höglast",
          "type": "variable",
          "price": {"priceExVat": 0.20, "priceIncVat": 0.25, "currency": "SEK"},
          "unit": "kWh",
          "recurringPeriods": [{
            "reference": "main",
            "frequency": "P1D",
            "activePeriods": [{
              "fromIncluding": "06:00:00",
              "toExcluding": "22:00:00",
              "calendarPatternReferences": {"include": ["weekdays"], "exclude": ["holidays"]}
            }]
          }]
        }]
      },
      "powerPrice": {
        "name": "Effektavgift",
        "description": "Beräknas på medelvärde av 3 högsta toppar",
        "components": [{
          "name": "Effektavgift",
          "type": "peak",
          "price": {"priceExVat": 40, "priceIncVat": 50, "currency": "SEK"},
          "unit": "kW",
          "peakIdentificationSettings": {
            "peakFunction": "peak(main)",
            "peakIdentificationPeriod": "P1M",
            "peakDuration": "PT1H",
            "numberOfPeaksForAverageCalculation": 3
          }
        }]
      }
    }
  ],
  "warnings": ["Lista med potentiella problem eller osäkerheter"]
}
```

## Validering och Varningar

Inkludera alltid ett `warnings`-fält med en array av strängar som beskriver:
- Oklarheter i källmaterialet
- Antaganden du har gjort
- Information som saknades och fylldes i med standardvärden
- Potentiella fel i extraktionen
- Om priser verkar ovanligt höga eller låga

## Viktiga regler

1. Alla priser MÅSTE ha både `priceExVat` och `priceIncVat` (25% moms i Sverige)
2. Använd ISO 8601 för datum (YYYY-MM-DD) och tider (HH:MM:SS)
3. EXTRAHERA företagsnamn från innehållet (URL, sidhuvud, etc.)
4. `validPeriod.fromIncluding` är OBLIGATORISK - använd 2025-01-01 om inte annat anges
5. Returnera ENDAST giltig JSON, ingen annan text före eller efter
6. **EFFEKTAVGIFTER KRÄVER peakIdentificationSettings** - beskriv beräkningsmetoden!
7. **ÅRSAVGIFTER**: Om avgiften anges per år (kr/år), använd `"pricedPeriod": "P1Y"`
8. **SKAPA MÅNGA TARIFFER**: Varje säkringsstorlek ska bli en EGEN tariff!
9. **ENERGIAVGIFTER**: Använd `type: "variable"` för kWh-priser (inte "fixed")
10. **SPOTPRIS**: Om priset är "variabelt" eller "spotbaserat", skriv det i description
"""


class TariffParser:
    """AI-powered parser for converting tariff documents to RISE format."""

    def __init__(self, api_key: str | None = None):
        """Initialize the parser with OpenRouter API key."""
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OpenRouter API key required")
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=self.api_key,
        )

    async def parse_text(
        self, text: str, company_name: str | None = None
    ) -> TariffsResponse:
        """Parse tariff information from text using Claude via OpenRouter."""
        # Truncate input if too long
        max_input_chars = 50000
        if len(text) > max_input_chars:
            text = text[:max_input_chars] + "\n\n[... innehåll trunkerat för längd ...]"

        user_prompt = f"""Analysera följande tariffbeskrivning och konvertera till RISE JSON-format.

VIKTIGT:
- Returnera ENDAST giltig JSON, ingen annan text
- Skapa EN SEPARAT TARIFF för varje säkringsstorlek (16A, 20A, 25A, etc.)
- Inkludera calendarPatterns för weekdays, weekends, holidays
- Om ingen tariff hittas, returnera: {{"tariffs": []}}

{f"Företagsnamn: {company_name}" if company_name else ""}

Tariffbeskrivning:
{text}"""

        response = self.client.chat.completions.create(
            model=OPENROUTER_MODEL,
            max_tokens=16000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content
        return self._parse_response(content)

    def parse_text_streaming(
        self, text: str, company_name: str | None = None
    ):
        """Generator that yields progress updates and final result."""
        # Truncate input if too long
        max_input_chars = 50000
        if len(text) > max_input_chars:
            text = text[:max_input_chars] + "\n\n[... innehåll trunkerat för längd ...]"

        user_prompt = f"""Analysera följande tariffbeskrivning och konvertera till RISE JSON-format.

VIKTIGT:
- Returnera ENDAST giltig JSON, ingen annan text
- Skapa EN SEPARAT TARIFF för varje säkringsstorlek (16A, 20A, 25A, etc.)
- Inkludera calendarPatterns för weekdays, weekends, holidays
- Om ingen tariff hittas, returnera: {{"tariffs": []}}

{f"Företagsnamn: {company_name}" if company_name else ""}

Tariffbeskrivning:
{text}"""

        content = ""

        try:
            # Streaming via OpenRouter/OpenAI format
            stream = self.client.chat.completions.create(
                model=OPENROUTER_MODEL,
                max_tokens=16000,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                stream=True,
            )

            # Accumulate the text from stream
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content += chunk.choices[0].delta.content

            # Parse and yield final result
            if content:
                result = self._parse_response(content)
                yield {'type': 'result', 'data': result.model_dump(by_alias=True)}
            else:
                yield {'type': 'error', 'message': 'AI returnerade ingen textdata'}

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield {'type': 'error', 'message': f'AI-fel: {str(e)}'}

    async def parse_pdf_content(
        self, pdf_text: str, company_name: str | None = None
    ) -> TariffsResponse:
        """Parse tariff information from PDF text content."""
        return await self.parse_text(pdf_text, company_name)

    async def improve_tariffs(
        self, existing_tariffs: dict, instruction: str
    ) -> TariffsResponse:
        """Improve existing tariff data based on user instruction."""
        # Use compact JSON to save tokens
        existing_json = json.dumps(existing_tariffs, ensure_ascii=False, separators=(',', ':'))

        # Simple system prompt for modifications (not the full RISE spec)
        improve_system = """Du är expert på RISE Eltariff API-standarden.
Din uppgift är att modifiera befintlig tariff-JSON enligt användarens instruktion.

REGLER:
- Returnera ENDAST giltig JSON, ingen annan text
- Behåll ALL befintlig data som inte explicit ska ändras
- Följ RISE-standarden: camelCase fältnamn, priser med priceExVat/priceIncVat
- Inkludera både tariffs och calendarPatterns i svaret"""

        user_prompt = f"""Modifiera denna tariff-JSON enligt instruktionen.

JSON:
{existing_json}

INSTRUKTION: {instruction}

Returnera den uppdaterade JSON:en (endast JSON, ingen förklaring):"""

        response = self.client.chat.completions.create(
            model=OPENROUTER_MODEL,
            max_tokens=16000,
            messages=[
                {"role": "system", "content": improve_system},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content
        return self._parse_response(content)

    async def explain_tariff(self, tariff: Tariff) -> dict[str, Any]:
        """Generate a human-readable explanation of a tariff."""
        tariff_json = tariff.model_dump_json(by_alias=True, indent=2)

        user_prompt = f"""Förklara följande tariff på enkel svenska för en vanlig elkund:

{tariff_json}

Svara med följande struktur:
1. Sammanfattning (2-3 meningar)
2. Fasta kostnader (vad betalar man oavsett förbrukning)
3. Energikostnader (pris per kWh, tidsvariationer)
4. Effektkostnader (om det finns)
5. Tips för att minimera kostnader

Formatera svaret som JSON:
{{
  "tariffName": "...",
  "summary": "...",
  "fixedCosts": "...",
  "energyCosts": "...",
  "powerCosts": "..." eller null,
  "timeVariations": "...",
  "tips": ["...", "..."]
}}"""

        response = self.client.chat.completions.create(
            model=OPENROUTER_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.choices[0].message.content
        # Try to extract JSON from the response
        try:
            # Find JSON in response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass

        return {
            "tariffName": tariff.name,
            "summary": content,
            "fixedCosts": "",
            "energyCosts": "",
            "powerCosts": None,
            "timeVariations": None,
            "tips": [],
        }

    def _parse_response(self, content: str) -> TariffsResponse:
        """Parse the AI response into TariffsResponse."""
        data = None

        # Try to extract JSON from the response
        try:
            # Find JSON in response (may have surrounding text)
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                data = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
        except json.JSONDecodeError as e:
            # Try to repair common JSON issues
            try:
                json_str = self._repair_json(content)
                data = json.loads(json_str)
            except Exception:
                raise ValueError(f"Failed to parse AI response as JSON: {e}")

        # Convert to TariffsResponse
        tariffs = []
        for t in data.get("tariffs", []):
            tariff = self._parse_tariff(t)
            tariffs.append(tariff)

        # Extract AI-generated warnings
        warnings = data.get("warnings", [])
        if not isinstance(warnings, list):
            warnings = []

        return TariffsResponse(
            tariffs=tariffs,
            calendarPatterns=DEFAULT_CALENDAR_PATTERNS,
            warnings=warnings,
        )

    def _repair_json(self, content: str) -> str:
        """Attempt to repair malformed JSON."""
        # Find JSON block
        start = content.find("{")
        if start < 0:
            raise ValueError("No JSON found")

        json_str = content[start:]

        # Count brackets to find balanced JSON
        brace_count = 0
        bracket_count = 0
        in_string = False
        escape_next = False
        end_pos = 0

        for i, char in enumerate(json_str):
            if escape_next:
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
            elif char == "[":
                bracket_count += 1
            elif char == "]":
                bracket_count -= 1

            if brace_count == 0 and bracket_count == 0 and i > 0:
                end_pos = i + 1
                break

        if end_pos > 0:
            return json_str[:end_pos]

        # If still unbalanced, try to close it
        json_str = json_str.rstrip()
        while brace_count > 0:
            json_str += "}"
            brace_count -= 1
        while bracket_count > 0:
            json_str += "]"
            bracket_count -= 1

        return json_str

    def _parse_tariff(self, data: dict) -> Tariff:
        """Parse a single tariff from dict."""
        valid_period = ValidPeriod(
            fromIncluding=date.fromisoformat(data["validPeriod"]["fromIncluding"]),
            toExcluding=date.fromisoformat(data["validPeriod"]["toExcluding"])
            if data["validPeriod"].get("toExcluding")
            else None,
        )

        fixed_price = None
        if "fixedPrice" in data and data["fixedPrice"]:
            fixed_price = self._parse_price_element(data["fixedPrice"])

        energy_price = None
        if "energyPrice" in data and data["energyPrice"]:
            energy_price = self._parse_price_element(data["energyPrice"])

        power_price = None
        if "powerPrice" in data and data["powerPrice"]:
            power_price = self._parse_price_element(data["powerPrice"])

        return Tariff(
            id=uuid4(),
            name=data["name"],
            description=data.get("description"),
            validPeriod=valid_period,
            timeZone=data.get("timeZone", "Europe/Stockholm"),
            lastUpdated=datetime.now(),
            companyName=data["companyName"],
            companyOrgNo=data.get("companyOrgNo", ""),
            product=data.get("product"),
            direction=Direction(data.get("direction", "consumption")),
            billingPeriod=data.get("billingPeriod", "P1M"),
            fixedPrice=fixed_price,
            energyPrice=energy_price,
            powerPrice=power_price,
        )

    def _parse_price_element(self, data: dict) -> PriceElement:
        """Parse a price element (fixedPrice, energyPrice, powerPrice)."""
        components = []
        for c in data.get("components", []):
            component = self._parse_component(c)
            components.append(component)

        return PriceElement(
            id=uuid4(),
            name=data.get("name", ""),
            description=data.get("description"),
            costFunction=data.get("costFunction"),
            components=components,
        )

    def _parse_component(self, data: dict) -> PriceComponent:
        """Parse a price component."""
        price_data = data.get("price", {})
        price = Price(
            priceExVat=Decimal(str(price_data.get("priceExVat", 0))),
            priceIncVat=Decimal(str(price_data.get("priceIncVat", 0))),
            currency=Currency(price_data.get("currency", "SEK")),
        )

        recurring_periods = []
        for rp in data.get("recurringPeriods", []):
            recurring_periods.append(self._parse_recurring_period(rp))

        peak_settings = None
        if "peakIdentificationSettings" in data and data["peakIdentificationSettings"]:
            ps = data["peakIdentificationSettings"]
            peak_settings = PeakIdentificationSettings(
                peakFunction=ps.get("peakFunction", "peak(main)"),
                peakIdentificationPeriod=ps.get("peakIdentificationPeriod", "P1D"),
                peakDuration=ps.get("peakDuration", "PT1H"),
                numberOfPeaksForAverageCalculation=ps.get(
                    "numberOfPeaksForAverageCalculation", 1
                ),
            )

        valid_period = None
        if "validPeriod" in data and data["validPeriod"]:
            valid_period = ValidPeriod(
                fromIncluding=date.fromisoformat(data["validPeriod"]["fromIncluding"]),
                toExcluding=date.fromisoformat(data["validPeriod"]["toExcluding"])
                if data["validPeriod"].get("toExcluding")
                else None,
            )

        unit = None
        if data.get("unit"):
            unit = Unit(data["unit"])

        return PriceComponent(
            id=uuid4(),
            name=data.get("name", ""),
            description=data.get("description"),
            type=ComponentType(data.get("type", "fixed")),
            reference=data.get("reference", "main"),
            validPeriod=valid_period,
            price=price,
            unit=unit,
            pricedPeriod=data.get("pricedPeriod"),
            recurringPeriods=recurring_periods,
            peakIdentificationSettings=peak_settings,
        )

    def _parse_recurring_period(self, data: dict) -> RecurringPeriod:
        """Parse a recurring period."""
        from datetime import time

        active_periods = []
        for ap in data.get("activePeriods", []):
            cal_refs = None
            if "calendarPatternReferences" in ap:
                cpr = ap["calendarPatternReferences"]
                cal_refs = CalendarPatternReference(
                    include=cpr.get("include", []),
                    exclude=cpr.get("exclude", []),
                )

            # Parse time strings
            from_time = time.fromisoformat(ap["fromIncluding"])
            to_time = time.fromisoformat(ap["toExcluding"])

            active_periods.append(
                ActivePeriod(
                    fromIncluding=from_time,
                    toExcluding=to_time,
                    calendarPatternReferences=cal_refs,
                )
            )

        return RecurringPeriod(
            reference=data.get("reference", "main"),
            frequency=data.get("frequency", "P1D"),
            activePeriods=active_periods,
        )
