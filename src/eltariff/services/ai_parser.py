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
"""


class TariffParser:
    """AI-powered parser for converting tariff documents to RISE format."""

    def __init__(self, api_key: str | None = None):
        """Initialize the parser with Anthropic API key."""
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key required")
        self.client = anthropic.Anthropic(api_key=self.api_key)

    async def parse_text(self, text: str, company_name: str | None = None) -> TariffsResponse:
        """Parse tariff information from text."""
        # Truncate input if too long (keep most relevant parts)
        max_input_chars = 50000
        if len(text) > max_input_chars:
            # Keep beginning and end, as tariff info is often at the start
            text = text[:max_input_chars] + "\n\n[... innehåll trunkerat för längd ...]"

        user_prompt = f"""Analysera följande tariffbeskrivning och konvertera till RISE JSON-format.

VIKTIGT:
- Returnera ENDAST giltig JSON, ingen annan text
- Håll svaret kompakt - inkludera endast nödvändig information
- Om ingen tariff hittas, returnera: {{"tariffs": []}}

{f"Företagsnamn: {company_name}" if company_name else ""}

Tariffbeskrivning:
{text}"""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Extract JSON from response
        content = response.content[0].text
        return self._parse_response(content)

    async def parse_pdf_content(
        self, pdf_text: str, company_name: str | None = None
    ) -> TariffsResponse:
        """Parse tariff information from PDF text content."""
        return await self.parse_text(pdf_text, company_name)

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
