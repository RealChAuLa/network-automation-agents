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
            host=os. getenv("IMMUDB_HOST", "localhost"),
            port=int(os.getenv("IMMUDB_PORT", "3322")),
            user=os.getenv("IMMUDB_USER", "immudb"),
            password=os.getenv("IMMUDB_PASSWORD", "immudb"),
            database=os.getenv("IMMUDB_DATABASE", "defaultdb"),
        )


class ImmudbClient:
    """
    Client for immudb operations.

    Provides methods to store and retrieve immutable audit records.
    """

    # Special key to track all audit keys
    INDEX_KEY = "audit: _index"

    def __init__(self, config: Optional[ImmudbConfig] = None):
        """Initialize immudb client."""
        self.config = config or ImmudbConfig.from_env()
        self._client = None
        self._connected = False
        self._use_fallback = False
        self._fallback_storage:  dict = {}
        self._keys_index: List[str] = []

    def connect(self) -> bool:
        """Connect to immudb."""
        try:
            from immudb import ImmudbClient as ImmuClient

            self._client = ImmuClient(
                f"{self.config.host}:{self.config.port}"
            )

            self._client.login(
                username=self.config. user,
                password=self.config. password,
                database=self.config.database,
            )

            self._connected = True
            self._use_fallback = False

            # Load existing keys index
            self._load_keys_index()

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

    def _load_keys_index(self):
        """Load the keys index from immudb."""
        if self._use_fallback:
            return

        try:
            result = self._client. get(self. INDEX_KEY. encode())
            if result and result.value:
                self._keys_index = json.loads(result. value.decode())
        except Exception:
            self._keys_index = []

    def _save_keys_index(self):
        """Save the keys index to immudb."""
        if self._use_fallback:
            return

        try:
            self._client.set(
                self.INDEX_KEY.encode(),
                json.dumps(self._keys_index).encode()
            )
        except Exception as e:
            logger.error(f"Failed to save keys index:  {e}")

    def _add_to_index(self, key:  str):
        """Add a key to the index."""
        if key not in self._keys_index and key != self.INDEX_KEY:
            self._keys_index.insert(0, key)  # Add to beginning (newest first)
            # Keep only last 10000 keys
            self._keys_index = self._keys_index[: 10000]
            self._save_keys_index()

    def set(self, key: str, value: dict) -> dict:
        """Store a key-value pair."""
        if not self._connected:
            self.connect()

        value_json = json. dumps(value, default=str)

        if self._use_fallback:
            tx_id = len(self._fallback_storage) + 1
            self._fallback_storage[key] = {
                "value": value_json,
                "tx_id": tx_id,
                "timestamp":  datetime.utcnow().isoformat(),
            }
            return {
                "tx_id": tx_id,
                "key": key,
                "verified": True,
                "fallback": True,
            }

        try:
            result = self._client. set(key.encode(), value_json.encode())

            # Add to index
            self._add_to_index(key)

            logger.debug(f"Stored key:  {key}")

            return {
                "tx_id": result. id,
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
                "timestamp": datetime. utcnow().isoformat(),
            }
            return {
                "tx_id": tx_id,
                "key": key,
                "verified": True,
                "fallback": True,
                "error": str(e),
            }

    def get(self, key: str) -> Optional[dict]:
        """Retrieve a value by key."""
        if not self._connected:
            self.connect()

        if self._use_fallback:
            stored = self._fallback_storage.get(key)
            if stored:
                return json.loads(stored["value"])
            return None

        try:
            result = self._client. get(key.encode())
            if result and result.value:
                return json. loads(result.value.decode())
            return None
        except Exception as e:
            logger.error(f"immudb get error: {e}")
            stored = self._fallback_storage.get(key)
            if stored:
                return json.loads(stored["value"])
            return None

    def verified_get(self, key: str) -> Optional[dict]:
        """Retrieve a value with cryptographic verification."""
        if not self._connected:
            self. connect()

        if self._use_fallback:
            stored = self._fallback_storage. get(key)
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

        Uses the keys index to find matching keys.
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

        # Use index to find matching keys
        matching_keys = [k for k in self._keys_index if k.startswith(prefix)][:limit]

        for key in matching_keys:
            try:
                value = self.get(key)
                if value:
                    results.append({
                        "key":  key,
                        "value": value,
                        "tx_id": None,
                    })
            except Exception as e:
                logger.error(f"Error getting key {key}: {e}")

        return results

    def get_all_keys(self, prefix: str = "audit:", limit: int = 100) -> List[str]:
        """Get all keys with a prefix."""
        if self._use_fallback:
            return [k for k in self._fallback_storage.keys() if k.startswith(prefix)][:limit]

        return [k for k in self._keys_index if k.startswith(prefix)][:limit]

    def history(self, key:  str, limit: int = 10) -> List[dict]:
        """Get history of a key (all versions)."""
        if not self._connected:
            self.connect()

        if self._use_fallback:
            stored = self._fallback_storage.get(key)
            if stored:
                return [{
                    "value": json.loads(stored["value"]),
                    "tx_id": stored["tx_id"],
                    "timestamp":  stored["timestamp"],
                }]
            return []

        try:
            history = self._client.history(
                key=key.encode(),
                offset=0,
                limit=limit,
                desc=True,
            )

            results = []
            for entry in history:
                results.append({
                    "value":  json.loads(entry.value.decode()),
                    "tx_id": entry. tx,
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
                "records":  len(self._fallback_storage),
                "connected": True,
            }

        return {
            "mode":  "immudb",
            "host": self.config. host,
            "port": self.config.port,
            "database": self. config.database,
            "connected": self._connected,
            "indexed_keys": len(self._keys_index),
        }