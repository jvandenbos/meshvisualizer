"""
PKC Key History Manager - Tracks public key history and metadata for nodes
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)

class PKCKeyHistory:
    """Manages public key history and metadata for debugging PKC issues"""

    def __init__(self, storage_path: str = "pkc_key_history.json"):
        """
        Initialize the PKC Key History Manager

        Args:
            storage_path: Path to persistent storage file
        """
        self.storage_path = Path(storage_path)
        self.node_keys: Dict[str, dict] = {}
        self.load_history()

    def load_history(self):
        """Load key history from disk"""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self.node_keys = data
                logger.info(f"Loaded PKC history for {len(self.node_keys)} nodes")
        except Exception as e:
            logger.error(f"Error loading PKC history: {e}")
            self.node_keys = {}

    def save_history(self):
        """Save key history to disk"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.node_keys, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving PKC history: {e}")

    def update_public_key(self, node_id: str, public_key: bytes, node_name: str = None) -> dict:
        """
        Update public key for a node and track history

        Args:
            node_id: Node ID (e.g., "!a0a53aa4")
            public_key: 32-byte public key
            node_name: Optional friendly name

        Returns:
            Dictionary with update info
        """
        if not public_key or len(public_key) != 32:
            return {"error": "Invalid public key"}

        # Convert to hex for storage and comparison
        key_hex = public_key.hex()
        key_hash = hashlib.sha256(public_key).hexdigest()[:8]
        current_time = datetime.now()

        # Initialize node entry if doesn't exist
        if node_id not in self.node_keys:
            self.node_keys[node_id] = {
                "node_name": node_name,
                "current_key": None,
                "last_updated": None,
                "first_seen": current_time.isoformat(),
                "history": [],
                "update_count": 0,
                "decryption_failures": 0,
                "last_failure": None
            }

        node_info = self.node_keys[node_id]

        # Update node name if provided
        if node_name:
            node_info["node_name"] = node_name

        # Check if key has changed
        key_changed = node_info["current_key"] != key_hex

        if key_changed:
            # Add old key to history if it exists
            if node_info["current_key"]:
                node_info["history"].append({
                    "key": node_info["current_key"],
                    "hash": hashlib.sha256(bytes.fromhex(node_info["current_key"])).hexdigest()[:8],
                    "added": node_info["last_updated"],
                    "removed": current_time.isoformat(),
                    "duration_hours": self._calculate_duration(node_info["last_updated"], current_time)
                })

            # Update current key
            node_info["current_key"] = key_hex
            node_info["current_key_hash"] = key_hash
            node_info["last_updated"] = current_time.isoformat()
            node_info["update_count"] += 1

            # Keep only last 10 history entries
            if len(node_info["history"]) > 10:
                node_info["history"] = node_info["history"][-10:]

            self.save_history()

            logger.info(f"Updated public key for {node_id} ({node_name}): {key_hash}")

            return {
                "node_id": node_id,
                "node_name": node_name,
                "key_changed": True,
                "key_hash": key_hash,
                "update_count": node_info["update_count"],
                "previous_key": node_info["history"][-1]["hash"] if node_info["history"] else None
            }
        else:
            # Key hasn't changed, just update timestamp
            node_info["last_confirmed"] = current_time.isoformat()
            return {
                "node_id": node_id,
                "node_name": node_name,
                "key_changed": False,
                "key_hash": key_hash,
                "last_updated": node_info["last_updated"]
            }

    def record_decryption_failure(self, node_id: str):
        """Record a PKC decryption failure for a node"""
        if node_id not in self.node_keys:
            self.node_keys[node_id] = {
                "node_name": None,
                "current_key": None,
                "last_updated": None,
                "first_seen": datetime.now().isoformat(),
                "history": [],
                "update_count": 0,
                "decryption_failures": 0,
                "last_failure": None
            }

        self.node_keys[node_id]["decryption_failures"] += 1
        self.node_keys[node_id]["last_failure"] = datetime.now().isoformat()
        self.save_history()

    def get_key_info(self, node_id: str) -> Optional[dict]:
        """
        Get current key info and metadata for a node

        Returns:
            Dictionary with key info or None if not found
        """
        if node_id not in self.node_keys:
            return None

        node_info = self.node_keys[node_id]

        # Calculate age if we have a last_updated time
        age_hours = None
        if node_info["last_updated"]:
            last_updated = datetime.fromisoformat(node_info["last_updated"])
            age_hours = (datetime.now() - last_updated).total_seconds() / 3600

        return {
            "node_id": node_id,
            "node_name": node_info["node_name"],
            "current_key_hash": node_info.get("current_key_hash", "unknown"),
            "current_key": node_info.get("current_key", ""),
            "last_updated": node_info["last_updated"],
            "age_hours": round(age_hours, 1) if age_hours else None,
            "update_count": node_info["update_count"],
            "history_count": len(node_info["history"]),
            "decryption_failures": node_info["decryption_failures"],
            "last_failure": node_info["last_failure"]
        }

    def get_diagnostics(self, node_id: str) -> str:
        """
        Get formatted diagnostic string for error messages

        Returns:
            Formatted string with key diagnostics
        """
        info = self.get_key_info(node_id)

        if not info:
            return "No PKC key on record"

        if not info["current_key"]:
            return f"No public key (failures: {info['decryption_failures']})"

        # Format diagnostic info
        diag_parts = []

        # Show key hash (first 16 chars of actual key)
        key_preview = info["current_key"][:16] if info["current_key"] else "none"
        diag_parts.append(f"key:{key_preview}...")

        # Show age
        if info["age_hours"] is not None:
            if info["age_hours"] < 1:
                age_str = "<1hr"
            elif info["age_hours"] < 24:
                age_str = f"{info['age_hours']:.1f}hr"
            else:
                days = info["age_hours"] / 24
                age_str = f"{days:.1f}d"
            diag_parts.append(f"age:{age_str}")

        # Show update count if > 1
        if info["update_count"] > 1:
            diag_parts.append(f"updates:{info['update_count']}")

        # Show failure count if any
        if info["decryption_failures"] > 0:
            diag_parts.append(f"fails:{info['decryption_failures']}")

        return " | ".join(diag_parts)

    def get_full_history(self, node_id: str) -> Optional[dict]:
        """Get full history for a node including all key changes"""
        if node_id not in self.node_keys:
            return None

        return self.node_keys[node_id]

    def _calculate_duration(self, start_time_str: str, end_time: datetime) -> float:
        """Calculate duration in hours between two times"""
        try:
            start_time = datetime.fromisoformat(start_time_str)
            return (end_time - start_time).total_seconds() / 3600
        except:
            return 0.0

    def clear_node(self, node_id: str):
        """Clear all data for a specific node"""
        if node_id in self.node_keys:
            del self.node_keys[node_id]
            self.save_history()
            logger.info(f"Cleared PKC history for {node_id}")

    def get_summary(self) -> dict:
        """Get summary statistics"""
        total_nodes = len(self.node_keys)
        nodes_with_keys = len([n for n in self.node_keys.values() if n["current_key"]])
        total_failures = sum(n["decryption_failures"] for n in self.node_keys.values())
        nodes_with_failures = len([n for n in self.node_keys.values() if n["decryption_failures"] > 0])

        return {
            "total_nodes": total_nodes,
            "nodes_with_keys": nodes_with_keys,
            "nodes_without_keys": total_nodes - nodes_with_keys,
            "total_decryption_failures": total_failures,
            "nodes_with_failures": nodes_with_failures,
            "average_key_age_hours": self._calculate_average_age()
        }

    def _calculate_average_age(self) -> Optional[float]:
        """Calculate average key age across all nodes"""
        ages = []
        now = datetime.now()

        for node in self.node_keys.values():
            if node["last_updated"]:
                try:
                    last_updated = datetime.fromisoformat(node["last_updated"])
                    age = (now - last_updated).total_seconds() / 3600
                    ages.append(age)
                except:
                    pass

        return round(sum(ages) / len(ages), 1) if ages else None