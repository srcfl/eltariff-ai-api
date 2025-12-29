"""PDF parsing service for extracting tariff information.

Uses pymupdf4llm for optimized LLM text extraction.
"""

import io
import tempfile
from pathlib import Path

import pymupdf4llm


class PDFParser:
    """Service for extracting text content from PDF files for LLM processing."""

    def extract_text(self, pdf_file) -> str:
        """Extract text content from a PDF file.

        Args:
            pdf_file: File-like object containing PDF data

        Returns:
            Extracted text content optimized for LLM processing
        """
        # pymupdf4llm needs a file path, so we write to a temp file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_file.read())
            tmp_path = tmp.name

        try:
            # Extract as markdown for better LLM understanding
            md_text = pymupdf4llm.to_markdown(tmp_path)
            return md_text
        finally:
            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)

    def extract_text_from_bytes(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes.

        Args:
            pdf_bytes: Raw PDF content as bytes

        Returns:
            Extracted text content optimized for LLM processing
        """
        return self.extract_text(io.BytesIO(pdf_bytes))
