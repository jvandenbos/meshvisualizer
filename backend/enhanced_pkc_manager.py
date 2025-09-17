"""Enhanced PKC Key Manager for Meshtastic DMs

This module provides comprehensive PKC key management with aggressive
key collection, validation, and recovery strategies.
"""

import asyncio
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Set, List, Tuple
from pathlib import Path
from collections import defaultdict
import base64

logger = logging.getLogger(__name__)


class EnhancedPKCManager:
    """Advanced PKC key management with proactive strategies"""

    def __init__(self, meshtastic_interface=None, db=None):
        self.interface = meshtastic_interface
        self.db = db

        # Core key storage
        self.public_keys: Dict[str, bytes] = {}  # node_id -> public_key
        self.key_metadata: Dict[str, dict] = {}  # node_id -> metadata

        # Tracking
        self.failed_decryptions: Dict[str, List[dict]] = defaultdict(list)
        self.pending_messages: Dict[str, List[dict]] = defaultdict(list)
        self.key_request_times: Dict[str, float] = {}
        self.successful_dms: Dict[str, int] = defaultdict(int)
        self.failed_dms: Dict[str, int] = defaultdict(int)

        # Configuration
        self.key_refresh_interval = 86400  # 24 hours
        self.key_request_cooldown = 300  # 5 minutes between requests
        self.max_retry_attempts = 3
        self.enable_auto_recovery = True

        # Statistics
        self.stats = {
            'total_keys': 0,
            'keys_requested': 0,
            'keys_received': 0,
            'dms_successful': 0,
            'dms_failed': 0,
            'recovery_attempts': 0,
            'recovery_successful': 0
        }

        # Load persisted keys
        self.storage_path = Path("pkc_keys_enhanced.json")
        self.load_keys()

        # Start background tasks
        self.tasks = []
        if asyncio.get_event_loop().is_running():
            self.tasks.append(asyncio.create_task(self.periodic_key_refresh()))
            self.tasks.append(asyncio.create_task(self.process_pending_messages()))
            self.tasks.append(asyncio.create_task(self.health_monitor()))

    def load_keys(self) -> None:
        """Load persisted keys from disk"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    # Convert base64 back to bytes
                    for node_id, key_data in data.get('keys', {}).items():
                        self.public_keys[node_id] = base64.b64decode(key_data['key'])
                        self.key_metadata[node_id] = key_data.get('metadata', {})
                    self.stats = data.get('stats', self.stats)
                logger.info(f"Loaded {len(self.public_keys)} PKC keys from disk")
            except Exception as e:
                logger.error(f"Failed to load PKC keys: {e}")

    def save_keys(self) -> None:
        """Persist keys to disk"""
        try:
            data = {
                'keys': {},
                'stats': self.stats,
                'saved_at': datetime.now().isoformat()
            }

            for node_id, public_key in self.public_keys.items():
                data['keys'][node_id] = {
                    'key': base64.b64encode(public_key).decode('ascii'),
                    'metadata': self.key_metadata.get(node_id, {})
                }

            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self.public_keys)} PKC keys to disk")
        except Exception as e:
            logger.error(f"Failed to save PKC keys: {e}")

    def handle_node_info(self, node_id: str, node_data: dict) -> None:
        """Process incoming NodeInfo with potential public key"""
        public_key = node_data.get('user', {}).get('publicKey', None)

        if public_key:
            # Convert from various formats
            if isinstance(public_key, str):
                # Base64 encoded
                try:
                    public_key = base64.b64decode(public_key)
                except:
                    # Hex encoded
                    try:
                        public_key = bytes.fromhex(public_key)
                    except:
                        logger.warning(f"Could not decode public key for {node_id}")
                        return

            if self.validate_key(public_key):
                existing_key = self.public_keys.get(node_id)

                if existing_key != public_key:
                    if existing_key:
                        logger.info(f"Updated public key for {node_id}")
                    else:
                        logger.info(f"New public key for {node_id}")
                        self.stats['keys_received'] += 1

                    self.public_keys[node_id] = public_key
                    self.key_metadata[node_id] = {
                        'received_at': time.time(),
                        'last_verified': time.time(),
                        'source': 'node_info',
                        'hardware': node_data.get('user', {}).get('hwModel', 'unknown'),
                        'long_name': node_data.get('user', {}).get('longName', ''),
                        'short_name': node_data.get('user', {}).get('shortName', '')
                    }
                    self.save_keys()

                    # Process any pending messages for this node
                    self.process_pending_for_node(node_id)

                self.stats['total_keys'] = len(self.public_keys)
            else:
                logger.warning(f"Invalid public key received for {node_id}")

    def validate_key(self, public_key: bytes) -> bool:
        """Validate a Curve25519 public key"""
        if not public_key or len(public_key) != 32:
            return False

        # Check for weak keys
        if all(b == 0 for b in public_key):
            logger.warning("Rejected all-zero public key")
            return False

        if all(b == 0xFF for b in public_key):
            logger.warning("Rejected all-FF public key")
            return False

        # Check for low-order points (basic check)
        # These are known weak points for Curve25519
        weak_points = [
            bytes([0] * 32),
            bytes([1] + [0] * 31),
            bytes([0xe0, 0xeb, 0x7a, 0x7c, 0x3b, 0x41, 0xb8, 0xae,
                  0x16, 0x56, 0xe3, 0xfa, 0xf1, 0x9f, 0xc4, 0x6a,
                  0xda, 0x09, 0x8d, 0xeb, 0x9c, 0x32, 0xb1, 0xfd,
                  0x86, 0x62, 0x05, 0x16, 0x5f, 0x49, 0xb8, 0x00])
        ]

        if public_key in weak_points:
            logger.warning("Rejected weak Curve25519 point")
            return False

        return True

    def handle_encrypted_packet(self, packet: dict) -> dict:
        """Process encrypted packet and attempt recovery if needed"""
        # Check if this is a PKI encrypted packet (channel 0)
        if packet.get('channel') != 0:
            return packet

        from_id = packet.get('fromId', packet.get('from'))
        to_id = packet.get('toId', packet.get('to'))

        # Track the failure
        self.failed_dms[from_id] += 1
        self.stats['dms_failed'] += 1

        failure_info = {
            'packet': packet,
            'timestamp': time.time(),
            'from_id': from_id,
            'to_id': to_id
        }

        self.failed_decryptions[from_id].append(failure_info)

        # Check if we need to request the key
        if from_id not in self.public_keys:
            logger.info(f"Missing public key for {from_id}, requesting...")
            self.request_node_info(from_id)

            # Queue for retry
            self.pending_messages[from_id].append(packet)
        else:
            # We have the key but decryption failed
            logger.warning(f"Have public key for {from_id} but decryption failed")

            # Check key age
            key_age = time.time() - self.key_metadata.get(from_id, {}).get('received_at', 0)
            if key_age > self.key_refresh_interval:
                logger.info(f"Key for {from_id} is {key_age/3600:.1f} hours old, refreshing...")
                self.request_node_info(from_id)

        return packet

    def request_node_info(self, node_id: str) -> bool:
        """Request NodeInfo from a specific node with rate limiting"""
        if not self.interface:
            logger.warning("No Meshtastic interface available for key request")
            return False

        # Rate limiting
        last_request = self.key_request_times.get(node_id, 0)
        if time.time() - last_request < self.key_request_cooldown:
            logger.debug(f"Rate limiting key request for {node_id}")
            return False

        try:
            logger.info(f"Requesting NodeInfo/public key from {node_id}")
            self.interface.sendNodeInfo(destinationId=node_id, wantResponse=True)
            self.key_request_times[node_id] = time.time()
            self.stats['keys_requested'] += 1
            return True
        except Exception as e:
            logger.error(f"Failed to request NodeInfo from {node_id}: {e}")
            return False

    def process_pending_for_node(self, node_id: str) -> None:
        """Process pending messages after receiving a key"""
        if node_id not in self.pending_messages:
            return

        pending = self.pending_messages[node_id]
        if not pending:
            return

        logger.info(f"Processing {len(pending)} pending messages for {node_id}")

        for packet in pending:
            # TODO: Trigger re-decryption attempt
            # This would need integration with your main packet handler
            logger.debug(f"Would retry decryption for packet {packet.get('id')}")

        # Clear pending messages
        self.pending_messages[node_id] = []

    async def periodic_key_refresh(self) -> None:
        """Periodically refresh old keys"""
        while True:
            try:
                await asyncio.sleep(3600)  # Check every hour

                now = time.time()
                for node_id, metadata in self.key_metadata.items():
                    key_age = now - metadata.get('received_at', 0)

                    # Refresh keys older than threshold
                    if key_age > self.key_refresh_interval:
                        logger.info(f"Refreshing old key for {node_id} (age: {key_age/3600:.1f} hours)")
                        self.request_node_info(node_id)
                        await asyncio.sleep(5)  # Space out requests

            except Exception as e:
                logger.error(f"Error in periodic key refresh: {e}")
                await asyncio.sleep(60)

    async def process_pending_messages(self) -> None:
        """Retry pending messages periodically"""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                for node_id, messages in list(self.pending_messages.items()):
                    if node_id in self.public_keys:
                        # We now have the key, process pending messages
                        self.process_pending_for_node(node_id)

            except Exception as e:
                logger.error(f"Error processing pending messages: {e}")
                await asyncio.sleep(10)

    async def health_monitor(self) -> None:
        """Monitor PKI health and trigger recovery actions"""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes

                # Calculate success rate
                total_dms = sum(self.successful_dms.values()) + sum(self.failed_dms.values())
                if total_dms > 0:
                    success_rate = sum(self.successful_dms.values()) / total_dms
                    failure_rate = 1 - success_rate

                    logger.info(f"PKI Health: {success_rate*100:.1f}% success rate "
                              f"({sum(self.successful_dms.values())}/{total_dms} DMs)")

                    # Trigger recovery if failure rate is high
                    if failure_rate > 0.3 and self.enable_auto_recovery:
                        logger.warning(f"High PKI failure rate: {failure_rate*100:.1f}%")
                        await self.trigger_recovery()

                # Log statistics
                self.log_statistics()

            except Exception as e:
                logger.error(f"Error in health monitor: {e}")
                await asyncio.sleep(60)

    async def trigger_recovery(self) -> None:
        """Trigger recovery actions for PKI issues"""
        logger.info("Triggering PKI recovery actions...")
        self.stats['recovery_attempts'] += 1

        # 1. Request keys from nodes we've had failures with
        for node_id in self.failed_dms.keys():
            if node_id not in self.public_keys:
                self.request_node_info(node_id)
                await asyncio.sleep(2)

        # 2. Refresh old keys
        now = time.time()
        for node_id, metadata in self.key_metadata.items():
            if now - metadata.get('received_at', 0) > 43200:  # 12 hours
                self.request_node_info(node_id)
                await asyncio.sleep(2)

        # 3. Broadcast our own NodeInfo to ensure others have our key
        if self.interface:
            try:
                self.interface.sendNodeInfo(wantResponse=False)
                logger.info("Broadcast our NodeInfo with public key")
            except Exception as e:
                logger.error(f"Failed to broadcast NodeInfo: {e}")

    def log_statistics(self) -> None:
        """Log current PKI statistics"""
        logger.info(f"PKI Stats: {self.stats['total_keys']} keys, "
                   f"{self.stats['keys_requested']} requested, "
                   f"{self.stats['keys_received']} received, "
                   f"{self.stats['dms_successful']} DMs successful, "
                   f"{self.stats['dms_failed']} failed")

    def get_diagnostics(self) -> dict:
        """Get comprehensive PKI diagnostics"""
        now = time.time()

        # Calculate key freshness
        key_ages = {}
        for node_id, metadata in self.key_metadata.items():
            age_hours = (now - metadata.get('received_at', 0)) / 3600
            key_ages[node_id] = age_hours

        # Find problematic nodes
        problem_nodes = []
        for node_id, failure_count in self.failed_dms.items():
            if failure_count > 5:
                problem_nodes.append({
                    'node_id': node_id,
                    'failures': failure_count,
                    'has_key': node_id in self.public_keys,
                    'key_age_hours': key_ages.get(node_id, -1)
                })

        # Success rates by node
        node_success_rates = {}
        for node_id in set(list(self.successful_dms.keys()) + list(self.failed_dms.keys())):
            success = self.successful_dms.get(node_id, 0)
            failed = self.failed_dms.get(node_id, 0)
            total = success + failed
            if total > 0:
                node_success_rates[node_id] = success / total

        return {
            'stats': self.stats,
            'total_nodes_with_keys': len(self.public_keys),
            'pending_messages': sum(len(msgs) for msgs in self.pending_messages.values()),
            'average_key_age_hours': sum(key_ages.values()) / len(key_ages) if key_ages else 0,
            'oldest_key_hours': max(key_ages.values()) if key_ages else 0,
            'problem_nodes': problem_nodes,
            'overall_success_rate': self.calculate_overall_success_rate(),
            'node_success_rates': node_success_rates
        }

    def calculate_overall_success_rate(self) -> float:
        """Calculate overall PKI success rate"""
        total_success = sum(self.successful_dms.values())
        total_failed = sum(self.failed_dms.values())
        total = total_success + total_failed
        return total_success / total if total > 0 else 0

    def mark_dm_success(self, from_id: str) -> None:
        """Mark a successful DM decryption"""
        self.successful_dms[from_id] += 1
        self.stats['dms_successful'] += 1

    def mark_dm_failure(self, from_id: str) -> None:
        """Mark a failed DM decryption"""
        self.failed_dms[from_id] += 1
        self.stats['dms_failed'] += 1

    def export_keys(self, filepath: str = "pkc_keys_export.json") -> None:
        """Export all keys for backup"""
        export_data = {
            'exported_at': datetime.now().isoformat(),
            'total_keys': len(self.public_keys),
            'keys': {}
        }

        for node_id, public_key in self.public_keys.items():
            metadata = self.key_metadata.get(node_id, {})
            export_data['keys'][node_id] = {
                'public_key': base64.b64encode(public_key).decode('ascii'),
                'received_at': datetime.fromtimestamp(
                    metadata.get('received_at', 0)
                ).isoformat() if metadata.get('received_at') else None,
                'hardware': metadata.get('hardware', 'unknown'),
                'long_name': metadata.get('long_name', ''),
                'short_name': metadata.get('short_name', ''),
                'success_rate': self.calculate_node_success_rate(node_id)
            }

        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        logger.info(f"Exported {len(self.public_keys)} keys to {filepath}")

    def calculate_node_success_rate(self, node_id: str) -> float:
        """Calculate success rate for a specific node"""
        success = self.successful_dms.get(node_id, 0)
        failed = self.failed_dms.get(node_id, 0)
        total = success + failed
        return success / total if total > 0 else 0

    def cleanup(self) -> None:
        """Clean up resources"""
        # Cancel background tasks
        for task in self.tasks:
            task.cancel()

        # Save keys one final time
        self.save_keys()

        logger.info("Enhanced PKC Manager cleaned up")


# Integration helper for your existing code
def integrate_enhanced_pkc(meshtastic_connector):
    """Integrate the enhanced PKC manager with your existing connector"""

    # Create the enhanced manager
    pkc_manager = EnhancedPKCManager(meshtastic_interface=meshtastic_connector.interface)

    # Hook into packet processing
    original_on_receive = meshtastic_connector.on_receive

    def enhanced_on_receive(packet, interface):
        # Let PKC manager process it first
        if packet.get('decoded', {}).get('portnum') == 'NODEINFO_APP':
            pkc_manager.handle_node_info(
                packet.get('fromId', ''),
                packet.get('decoded', {})
            )

        # Check for failed DM decryption
        if packet.get('channel') == 0 and not packet.get('decoded'):
            pkc_manager.handle_encrypted_packet(packet)
            pkc_manager.mark_dm_failure(packet.get('fromId', ''))
        elif packet.get('pki_encrypted'):
            # Successfully decrypted
            pkc_manager.mark_dm_success(packet.get('fromId', ''))

        # Call original handler
        return original_on_receive(packet, interface)

    meshtastic_connector.on_receive = enhanced_on_receive

    return pkc_manager