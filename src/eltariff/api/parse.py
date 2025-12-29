"""API endpoints for parsing tariff documents."""

import json
import os

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models.rise_schema import TariffsResponse
from ..services.ai_parser import TariffParser
from ..services.pdf_parser import PDFParser
from ..services.url_scraper import URLScraper


class ImproveRequest(BaseModel):
    """Request to improve existing tariff data."""
    tariffs_json: str
    instruction: str


class StreamRequest(BaseModel):
    """Request for streaming analysis."""
    url: str | None = None
    text: str | None = None
    company_name: str | None = None


router = APIRouter(prefix="/api/parse", tags=["parse"])

# Rate limiter - 10 requests per hour per IP (to prevent API abuse)
limiter = Limiter(key_func=get_remote_address)

# Security limits
MAX_TEXT_LENGTH = 100_000  # 100KB text limit
MAX_PDF_SIZE = 10 * 1024 * 1024  # 10MB PDF limit
MAX_URL_LENGTH = 2048  # Standard URL length limit


@router.post("/text", response_model=TariffsResponse)
@limiter.limit("10/hour")
async def parse_text(
    request: Request,
    content: str = Form(..., description="Tariff description text"),
    company_name: str | None = Form(None, description="Company name"),
):
    """Parse tariff information from text. Rate limited to 10 requests/hour."""
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
@limiter.limit("10/hour")
async def parse_pdf(
    request: Request,
    file: UploadFile = File(..., description="PDF file with tariff information"),
    company_name: str | None = Form(None, description="Company name"),
):
    """Parse tariff information from a PDF file. Rate limited to 10 requests/hour."""
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
@limiter.limit("10/hour")
async def parse_url(
    request: Request,
    url: str = Form(..., description="URL with tariff information"),
    company_name: str | None = Form(None, description="Company name"),
):
    """Parse tariff information from a URL (supports both web pages and PDFs). Rate limited to 10 requests/hour."""
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


@router.post("/combined", response_model=TariffsResponse)
@limiter.limit("10/hour")
async def parse_combined(
    request: Request,
    url: str | None = Form(None, description="URL with tariff information"),
    file: UploadFile | None = File(None, description="PDF file with tariff information"),
    text: str | None = Form(None, description="Text description of tariffs"),
):
    """Parse tariff information from multiple sources (URL, PDF, text).

    Combines all provided inputs for best AI analysis.
    Rate limited to 10 requests/hour.
    """
    combined_content = []

    # Process URL if provided
    if url and url.strip():
        if len(url) > MAX_URL_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"URL too long. Maximum {MAX_URL_LENGTH} characters allowed."
            )
        try:
            scraper = URLScraper()
            url_text = await scraper.scrape_url(url)
            if url_text.strip():
                combined_content.append(f"=== INNEHÅLL FRÅN URL ({url}) ===\n{url_text}")
        except Exception as e:
            # Continue with other sources if URL fails
            combined_content.append(f"=== URL FEL: {str(e)} ===")

    # Process PDF if provided
    if file and file.filename:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="File must be a PDF")
        try:
            pdf_parser = PDFParser()
            pdf_content = await file.read()
            if len(pdf_content) > MAX_PDF_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"PDF too large. Maximum {MAX_PDF_SIZE // (1024*1024)}MB allowed."
                )
            pdf_text = pdf_parser.extract_text_from_bytes(pdf_content)
            if pdf_text.strip():
                combined_content.append(f"=== INNEHÅLL FRÅN PDF ({file.filename}) ===\n{pdf_text}")
        except HTTPException:
            raise
        except Exception as e:
            combined_content.append(f"=== PDF FEL: {str(e)} ===")

    # Process text if provided
    if text and text.strip():
        if len(text) > MAX_TEXT_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Text too long. Maximum {MAX_TEXT_LENGTH} characters allowed."
            )
        combined_content.append(f"=== FRITEXT ===\n{text}")

    if not combined_content:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one of: url, file, or text"
        )

    # Combine all content
    full_content = "\n\n".join(combined_content)

    # Parse with AI
    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="API key not configured")

        parser = TariffParser(api_key)
        # Note: company_name is now extracted by AI from content
        result = await parser.parse_text(full_content, None)
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse: {str(e)}")


@router.post("/improve", response_model=TariffsResponse)
@limiter.limit("10/hour")
async def improve_tariffs(
    request: Request,
    body: ImproveRequest,
):
    """Improve existing tariff data based on user instructions.

    Takes existing tariff JSON and a natural language instruction,
    and returns updated tariff data.
    Rate limited to 10 requests/hour.
    """
    try:
        # Validate JSON
        tariffs_data = json.loads(body.tariffs_json)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    if not body.instruction.strip():
        raise HTTPException(status_code=400, detail="Instruction cannot be empty")

    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="API key not configured")

        parser = TariffParser(api_key)
        result = await parser.improve_tariffs(tariffs_data, body.instruction)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to improve: {str(e)}")


@router.post("/stream")
@limiter.limit("10/hour")
async def stream_analysis(
    request: Request,
    body: StreamRequest,
):
    """Stream AI analysis with thinking process visible via SSE.

    Returns Server-Sent Events with:
    - type: thinking_start, thinking, text_start, text, block_stop, result, error
    """
    if not body.url and not body.text:
        raise HTTPException(status_code=400, detail="Provide url or text")

    async def generate_events():
        try:
            content_to_parse = ""

            # Fetch URL content if provided
            if body.url:
                yield f"data: {json.dumps({'type': 'status', 'message': 'Hämtar URL...'})}\n\n"
                try:
                    scraper = URLScraper()
                    content_to_parse = await scraper.scrape_url(body.url)
                    yield f"data: {json.dumps({'type': 'status', 'message': f'Hämtade {len(content_to_parse)} tecken'})}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Kunde inte hämta URL: {str(e)}'})}\n\n"
                    return

            # Use text if provided (in addition to or instead of URL)
            if body.text:
                if content_to_parse:
                    content_to_parse += f"\n\n=== FRITEXT ===\n{body.text}"
                else:
                    content_to_parse = body.text

            if not content_to_parse.strip():
                yield f"data: {json.dumps({'type': 'error', 'message': 'Inget innehåll att analysera'})}\n\n"
                return

            # Initialize parser
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                yield f"data: {json.dumps({'type': 'error', 'message': 'API-nyckel saknas'})}\n\n"
                return

            yield f"data: {json.dumps({'type': 'status', 'message': 'Startar AI-analys med Opus...'})}\n\n"

            parser = TariffParser(api_key)

            # Stream the analysis
            for chunk in parser.parse_text_streaming(content_to_parse, body.company_name):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
