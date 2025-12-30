"""Simple file-based storage for shareable results."""

import hashlib
import json
import os
import secrets
import string
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class ResultStorage:
    """Stores and retrieves tariff results by unique ID."""

    def __init__(self, storage_dir: str | None = None):
        """Initialize storage with a directory path."""
        if storage_dir is None:
            # Default to a data directory relative to the project
            storage_dir = os.environ.get(
                "ELTARIFF_STORAGE_DIR",
                str(Path(__file__).parent.parent.parent.parent / "data" / "results")
            )
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _generate_id(self, length: int = 8) -> str:
        """Generate a short, URL-safe ID."""
        # Use a mix of lowercase letters and digits, avoiding confusing chars
        alphabet = string.ascii_lowercase + string.digits
        # Remove confusing characters
        alphabet = alphabet.replace('l', '').replace('1', '').replace('0', '').replace('o', '')
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def _hash_ip(self, ip: str) -> str:
        """Hash IP address for privacy-preserving tracking."""
        # Use first 8 chars of SHA256 hash - enough to identify unique users
        # but not reversible to actual IP
        return hashlib.sha256(ip.encode()).hexdigest()[:8]

    def save(
        self,
        data: dict[str, Any],
        source_url: str | None = None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> str:
        """Save tariff data and return a unique ID.

        Args:
            data: The tariff data to save
            source_url: Optional URL where the data was parsed from
            user_agent: Optional user agent string for tracking
            ip_address: Optional IP address for tracking

        Returns:
            A unique ID that can be used to retrieve the data
        """
        # Generate unique ID
        result_id = self._generate_id()

        # Ensure ID is unique
        while (self.storage_dir / f"{result_id}.json").exists():
            result_id = self._generate_id()

        # Create metadata with tracking info
        result = {
            "id": result_id,
            "created_at": datetime.now().isoformat(),
            "source_url": source_url,
            "user_agent": user_agent,
            "ip_hash": self._hash_ip(ip_address) if ip_address else None,
            "data": data,
        }

        # Save to file
        file_path = self.storage_dir / f"{result_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return result_id

    def load(self, result_id: str) -> dict[str, Any] | None:
        """Load tariff data by ID.

        Args:
            result_id: The unique ID of the result

        Returns:
            The stored data or None if not found
        """
        # Sanitize ID to prevent path traversal
        safe_id = "".join(c for c in result_id if c.isalnum())
        if len(safe_id) != len(result_id):
            return None

        file_path = self.storage_dir / f"{safe_id}.json"
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def delete(self, result_id: str) -> bool:
        """Delete a stored result.

        Args:
            result_id: The unique ID of the result

        Returns:
            True if deleted, False if not found
        """
        safe_id = "".join(c for c in result_id if c.isalnum())
        file_path = self.storage_dir / f"{safe_id}.json"

        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def list_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        """List recent results (metadata only).

        Args:
            limit: Maximum number of results to return

        Returns:
            List of result metadata
        """
        results = []
        for file_path in sorted(
            self.storage_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:limit]:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Return metadata only, not full tariff data
                    # Extract browser from user agent for display
                    user_agent = data.get("user_agent", "")
                    browser = "Unknown"
                    if "Chrome" in user_agent:
                        browser = "Chrome"
                    elif "Firefox" in user_agent:
                        browser = "Firefox"
                    elif "Safari" in user_agent:
                        browser = "Safari"

                    results.append({
                        "id": data.get("id"),
                        "created_at": data.get("created_at"),
                        "source_url": data.get("source_url"),
                        "tariff_count": len(data.get("data", {}).get("tariffs", [])),
                        "ip_hash": data.get("ip_hash"),
                        "browser": browser,
                    })
            except (json.JSONDecodeError, IOError):
                continue
        return results

    def cleanup(self, max_age_days: int | None = None, delete_all: bool = False) -> int:
        """Delete stored results by age or all results.

        Args:
            max_age_days: Delete results older than this many days
            delete_all: Delete all results regardless of age

        Returns:
            Number of deleted results
        """
        if delete_all:
            max_age_days = None

        cutoff = None
        if max_age_days is not None:
            cutoff = datetime.now() - timedelta(days=max_age_days)

        deleted = 0
        for file_path in self.storage_dir.glob("*.json"):
            try:
                if cutoff is not None:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime >= cutoff:
                        continue
                file_path.unlink()
                deleted += 1
            except OSError:
                continue
        return deleted


# Singleton instance
_storage: ResultStorage | None = None


def get_storage() -> ResultStorage:
    """Get the singleton storage instance."""
    global _storage
    if _storage is None:
        _storage = ResultStorage()
    return _storage
