"""API code generator for creating deployable RISE-compatible APIs."""

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..models.rise_schema import TariffsResponse


class APIGenerator:
    """Generator for creating deployable RISE API code."""

    def __init__(self):
        """Initialize the generator with templates."""
        template_dir = Path(__file__).parent.parent / "templates"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))

    def generate_openapi_spec(
        self, tariffs: TariffsResponse, company_name: str, company_org_no: str
    ) -> dict:
        """Generate OpenAPI specification for the tariffs.

        Args:
            tariffs: Parsed tariffs
            company_name: Name of the grid company
            company_org_no: Organization number

        Returns:
            OpenAPI specification as dict
        """
        return {
            "openapi": "3.0.1",
            "info": {
                "title": f"{company_name} - Elnätstariff API",
                "description": f"API för elnätstariffer från {company_name}",
                "version": "0.1.0",
                "contact": {"name": company_name},
            },
            "servers": [{"url": "/gridtariff/v0", "description": "Grid Tariff API"}],
            "paths": {
                "/info": {
                    "get": {
                        "summary": "Get API info",
                        "responses": {
                            "200": {
                                "description": "API information",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/InfoResponse"}
                                    }
                                },
                            }
                        },
                    }
                },
                "/tariffs": {
                    "get": {
                        "summary": "Get all tariffs",
                        "responses": {
                            "200": {
                                "description": "List of tariffs",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/TariffsResponse"}
                                    }
                                },
                            }
                        },
                    }
                },
                "/tariffs/{id}": {
                    "get": {
                        "summary": "Get tariff by ID",
                        "parameters": [
                            {
                                "name": "id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string", "format": "uuid"},
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "Tariff details",
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/TariffResponse"}
                                    }
                                },
                            },
                            "404": {"description": "Tariff not found"},
                        },
                    }
                },
            },
            "components": {
                "schemas": {
                    "InfoResponse": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "apiVersion": {"type": "string"},
                            "implementationVersion": {"type": "string"},
                            "lastUpdated": {"type": "string", "format": "date-time"},
                            "operator": {"type": "string"},
                            "timeZone": {"type": "string"},
                        },
                    },
                    "TariffsResponse": {
                        "type": "object",
                        "properties": {
                            "tariffs": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/Tariff"},
                            },
                            "calendarPatterns": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/CalendarPattern"},
                            },
                        },
                    },
                    "TariffResponse": {
                        "type": "object",
                        "properties": {
                            "tariff": {"$ref": "#/components/schemas/Tariff"},
                            "calendarPatterns": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/CalendarPattern"},
                            },
                        },
                    },
                    "Tariff": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "format": "uuid"},
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "validPeriod": {"$ref": "#/components/schemas/ValidPeriod"},
                            "timeZone": {"type": "string"},
                            "lastUpdated": {"type": "string", "format": "date-time"},
                            "companyName": {"type": "string"},
                            "companyOrgNo": {"type": "string"},
                            "direction": {"type": "string", "enum": ["consumption", "production"]},
                            "billingPeriod": {"type": "string"},
                            "fixedPrice": {"$ref": "#/components/schemas/PriceElement"},
                            "energyPrice": {"$ref": "#/components/schemas/PriceElement"},
                            "powerPrice": {"$ref": "#/components/schemas/PriceElement"},
                        },
                    },
                    "ValidPeriod": {
                        "type": "object",
                        "properties": {
                            "fromIncluding": {"type": "string", "format": "date"},
                            "toExcluding": {"type": "string", "format": "date"},
                        },
                    },
                    "PriceElement": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "format": "uuid"},
                            "name": {"type": "string"},
                            "components": {
                                "type": "array",
                                "items": {"$ref": "#/components/schemas/PriceComponent"},
                            },
                        },
                    },
                    "PriceComponent": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "format": "uuid"},
                            "name": {"type": "string"},
                            "type": {"type": "string", "enum": ["fixed", "peak"]},
                            "price": {"$ref": "#/components/schemas/Price"},
                            "unit": {"type": "string", "enum": ["kWh", "kW", "kVAr"]},
                        },
                    },
                    "Price": {
                        "type": "object",
                        "properties": {
                            "priceExVat": {"type": "number"},
                            "priceIncVat": {"type": "number"},
                            "currency": {"type": "string"},
                        },
                    },
                    "CalendarPattern": {
                        "type": "object",
                        "properties": {
                            "reference": {"type": "string"},
                            "frequency": {"type": "string"},
                            "days": {"type": "array", "items": {"type": "integer"}},
                            "dates": {"type": "array", "items": {"type": "string", "format": "date"}},
                        },
                    },
                },
            },
        }

    def generate_fastapi_app(
        self,
        tariffs: TariffsResponse,
        company_name: str,
        company_org_no: str,
    ) -> str:
        """Generate FastAPI application code.

        Args:
            tariffs: Parsed tariffs
            company_name: Name of the grid company
            company_org_no: Organization number

        Returns:
            Python code for FastAPI application
        """
        # Serialize tariffs to JSON for embedding
        tariffs_json = tariffs.model_dump_json(by_alias=True, indent=2)

        template = self.env.get_template("fastapi_app.py.j2")
        return template.render(
            company_name=company_name,
            company_org_no=company_org_no,
            tariffs_json=tariffs_json,
        )

    def generate_docker_compose(self, company_name: str) -> str:
        """Generate docker-compose.yml.

        Args:
            company_name: Name of the grid company

        Returns:
            docker-compose.yml content
        """
        template = self.env.get_template("docker-compose.yml.j2")
        # Create a safe service name from company name
        service_name = (
            company_name.lower()
            .replace(" ", "-")
            .replace("å", "a")
            .replace("ä", "a")
            .replace("ö", "o")
        )
        return template.render(
            company_name=company_name,
            service_name=service_name,
        )

    def generate_dockerfile(self) -> str:
        """Generate Dockerfile.

        Returns:
            Dockerfile content
        """
        template = self.env.get_template("Dockerfile.j2")
        return template.render()

    def generate_instructions(self, company_name: str) -> str:
        """Generate deployment instructions.

        Args:
            company_name: Name of the grid company

        Returns:
            Markdown instructions
        """
        template = self.env.get_template("instructions.md.j2")
        return template.render(company_name=company_name)

    def generate_deployment_package(
        self,
        tariffs: TariffsResponse,
        company_name: str,
        company_org_no: str,
    ) -> dict[str, str]:
        """Generate complete deployment package.

        Args:
            tariffs: Parsed tariffs
            company_name: Name of the grid company
            company_org_no: Organization number

        Returns:
            Dict mapping filename to content
        """
        return {
            "app.py": self.generate_fastapi_app(tariffs, company_name, company_org_no),
            "docker-compose.yml": self.generate_docker_compose(company_name),
            "Dockerfile": self.generate_dockerfile(),
            "README.md": self.generate_instructions(company_name),
            "openapi.json": json.dumps(
                self.generate_openapi_spec(tariffs, company_name, company_org_no),
                indent=2,
                ensure_ascii=False,
            ),
            "tariffs.json": tariffs.model_dump_json(by_alias=True, indent=2),
        }
