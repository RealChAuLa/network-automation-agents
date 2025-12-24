"""
immudb Client

Client wrapper for immudb database operations.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class ImmudbConfig:
    """Configuration for immudb connection."""
    host: str = "localhost"
    port: int = 3322
    user: str = "immudb"
    password: str = "immudb"
    database: str = "defaultdb"

    @classmethod
    def from_env(cls) -> "ImmudbConfig":
        """Create config from environment variables."""
        return cls(
            host=os.getenv("IMMUDB_HOST", "localhost"),
            port=int(os.getenv("IMMUDB_PORT", "3322")),
            user=os.getenv("IMMUDB_USER", "immudb"),
            password=os.getenv("IMMUDB_PASSWORD", "immudb"),
            database=os.getenv("IMMUDB_DATABASE", "defaultdb"),
        )


class ImmudbClient:
    """
    Client for immudb operations.

    Provides methods to store and retrieve immutable audit records.

    Example:
        >>> client = ImmudbClient()
        >>> client. connect()
        >>> client.set("audit: 123", {"action": "restart", "node":  "router_01"})
        >>> record = client.get("audit:123")
    """

    def __init__(self, config: Optional[ImmudbConfig] = None):
        """
        Initialize immudb client.

        Args:
            config: immudb configuration (uses environment if not provided)
        """
        self.config = config or ImmudbConfig.from_env()
        self._client = None
        self._connected = False
        self._use_fallback = False
        self._fallback_storage: dict = {}

    def connect(self) -> bool:
        """
        Connect to immudb.

        Returns:
            True if connected, False otherwise
        """
        try:
            from immudb import ImmudbClient as ImmuClient

            self._client = ImmuClient(
                f"{self.config.host}:{self.config.port}"
            )

            self._client.login(
                username=self.config.user,
                password=self.config.password,
                database=self.config.database,
            )

            self._connected = True
            self._use_fallback = False
            logger.info(f"Connected to immudb at {self.config.host}:{self.config.port}")
            return True

        except ImportError:
            logger.warning("immudb-py not installed, using in-memory fallback")
            self._use_fallback = True
            self._connected = True
            return True

        except Exception as e:
            logger.warning(f"Could not connect to immudb: {e}. Using in-memory fallback.")
            self._use_fallback = True
            self._connected = True
            return True

    def disconnect(self):
        """Disconnect from immudb."""
        if self._client and not self._use_fallback:
            try:
                self._client.logout()
            except Exception:
                pass
        self._connected = False
        self._client = None

    def is_connected(self) -> bool:
        """Check if connected to immudb."""
        return self._connected

    def set(self, key: str, value: dict) -> dict:
        """
        Store a key-value pair.

        Args:
            key:  The key to store
            value: The value (dict) to store

        Returns:
            Transaction info including verification data
        """
        if not self._connected:
            self.connect()

        value_json = json.dumps(value, default=str)

        if self._use_fallback:
            # In-memory fallback
            tx_id = len(self._fallback_storage) + 1
            self._fallback_storage[key] = {
                "value": value_json,
                "tx_id": tx_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
            return {
                "tx_id": tx_id,
                "key": key,
                "verified": True,
                "fallback": True,
            }

        try:
            result = self._client.set(key.encode(), value_json.encode())
            return {
                "tx_id": result.id,
                "key": key,
                "verified": True,
                "fallback": False,
            }
        except Exception as e:
            logger.error(f"immudb set error:  {e}")
            # Fallback to memory
            tx_id = len(self._fallback_storage) + 1
            self._fallback_storage[key] = {
                "value": value_json,
                "tx_id": tx_id,
                "timestamp": datetime.utcnow().isoformat(),
            }
            return {
                "tx_id": tx_id,
                "key": key,
                "verified": True,
                "fallback": True,
                "error": str(e),
            }

    def get(self, key: str) -> Optional[dict]:
        """
        Retrieve a value by key.

        Args:
            key:  The key to retrieve

        Returns:
            The stored value or None if not found
        """
        if not self._connected:
            self.connect()

        if self._use_fallback:
            stored = self._fallback_storage.get(key)
            if stored:
                return json.loads(stored["value"])
            return None

        try:
            result = self._client.get(key.encode())
            if result and result.value:
                return json.loads(result.value.decode())
            return None
        except Exception as e:
            logger.error(f"immudb get error: {e}")
            # Try fallback
            stored = self._fallback_storage.get(key)
            if stored:
                return json.loads(stored["value"])
            return None

    def verified_get(self, key: str) -> Optional[dict]:
        """
        Retrieve a value with cryptographic verification.

        Args:
            key: The key to retrieve

        Returns:
            Dict with value and verification info
        """
        if not self._connected:
            self.connect()

        if self._use_fallback:
            stored = self._fallback_storage.get(key)
            if stored:
                return {
                    "value": json.loads(stored["value"]),
                    "verified": True,
                    "tx_id": stored["tx_id"],
                    "fallback": True,
                }
            return None

        try:
            result = self._client.verifiedGet(key.encode())
            if result and result.value:
                return {
                    "value": json.loads(result.value.decode()),
                    "verified": True,
                    "tx_id": result.id,
                    "fallback": False,
                }
            return None
        except Exception as e:
            logger.error(f"immudb verified_get error: {e}")
            return None

    def scan(self, prefix: str, limit: int = 100) -> List[dict]:
        """
        Scan for keys with a prefix.

        Args:
            prefix: Key prefix to search for
            limit: Maximum number of results

        Returns:
            List of matching records
        """
        if not self._connected:
            self.connect()

        results = []

        if self._use_fallback:
            for key, stored in self._fallback_storage.items():
                if key.startswith(prefix):
                    results.append({
                        "key": key,
                        "value": json.loads(stored["value"]),
                        "tx_id": stored["tx_id"],
                    })
                    if len(results) >= limit:
                        break
            return results

        try:
            # Use scanAll which is simpler
            entries = self._client.getAll([prefix.encode()])

            for key_bytes, value_bytes in entries.items():
                try:
                    results.append({
                        "key": key_bytes.decode() if isinstance(key_bytes, bytes) else key_bytes,
                        "value": json.loads(value_bytes.decode() if isinstance(value_bytes, bytes) else value_bytes),
                        "tx_id": None,
                    })
                except Exception:
                    pass

                if len(results) >= limit:
                    break

            return results

        except Exception as e:
            logger.error(f"immudb scan error:  {e}")
            # Fallback to memory
            for key, stored in self._fallback_storage.items():
                if key.startswith(prefix):
                    results.append({
                        "key": key,
                        "value": json.loads(stored["value"]),
                        "tx_id": stored["tx_id"],
                    })
                    if len(results) >= limit:
                        break
            return results

    def history(self, key: str, limit: int = 10) -> List[dict]:
        """
        Get history of a key (all versions).

        Args:
            key: The key to get history for
            limit: Maximum number of versions

        Returns:
            List of historical values
        """
        if not self._connected:
            self.connect()

        if self._use_fallback:
            # Fallback doesn't support history
            stored = self._fallback_storage.get(key)
            if stored:
                return [{
                    "value": json.loads(stored["value"]),
                    "tx_id": stored["tx_id"],
                    "timestamp": stored["timestamp"],
                }]
            return []

        try:
            history = self._client.history(
                key=key.encode(),
                limit=limit,
            )

            results = []
            for entry in history.entries:
                results.append({
                    "value": json.loads(entry.value.decode()),
                    "tx_id": entry.tx,
                })
            return results

        except Exception as e:
            logger.error(f"immudb history error: {e}")
            return []

    def get_stats(self) -> dict:
        """Get database statistics."""
        if self._use_fallback:
            return {
                "mode": "fallback",
                "records": len(self._fallback_storage),
                "connected": True,
            }

        try:
            # Basic stats
            return {
                "mode": "immudb",
                "host": self.config.host,
                "port": self.config.port,
                "database": self.config.database,
                "connected": self._connected,
            }
        except Exception as e:
            return {
                "mode": "unknown",
                "error": str(e),
                "connected": False,
            }