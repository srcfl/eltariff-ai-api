"""API endpoints for parsing tariff documents."""

import os

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models.rise_schema import TariffsResponse
from ..services.ai_parser import TariffParser
from ..services.pdf_parser import PDFParser
from ..services.url_scraper import URLScraper

router = APIRouter(prefix="/api/parse", tags=["parse"])

# Rate limiter - 10 requests per minute per IP
limiter = Limiter(key_func=get_remote_address)

# Security limits
MAX_TEXT_LENGTH = 100_000  # 100KB text limit
MAX_PDF_SIZE = 10 * 1024 * 1024  # 10MB PDF limit
MAX_URL_LENGTH = 2048  # Standard URL length limit


@router.post("/text", response_model=TariffsResponse)
@limiter.limit("10/minute")
async def parse_text(
    request: Request,
    content: str = Form(..., description="Tariff description text"),
    company_name: str | None = Form(None, description="Company name"),
):
    """Parse tariff information from text. Rate limited to 10 requests/minute."""
    # Input validation
    if len(content) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Text too long. Maximum {MAX_TEXT_LENGTH} characters allowed."
        )

    if not content.strip():
        raise HTTPException(status_code=400, detail="Content cannot be empty")

    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="API key not configured")

        parser = TariffParser(api_key)
        result = await parser.parse_text(content, company_name)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse: {str(e)}")


@router.post("/pdf", response_model=TariffsResponse)
@limiter.limit("10/minute")
async def parse_pdf(
    request: Request,
    file: UploadFile = File(..., description="PDF file with tariff information"),
    company_name: str | None = Form(None, description="Company name"),
):
    """Parse tariff information from a PDF file. Rate limited to 10 requests/minute."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        # Extract text from PDF
        pdf_parser = PDFParser()
        pdf_content = await file.read()

        # Check file size
        if len(pdf_content) > MAX_PDF_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"PDF too large. Maximum {MAX_PDF_SIZE // (1024*1024)}MB allowed."
            )
        text = pdf_parser.extract_text_from_bytes(pdf_content)

        if not text.strip():
            raise HTTPException(
                status_code=400, detail="Could not extract text from PDF"
            )

        # Parse with AI
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="API key not configured")

        parser = TariffParser(api_key)
        result = await parser.parse_pdf_content(text, company_name)
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {str(e)}")


@router.post("/url", response_model=TariffsResponse)
@limiter.limit("10/minute")
async def parse_url(
    request: Request,
    url: str = Form(..., description="URL with tariff information"),
    company_name: str | None = Form(None, description="Company name"),
):
    """Parse tariff information from a URL. Rate limited to 10 requests/minute."""
    # URL validation
    if len(url) > MAX_URL_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"URL too long. Maximum {MAX_URL_LENGTH} characters allowed."
        )

    try:
        # Scrape URL (includes SSRF protection)
        scraper = URLScraper()
        text = await scraper.scrape_url(url)

        if not text.strip():
            raise HTTPException(
                status_code=400, detail="Could not extract content from URL"
            )

        # Parse with AI
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="API key not configured")

        parser = TariffParser(api_key)
        result = await parser.parse_text(text, company_name)
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse URL: {str(e)}")
