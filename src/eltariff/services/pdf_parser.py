"""PDF parsing service for extracting tariff information."""

import io
from typing import BinaryIO

import pdfplumber


class PDFParser:
    """Service for extracting text content from PDF files."""

    def extract_text(self, pdf_file: BinaryIO) -> str:
        """Extract text content from a PDF file.

        Args:
            pdf_file: File-like object containing PDF data

        Returns:
            Extracted text content from all pages
        """
        text_content = []

        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                # Extract text
                text = page.extract_text()
                if text:
                    text_content.append(text)

                # Also try to extract tables
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        table_text = self._format_table(table)
                        text_content.append(table_text)

        return "\n\n".join(text_content)

    def extract_text_from_bytes(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes.

        Args:
            pdf_bytes: Raw PDF content as bytes

        Returns:
            Extracted text content
        """
        return self.extract_text(io.BytesIO(pdf_bytes))

    def _format_table(self, table: list[list[str | None]]) -> str:
        """Format a table as readable text.

        Args:
            table: 2D list of table cells

        Returns:
            Formatted table as text
        """
        rows = []
        for row in table:
            if row:
                cells = [str(cell) if cell else "" for cell in row]
                rows.append(" | ".join(cells))
        return "\n".join(rows)
