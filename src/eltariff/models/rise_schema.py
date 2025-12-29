"""RISE Eltariff API Schema - Pydantic models matching the RISE specification.

Based on: https://github.com/RI-SE/Eltariff-API
"""

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Direction(str, Enum):
    """Direction of energy flow."""
    CONSUMPTION = "consumption"
    PRODUCTION = "production"


class ComponentType(str, Enum):
    """Type of price component."""
    FIXED = "fixed"
    VARIABLE = "variable"
    PEAK = "peak"
    DYNAMIC = "dynamic"


class Currency(str, Enum):
    """Supported currencies."""
    SEK = "SEK"
    EUR = "EUR"


class Unit(str, Enum):
    """Units for pricing."""
    KWH = "kWh"
    KW = "kW"
    KVAR = "kVAr"


class ValidPeriod(BaseModel):
    """Time period during which something is valid."""
    from_including: date = Field(alias="fromIncluding")
    to_excluding: date | None = Field(default=None, alias="toExcluding")

    model_config = {"populate_by_name": True}


class Price(BaseModel):
    """Price information with VAT breakdown."""
    price_ex_vat: Decimal = Field(alias="priceExVat")
    price_inc_vat: Decimal = Field(alias="priceIncVat")
    currency: Currency = Currency.SEK

    model_config = {"populate_by_name": True}


class CalendarPatternReference(BaseModel):
    """References to calendar patterns for filtering active periods."""
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class ActivePeriod(BaseModel):
    """Time period within a day when a component is active."""
    from_including: time = Field(alias="fromIncluding")
    to_excluding: time = Field(alias="toExcluding")
    calendar_pattern_references: CalendarPatternReference | None = Field(
        default=None, alias="calendarPatternReferences"
    )

    model_config = {"populate_by_name": True}


class RecurringPeriod(BaseModel):
    """Recurring time periods for price components."""
    reference: str
    frequency: str = "P1D"  # ISO 8601 duration (P1D = daily)
    active_periods: list[ActivePeriod] = Field(default_factory=list, alias="activePeriods")

    model_config = {"populate_by_name": True}


class PeakIdentificationSettings(BaseModel):
    """Settings for identifying peak consumption/power."""
    peak_function: str = Field(alias="peakFunction")  # e.g., "peak(main)"
    peak_identification_period: str = Field(alias="peakIdentificationPeriod")  # e.g., "P1D"
    peak_duration: str = Field(alias="peakDuration")  # e.g., "PT1H"
    number_of_peaks_for_average_calculation: int = Field(
        default=1, alias="numberOfPeaksForAverageCalculation"
    )

    model_config = {"populate_by_name": True}


class PriceComponent(BaseModel):
    """A component of a price (fixed fee, energy price, power price)."""
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str | None = None
    type: ComponentType = ComponentType.FIXED
    reference: str = "main"
    valid_period: ValidPeriod | None = Field(default=None, alias="validPeriod")
    price: Price
    unit: Unit | None = None
    priced_period: str | None = Field(default=None, alias="pricedPeriod")  # e.g., "P1Y" for yearly
    recurring_periods: list[RecurringPeriod] = Field(
        default_factory=list, alias="recurringPeriods"
    )
    peak_identification_settings: PeakIdentificationSettings | None = Field(
        default=None, alias="peakIdentificationSettings"
    )

    model_config = {"populate_by_name": True}


class PriceElement(BaseModel):
    """Container for price components (fixed, energy, power)."""
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str | None = None
    cost_function: str | None = Field(default=None, alias="costFunction")
    components: list[PriceComponent] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class CalendarPattern(BaseModel):
    """Calendar pattern for defining weekdays, weekends, holidays."""
    reference: str
    frequency: str  # P1W for weekly, P1Y for yearly
    days: list[int] | None = None  # 1-7 for weekdays
    dates: list[date] | None = None  # Specific dates (holidays)


class Tariff(BaseModel):
    """Complete tariff definition following RISE specification."""
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str | None = None
    valid_period: ValidPeriod = Field(alias="validPeriod")
    time_zone: str = Field(default="Europe/Stockholm", alias="timeZone")
    last_updated: datetime = Field(default_factory=datetime.now, alias="lastUpdated")
    company_name: str = Field(alias="companyName")
    company_org_no: str = Field(alias="companyOrgNo")
    product: str | None = None
    direction: Direction = Direction.CONSUMPTION
    billing_period: str = Field(default="P1M", alias="billingPeriod")  # P1M = monthly
    fixed_price: PriceElement | None = Field(default=None, alias="fixedPrice")
    energy_price: PriceElement | None = Field(default=None, alias="energyPrice")
    power_price: PriceElement | None = Field(default=None, alias="powerPrice")

    model_config = {"populate_by_name": True}


class TariffsResponse(BaseModel):
    """Response containing multiple tariffs."""
    tariffs: list[Tariff]
    calendar_patterns: list[CalendarPattern] = Field(
        default_factory=list, alias="calendarPatterns"
    )
    warnings: list[str] = Field(
        default_factory=list, description="AI-generated warnings about potential issues"
    )

    model_config = {"populate_by_name": True}


class TariffResponse(BaseModel):
    """Response containing a single tariff."""
    tariff: Tariff
    calendar_patterns: list[CalendarPattern] = Field(
        default_factory=list, alias="calendarPatterns"
    )

    model_config = {"populate_by_name": True}


class InfoResponse(BaseModel):
    """API info response."""
    name: str
    api_version: str = Field(alias="apiVersion")
    implementation_version: str = Field(alias="implementationVersion")
    last_updated: datetime = Field(alias="lastUpdated")
    operator: str
    time_zone: str = Field(default="Europe/Stockholm", alias="timeZone")
    identity_provider_url: str | None = Field(default=None, alias="identityProviderUrl")

    model_config = {"populate_by_name": True}


# Default calendar patterns for Sweden
DEFAULT_CALENDAR_PATTERNS = [
    CalendarPattern(
        reference="weekdays",
        frequency="P1W",
        days=[1, 2, 3, 4, 5],
    ),
    CalendarPattern(
        reference="weekends",
        frequency="P1W",
        days=[6, 7],
    ),
    CalendarPattern(
        reference="holidays",
        frequency="P1Y",
        dates=[
            date(2025, 1, 1),   # Nyårsdagen
            date(2025, 1, 6),   # Trettondedag jul
            date(2025, 4, 18),  # Långfredagen
            date(2025, 4, 21),  # Annandag påsk
            date(2025, 5, 1),   # Första maj
            date(2025, 5, 29),  # Kristi himmelsfärdsdag
            date(2025, 6, 6),   # Nationaldagen
            date(2025, 6, 21),  # Midsommardagen
            date(2025, 11, 1),  # Alla helgons dag
            date(2025, 12, 25), # Juldagen
            date(2025, 12, 26), # Annandag jul
        ],
    ),
]
