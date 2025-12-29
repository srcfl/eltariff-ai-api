"""AI-powered tariff parser using Anthropic Claude."""

import json
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import anthropic

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

## VIKTIGT: Skapa SEPARATA tariffer!

KRITISKT: Om det finns olika priser för olika säkringsstorlekar (16A, 20A, 25A, 35A, etc.) ska du skapa EN SEPARAT TARIFF för varje säkringsstorlek!

Exempel: Om sidan visar en tabell med:
- 16A: 1 984 kr/år
- 20A: 5 673 kr/år
- 25A: 7 149 kr/år

Då skapar du TRE separata tariffer:
1. "Elnät 16A" med fixedPrice 1984 kr/år
2. "Elnät 20A" med fixedPrice 5673 kr/år
3. "Elnät 25A" med fixedPrice 7149 kr/år

## Svenska elnätstariffer - Bakgrund

Svenska elnätstariffer består typiskt av:

1. **Fast avgift** (fixedPrice): Månads- eller årsavgift som inte beror på förbrukning
2. **Energiavgift** (energyPrice): Pris per kWh, ofta tidsdifferentierat
3. **Effektavgift** (powerPrice): Pris per kW - VIKTIGT att fånga komplexiteten!

## Effektavgifter - VIKTIGT!

Effektavgifter är ofta komplexa. Fånga ALLA detaljer:

- **Beräkningsmetod**: Hur beräknas effekttoppen?
  - "Medelvärde av 3 högsta topparna på olika dygn" = numberOfPeaksForAverageCalculation: 3
  - "Högsta timeffekten under månaden" = numberOfPeaksForAverageCalculation: 1

- **Tidsfaktorer**: Används reduktion nattetid?
  - "Natt (22-06) räknas som halv effekt" = lägg i description
  - "Effekttopp kl 22-06 multipliceras med 0.5" = lägg i description

- **Säsongsvariationer**: Olika pris vinter/sommar?
  - Skapa separata komponenter för vinter och sommar med recurringPeriods

## Tidsdifferentiering

Vanliga mönster:
- "Höglast": vardagar 06:00-22:00
- "Låglast": nätter 22:00-06:00 + helger + helgdagar
- "Vinter": november-mars (högre priser)
- "Sommar": april-oktober (lägre priser)

## Output-format

```json
{
  "tariffs": [
    {
      "name": "Tarifnamn",
      "description": "Beskrivning med ALLA viktiga detaljer som inte passar i strukturen",
      "validPeriod": {
        "fromIncluding": "2025-01-01",
        "toExcluding": null
      },
      "companyName": "Företagsnamn AB",
      "companyOrgNo": "",
      "fixedPrice": {
        "name": "Fast avgift",
        "components": [
          {
            "name": "Abonnemangsavgift",
            "type": "fixed",
            "price": {"priceExVat": 100, "priceIncVat": 125, "currency": "SEK"},
            "pricedPeriod": "P1M"
          }
        ]
      },
      "energyPrice": {
        "name": "Energiavgift",
        "components": [
          {
            "name": "Överföringsavgift höglast",
            "description": "Vardagar 06-22",
            "type": "fixed",
            "price": {"priceExVat": 0.20, "priceIncVat": 0.25, "currency": "SEK"},
            "unit": "kWh",
            "recurringPeriods": [
              {
                "reference": "main",
                "frequency": "P1D",
                "activePeriods": [
                  {
                    "fromIncluding": "06:00:00",
                    "toExcluding": "22:00:00",
                    "calendarPatternReferences": {"include": ["weekdays"], "exclude": ["holidays"]}
                  }
                ]
              }
            ]
          }
        ]
      },
      "powerPrice": {
        "name": "Effektavgift",
        "description": "VIKTIG INFO: Baseras på medelvärde av 3 högsta effekttopparna på olika dygn. Nattetid (22-06) räknas som halv effekt.",
        "components": [
          {
            "name": "Effektavgift",
            "description": "Snitt av 3 högsta toppar. Natteffekt (22-06) räknas som 50%.",
            "type": "peak",
            "price": {"priceExVat": 40, "priceIncVat": 50, "currency": "SEK"},
            "unit": "kW",
            "peakIdentificationSettings": {
              "peakFunction": "peak(main)",
              "peakIdentificationPeriod": "P1M",
              "peakDuration": "PT1H",
              "numberOfPeaksForAverageCalculation": 3
            }
          }
        ]
      }
    }
  ]
}
```

## Viktiga regler

1. Alla priser ska ha både exkl. och inkl. moms (25%)
2. Använd ISO 8601 för datum och tider
3. EXTRAHERA företagsnamn från innehållet (URL, sidhuvud, etc.)
4. Inkludera alltid `validPeriod` - använd innevarande år om inte annat anges
5. Returnera ENDAST JSON, ingen annan text
6. **VIKTIGT**: Fånga ALLA detaljer om effektberäkning i description-fält!
7. Om det finns komplexa regler (nattrabatt på effekt, etc.) - beskriv dem tydligt!
8. **ÅRSAVGIFTER**: Om avgiften anges per år (kr/år), använd "pricedPeriod": "P1Y", INTE "P1M"!
9. **SKAPA MÅNGA TARIFFER**: Varje säkringsstorlek (16A, 20A, 25A...) ska bli en EGEN tariff!
10. **SPOTPRIS**: Om överföringsavgift är "spotprisbaserad" eller "variabel", skriv det i description och använd ett typiskt medelvärde som pris.
"""


class TariffParser:
    """AI-powered parser for converting tariff documents to RISE format."""

    def __init__(self, api_key: str | None = None):
        """Initialize the parser with Anthropic API key."""
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key required")
        self.client = anthropic.Anthropic(api_key=self.api_key)

    async def parse_text(
        self, text: str, company_name: str | None = None, progress_callback=None
    ) -> TariffsResponse:
        """Parse tariff information from text using two-step AI process.

        Step 1 (Sonnet): Pre-process and structure the raw content
        Step 2 (Opus): Generate precise RISE JSON with all tariffs
        """
        # Truncate input if too long
        max_input_chars = 50000
        if len(text) > max_input_chars:
            text = text[:max_input_chars] + "\n\n[... innehåll trunkerat för längd ...]"

        # ========== STEP 1: Pre-process with Sonnet ==========
        if progress_callback:
            progress_callback("step1_start", "Steg 1: Förbehandlar data med Sonnet...")

        step1_prompt = f"""Analysera följande text och extrahera ALL tariff-relaterad information på ett strukturerat sätt.

Din uppgift är att:
1. Identifiera företagsnamn
2. Lista ALLA tariffer/säkringsstorlekar som nämns (16A, 20A, 25A, etc.)
3. Extrahera ALLA priser och avgifter
4. Identifiera tidsregler (höglast/låglast, säsong, etc.)
5. Identifiera effektavgifter och hur de beräknas

Formatera som strukturerad text, INTE JSON ännu.

{f"Angivet företagsnamn: {company_name}" if company_name else ""}

TEXT ATT ANALYSERA:
{text}"""

        step1_response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": step1_prompt}],
        )

        structured_info = step1_response.content[0].text

        if progress_callback:
            progress_callback("step1_done", "Steg 1 klar: Data strukturerad")

        # ========== STEP 2: Generate RISE JSON with Opus (streaming) ==========
        if progress_callback:
            progress_callback("step2_start", "Steg 2: Genererar RISE JSON med Opus...")

        step2_prompt = f"""Baserat på följande strukturerade tariff-information, generera komplett RISE JSON.

VIKTIGT:
- Skapa EN SEPARAT TARIFF för varje säkringsstorlek (16A, 20A, 25A, etc.)
- Returnera ENDAST giltig JSON, ingen annan text
- Inkludera calendarPatterns för weekdays, weekends, holidays

STRUKTURERAD INFORMATION:
{structured_info}

ORIGINAL TEXT (för referens):
{text[:10000]}"""

        # Use streaming for Opus (required for long operations)
        content = ""
        with self.client.messages.stream(
            model="claude-opus-4-20250514",
            max_tokens=16384,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": step2_prompt}],
        ) as stream:
            for text_chunk in stream.text_stream:
                content += text_chunk

        if progress_callback:
            progress_callback("step2_done", "Steg 2 klar: RISE JSON genererad")

        return self._parse_response(content)

    async def parse_pdf_content(
        self, pdf_text: str, company_name: str | None = None
    ) -> TariffsResponse:
        """Parse tariff information from PDF text content."""
        return await self.parse_text(pdf_text, company_name)

    async def improve_tariffs(
        self, existing_tariffs: dict, instruction: str
    ) -> TariffsResponse:
        """Improve existing tariff data based on user instruction."""
        existing_json = json.dumps(existing_tariffs, indent=2, ensure_ascii=False)

        user_prompt = f"""Du har fått befintlig tariffdata i JSON-format och en instruktion från användaren.
Din uppgift är att UPPDATERA tariffdata enligt instruktionen.

VIKTIGT:
- Behåll ALL befintlig data som inte explicit ska ändras
- Returnera ENDAST giltig JSON i samma RISE-format
- Om instruktionen är otydlig, gör ditt bästa för att tolka den
- Behåll samma ID:n och struktur om möjligt

BEFINTLIG TARIFFDATA:
{existing_json}

ANVÄNDARENS INSTRUKTION:
{instruction}

Returnera den uppdaterade tariffdata som komplett JSON (inkludera tariffs och calendarPatterns)."""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0].text
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

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0].text
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

        return TariffsResponse(
            tariffs=tariffs,
            calendarPatterns=DEFAULT_CALENDAR_PATTERNS,
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
