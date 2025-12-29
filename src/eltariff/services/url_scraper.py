"""URL scraping service for extracting tariff information from web pages."""

import ipaddress
import socket
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

# Allowed domains for RISE API fetching (whitelist for known safe APIs)
ALLOWED_API_DOMAINS = [
    "api.goteborgenergi.cloud",
    "api.ellevio.se",
    "api.vattenfall.se",
    "api.eon.se",
]


def is_safe_url(url: str) -> bool:
    """Check if URL is safe to request (prevents SSRF attacks).

    Args:
        url: URL to validate

    Returns:
        True if URL is safe to request

    Raises:
        ValueError: If URL is not safe
    """
    try:
        parsed = urlparse(url)

        # Must be http or https
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Invalid URL scheme: {parsed.scheme}")

        # Must have a hostname
        if not parsed.hostname:
            raise ValueError("URL must have a hostname")

        hostname = parsed.hostname.lower()

        # Block localhost and local hostnames
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            raise ValueError("Cannot request localhost")

        # Block internal IP ranges
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                raise ValueError("Cannot request internal IP addresses")
        except ValueError:
            # Not an IP address, check if hostname resolves to internal IP
            try:
                resolved = socket.gethostbyname(hostname)
                ip = ipaddress.ip_address(resolved)
                if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                    raise ValueError("Hostname resolves to internal IP address")
            except socket.gaierror:
                # Could not resolve - will fail on actual request
                pass

        # Block common internal hostnames
        internal_patterns = [
            "internal", "intranet", "corp", "private",
            "admin", "metadata", "169.254"
        ]
        if any(pattern in hostname for pattern in internal_patterns):
            raise ValueError("Cannot request internal hostnames")

        return True

    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Invalid URL: {e}")


class URLScraper:
    """Service for scraping tariff information from web pages."""

    def __init__(self, timeout: float = 60.0):
        """Initialize the scraper.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Eltariff-AI-API/1.0 (https://github.com/sourceful-energy/eltariff-ai-api)"
        }

    async def scrape_url(self, url: str) -> str:
        """Scrape text content from a URL.

        Args:
            url: URL to scrape

        Returns:
            Extracted text content

        Raises:
            ValueError: If URL is not safe to request
        """
        # Validate URL to prevent SSRF
        is_safe_url(url)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=self.headers, follow_redirects=True)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            if "application/pdf" in content_type:
                # If it's a PDF, return info that it needs PDF handling
                raise ValueError(
                    "URL points to a PDF file. Please download and upload it instead."
                )

            # Parse HTML
            return self._extract_text(response.text)

    def _extract_text(self, html: str) -> str:
        """Extract readable text from HTML.

        Args:
            html: HTML content

        Returns:
            Extracted text content
        """
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # Try to find main content
        main_content = soup.find("main") or soup.find("article") or soup.find(
            "div", {"class": ["content", "main-content", "article"]}
        )

        if main_content:
            text = main_content.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)

    async def fetch_rise_api(self, api_url: str) -> dict:
        """Fetch data from a RISE-compatible API.

        Args:
            api_url: Base URL of the RISE API

        Returns:
            API response as dict

        Raises:
            ValueError: If URL is not safe to request
        """
        # Validate URL to prevent SSRF
        is_safe_url(api_url)

        # Normalize URL
        base_url = api_url.rstrip("/")

        # Try to fetch tariffs
        tariffs_url = f"{base_url}/tariffs"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(tariffs_url, headers=self.headers)
            response.raise_for_status()
            return response.json()
