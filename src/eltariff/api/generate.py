"""API endpoints for generating deployable API code."""

import io
import json
import zipfile
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
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


@router.post("/excel")
async def generate_excel(request: GenerateRequest) -> Response:
    """Generate an Excel file with tariff data for easy sharing."""
    try:
        tariffs_data = json.loads(request.tariffs_json)
        tariffs = TariffsResponse.model_validate(tariffs_data)

        # Create workbook
        wb = Workbook()

        # Styles
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="017E7A", end_color="017E7A", fill_type="solid")
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        # Sheet 1: Overview
        ws_overview = wb.active
        ws_overview.title = "Översikt"
        ws_overview.append(["Företag", "Tariffnamn", "Beskrivning", "Giltig från", "Giltig till"])
        for cell in ws_overview[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border

        for tariff in tariffs.tariffs:
            ws_overview.append([
                tariff.companyName,
                tariff.name,
                tariff.description or "",
                str(tariff.validPeriod.fromIncluding) if tariff.validPeriod else "",
                str(tariff.validPeriod.toExcluding) if tariff.validPeriod and tariff.validPeriod.toExcluding else "Tillsvidare"
            ])

        # Sheet 2: Fixed prices
        ws_fixed = wb.create_sheet("Fasta avgifter")
        ws_fixed.append(["Tariff", "Avgift", "Pris ex moms", "Pris ink moms", "Valuta", "Period"])
        for cell in ws_fixed[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border

        for tariff in tariffs.tariffs:
            if tariff.fixedPrice and tariff.fixedPrice.components:
                for comp in tariff.fixedPrice.components:
                    period = comp.pricedPeriod or ""
                    if period == "P1M":
                        period = "per månad"
                    elif period == "P1Y":
                        period = "per år"
                    ws_fixed.append([
                        tariff.name,
                        comp.name,
                        float(comp.price.priceExVat) if comp.price else 0,
                        float(comp.price.priceIncVat) if comp.price else 0,
                        comp.price.currency.value if comp.price else "SEK",
                        period
                    ])

        # Sheet 3: Energy prices
        ws_energy = wb.create_sheet("Energiavgifter")
        ws_energy.append(["Tariff", "Avgift", "Pris ex moms", "Pris ink moms", "Valuta", "Enhet"])
        for cell in ws_energy[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border

        for tariff in tariffs.tariffs:
            if tariff.energyPrice and tariff.energyPrice.components:
                for comp in tariff.energyPrice.components:
                    ws_energy.append([
                        tariff.name,
                        comp.name,
                        float(comp.price.priceExVat) if comp.price else 0,
                        float(comp.price.priceIncVat) if comp.price else 0,
                        comp.price.currency.value if comp.price else "SEK",
                        comp.unit.value if comp.unit else "kWh"
                    ])

        # Sheet 4: Power prices
        ws_power = wb.create_sheet("Effektavgifter")
        ws_power.append(["Tariff", "Avgift", "Pris ex moms", "Pris ink moms", "Valuta", "Enhet"])
        for cell in ws_power[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border

        for tariff in tariffs.tariffs:
            if tariff.powerPrice and tariff.powerPrice.components:
                for comp in tariff.powerPrice.components:
                    ws_power.append([
                        tariff.name,
                        comp.name,
                        float(comp.price.priceExVat) if comp.price else 0,
                        float(comp.price.priceIncVat) if comp.price else 0,
                        comp.price.currency.value if comp.price else "SEK",
                        comp.unit.value if comp.unit else "kW"
                    ])

        # Auto-adjust column widths
        for ws in [ws_overview, ws_fixed, ws_energy, ws_power]:
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                ws.column_dimensions[column_letter].width = min(max_length + 2, 50)

        # Save to buffer
        excel_buffer = io.BytesIO()
        wb.save(excel_buffer)
        excel_buffer.seek(0)

        # Create safe filename
        safe_name = (
            request.company_name.lower()
            .replace(" ", "-")
            .replace("å", "a")
            .replace("ä", "a")
            .replace("ö", "o")
        )

        return Response(
            content=excel_buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}-tariffer.xlsx"'
            },
        )
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel: {str(e)}")
