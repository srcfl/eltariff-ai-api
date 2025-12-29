"""API endpoints for exploring existing RISE APIs."""

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from ..models.input import TariffExplanation
from ..models.rise_schema import Tariff, TariffsResponse
from ..services.ai_parser import TariffParser
from ..services.url_scraper import URLScraper

router = APIRouter(prefix="/api/explore", tags=["explore"])


class ExploreRequest(BaseModel):
    """Request to explore a RISE API."""

    api_url: HttpUrl


class ExploreResponse(BaseModel):
    """Response from exploring a RISE API."""

    success: bool
    tariffs: Any | None = None
    explanations: list[TariffExplanation] = []
    error: str | None = None


# Known Swedish RISE APIs
# Note: We only list publicly accessible APIs. Some utilities have RISE APIs that require authentication.
KNOWN_APIS = {
    "goteborg-energi": {
        "name": "Göteborg Energi Nät AB",
        "url": "https://api.goteborgenergi.cloud/gridtariff/v0",
        "description": "Göteborg med omnejd. Har tidsdifferentierade tariffer (höglast/låglast, vinter/sommar).",
    },
    "tekniska-verken": {
        "name": "Tekniska verken Linköping Nät AB",
        "url": "https://api.tekniskaverken.net/subscription/public/v0",
        "description": "Linköping med omnejd. 171 tariffer för olika kundtyper.",
    },
    # More APIs will be added as they become publicly available
    # Known implementations (not yet public):
    # - Ellevio
    # - Vattenfall
}


@router.get("/known")
async def get_known_apis() -> dict[str, Any]:
    """Get list of known RISE-compatible APIs."""
    return {"apis": KNOWN_APIS}


@router.post("/fetch")
async def fetch_api(request: ExploreRequest) -> ExploreResponse:
    """Fetch and parse tariffs from a RISE-compatible API."""
    try:
        scraper = URLScraper()
        data = await scraper.fetch_rise_api(str(request.api_url))

        # Return raw data without validation for now
        return ExploreResponse(success=True, tariffs=data)
    except Exception as e:
        return ExploreResponse(success=False, error=str(e))


@router.post("/explain")
async def explain_tariffs(request: ExploreRequest) -> ExploreResponse:
    """Fetch tariffs and generate human-readable explanations."""
    try:
        # First fetch the tariffs
        scraper = URLScraper()
        data = await scraper.fetch_rise_api(str(request.api_url))
        tariffs_response = TariffsResponse.model_validate(data)

        # Generate explanations for each tariff
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return ExploreResponse(
                success=True,
                tariffs=tariffs_response,
                explanations=[],
            )

        parser = TariffParser(api_key)
        explanations = []

        for tariff in tariffs_response.tariffs:
            explanation_data = await parser.explain_tariff(tariff)
            explanations.append(TariffExplanation.model_validate(explanation_data))

        return ExploreResponse(
            success=True,
            tariffs=tariffs_response,
            explanations=explanations,
        )
    except Exception as e:
        return ExploreResponse(success=False, error=str(e))


@router.get("/goteborg-energi")
async def explore_goteborg_energi() -> ExploreResponse:
    """Quick access to explore Göteborg Energi's API (without AI explanations for speed)."""
    request = ExploreRequest(api_url="https://api.goteborgenergi.cloud/gridtariff/v0")
    return await fetch_api(request)


@router.get("/tekniska-verken")
async def explore_tekniska_verken() -> ExploreResponse:
    """Quick access to explore Tekniska verken's API (without AI explanations for speed)."""
    request = ExploreRequest(api_url="https://api.tekniskaverken.net/subscription/public/v0")
    return await fetch_api(request)
