"""
PKC Key Manager - Intelligent key refresh with loop prevention
Handles automatic PKC key refresh when DM decryption fails
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
import subprocess

logger = logging.getLogger(__name__)

class PKCKeyManager:
    """Manages PKC key refresh attempts with loop prevention"""

    def __init__(self, max_retries: int = 2, backoff_minutes: int = 30):
        """
        Initialize the PKC Key Manager

        Args:
            max_retries: Maximum key refresh attempts per node
            backoff_minutes: Minutes to wait before allowing retry for same node
        """
        self.max_retries = max_retries
        self.backoff_minutes = backoff_minutes

        # Track retry attempts per node
        self.retry_counts: Dict[str, int] = {}

        # Track last retry time per node
        self.last_retry: Dict[str, datetime] = {}

        # Track permanently failed nodes (exceeded max retries)
        self.failed_nodes: set = set()

        # Track nodes currently being refreshed (prevent concurrent refreshes)
        self.refreshing_nodes: set = set()

    def should_attempt_refresh(self, node_id: str) -> bool:
        """
        Check if we should attempt a key refresh for this node

        Returns:
            True if refresh should be attempted, False otherwise
        """
        # Check if permanently failed
        if node_id in self.failed_nodes:
            logger.debug(f"Node {node_id} has permanently failed PKC refresh")
            return False

        # Check if already refreshing
        if node_id in self.refreshing_nodes:
            logger.debug(f"Node {node_id} is already being refreshed")
            return False

        # Check retry count
        retry_count = self.retry_counts.get(node_id, 0)
        if retry_count >= self.max_retries:
            logger.warning(f"Node {node_id} has exceeded max retries ({self.max_retries})")
            self.failed_nodes.add(node_id)
            return False

        # Check backoff period
        if node_id in self.last_retry:
            time_since_retry = datetime.now() - self.last_retry[node_id]
            backoff_time = timedelta(minutes=self.backoff_minutes)

            if time_since_retry < backoff_time:
                remaining = (backoff_time - time_since_retry).total_seconds() / 60
                logger.info(f"Node {node_id} in backoff period ({remaining:.1f} min remaining)")
                return False

        return True

    async def refresh_node_key(self, node_id: str, from_name: str = None) -> bool:
        """
        Attempt to refresh PKC key for a specific node

        Args:
            node_id: Node ID to refresh (e.g., "!a0a53aa4")
            from_name: Optional friendly name for logging

        Returns:
            True if refresh was attempted, False if skipped
        """
        if not self.should_attempt_refresh(node_id):
            return False

        try:
            # Mark as refreshing
            self.refreshing_nodes.add(node_id)

            # Update retry tracking
            self.retry_counts[node_id] = self.retry_counts.get(node_id, 0) + 1
            self.last_retry[node_id] = datetime.now()

            logger.warning(f"""
╔══════════════════════════════════════════════════════════╗
║          PKC KEY REFRESH INITIATED                        ║
║                                                            ║
║  Node: {node_id:<20} {f'({from_name})' if from_name else '':<20} ║
║  Attempt: {self.retry_counts[node_id]} of {self.max_retries}                                       ║
║  Reason: DM decryption failed (likely stale public key)   ║
╚══════════════════════════════════════════════════════════╝
            """)

            # Remove the specific node from nodeDB
            result = await self.execute_meshtastic_command(['--remove-node', node_id])

            if result:
                logger.info(f"✓ Successfully removed node {node_id} from nodeDB")

                # Wait for node to rebroadcast its info
                logger.info("⏳ Waiting 15 seconds for node to rebroadcast info...")
                await asyncio.sleep(15)

                # Request node info to trigger key exchange
                await self.execute_meshtastic_command(['--dest', node_id, '--request-telemetry'])

                logger.info(f"✓ Requested fresh info from {node_id}")
                return True
            else:
                logger.error(f"✗ Failed to remove node {node_id} from nodeDB")
                return False

        except Exception as e:
            logger.error(f"Error refreshing key for {node_id}: {e}")
            return False
        finally:
            # Remove from refreshing set
            self.refreshing_nodes.discard(node_id)

    async def execute_meshtastic_command(self, args: list) -> bool:
        """
        Execute a meshtastic CLI command

        Args:
            args: Command arguments (e.g., ['--remove-node', '!a0a53aa4'])

        Returns:
            True if successful, False otherwise
        """
        try:
            cmd = ['meshtastic'] + args
            logger.debug(f"Executing: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return True
            else:
                logger.error(f"Command failed: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Failed to execute command: {e}")
            return False

    def reset_node(self, node_id: str):
        """
        Reset retry counts for a specific node (e.g., after successful communication)
        """
        if node_id in self.retry_counts:
            logger.info(f"Resetting retry count for {node_id} (was {self.retry_counts[node_id]})")
            del self.retry_counts[node_id]

        if node_id in self.last_retry:
            del self.last_retry[node_id]

        self.failed_nodes.discard(node_id)
        self.refreshing_nodes.discard(node_id)

    def get_status(self) -> dict:
        """Get current status of PKC key management"""
        return {
            "retry_counts": dict(self.retry_counts),
            "failed_nodes": list(self.failed_nodes),
            "refreshing_nodes": list(self.refreshing_nodes),
            "last_retry": {
                node: self.last_retry[node].isoformat()
                for node in self.last_retry
            }
        }

    def clear_all(self):
        """Clear all tracking data (use with caution)"""
        self.retry_counts.clear()
        self.last_retry.clear()
        self.failed_nodes.clear()
        self.refreshing_nodes.clear()
        logger.info("Cleared all PKC key tracking data")