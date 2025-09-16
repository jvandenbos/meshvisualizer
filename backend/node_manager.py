"""
Centralized node management with consistent ID and name handling.
Ensures all node IDs are in hex format and names follow the priority system.
"""

from typing import Optional, Dict, Any
from backend.models import NodeInfo
from backend.name_generator import generate_friendly_name, is_generated_name
import logging

logger = logging.getLogger(__name__)


def normalize_node_id(node_id: str) -> str:
    """
    Normalize any node ID to consistent hex format with 8-digit padding.
    This is an alias for ensure_hex_id for clearer naming.

    Args:
        node_id: Node ID in any format

    Returns:
        Normalized node ID in hex format (e.g., !421d066a)
    """
    return ensure_hex_id(node_id)


def ensure_hex_id(node_id: str) -> str:
    """
    Convert any node ID to hex format with consistent 8-digit padding.

    Args:
        node_id: Node ID in any format (decimal or hex)

    Returns:
        Node ID in hex format with 8 digits (e.g., !421d066a)
    """
    if not node_id:
        return node_id

    # Already hex format - ensure it's properly padded
    if node_id.startswith('!'):
        # Extract hex part and reformat with padding
        hex_part = node_id[1:]  # Remove the !
        try:
            # Convert to int and back to ensure proper padding
            decimal_val = int(hex_part, 16)
            return f"!{decimal_val:08x}"
        except (ValueError, TypeError):
            # If we can't parse it, return as-is
            logger.warning(f"Could not normalize hex ID: {node_id}")
            return node_id

    # Convert decimal to hex with padding
    try:
        # Try to parse as decimal integer
        decimal_id = int(node_id)
        hex_id = f"!{decimal_id:08x}"  # Use 08x for 8-digit padding
        return hex_id
    except (ValueError, TypeError):
        # Not a valid decimal, return as-is
        logger.warning(f"Could not convert node ID to hex: {node_id}")
        return node_id


def should_use_generated_name(short_name: Optional[str], long_name: Optional[str]) -> bool:
    """
    Determine if we should use a generated name for this node.

    Args:
        short_name: Node's short name
        long_name: Node's long name

    Returns:
        True if we should generate a name, False if node has a real name
    """
    # No names at all
    if not short_name and not long_name:
        return True

    # Check if names are default placeholders
    if short_name:
        # Never show Node-[anything]
        if short_name.startswith("Node-"):
            return True
        # Already has generated name
        if short_name.startswith("*"):
            return False
        # Has real name
        return False

    if long_name:
        if long_name.startswith("Node-"):
            return True
        return False

    return True


def get_display_name_for_node(
    node_id: str,
    short_name: Optional[str],
    long_name: Optional[str],
    generated_name: Optional[str] = None
) -> str:
    """
    Get the appropriate display name for a node.
    Priority: Real name > Generated name > Hex ID (never Node-[decimal])

    Args:
        node_id: Node ID (will be converted to hex)
        short_name: Node's short name
        long_name: Node's long name
        generated_name: Previously generated name if available

    Returns:
        Best name to display for the node
    """
    # Ensure we have hex ID
    hex_id = ensure_hex_id(node_id)

    # Check if we should use generated name
    if should_use_generated_name(short_name, long_name):
        if generated_name and generated_name.startswith("*"):
            return generated_name
        else:
            # Generate new name
            return generate_friendly_name(hex_id)

    # Use real name if available
    if long_name and not long_name.startswith("Node-"):
        return long_name
    if short_name and not short_name.startswith("Node-"):
        return short_name

    # Last resort - use hex ID (but never Node-[decimal])
    return hex_id


def process_node_data(node_data: Dict[str, Any], existing_node: Optional[NodeInfo] = None) -> Dict[str, Any]:
    """
    Process node data to ensure consistent IDs and names.

    Args:
        node_data: Raw node data
        existing_node: Existing node info if updating

    Returns:
        Processed node data with hex ID and appropriate name
    """
    # Ensure hex ID
    node_id = ensure_hex_id(str(node_data.get("id", "")))
    node_data["id"] = node_id

    # Get names from data
    new_short = node_data.get("short_name")
    new_long = node_data.get("long_name")

    # Handle existing node updates
    if existing_node:
        current_short = existing_node.short_name
        current_long = existing_node.long_name

        # If current name is generated/default and new name is real, update
        if current_short and (current_short.startswith("*") or current_short.startswith("Node-")):
            if new_short and not new_short.startswith("Node-"):
                # Real name arrived, use it
                node_data["short_name"] = new_short
                logger.info(f"Replacing generated/default name with real name: {new_short}")
            else:
                # Keep generated name or generate new one
                if current_short.startswith("*"):
                    node_data["short_name"] = current_short
                else:
                    node_data["short_name"] = generate_friendly_name(node_id)
                    logger.info(f"Replacing default name with generated: {node_data['short_name']}")
        elif new_short:
            # Update with new name if not default
            if not new_short.startswith("Node-"):
                node_data["short_name"] = new_short
            else:
                # New name is default, keep current or generate
                if current_short and not current_short.startswith("Node-"):
                    node_data["short_name"] = current_short
                else:
                    node_data["short_name"] = generate_friendly_name(node_id)
    else:
        # New node - ensure proper name
        if should_use_generated_name(new_short, new_long):
            node_data["short_name"] = generate_friendly_name(node_id)
            logger.info(f"Generated name for new node {node_id}: {node_data['short_name']}")
        elif new_short and new_short.startswith("Node-"):
            # Replace default with generated
            node_data["short_name"] = generate_friendly_name(node_id)
            logger.info(f"Replaced default name with generated: {node_data['short_name']}")
        elif new_short:
            # Has real name - use it
            node_data["short_name"] = new_short
            logger.info(f"Using real name for new node {node_id}: {new_short}")
        elif new_long:
            # Has real long name - use it
            node_data["short_name"] = new_long
            logger.info(f"Using real long name for new node {node_id}: {new_long}")
        else:
            # Fallback to generated name
            node_data["short_name"] = generate_friendly_name(node_id)
            logger.info(f"Fallback generated name for new node {node_id}: {node_data['short_name']}")

    return node_data