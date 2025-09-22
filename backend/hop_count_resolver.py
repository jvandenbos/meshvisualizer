"""
Enhanced Hop Count Resolver for Meshtastic packets.
Provides intelligent hop count calculation and estimation when direct information is missing.
"""

import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class HopCountResolver:
    """
    Resolves hop counts for Meshtastic packets using multiple strategies:
    1. Direct calculation from hopStart/hopLimit
    2. Inference from signal strength
    3. Path tracking through relay nodes
    4. Historical pattern analysis
    """

    def __init__(self):
        # Track hop counts between node pairs
        self.hop_history: Dict[Tuple[str, str], list] = defaultdict(list)  # (from, to) -> [hop_counts]

        # Track relay paths for next-hop routing
        self.relay_paths: Dict[Tuple[str, str], str] = {}  # (from, to) -> relay_node

        # Track signal quality per hop distance
        self.rssi_by_hops: Dict[int, list] = defaultdict(list)  # hop_count -> [rssi_values]

        # Cache resolved hop counts
        self.hop_cache: Dict[str, int] = {}  # node_id -> estimated_hops

        # Local node for reference
        self.local_node_id: Optional[str] = None

    def set_local_node(self, node_id: str):
        """Set the local node ID for hop calculations"""
        self.local_node_id = node_id
        logger.info(f"Local node set for hop resolver: {node_id}")

    def calculate_hop_count(self, packet: Dict) -> Optional[int]:
        """
        Calculate hop count from packet data using multiple methods.

        Args:
            packet: Raw packet data from Meshtastic

        Returns:
            Hop count if determinable, None if unknown
        """
        from_id = packet.get('fromId') or packet.get('from')

        # Method 1: Direct calculation from hopStart/hopLimit
        hop_start = packet.get('hopStart', 0)
        hop_limit = packet.get('hopLimit', 0)

        if hop_start > 0:
            # Standard calculation: hopStart - hopLimit
            calculated_hops = hop_start - hop_limit
            logger.debug(f"Direct hop calculation: start={hop_start}, limit={hop_limit}, hops={calculated_hops}")

            # Validate and learn from this
            if 0 <= calculated_hops <= 7:  # Max 7 hops in Meshtastic
                self._learn_hop_pattern(from_id, calculated_hops, packet)
                return calculated_hops

        # Method 2: Check if it's the local node (always 0 hops)
        if from_id and from_id == self.local_node_id:
            logger.debug("Local node detected: 0 hops")
            return 0

        # Method 3: Infer from signal strength
        rssi = packet.get('rxRssi') or packet.get('rssi')
        snr = packet.get('rxSnr') or packet.get('snr')

        if rssi is not None:
            estimated = self._estimate_from_signal(rssi, snr)
            if estimated is not None:
                logger.debug(f"Signal-based estimation: RSSI={rssi}, SNR={snr}, estimated_hops={estimated}")
                return estimated

        # Method 4: Use historical data
        if from_id:
            historical = self._get_historical_hops(from_id)
            if historical is not None:
                logger.debug(f"Historical hop count for {from_id}: {historical}")
                return historical

        # Method 5: Check relay path tracking
        to_id = packet.get('toId') or packet.get('to')
        if from_id and to_id:
            relay_hops = self._check_relay_path(from_id, to_id)
            if relay_hops is not None:
                logger.debug(f"Relay path estimation: {relay_hops} hops")
                return relay_hops

        # Unable to determine
        logger.debug(f"Could not determine hop count for packet from {from_id}")
        return None

    def _learn_hop_pattern(self, node_id: str, hop_count: int, packet: Dict):
        """Learn from packets with known hop counts"""
        # Store hop count
        if node_id:
            self.hop_cache[node_id] = hop_count

        # Learn RSSI patterns
        rssi = packet.get('rxRssi') or packet.get('rssi')
        if rssi is not None and hop_count is not None:
            self.rssi_by_hops[hop_count].append(rssi)

            # Keep only recent samples (last 100)
            if len(self.rssi_by_hops[hop_count]) > 100:
                self.rssi_by_hops[hop_count] = self.rssi_by_hops[hop_count][-100:]

        # Track hop history
        to_id = packet.get('toId') or packet.get('to')
        if node_id and to_id:
            key = (node_id, to_id)
            self.hop_history[key].append(hop_count)

            # Keep only recent history
            if len(self.hop_history[key]) > 20:
                self.hop_history[key] = self.hop_history[key][-20:]

    def _estimate_from_signal(self, rssi: int, snr: Optional[float]) -> Optional[int]:
        """
        Estimate hop count based on signal strength patterns.

        Strong signals indicate fewer hops, weak signals indicate more hops.
        """
        if rssi is None:
            return None

        # Direct connection heuristics
        if rssi > -70:
            # Very strong signal - likely direct (1 hop)
            return 1
        elif rssi > -90:
            # Moderate signal - likely 1-2 hops
            if snr and snr > 0:
                return 1
            else:
                return 2
        elif rssi > -110:
            # Weak signal - likely 2-3 hops
            return 3
        elif rssi > -120:
            # Very weak signal - likely 3-4 hops
            return 4
        else:
            # Extremely weak - 5+ hops
            return 5

        # Use learned patterns if available
        best_match_hops = None
        best_match_diff = float('inf')

        for hop_count, rssi_values in self.rssi_by_hops.items():
            if rssi_values:
                avg_rssi = sum(rssi_values) / len(rssi_values)
                diff = abs(avg_rssi - rssi)

                if diff < best_match_diff and diff < 10:  # Within 10 dBm
                    best_match_diff = diff
                    best_match_hops = hop_count

        return best_match_hops

    def _get_historical_hops(self, node_id: str) -> Optional[int]:
        """Get typical hop count for a node based on history"""
        # Check cache first
        if node_id in self.hop_cache:
            return self.hop_cache[node_id]

        # Check historical patterns
        total_hops = []
        for (from_id, _), hop_counts in self.hop_history.items():
            if from_id == node_id and hop_counts:
                total_hops.extend(hop_counts)

        if total_hops:
            # Return most common hop count
            from collections import Counter
            hop_counter = Counter(total_hops)
            most_common = hop_counter.most_common(1)[0][0]

            # Cache for future use
            self.hop_cache[node_id] = most_common
            return most_common

        return None

    def _check_relay_path(self, from_id: str, to_id: str) -> Optional[int]:
        """Check if we know the relay path and estimate hops"""
        key = (from_id, to_id)

        # Direct path tracking
        if key in self.relay_paths:
            relay = self.relay_paths[key]
            # If we know the relay, it's typically 2 hops (from -> relay -> to)
            return 2

        # Reverse path check
        reverse_key = (to_id, from_id)
        if reverse_key in self.relay_paths:
            # Same relay path in reverse
            return 2

        return None

    def track_relay(self, from_id: str, to_id: str, relay_id: str):
        """Track a relay node in the path between two nodes"""
        key = (from_id, to_id)
        self.relay_paths[key] = relay_id
        logger.debug(f"Tracked relay path: {from_id} -> {relay_id} -> {to_id}")

    def get_hop_statistics(self, node_id: str) -> Dict:
        """Get hop count statistics for a node"""
        stats = {
            "cached_hops": self.hop_cache.get(node_id),
            "historical_hops": [],
            "avg_hops": None,
            "min_hops": None,
            "max_hops": None
        }

        # Gather all historical hop counts
        all_hops = []
        for (from_id, _), hop_counts in self.hop_history.items():
            if from_id == node_id:
                all_hops.extend(hop_counts)

        if all_hops:
            stats["historical_hops"] = all_hops[-10:]  # Last 10 values
            stats["avg_hops"] = sum(all_hops) / len(all_hops)
            stats["min_hops"] = min(all_hops)
            stats["max_hops"] = max(all_hops)

        return stats

    def update_from_nodeinfo(self, node_id: str, packet: Dict):
        """
        Update hop information when NodeInfo is received.
        NodeInfo packets often have more complete hop information.
        """
        hop_count = self.calculate_hop_count(packet)
        if hop_count is not None and node_id:
            self.hop_cache[node_id] = hop_count
            logger.info(f"Updated hop count for {node_id} from NodeInfo: {hop_count}")


# Global singleton instance
_resolver: Optional[HopCountResolver] = None


def get_hop_resolver() -> HopCountResolver:
    """Get or create the global hop resolver instance"""
    global _resolver
    if _resolver is None:
        _resolver = HopCountResolver()
    return _resolver


def resolve_hop_count(packet: Dict) -> Optional[int]:
    """
    Convenience function to resolve hop count for a packet.

    Usage:
        hop_count = resolve_hop_count(packet_data)
    """
    resolver = get_hop_resolver()
    return resolver.calculate_hop_count(packet)