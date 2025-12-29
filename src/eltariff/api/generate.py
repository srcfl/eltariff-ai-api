"""API endpoints for generating deployable API code."""

import io
import json
import zipfile
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from ..models.rise_schema import TariffsResponse
from ..services.api_generator import APIGenerator

router = APIRouter(prefix="/api/generate", tags=["generate"])


class GenerateRequest(BaseModel):
    """Request to generate deployment package."""

    tariffs_json: str
    company_name: str
    company_org_no: str


@router.post("/package")
async def generate_package(request: GenerateRequest) -> Response:
    """Generate a complete deployment package as a ZIP file."""
    try:
        # Parse tariffs from JSON
        tariffs_data = json.loads(request.tariffs_json)
        tariffs = TariffsResponse.model_validate(tariffs_data)

        # Generate package
        generator = APIGenerator()
        files = generator.generate_deployment_package(
            tariffs, request.company_name, request.company_org_no
        )

        # Create ZIP file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for filename, content in files.items():
                zip_file.writestr(filename, content)

        zip_buffer.seek(0)

        # Create safe filename
        safe_name = (
            request.company_name.lower()
            .replace(" ", "-")
            .replace("å", "a")
            .replace("ä", "a")
            .replace("ö", "o")
        )

        return Response(
            content=zip_buffer.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}-tariff-api.zip"'
            },
        )
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate: {str(e)}")


@router.post("/preview")
async def preview_package(request: GenerateRequest) -> dict[str, Any]:
    """Preview the generated files without downloading."""
    try:
        # Parse tariffs from JSON
        tariffs_data = json.loads(request.tariffs_json)
        tariffs = TariffsResponse.model_validate(tariffs_data)

        # Generate package
        generator = APIGenerator()
        files = generator.generate_deployment_package(
            tariffs, request.company_name, request.company_org_no
        )

        return {"files": files}
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to preview: {str(e)}")


@router.post("/openapi")
async def generate_openapi(request: GenerateRequest) -> dict[str, Any]:
    """Generate only the OpenAPI specification."""
    try:
        tariffs_data = json.loads(request.tariffs_json)
        tariffs = TariffsResponse.model_validate(tariffs_data)

        generator = APIGenerator()
        return generator.generate_openapi_spec(
            tariffs, request.company_name, request.company_org_no
        )
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate: {str(e)}")
