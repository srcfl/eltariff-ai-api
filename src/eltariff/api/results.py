"""API endpoints for saving and loading shareable results."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

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
