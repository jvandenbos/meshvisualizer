"""
Enhanced Node Name Resolver with multi-source fallback and persistence.
Ensures every node always has a displayable name through a robust resolution chain.
"""

import logging
import asyncio
import aiosqlite
from typing import Dict, Optional, Set, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json
from backend.name_generator import generate_friendly_name, is_generated_name

logger = logging.getLogger(__name__)


class EnhancedNodeResolver:
    """
    Robust node name resolution with multiple data sources and smart caching.

    Resolution Priority:
    1. Real user-provided names (from NodeInfo)
    2. Previously seen real names (persistent cache)
    3. Agent-assigned names
    4. Generated friendly names (*swift-eagle format)
    5. Fallback to Node-ID format
    """

    def __init__(self, db_path: str = "meshtastic.db", cache_path: str = "node_name_cache.json"):
        self.db_path = db_path
        self.cache_path = Path(cache_path)

        # In-memory caches
        self.name_cache: Dict[str, str] = {}  # node_id -> best_known_name
        self.real_names: Dict[str, Tuple[str, datetime]] = {}  # node_id -> (real_name, last_seen)
        self.pending_resolution: Set[str] = set()  # IDs being actively resolved

        # Statistics
        self.stats = {
            "total_resolutions": 0,
            "cache_hits": 0,
            "db_lookups": 0,
            "generated_names": 0,
            "nodeinfo_updates": 0
        }

        # Load persistent cache on init
        self._load_cache()

    def _load_cache(self):
        """Load persistent name cache from disk"""
        try:
            if self.cache_path.exists():
                with open(self.cache_path, 'r') as f:
                    data = json.load(f)
                    # Convert timestamps back to datetime
                    for node_id, info in data.get("real_names", {}).items():
                        if isinstance(info, dict):
                            self.real_names[node_id] = (
                                info["name"],
                                datetime.fromisoformat(info["last_seen"])
                            )
                    self.name_cache = data.get("name_cache", {})
                    logger.info(f"Loaded name cache: {len(self.real_names)} real names, {len(self.name_cache)} cached")
        except Exception as e:
            logger.error(f"Error loading name cache: {e}")

    def _save_cache(self):
        """Persist name cache to disk"""
        try:
            data = {
                "real_names": {
                    node_id: {
                        "name": name,
                        "last_seen": last_seen.isoformat()
                    }
                    for node_id, (name, last_seen) in self.real_names.items()
                },
                "name_cache": self.name_cache,
                "stats": self.stats,
                "last_updated": datetime.now().isoformat()
            }
            with open(self.cache_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving name cache: {e}")

    def normalize_node_id(self, node_id: str) -> str:
        """Ensure consistent node ID format (!XXXXXXXX)"""
        if not node_id:
            return ""

        # Already in hex format
        if node_id.startswith("!"):
            return node_id[:9]  # Ensure 8 hex digits after !

        # Decimal format - convert to hex
        try:
            num_id = int(node_id)
            return f"!{num_id:08x}"
        except:
            return node_id

    async def resolve_name(self, node_id: str, hint_name: Optional[str] = None) -> str:
        """
        Resolve node ID to best available name.

        Args:
            node_id: Node identifier (hex or decimal)
            hint_name: Optional name hint from current packet

        Returns:
            Best available name for the node
        """
        self.stats["total_resolutions"] += 1
        node_id = self.normalize_node_id(node_id)

        if not node_id:
            return "Unknown"

        # Priority 1: Use hint if it's a real name
        if hint_name and not self._is_placeholder_name(hint_name):
            self._update_real_name(node_id, hint_name)
            return hint_name

        # Priority 2: Check memory cache
        if node_id in self.name_cache:
            self.stats["cache_hits"] += 1
            return self.name_cache[node_id]

        # Priority 3: Check real names history
        if node_id in self.real_names:
            name, last_seen = self.real_names[node_id]
            # Use if seen within last 7 days
            if datetime.now() - last_seen < timedelta(days=7):
                self.name_cache[node_id] = name
                return name

        # Priority 4: Database lookup (async)
        if node_id not in self.pending_resolution:
            self.pending_resolution.add(node_id)
            try:
                db_name = await self._lookup_in_database(node_id)
                if db_name and not self._is_placeholder_name(db_name):
                    self._update_real_name(node_id, db_name)
                    return db_name
            finally:
                self.pending_resolution.discard(node_id)

        # Priority 5: Generate friendly name
        friendly = generate_friendly_name(node_id)
        self.stats["generated_names"] += 1
        self.name_cache[node_id] = friendly
        logger.info(f"Generated name for {node_id}: {friendly}")

        # Save cache periodically
        if self.stats["total_resolutions"] % 100 == 0:
            self._save_cache()

        return friendly

    async def _lookup_in_database(self, node_id: str) -> Optional[str]:
        """Look up node name in database"""
        self.stats["db_lookups"] += 1

        try:
            async with aiosqlite.connect(self.db_path) as db:
                # First try current session
                cursor = await db.execute("""
                    SELECT short_name, long_name
                    FROM nodes
                    WHERE id = ? AND session_id = (
                        SELECT MAX(id) FROM sessions WHERE is_active = 1
                    )
                """, (node_id,))
                row = await cursor.fetchone()

                if row and row[0]:
                    return row[0] if not self._is_placeholder_name(row[0]) else row[1]

                # Try history with real names
                cursor = await db.execute("""
                    SELECT short_name, long_name
                    FROM nodes_history
                    WHERE id = ?
                    AND short_name NOT LIKE 'Node-%'
                    AND short_name NOT LIKE '!%'
                    AND short_name IS NOT NULL
                    ORDER BY timestamp DESC
                    LIMIT 1
                """, (node_id,))
                row = await cursor.fetchone()

                if row and row[0]:
                    return row[0] if not self._is_placeholder_name(row[0]) else row[1]

        except Exception as e:
            logger.error(f"Database lookup failed for {node_id}: {e}")

        return None

    def _is_placeholder_name(self, name: str) -> bool:
        """Check if name is a placeholder/default"""
        if not name:
            return True

        placeholders = [
            "Node-", "!",  # Default formats
            "Unknown", "Meshtastic",  # Generic names
            "N/A", "None", "null"  # Empty indicators
        ]

        name_lower = name.lower()
        return any(name.startswith(p) or name_lower == p.lower() for p in placeholders)

    def _update_real_name(self, node_id: str, name: str):
        """Record a real name for a node"""
        if not self._is_placeholder_name(name):
            self.real_names[node_id] = (name, datetime.now())
            self.name_cache[node_id] = name
            self.stats["nodeinfo_updates"] += 1
            logger.debug(f"Updated real name: {node_id} = {name}")

    def process_nodeinfo_update(self, node_id: str, short_name: str, long_name: str):
        """
        Process a NodeInfo packet update.

        Called when NodeInfo is received to update our name cache.
        """
        node_id = self.normalize_node_id(node_id)

        # Prefer short_name, fallback to long_name
        best_name = None
        if short_name and not self._is_placeholder_name(short_name):
            best_name = short_name
        elif long_name and not self._is_placeholder_name(long_name):
            best_name = long_name

        if best_name:
            self._update_real_name(node_id, best_name)
            # Persist immediately for NodeInfo updates
            self._save_cache()
            logger.info(f"NodeInfo update: {node_id} = {best_name}")

    async def request_missing_nodeinfo(self, node_id: str, interface):
        """
        Proactively request NodeInfo for nodes with generated names.

        Args:
            node_id: Node to request info for
            interface: Meshtastic interface for sending requests
        """
        node_id = self.normalize_node_id(node_id)

        # Only request if we don't have a real name
        if node_id in self.real_names:
            return

        current_name = self.name_cache.get(node_id, "")
        if is_generated_name(current_name) or self._is_placeholder_name(current_name):
            try:
                # Convert hex ID to decimal for Meshtastic
                decimal_id = int(node_id[1:], 16)
                logger.info(f"Requesting NodeInfo for {node_id} (currently: {current_name})")

                # Send NodeInfo request
                interface.sendNodeInfo(destinationId=decimal_id)

                # Rate limit requests
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Failed to request NodeInfo for {node_id}: {e}")

    def get_stats(self) -> Dict:
        """Get resolver statistics"""
        return {
            **self.stats,
            "cached_names": len(self.name_cache),
            "known_real_names": len(self.real_names),
            "cache_hit_rate": f"{(self.stats['cache_hits'] / max(1, self.stats['total_resolutions'])) * 100:.1f}%"
        }

    def get_all_known_names(self) -> Dict[str, str]:
        """Get all currently known node names"""
        return dict(self.name_cache)


# Global singleton instance
_resolver: Optional[EnhancedNodeResolver] = None


def get_resolver() -> EnhancedNodeResolver:
    """Get or create the global resolver instance"""
    global _resolver
    if _resolver is None:
        _resolver = EnhancedNodeResolver()
    return _resolver


async def resolve_node_name(node_id: str, hint_name: Optional[str] = None) -> str:
    """
    Convenience function to resolve a node name.

    Usage:
        name = await resolve_node_name("!421d066a")
        name = await resolve_node_name("1109198442", hint_name="jsp0")
    """
    resolver = get_resolver()
    return await resolver.resolve_name(node_id, hint_name)