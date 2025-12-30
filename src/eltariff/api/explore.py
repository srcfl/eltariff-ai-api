"""API endpoints for exploring existing RISE APIs."""

import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter
from pydantic import BaseModel, HttpUrl

from ..models.input import TariffExplanation
from ..models.rise_schema import TariffsResponse
from ..services.ai_parser import TariffParser
from ..services.url_scraper import URLScraper

router = APIRouter(prefix="/api/explore", tags=["explore"])

CATALOGUE_URL = "https://eltariff.deplide.org/tariffcatalogue/all"
_catalogue_cache: list["CatalogueApi"] = []
_catalogue_cache_updated_at: datetime | None = None


class ExploreRequest(BaseModel):
    """Request to explore a RISE API."""

    api_url: HttpUrl


class ExploreResponse(BaseModel):
    """Response from exploring a RISE API."""

    success: bool
    tariffs: Any | None = None
    explanations: list[TariffExplanation] = []
    error: str | None = None


class CatalogueApi(BaseModel):
    """Normalized catalogue entry for a RISE-compatible API."""

    name: str
    api_url: HttpUrl
    description: str | None = None
    region: str | None = None
    tariff_count: int | None = None
    source_url: HttpUrl | None = None
    company_org_no: str | None = None
    metering_point_id_from: str | None = None
    metering_point_id_to: str | None = None


class CatalogueResponse(BaseModel):
    """Response from the tariff catalogue."""

    success: bool
    apis: list[CatalogueApi] = []
    warning: str | None = None
    error: str | None = None


def _extract_catalogue_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("apis", "items", "data", "results", "entries", "catalogue"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _pick_first(item: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        digits = "".join(char for char in value if char.isdigit())
        return int(digits) if digits else None
    return None


def _normalize_catalogue(data: Any) -> list[CatalogueApi]:
    items = _extract_catalogue_items(data)
    apis: list[CatalogueApi] = []
    for item in items:
        api_url = _pick_first(
            item,
            [
                "api_url",
                "apiUrl",
                "base_url",
                "baseUrl",
                "url",
                "endpoint",
                "rise_api",
                "riseApi",
                "tariff_api_url",
            ],
        )
        if not api_url:
            continue

        name = _pick_first(
            item,
            [
                "name",
                "title",
                "company",
                "companyName",
                "company_name",
                "utility",
                "network_company",
                "networkCompany",
                "grid_owner",
                "operator",
            ],
        )
        if not name:
            try:
                hostname = urlparse(str(api_url)).hostname or str(api_url)
            except Exception:
                hostname = str(api_url)
            name = hostname.replace("www.", "")

        description = _pick_first(item, ["description", "summary", "notes"])
        region = _pick_first(item, ["region", "area", "city", "municipality", "county"])

        tariff_count = _pick_first(item, ["tariff_count", "tariffCount", "count"])
        if tariff_count is None and isinstance(item.get("tariffs"), list):
            tariff_count = len(item["tariffs"])
        tariff_count = _coerce_int(tariff_count)

        source_url = _pick_first(
            item,
            [
                "source_url",
                "sourceUrl",
                "homepage",
                "website",
                "userDocUrlOrEmail",
            ],
        )

        company_org_no = _pick_first(item, ["company_org_no", "companyOrgNo", "orgNo"])
        mp_from = _pick_first(item, ["meteringPointIdFrom", "metering_point_id_from"])
        mp_to = _pick_first(item, ["meteringPointIdTo", "metering_point_id_to"])

        try:
            apis.append(
                CatalogueApi(
                    name=str(name),
                    api_url=str(api_url),
                    description=str(description) if description else None,
                    region=str(region) if region else None,
                    tariff_count=tariff_count,
                    source_url=str(source_url) if source_url else None,
                    company_org_no=str(company_org_no) if company_org_no else None,
                    metering_point_id_from=str(mp_from) if mp_from else None,
                    metering_point_id_to=str(mp_to) if mp_to else None,
                )
            )
        except Exception:
            continue

    apis.sort(key=lambda api: api.name.lower())
    return apis


def _fallback_catalogue() -> list[CatalogueApi]:
    return [
        CatalogueApi(
            name="Göteborg Energi Nät AB",
            api_url="https://api.goteborgenergi.cloud/gridtariff/v0",
            description="Göteborg med omnejd. Har tidsdifferentierade tariffer (höglast/låglast, vinter/sommar).",
            region="Göteborg",
            tariff_count=12,
        ),
        CatalogueApi(
            name="Tekniska verken Linköping Nät AB",
            api_url="https://api.tekniskaverken.net/subscription/public/v0",
            description="Linköping med omnejd. 171 tariffer för olika kundtyper.",
            region="Linköping",
            tariff_count=171,
        ),
    ]


@router.get("/known")
async def get_known_apis() -> dict[str, Any]:
    """Get list of known RISE-compatible APIs."""
    response = await get_catalogue()
    if response.success:
        return {"apis": response.apis, "warning": response.warning}
    return {"apis": [], "error": response.error}


@router.get("/catalogue")
async def get_catalogue() -> CatalogueResponse:
    """Fetch the tariff catalogue used by the Explorer UI."""
    global _catalogue_cache_updated_at
    try:
        scraper = URLScraper()
        data = await scraper.fetch_json(CATALOGUE_URL)
        apis = _normalize_catalogue(data)
        if apis:
            _catalogue_cache.clear()
            _catalogue_cache.extend(apis)
            _catalogue_cache_updated_at = datetime.now(timezone.utc)
        return CatalogueResponse(success=True, apis=apis)
    except Exception as e:
        if _catalogue_cache:
            return CatalogueResponse(
                success=True,
                apis=_catalogue_cache,
                warning="Katalogen kunde inte nås. Visar senast hämtade data.",
                error=str(e),
            )
        fallback = _fallback_catalogue()
        return CatalogueResponse(
            success=True,
            apis=fallback,
            warning="Katalogen kunde inte nås. Visar statisk fallback-lista.",
            error=str(e),
        )


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


@router.get("/goteborg-energi", deprecated=True)
async def explore_goteborg_energi() -> ExploreResponse:
    """Deprecated: use /api/explore/catalogue instead."""
    request = ExploreRequest(api_url="https://api.goteborgenergi.cloud/gridtariff/v0")
    return await fetch_api(request)


@router.get("/tekniska-verken", deprecated=True)
async def explore_tekniska_verken() -> ExploreResponse:
    """Deprecated: use /api/explore/catalogue instead."""
    request = ExploreRequest(api_url="https://api.tekniskaverken.net/subscription/public/v0")
    return await fetch_api(request)
