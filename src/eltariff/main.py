"""Eltariff AI API - Main FastAPI application.

Byggt av Sourceful Labs AB
https://sourceful.energy
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .api import explore, generate, parse

# Rate limiter - 10 requests per minute for AI endpoints
limiter = Limiter(key_func=get_remote_address)

# Create FastAPI app
app = FastAPI(
    title="Eltariff AI API",
    description="AI-drivet verktyg för att konvertera svenska elnätstariffer till RISE-standard API. Byggt av Sourceful Labs AB.",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(parse.router)
app.include_router(generate.router)
app.include_router(explore.router)

# Setup templates and static files
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Mount static files if directory exists
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/explorer", response_class=HTMLResponse)
async def explorer(request: Request):
    """Serve the API explorer page."""
    return templates.TemplateResponse("explorer.html", {"request": request})


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "api_key_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
