"""API endpoints for saving and loading shareable results."""

import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models.rise_schema import TariffsResponse
from ..services.tariff_guard import check_tariffs_response
from ..services.storage import get_storage


class SaveResultRequest(BaseModel):
    """Request to save a result."""
    tariffs_json: dict
    source_url: str | None = None


class SaveResultResponse(BaseModel):
    """Response with the result ID."""
    id: str
    url: str


router = APIRouter(prefix="/api/results", tags=["results"])

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@router.post("/save", response_model=SaveResultResponse)
@limiter.limit("30/hour")
async def save_result(
    request: Request,
    body: SaveResultRequest,
):
    """Save tariff result and return a shareable ID.

    Rate limited to 30 saves per hour per IP.
    """
    try:
        tariffs_response = TariffsResponse.model_validate(body.tariffs_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid tariff data: {str(e)}")

    guard = check_tariffs_response(tariffs_response)
    if not guard.ok:
        raise HTTPException(status_code=400, detail=guard.reason)

    storage = get_storage()

    # Get tracking info from request
    user_agent = request.headers.get("user-agent", "")[:200]  # Truncate
    ip_address = get_remote_address(request)

    result_id = storage.save(
        body.tariffs_json,
        body.source_url,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    # Build the share URL
    host = request.headers.get("host", "eltariff.sourceful.dev")
    scheme = "https" if "localhost" not in host else "http"
    share_url = f"{scheme}://{host}/r/{result_id}"

    return SaveResultResponse(id=result_id, url=share_url)


@router.get("/list/recent")
async def list_recent_results(limit: int = 20):
    """List recent saved results (metadata only)."""
    storage = get_storage()
    results = storage.list_recent(limit=limit)
    return {"results": results}


@router.get("/{result_id}")
async def get_result(result_id: str):
    """Get a saved tariff result by ID."""
    storage = get_storage()
    result = storage.load(result_id)

    if result is None:
        raise HTTPException(status_code=404, detail="Result not found")

    return {
        "id": result.get("id"),
        "created_at": result.get("created_at"),
        "source_url": result.get("source_url"),
        "tariffs": result.get("data"),
    }


@router.get("/cleanup", include_in_schema=False)
async def cleanup_results(
    request: Request,
    all: bool = False,
    max_age_days: int | None = None,
    token: str | None = None,
):
    """Cleanup stored results (undocumented, for admin use)."""
    required_token = os.environ.get("ELTARIFF_CLEANUP_TOKEN")
    if required_token and token != required_token:
        raise HTTPException(status_code=403, detail="Invalid cleanup token")

    if not all and max_age_days is None:
        raise HTTPException(status_code=400, detail="Provide all=true or max_age_days")

    if max_age_days is not None and max_age_days < 0:
        raise HTTPException(status_code=400, detail="max_age_days must be >= 0")

    storage = get_storage()
    deleted = storage.cleanup(max_age_days=max_age_days, delete_all=all)
    return {"deleted": deleted}
