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

## Svenska elnätstariffer - Bakgrund

Svenska elnätstariffer består typiskt av:

1. **Fast avgift** (fixedPrice): Månads- eller årsavgift som inte beror på förbrukning
2. **Energiavgift** (energyPrice): Pris per kWh, ofta tidsdifferentierat:
   - Höglast/dag (typiskt 06-22 vardagar)
   - Låglast/natt (typiskt 22-06 + helger)
3. **Effektavgift** (powerPrice): Pris per kW baserat på:
   - Högsta effektuttag under en period
   - Ofta baserat på medelvärde av 3 högsta topparna

## Tidsdifferentiering

Vanliga mönster:
- "Höglast": vardagar 06:00-22:00
- "Låglast": nätter 22:00-06:00 + helger + helgdagar
- "Vinter": november-mars (högre priser)
- "Sommar": april-oktober (lägre priser)

## Output-format

Returnera ALLTID en JSON-struktur med följande format:

```json
{
  "tariffs": [
    {
      "name": "Tarifnamn",
      "description": "Beskrivning av målgrupp",
      "validPeriod": {
        "fromIncluding": "2025-01-01",
        "toExcluding": "2026-01-01"
      },
      "companyName": "Företagsnamn",
      "companyOrgNo": "556xxx-xxxx",
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
        "components": [
          {
            "name": "Effektavgift vinter",
            "type": "peak",
            "price": {"priceExVat": 40, "priceIncVat": 50, "currency": "SEK"},
            "unit": "kW",
            "peakIdentificationSettings": {
              "peakFunction": "peak(main)",
              "peakIdentificationPeriod": "P1D",
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
3. Om information saknas, gör rimliga antaganden baserat på svenska standarder
4. Inkludera alltid `validPeriod` - använd innevarande år om inte annat anges
5. Returnera ENDAST JSON, ingen annan text
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
        user_prompt = f"""Analysera följande tariffbeskrivning och konvertera till RISE JSON-format:

{text}

{"Företagsnamn: " + company_name if company_name else ""}

Returnera endast JSON-strukturen, ingen annan text."""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
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
