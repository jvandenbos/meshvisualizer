"""Network metrics calculation and analysis"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import math
import asyncio
import logging

logger = logging.getLogger(__name__)


class NetworkMetrics:
    """Calculate real-time network metrics for mesh topology"""

    def __init__(self, db=None):
        self.db = db

    async def calculate_metrics(self, nodes: List[Any], links: List[Any], messages: List[Any]) -> Dict[str, Any]:
        """Calculate comprehensive network metrics"""
        try:
            # Basic counts
            total_nodes = len(nodes)
            active_nodes = len([n for n in nodes if self._is_active(n)])

            # Node categorization
            node_categories = self._categorize_nodes(nodes)

            # Network topology metrics
            topology_metrics = self._calculate_topology_metrics(nodes, links)

            # Communication metrics
            comm_metrics = self._calculate_communication_metrics(messages)

            # Performance metrics
            perf_metrics = self._calculate_performance_metrics(nodes, links)

            # Reliability metrics
            reliability_metrics = self._calculate_reliability_metrics(links, messages)

            # Time-based activity patterns
            activity_patterns = self._calculate_activity_patterns(messages)

            return {
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total_nodes": total_nodes,
                    "active_nodes": active_nodes,
                    "inactive_nodes": total_nodes - active_nodes,
                    "network_health_score": self._calculate_health_score(topology_metrics, perf_metrics, reliability_metrics),
                },
                "node_categories": node_categories,
                "topology": topology_metrics,
                "communication": comm_metrics,
                "performance": perf_metrics,
                "reliability": reliability_metrics,
                "activity": activity_patterns,
                "alerts": self._generate_alerts(topology_metrics, perf_metrics, reliability_metrics)
            }
        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
            return {"error": str(e)}

    def _is_active(self, node: Any, threshold_minutes: int = 15) -> bool:
        """Check if node is active based on last_heard time"""
        if not hasattr(node, 'last_heard') or not node.last_heard:
            return False

        try:
            last_heard = datetime.fromisoformat(str(node.last_heard))
            cutoff = datetime.now() - timedelta(minutes=threshold_minutes)
            return last_heard > cutoff
        except:
            return False

    def _categorize_nodes(self, nodes: List[Any]) -> Dict[str, Any]:
        """Categorize nodes by various attributes"""
        categories = {
            "by_role": defaultdict(int),
            "by_hardware": defaultdict(int),
            "by_hop_distance": defaultdict(int),
            "by_battery_status": {
                "critical": [],  # < 20%
                "low": [],       # 20-40%
                "medium": [],    # 40-70%
                "good": [],      # 70-100%
                "external": []   # > 100% (external power)
            },
            "by_signal_quality": {
                "excellent": [],  # > -70 dBm
                "good": [],      # -70 to -85 dBm
                "fair": [],      # -85 to -100 dBm
                "poor": [],      # < -100 dBm
                "unknown": []
            }
        }

        for node in nodes:
            # By role
            role = getattr(node, 'role', 'CLIENT')
            categories["by_role"][role] += 1

            # By hardware
            hw = getattr(node, 'hardware_model', 'Unknown')
            categories["by_hardware"][hw] += 1

            # By hop distance
            hops = getattr(node, 'hop_count', None)
            if hops is not None and hops < 999:
                categories["by_hop_distance"][f"{hops}_hop"] += 1
            else:
                categories["by_hop_distance"]["unknown"] += 1

            # By battery status
            battery = getattr(node, 'battery_level', None)
            node_id = getattr(node, 'short_name', getattr(node, 'id', 'Unknown'))
            if battery is not None:
                if battery > 100:
                    categories["by_battery_status"]["external"].append(node_id)
                elif battery >= 70:
                    categories["by_battery_status"]["good"].append(node_id)
                elif battery >= 40:
                    categories["by_battery_status"]["medium"].append(node_id)
                elif battery >= 20:
                    categories["by_battery_status"]["low"].append(node_id)
                else:
                    categories["by_battery_status"]["critical"].append(node_id)

            # By signal quality (only for direct connections)
            if hops == 0:
                rssi = getattr(node, 'rssi', None)
                if rssi is not None:
                    if rssi > -70:
                        categories["by_signal_quality"]["excellent"].append(node_id)
                    elif rssi > -85:
                        categories["by_signal_quality"]["good"].append(node_id)
                    elif rssi > -100:
                        categories["by_signal_quality"]["fair"].append(node_id)
                    else:
                        categories["by_signal_quality"]["poor"].append(node_id)
                else:
                    categories["by_signal_quality"]["unknown"].append(node_id)

        return dict(categories)

    def _calculate_topology_metrics(self, nodes: List[Any], links: List[Any]) -> Dict[str, Any]:
        """Calculate network topology metrics"""
        # Build adjacency list
        adj_list = defaultdict(set)
        for link in links:
            from_id = getattr(link, 'from_id', None)
            to_id = getattr(link, 'to_id', None)
            if from_id and to_id and to_id not in ['broadcast', '^all']:
                adj_list[from_id].add(to_id)
                adj_list[to_id].add(from_id)

        # Calculate metrics
        node_degrees = {node_id: len(neighbors) for node_id, neighbors in adj_list.items()}

        # Network diameter (max shortest path between any two nodes)
        diameter = self._calculate_network_diameter(adj_list) if adj_list else 0

        # Clustering coefficient (how connected are neighbors)
        clustering_coeff = self._calculate_clustering_coefficient(adj_list)

        # Find critical nodes (removal would partition network)
        critical_nodes = self._find_critical_nodes(adj_list)

        return {
            "total_edges": len(links),
            "average_degree": sum(node_degrees.values()) / len(node_degrees) if node_degrees else 0,
            "max_degree": max(node_degrees.values()) if node_degrees else 0,
            "network_diameter": diameter,
            "clustering_coefficient": clustering_coeff,
            "connected_components": self._count_components(adj_list),
            "critical_nodes": critical_nodes,
            "node_degrees": dict(sorted(node_degrees.items(), key=lambda x: x[1], reverse=True)[:10])  # Top 10
        }

    def _calculate_communication_metrics(self, messages: List[Any]) -> Dict[str, Any]:
        """Calculate message and communication metrics"""
        if not messages:
            return {
                "total_messages": 0,
                "messages_per_minute": 0,
                "most_active_nodes": [],
                "message_types": {}
            }

        # Time window analysis
        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        last_24h = now - timedelta(hours=24)

        hour_messages = []
        day_messages = []

        # Message type counter
        message_types = Counter()
        sender_counter = Counter()

        for msg in messages:
            timestamp = getattr(msg, 'timestamp', None)
            if timestamp:
                try:
                    msg_time = datetime.fromisoformat(str(timestamp))
                    if msg_time > last_hour:
                        hour_messages.append(msg)
                    if msg_time > last_24h:
                        day_messages.append(msg)
                except:
                    pass

            # Count message types
            msg_type = getattr(msg, 'type', 'unknown')
            message_types[msg_type] += 1

            # Count sender activity
            sender = getattr(msg, 'from_name', getattr(msg, 'from_id', 'unknown'))
            sender_counter[sender] += 1

        return {
            "total_messages": len(messages),
            "messages_last_hour": len(hour_messages),
            "messages_last_24h": len(day_messages),
            "messages_per_minute": len(hour_messages) / 60 if hour_messages else 0,
            "most_active_nodes": dict(sender_counter.most_common(5)),
            "message_types": dict(message_types),
            "average_message_length": self._calculate_avg_message_length(messages)
        }

    def _calculate_performance_metrics(self, nodes: List[Any], links: List[Any]) -> Dict[str, Any]:
        """Calculate network performance metrics"""
        # RSSI/SNR statistics for direct links
        rssi_values = []
        snr_values = []
        hop_counts = []

        for node in nodes:
            hops = getattr(node, 'hop_count', None)
            if hops is not None and hops < 999:
                hop_counts.append(hops)

                if hops == 0:  # Direct connection
                    rssi = getattr(node, 'rssi', None)
                    snr = getattr(node, 'snr', None)
                    if rssi is not None:
                        rssi_values.append(rssi)
                    if snr is not None:
                        snr_values.append(snr)

        return {
            "average_rssi": sum(rssi_values) / len(rssi_values) if rssi_values else None,
            "min_rssi": min(rssi_values) if rssi_values else None,
            "max_rssi": max(rssi_values) if rssi_values else None,
            "average_snr": sum(snr_values) / len(snr_values) if snr_values else None,
            "average_hop_count": sum(hop_counts) / len(hop_counts) if hop_counts else None,
            "max_hop_count": max(hop_counts) if hop_counts else None,
            "signal_quality_distribution": self._get_signal_distribution(rssi_values),
            "hop_distribution": Counter(hop_counts) if hop_counts else {}
        }

    def _calculate_reliability_metrics(self, links: List[Any], messages: List[Any]) -> Dict[str, Any]:
        """Calculate network reliability metrics"""
        # Link success rates
        link_stats = defaultdict(lambda: {"attempts": 0, "success": 0})

        for link in links:
            from_id = getattr(link, 'from_id', None)
            to_id = getattr(link, 'to_id', None)
            if from_id and to_id:
                key = f"{from_id}->{to_id}"
                link_stats[key]["attempts"] += 1
                # Assume successful if we received it
                link_stats[key]["success"] += 1

        # Calculate packet loss estimate (based on expected vs received)
        total_attempts = sum(s["attempts"] for s in link_stats.values())
        total_success = sum(s["success"] for s in link_stats.values())

        # Message delivery success rate (simplified)
        broadcast_messages = len([m for m in messages if getattr(m, 'to_id', '') in ['broadcast', '^all']])
        direct_messages = len(messages) - broadcast_messages

        return {
            "estimated_packet_loss_rate": 1 - (total_success / total_attempts) if total_attempts > 0 else 0,
            "total_link_attempts": total_attempts,
            "successful_transmissions": total_success,
            "broadcast_messages": broadcast_messages,
            "direct_messages": direct_messages,
            "link_reliability": {
                k: v["success"] / v["attempts"] if v["attempts"] > 0 else 0
                for k, v in sorted(link_stats.items(), key=lambda x: x[1]["attempts"], reverse=True)[:10]
            }
        }

    def _calculate_activity_patterns(self, messages: List[Any]) -> Dict[str, Any]:
        """Calculate temporal activity patterns"""
        if not messages:
            return {"hourly_distribution": {}, "peak_hours": []}

        # Hourly message distribution
        hourly = defaultdict(int)

        for msg in messages:
            timestamp = getattr(msg, 'timestamp', None)
            if timestamp:
                try:
                    msg_time = datetime.fromisoformat(str(timestamp))
                    hour = msg_time.hour
                    hourly[hour] += 1
                except:
                    pass

        # Find peak hours
        sorted_hours = sorted(hourly.items(), key=lambda x: x[1], reverse=True)
        peak_hours = [h for h, _ in sorted_hours[:3]]

        return {
            "hourly_distribution": dict(hourly),
            "peak_hours": peak_hours,
            "total_active_hours": len(hourly),
            "messages_per_hour_avg": sum(hourly.values()) / len(hourly) if hourly else 0
        }

    def _calculate_health_score(self, topology: Dict, performance: Dict, reliability: Dict) -> float:
        """Calculate overall network health score (0-100)"""
        score = 100.0

        # Topology factors
        if topology.get("connected_components", 1) > 1:
            score -= 20  # Network is partitioned

        if topology.get("average_degree", 0) < 2:
            score -= 10  # Low connectivity

        # Performance factors
        avg_rssi = performance.get("average_rssi", -100)
        if avg_rssi < -100:
            score -= 15
        elif avg_rssi < -90:
            score -= 10
        elif avg_rssi < -80:
            score -= 5

        # Reliability factors
        packet_loss = reliability.get("estimated_packet_loss_rate", 0)
        score -= packet_loss * 30  # High penalty for packet loss

        return max(0, min(100, score))

    def _generate_alerts(self, topology: Dict, performance: Dict, reliability: Dict) -> List[Dict]:
        """Generate network health alerts"""
        alerts = []

        # Check for network partition
        if topology.get("connected_components", 1) > 1:
            alerts.append({
                "level": "warning",
                "type": "topology",
                "message": f"Network is partitioned into {topology['connected_components']} segments"
            })

        # Check for critical nodes
        critical = topology.get("critical_nodes", [])
        if critical:
            alerts.append({
                "level": "info",
                "type": "topology",
                "message": f"Critical nodes that could partition network: {', '.join(critical[:3])}"
            })

        # Check signal quality
        avg_rssi = performance.get("average_rssi", -100)
        if avg_rssi < -95:
            alerts.append({
                "level": "warning",
                "type": "performance",
                "message": f"Poor average signal strength: {avg_rssi:.1f} dBm"
            })

        # Check packet loss
        packet_loss = reliability.get("estimated_packet_loss_rate", 0)
        if packet_loss > 0.3:
            alerts.append({
                "level": "critical",
                "type": "reliability",
                "message": f"High packet loss rate: {packet_loss:.1%}"
            })
        elif packet_loss > 0.1:
            alerts.append({
                "level": "warning",
                "type": "reliability",
                "message": f"Moderate packet loss rate: {packet_loss:.1%}"
            })

        return alerts

    # Helper methods
    def _calculate_network_diameter(self, adj_list: Dict) -> int:
        """Calculate maximum shortest path between any two nodes"""
        if not adj_list:
            return 0

        max_dist = 0
        nodes = list(adj_list.keys())

        for start in nodes[:min(10, len(nodes))]:  # Sample for performance
            distances = self._bfs_distances(start, adj_list)
            if distances:
                max_dist = max(max_dist, max(distances.values()))

        return max_dist

    def _bfs_distances(self, start: str, adj_list: Dict) -> Dict[str, int]:
        """BFS to find distances from start node"""
        distances = {start: 0}
        queue = [(start, 0)]
        visited = {start}

        while queue:
            node, dist = queue.pop(0)
            for neighbor in adj_list.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    distances[neighbor] = dist + 1
                    queue.append((neighbor, dist + 1))

        return distances

    def _calculate_clustering_coefficient(self, adj_list: Dict) -> float:
        """Calculate average clustering coefficient"""
        if not adj_list:
            return 0

        coefficients = []

        for node, neighbors in adj_list.items():
            if len(neighbors) < 2:
                coefficients.append(0)
                continue

            # Count edges between neighbors
            edges = 0
            neighbors_list = list(neighbors)
            for i in range(len(neighbors_list)):
                for j in range(i + 1, len(neighbors_list)):
                    if neighbors_list[j] in adj_list.get(neighbors_list[i], []):
                        edges += 1

            # Calculate coefficient
            possible = len(neighbors) * (len(neighbors) - 1) / 2
            coefficients.append(edges / possible if possible > 0 else 0)

        return sum(coefficients) / len(coefficients) if coefficients else 0

    def _count_components(self, adj_list: Dict) -> int:
        """Count connected components in the graph"""
        if not adj_list:
            return 0

        visited = set()
        components = 0

        for node in adj_list:
            if node not in visited:
                components += 1
                # DFS to mark all connected nodes
                stack = [node]
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        stack.extend(adj_list.get(current, []))

        return components

    def _find_critical_nodes(self, adj_list: Dict) -> List[str]:
        """Find nodes whose removal would increase connected components"""
        if not adj_list or len(adj_list) < 3:
            return []

        original_components = self._count_components(adj_list)
        critical = []

        for node in list(adj_list.keys())[:20]:  # Check top 20 nodes for performance
            # Create graph without this node
            temp_adj = {k: v - {node} for k, v in adj_list.items() if k != node}
            new_components = self._count_components(temp_adj)

            if new_components > original_components:
                critical.append(node)

        return critical

    def _get_signal_distribution(self, rssi_values: List[float]) -> Dict[str, int]:
        """Get distribution of signal quality"""
        if not rssi_values:
            return {}

        distribution = {
            "excellent": 0,  # > -70
            "good": 0,       # -70 to -85
            "fair": 0,       # -85 to -100
            "poor": 0        # < -100
        }

        for rssi in rssi_values:
            if rssi > -70:
                distribution["excellent"] += 1
            elif rssi > -85:
                distribution["good"] += 1
            elif rssi > -100:
                distribution["fair"] += 1
            else:
                distribution["poor"] += 1

        return distribution

    def _calculate_avg_message_length(self, messages: List[Any]) -> float:
        """Calculate average message length"""
        lengths = []
        for msg in messages:
            text = getattr(msg, 'message', '')
            if text:
                lengths.append(len(text))

        return sum(lengths) / len(lengths) if lengths else 0