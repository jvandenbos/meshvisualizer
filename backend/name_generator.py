"""
Friendly name generator for unnamed nodes.
Generates memorable names in the format: adjective-noun (e.g., "green-pet", "swift-eagle")
"""

import hashlib
from typing import Optional

# Adjectives - descriptive words (colors, qualities, characteristics)
ADJECTIVES = [
    "amber", "azure", "brave", "bright", "calm", "clear", "clever", "cool",
    "coral", "cosmic", "crystal", "daring", "dawn", "deep", "dream", "dusty",
    "eager", "early", "echo", "electric", "emerald", "epic", "fair", "fast",
    "fierce", "fire", "fleet", "fresh", "frost", "gentle", "glad", "golden",
    "grand", "green", "happy", "hasty", "hidden", "high", "holy", "humble",
    "ice", "iron", "jade", "jolly", "keen", "kind", "lake", "large",
    "light", "little", "lively", "lone", "long", "loud", "lucky", "lunar",
    "magic", "major", "merry", "mighty", "mint", "misty", "moon", "morning",
    "mystic", "navy", "neat", "nice", "night", "noble", "north", "ocean",
    "old", "orange", "pacific", "pearl", "pink", "plain", "polar", "proud",
    "pure", "purple", "quick", "quiet", "rapid", "red", "rich", "rocky",
    "rough", "royal", "ruby", "rusty", "sacred", "sage", "sandy", "scarlet",
    "secret", "shadow", "sharp", "shiny", "short", "silent", "silver", "simple",
    "sky", "small", "smart", "smooth", "snow", "soft", "solar", "solid",
    "south", "space", "spark", "spring", "star", "steel", "stone", "storm",
    "strong", "summer", "sun", "super", "swift", "tall", "teal", "thunder",
    "tiny", "topaz", "tough", "trade", "tree", "true", "turbo", "twilight",
    "ultra", "valley", "violet", "vivid", "warm", "wave", "west", "white",
    "wild", "wind", "winter", "wise", "yellow", "young", "zephyr", "zinc"
]

# Nouns - things, animals, objects
NOUNS = [
    "anchor", "angel", "apple", "arrow", "badge", "bear", "bee", "bell",
    "bird", "blade", "boat", "book", "boulder", "box", "bridge", "brook",
    "buffalo", "butterfly", "candle", "canyon", "castle", "cat", "cedar", "chain",
    "chair", "cliff", "cloud", "comet", "compass", "coyote", "crow", "crystal",
    "deer", "delta", "desert", "diamond", "dog", "dolphin", "door", "dove",
    "dragon", "dream", "duck", "eagle", "echo", "falcon", "feather", "field",
    "fire", "fish", "flame", "flower", "fog", "forest", "fort", "fox",
    "gate", "gem", "ghost", "glacier", "glass", "globe", "goose", "granite",
    "grass", "grove", "guardian", "hammer", "harbor", "hawk", "heart", "hill",
    "horse", "house", "hunter", "ice", "island", "jaguar", "jewel", "journey",
    "key", "king", "kite", "knight", "lake", "lamp", "leaf", "leopard",
    "light", "lily", "lion", "lotus", "lynx", "maple", "meadow", "mesa",
    "meteor", "mirror", "moon", "mountain", "mouse", "needle", "nest", "night",
    "oak", "ocean", "orchid", "otter", "owl", "palm", "panther", "path",
    "peak", "pearl", "phoenix", "pine", "plain", "pond", "pony", "prairie",
    "prism", "python", "quartz", "queen", "quest", "rabbit", "rain", "ranger",
    "raven", "reef", "ridge", "river", "road", "rock", "root", "rose",
    "sage", "sail", "scout", "sea", "seed", "shadow", "shark", "shield",
    "ship", "shore", "sierra", "sky", "smoke", "snake", "snow", "spark",
    "spider", "spring", "spruce", "star", "stone", "storm", "stream", "summit",
    "sun", "swan", "sword", "table", "temple", "thunder", "tide", "tiger",
    "tower", "trail", "tree", "tulip", "turtle", "valley", "vault", "village",
    "vine", "viper", "voice", "wall", "water", "wave", "whale", "wheel",
    "willow", "wind", "wing", "wolf", "wood", "zebra", "zenith", "zone"
]


def generate_friendly_name(node_id: str) -> str:
    """
    Generate a deterministic friendly name based on node ID.
    Uses hash to ensure same ID always gets same name.

    Args:
        node_id: The node ID (decimal or hex)

    Returns:
        A friendly name like "green-pet" prefixed with asterisk
    """
    # Create hash of the node ID for deterministic selection
    hash_bytes = hashlib.md5(str(node_id).encode()).digest()

    # Use first byte for adjective, second byte for noun
    adj_index = hash_bytes[0] % len(ADJECTIVES)
    noun_index = hash_bytes[1] % len(NOUNS)

    adjective = ADJECTIVES[adj_index]
    noun = NOUNS[noun_index]

    # Return with asterisk prefix to indicate it's generated
    return f"*{adjective}-{noun}"


def is_generated_name(name: str) -> bool:
    """
    Check if a name is a generated friendly name.

    Args:
        name: The name to check

    Returns:
        True if this is a generated name (starts with *)
    """
    return name and name.startswith("*")


def get_display_name(node_id: str, short_name: Optional[str], long_name: Optional[str]) -> str:
    """
    Get the display name for a node, using real name if available, otherwise generated.

    Args:
        node_id: The node ID
        short_name: The node's short name (if any)
        long_name: The node's long name (if any)

    Returns:
        The best available name for display
    """
    # Prefer real names over generated
    if long_name and long_name.strip() and not long_name.startswith("Node-"):
        return long_name
    if short_name and short_name.strip() and not short_name.startswith("Node-"):
        return short_name

    # Generate friendly name if no real name
    return generate_friendly_name(node_id)