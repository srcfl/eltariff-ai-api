"""Input models for the Eltariff API."""

from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class InputType(str, Enum):
    """Type of tariff input."""
    TEXT = "text"
    PDF = "pdf"
    URL = "url"


class ParseRequest(BaseModel):
    """Request to parse tariff information."""
    input_type: InputType = Field(alias="inputType")
    content: str | None = None  # For text input
    url: HttpUrl | None = None  # For URL input
    # PDF content is handled via file upload

    model_config = {"populate_by_name": True}


class CompanyInfo(BaseModel):
    """Information about the grid company."""
    name: str = Field(description="Företagsnamn")
    org_no: str = Field(alias="orgNo", description="Organisationsnummer")

    model_config = {"populate_by_name": True}


class GenerateRequest(BaseModel):
    """Request to generate API code."""
    company_info: CompanyInfo = Field(alias="companyInfo")
    tariffs_json: str = Field(alias="tariffsJson", description="JSON string of parsed tariffs")

    model_config = {"populate_by_name": True}


class ExploreRequest(BaseModel):
    """Request to explore an existing RISE API."""
    api_url: HttpUrl = Field(alias="apiUrl")

    model_config = {"populate_by_name": True}


class TariffExplanation(BaseModel):
    """Human-readable explanation of a tariff."""
    tariff_name: str = Field(alias="tariffName")
    summary: str
    fixed_costs: str = Field(alias="fixedCosts")
    energy_costs: str = Field(alias="energyCosts")
    power_costs: str | None = Field(default=None, alias="powerCosts")
    time_variations: str | None = Field(default=None, alias="timeVariations")
    tips: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
